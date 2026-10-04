"""Assessor (searches the law itself) -> quote check -> Verifier -> at most one revision.

    python -m src.agents path/to/case.pdf [more files...]
"""

import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, ValidationError
from pydantic.json_schema import SkipJsonSchema

from src import law
from src.citations import check_references
from src.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from src.ingest import case_passages

MAX_SEARCH_ROUNDS = 6
MAX_CASE_CHARS = 500_000
LLM_TIMEOUT_S = 120  # per call; the SDK default is 600


class Reference(BaseModel):
    chunk_id: str
    quote: str
    start: SkipJsonSchema[int | None] = None  # set by check_references, hidden from the model
    end: SkipJsonSchema[int | None] = None


class Claim(BaseModel):
    id: str
    kind: Literal["fact", "legal"]
    text: str
    references: list[Reference] = []


class Requirement(BaseModel):
    requirement: str
    status: Literal["met", "gap", "unclear", "not_applicable"]
    explanation: str
    claim_ids: list[str] = []


class Question(BaseModel):
    topic: str
    question: str


class Assessment(BaseModel):
    summary: str
    ai_system: Literal["yes", "no", "unclear"]
    role: Literal["provider", "deployer", "both", "unclear"]
    risk_tier: Literal["prohibited", "high_risk", "limited_risk", "minimal_risk", "unclear"]
    gpai_involved: Literal["yes", "no", "unclear"]
    confidence: Literal["low", "medium", "high"]
    reasoning: str
    claims: list[Claim]
    requirements: list[Requirement]
    missing_information: list[Question]


class Verdict(BaseModel):
    claim_id: str
    status: Literal["supported", "contradicted", "insufficient"]
    reason: str


class Verification(BaseModel):
    verdicts: list[Verdict]


ASSESSOR_PROMPT = f"""You are an EU AI Act compliance analyst. A business describes an AI use case in the case documents. Decide whether the AI Act applies, the risk category, the business's role, which obligations follow, and whether the documents show those obligations are met.

Process
- Use the search_law tool to find every provision you rely on. Use specific legal terms, e.g. "Article 3 definition AI system inference", "Article 5 emotion recognition workplace", "Annex III employment recruitment", "Article 50 inform natural persons interacting with AI system", "general-purpose AI model provider obligations". Check at least: the AI system definition, prohibited practices, high-risk classification (Article 6, Annex I, Annex III), transparency (Article 50), AI literacy (Article 4), and general-purpose AI when a third-party or foundation model is used.
- You may cite only passages shown to you: case passages (ids like doc1:2) and law passages returned by search_law (ids like eu_ai_act/art-50/1).

Rules
1. Every claim has references: an exact chunk_id and a verbatim quote copied from that passage (a full phrase or sentence, no ellipses, no paraphrase). Facts about the business ("fact") cite case passages; statements about the law ("legal") cite law passages.
2. Never invent facts. When something needed is not in the documents, add it to missing_information and mark dependent requirements "unclear".
3. Use qualified language ("appears to", "likely"). This is a preliminary assessment, not legal advice.
4. Use low confidence when purpose, affected persons, decision impact, human oversight, deployment context, or role are missing.
5. requirements: the obligations that follow from the risk tier and role (for example risk management, data governance, technical documentation, record-keeping, human oversight, accuracy and robustness, transparency, registration, AI literacy), each with status met / gap / unclear / not_applicable, a short explanation, and the ids of the claims that back it.
6. risk_tier is the most severe tier that applies; general-purpose AI use goes in gpai_involved.
8. role is the business's role for this system under Article 3: "provider" if it develops the system, or has it developed and places it on the market or puts it into service under its own name or trademark; "deployer" if it uses a system under its authority that someone else provides; "both" if it develops and uses the system itself. Use "unclear" only when the documents do not say who develops or who uses the system, and then ask about it in missing_information.
7. Write summary, reasoning, claim texts, requirements and questions in English, unless the case documents are clearly written in another language; then use that language. Quotes always stay verbatim in their source language; enum values stay in English.

When you are done searching, reply with one JSON object only, matching this JSON schema:
{json.dumps(Assessment.model_json_schema())}"""

VERIFIER_PROMPT = """You verify claims in an EU AI Act assessment against the passages they quote.
For each claim, decide whether its quoted passages establish the entire claim. Check negation, the actor responsible, scope, conditions and exceptions. Accept faithful paraphrases even with little word overlap.
- supported: the passages establish the whole claim
- contradicted: the passages say the opposite
- insufficient: evidence missing, ambiguous, about a different actor, or narrower than the claim
Write each reason in the language of the claim.
Reply with JSON only: {"verdicts": [{"claim_id": "...", "status": "supported|contradicted|insufficient", "reason": "one sentence"}]}, exactly one verdict per claim."""

SEARCH_TOOL = {"type": "function", "function": {
    "name": "search_law",
    "description": "Full-text search over the EU AI Act and Commission guidelines. Returns passages with ids to cite.",
    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
}}


class CaseError(Exception):
    """The uploaded case cannot be assessed (empty, too large). The caller's fault, unlike model errors."""


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    return OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=LLM_TIMEOUT_S, max_retries=2)


def chat(messages: list[dict], tools: list | None = None) -> dict:
    kwargs = {"tools": tools} if tools else {"response_format": {"type": "json_object"}}
    reply = _client().chat.completions.create(model=LLM_MODEL, messages=messages, temperature=0.1, **kwargs)
    message = reply.choices[0].message.model_dump(exclude_none=True)
    return {k: v for k, v in message.items() if k in ("role", "content", "tool_calls")}


def _format(chunks) -> str:
    return "\n\n---\n\n".join(f"[{c['id']}] {c['label']}\n{c['text']}" for c in chunks)


def _parse(content: str, model: type[BaseModel]):
    match = re.search(r"\{.*\}", content or "", re.S)
    return model.model_validate_json(match.group() if match else content or "")


def _assess(messages: list[dict], pack: dict) -> Assessment:
    for round_ in range(MAX_SEARCH_ROUNDS + 1):
        message = chat(messages, tools=None if round_ == MAX_SEARCH_ROUNDS else [SEARCH_TOOL])
        messages.append(message)
        if not message.get("tool_calls"):
            break
        for call in message["tool_calls"]:
            try:
                hits = law.search(json.loads(call["function"]["arguments"])["query"])
                content = _format(hits) or "No results."
                pack.update((c["id"], c) for c in hits)
            except (ValueError, KeyError, TypeError):
                content = 'Invalid arguments. Call search_law with {"query": "<search terms>"}.'
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": content})
    try:
        return _parse(message.get("content"), Assessment)
    except ValidationError as error:
        messages.append({"role": "user", "content": f"That reply is not valid JSON for the schema:\n{error}\nReply with the corrected JSON object only."})
        message = chat(messages)
        messages.append(message)
        return _parse(message.get("content"), Assessment)


def verify(assessment: Assessment, pack: dict) -> list[Verdict]:
    claims = [{"claim_id": c.id, "kind": c.kind, "claim": c.text,
               "evidence": [{"chunk_id": r.chunk_id, "quote": r.quote, "passage": pack[r.chunk_id]["text"]}
                            for r in c.references]} for c in assessment.claims]
    reply = chat([{"role": "system", "content": VERIFIER_PROMPT},
                  {"role": "user", "content": json.dumps(claims, ensure_ascii=False)}])
    try:
        given = {v.claim_id: v for v in _parse(reply.get("content"), Verification).verdicts}
    except ValidationError:  # fail closed: an unusable review supports nothing
        given = {}
    return [given.get(c.id) or Verdict(claim_id=c.id, status="insufficient", reason="The verifier returned no usable verdict.")
            for c in assessment.claims]


def assess_case(case: list[dict]) -> dict:
    """Raises CaseError for unusable input; openai.OpenAIError or pydantic.ValidationError when the model fails."""
    if not case:
        raise CaseError("No readable case documents or description.")
    if sum(len(c["text"]) for c in case) > MAX_CASE_CHARS:
        raise CaseError(f"Case documents exceed {MAX_CASE_CHARS:,} characters; upload the relevant parts.")
    pack = {c["id"]: c for c in case}
    messages = [{"role": "system", "content": ASSESSOR_PROMPT},
                {"role": "user", "content": "## Case documents\n\n" + _format(case) +
                 "\n\nWrite your prose in the language these case documents are written in (English if unsure)."}]
    assessment = _assess(messages, pack)
    problems = check_references(assessment, pack)
    verdicts = verify(assessment, pack)
    revised = False
    failed = [v for v in verdicts if v.status != "supported"]
    if problems or failed:
        revised = True
        feedback = "\n".join(problems + [f"{v.claim_id}: {v.status} - {v.reason}" for v in failed])
        messages.append({"role": "user", "content": "A reviewer checked your claims:\n" + feedback +
                         "\n\nRevise: fix, requote or remove these claims (search again if needed) and lower "
                         "confidence where evidence is missing. Reply with the full JSON object."})
        assessment = _assess(messages, pack)
        problems = check_references(assessment, pack)
        verdicts = verify(assessment, pack)
    cited = sorted({r.chunk_id for c in assessment.claims for r in c.references})
    return {"assessment": assessment.model_dump(), "verdicts": [v.model_dump() for v in verdicts],
            "reference_problems": problems, "revised": revised, "sources": {i: pack[i] for i in cited}}


if __name__ == "__main__":
    case, errors = case_passages([(Path(p).name, Path(p).read_bytes()) for p in sys.argv[1:]])
    for error in errors:
        print(f"skipped {error['file']}: {error['error']}", file=sys.stderr)
    print(json.dumps(assess_case(case), indent=2, ensure_ascii=False))
