"""Decision tree: questionnaire (call 1) -> quote check -> Verifier -> rules -> obligation status and prose (call 2).

    python -m src.agents path/to/case.pdf [more files...]
"""

import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, ValidationError, field_validator
from pydantic.json_schema import SkipJsonSchema

from src import rules
from src.citations import check_references
from src.config import LLM_API_KEY, LLM_BASE_URL, LLM_EXTRA_BODY, LLM_MODEL
from src.ingest import case_passages

MAX_CASE_CHARS = 500_000
LLM_TIMEOUT_S = 120  # per call; the SDK default is 600
MAX_OUTPUT_TOKENS = 32_768  # DeepSeek's default (~8k) cut off the 69-answer questionnaire reply


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


class Verdict(BaseModel):
    claim_id: str
    status: Literal["supported", "contradicted", "insufficient"]
    reason: str


class Verification(BaseModel):
    verdicts: list[Verdict]


class Status(BaseModel):
    id: str
    status: Literal["met", "gap", "unclear", "not_applicable"]
    explanation: str
    references: list[Reference] = []


class Rating(BaseModel):
    summary: str
    reasoning: str
    statuses: list[Status]


class Answer(BaseModel):
    question: str  # the id ("A1"); models often echo "A1: <question text>", trimmed below
    answer: Literal["yes", "no", "not_mentioned"]
    statement: str = ""
    references: list[Reference] = []

    @field_validator("question")
    @classmethod
    def _id_only(cls, value: str) -> str:
        return value.split(":", 1)[0].strip()


class Answers(BaseModel):
    answers: list[Answer]
    other_concerns: list[Claim] = []


# Decision-tree pipeline: every call starts with CASE_PROMPT and the case documents, so DeepSeek's prefix cache
# serves the case after the first call; the task follows in the same user message.
CASE_PROMPT = """You analyse one AI use case against the EU AI Act. The user message starts with the case documents and ends with your task.
Rules for every task:
1. Cite only passages shown to you. Each reference is an exact chunk_id and a verbatim quote copied from that passage (a full phrase or sentence, no ellipses, no paraphrase). Facts about the business cite case passages (ids like doc1:2).
2. Never invent facts. What the documents do not show is not_mentioned or unclear, never assumed.
3. Write prose in English unless the case documents are clearly written in another language; then use that language. Quotes stay verbatim in their source language; enum values and ids stay in English."""

QUESTIONS_TASK = """## Task: answer every question

Answer each question below about the AI system in the case documents. Its legal test decides what counts.
- "yes": the documents show it. Quote the passage that shows it.
- "no": nothing in the documents indicates it, given what they say the system is and does. Quote that description (its purpose, functions or users). Most questions about practices unrelated to the system's purpose are "no".
- "not_mentioned": it is plausible for this system, but the documents do not say either way. No references.
`question` is the question id only, for example "A1". For yes and no, `statement` is one sentence stating the fact your quotes establish about this system.
Put anything relevant under the AI Act that no question covers in other_concerns (kind "fact", with quotes).

{questions}

Reply with one JSON object only, matching this JSON schema:
{schema}"""

STATUS_TASK = """## Task: rate the obligations

The rules of the AI Act have already classified this system; do not change the classification:
{classification}

Rate each obligation below against the case documents, using its legal text:
- "met": the documents show it is fulfilled. Quote the passages that show it.
- "gap": the documents show it is missing or contradicted. Quote what shows it, when there is such a passage.
- "unclear": the documents do not say.
- "not_applicable": only when the documents show this business is not the one that owes it (for example it is not the provider).
Give every obligation id exactly once, with a one-sentence explanation. Then write `summary` (two or three sentences for the business) and `reasoning` (why the classification follows, in plain language, using qualified wording: this is a preliminary assessment, not legal advice).

{obligations}

Reply with one JSON object only, matching this JSON schema:
{schema}"""

MAX_QUESTIONS = 10  # more open questions than this means the documents say too little; ask for a description instead
DESCRIBE = ("The documents say too little to assess this system. Describe what it does, who uses it and on whom, what its "
            "output is used for, and whether you build it or buy it.")
GATING = ("A1", "B1", "B2")

GROUPS = {"A": "Scope", "B": "Role", "C": "Prohibited practices", "D": "Regulated products", "E": "High-risk uses",
          "F": "High-risk exception", "G": "Transparency", "H": "General-purpose AI"}


VERIFIER_PROMPT = """You verify claims in an EU AI Act assessment against the passages they quote.
For each claim, decide whether its quoted passages establish the entire claim. Check negation, the actor responsible, scope, conditions and exceptions. Accept faithful paraphrases even with little word overlap.
- supported: the passages establish the whole claim
- contradicted: the passages say the opposite
- insufficient: evidence missing, ambiguous, about a different actor, or narrower than the claim
Write each reason in the language of the claim.
A claim that starts with "Does not apply:" is supported when the passages describe the system's purpose and functions and nothing in them suggests that it applies; it does not need an explicit denial.
Reply with JSON only: {"verdicts": [{"claim_id": "...", "status": "supported|contradicted|insufficient", "reason": "one sentence"}]}, exactly one verdict per claim."""

class CaseError(Exception):
    """The uploaded case cannot be assessed (empty, too large). The caller's fault, unlike model errors."""


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    return OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=LLM_TIMEOUT_S, max_retries=2)


def chat(messages: list[dict]) -> dict:
    reply = _client().chat.completions.create(model=LLM_MODEL, messages=messages, temperature=0.1, max_tokens=MAX_OUTPUT_TOKENS,
                                              response_format={"type": "json_object"}, extra_body=LLM_EXTRA_BODY)
    return {"role": "assistant", "content": reply.choices[0].message.content}


def _format(chunks) -> str:
    return "\n\n---\n\n".join(f"[{c['id']}] {c['label']}\n{c['text']}" for c in chunks)


def _parse(content: str, model: type[BaseModel]):
    match = re.search(r"\{.*\}", content or "", re.S)
    return model.model_validate_json(match.group() if match else content or "")


def _parsed(messages: list[dict], model: type[BaseModel]):
    """Parse the last reply; on invalid JSON ask once for a corrected object."""
    try:
        return _parse(messages[-1].get("content"), model)
    except ValidationError as error:
        messages.append({"role": "user", "content": f"That reply is not valid JSON for the schema:\n{error}\nReply with the corrected JSON object only."})
        messages.append(chat(messages))
        return _parse(messages[-1].get("content"), model)


def _case_messages(case: list[dict], task: str) -> list[dict]:
    return [{"role": "system", "content": CASE_PROMPT},
            {"role": "user", "content": "## Case documents\n\n" + _format(case) + "\n\n" + task}]


def _checked(answers, pack: dict) -> tuple[dict, dict, list[str], set[str]]:
    """Yes/no answers as fact claims through the quote check and the Verifier: (claims, verdicts, problems, failed ids)."""
    claims = [Claim(id=a.question, kind="fact", references=a.references,
                    text=((a.statement or rules.BY_ID[a.question].text) if a.answer == "yes"
                          else f"Does not apply: {rules.BY_ID[a.question].text} {a.statement}"))
              for a in answers if a.answer != "not_mentioned"]
    holder = SimpleNamespace(claims=claims)
    problems = check_references(holder, pack)
    verdicts = {v.claim_id: v for v in verify(holder, pack)} if claims else {}
    failed = {c.id for c in claims if not c.references or verdicts[c.id].status != "supported"}
    return {c.id: c for c in claims}, verdicts, problems, failed


def answer_questions(case: list[dict], pack: dict) -> dict:
    """Call ①: rules.QUESTIONS answered from the case. A yes/no whose quotes fail gets one revision if it is on the
    decision path; whatever still fails becomes not_mentioned, so the rules fail closed."""
    schema = json.dumps(Answers.model_json_schema())
    messages = _case_messages(case, QUESTIONS_TASK.format(questions=rules.render(), schema=schema))
    messages.append(chat(messages))
    given = _parsed(messages, Answers)
    answers = {a.question: a for a in given.answers if a.question in rules.BY_ID}
    claims, verdicts, problems, failed = _checked(answers.values(), pack)
    path = {p["question"] for p in rules.classify({q: a.answer for q, a in answers.items()})["path"]}
    retry = failed & path
    if retry:
        feedback = [p for p in problems if p.split(":")[0] in retry] + [
            f"{q}: {verdicts[q].status} - {verdicts[q].reason}" for q in sorted(retry) if q in verdicts]
        messages.append({"role": "user", "content": "A reviewer could not confirm these answers:\n" + "\n".join(feedback) +
                         "\n\nAnswer only these questions again: requote them, or use not_mentioned. Same JSON schema."})
        messages.append(chat(messages))
        again = {a.question: a for a in _parsed(messages, Answers).answers if a.question in retry}
        answers |= again
        c2, v2, p2, f2 = _checked(again.values(), pack)
        problems = [p for p in problems if p.split(":")[0] not in again] + p2
        claims, verdicts, failed = claims | c2, verdicts | v2, (failed - set(again)) | f2
    unverified = {q: answers[q].answer for q in sorted(failed)}  # what the model said before failing closed
    for q in failed:
        answers[q] = answers[q].model_copy(update={"answer": "not_mentioned", "references": []})
    check_references(SimpleNamespace(claims=given.other_concerns), pack)
    kept = [q for q, a in answers.items() if a.answer != "not_mentioned"]
    return {"answers": {q: a.answer for q, a in answers.items()}, "claims": [claims[q] for q in kept],
            "verdicts": [verdicts[q] for q in kept], "problems": problems, "revised": bool(retry), "unverified": unverified,
            "other_concerns": [c for c in given.other_concerns if c.references]}


def verify(assessment, pack: dict) -> list[Verdict]:
    """One verdict per claim of `assessment.claims`; an unusable reply supports nothing."""
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


def _usable(case: list[dict]) -> dict:
    """The case as a pack of passages by id; CaseError if it is empty or too large."""
    if not case:
        raise CaseError("No readable case documents or description.")
    if sum(len(c["text"]) for c in case) > MAX_CASE_CHARS:
        raise CaseError(f"Case documents exceed {MAX_CASE_CHARS:,} characters; upload the relevant parts.")
    return {c["id"]: c for c in case}


def assess_case(case: list[dict]) -> dict:
    """Questionnaire (call ①) -> rules.classify -> rules.obligations -> status and prose (call ②), plus `decision`.
    Raises CaseError for unusable input; openai.OpenAIError or pydantic.ValidationError when the model fails."""
    pack = _usable(case)
    return _finish(case, pack, answer_questions(case, pack))


def reassess(case: list[dict], previous: dict, given: dict[str, dict]) -> dict:
    """Re-run with the user's answers ({id: {"answer": "yes"|"no", "text": ...}}) instead of call ①. Earlier answers
    stay when their quotes still match the documents (no Verifier: it is the user's own report); each user answer
    becomes a citable "Your answers" passage. Only call ② and its Verifier run again."""
    mine = [{"id": f"answers:{i}", "source": "Your answers", "label": "Your answers",
             "text": f"{rules.BY_ID[q].text} {a['answer'].capitalize()}. {a.get('text', '')}".strip()}
            for i, (q, a) in enumerate(given.items(), 1)]
    pack = _usable(case + mine)
    earlier = [Claim.model_validate(c) for c in previous.get("claims", []) if c.get("id") in rules.BY_ID and c["id"] not in given]
    problems = check_references(SimpleNamespace(claims=earlier), pack)
    kept = {c.id: c for c in earlier if c.references}
    answers = {q: v if v == "not_mentioned" or q in kept else "not_mentioned"
               for q, v in previous.get("answers", {}).items() if q in rules.BY_ID and q not in given}
    yours = [Claim(id=q, kind="fact", text=p["text"], references=[Reference(chunk_id=p["id"], quote=p["text"])])
             for q, p in zip(given, mine)]
    check_references(SimpleNamespace(claims=yours), pack)
    note = lambda c, why: Verdict(claim_id=c.id, status="supported", reason=why)  # noqa: E731
    q = {"answers": answers | {q: a["answer"] for q, a in given.items()}, "claims": list(kept.values()) + yours,
         "verdicts": [note(c, "Confirmed in the earlier assessment.") for c in kept.values()] + [note(c, "Your answer.") for c in yours],
         "problems": problems, "revised": False, "unverified": {}, "other_concerns": []}
    return _finish(case + mine, pack, q)


def _finish(case: list[dict], pack: dict, q: dict) -> dict:
    """Everything after the answers: rules, code-written legal claims, call ② and the result."""
    decision = rules.classify(q["answers"])
    rows = rules.obligations(decision, q["answers"])
    legal = []
    for o in rows:  # legal claims are written by code and quote the obligation's own provision
        passage = rules.legal_test(o)
        pack[passage["id"]] = passage
        legal.append(Claim(id=f"L{o.id}", kind="legal", text=f"{o.requirement} ({passage['label']}).",
                           references=[Reference(chunk_id=passage["id"], quote=o.anchor)]))
    problems = q["problems"] + check_references(SimpleNamespace(claims=legal), pack)

    shown = {c.references[0].chunk_id: pack[c.references[0].chunk_id] for c in legal if c.references}
    facts = "\n".join(f"- {p['question']} {rules.BY_ID[p['question']].text} -> {p['answer']}" for p in decision["path"])
    classification = (f"AI system: {decision['ai_system']}; risk tier: {decision['risk_tier']}; role: {decision['role']}; "
                      f"general-purpose AI: {decision['gpai_involved']}.\nDeciding answers:\n{facts}")
    listed = "\n".join(f"- {o.id}: {o.requirement} (legal text: {c.references[0].chunk_id})" for o, c in zip(rows, legal))
    rating = Rating(summary="", reasoning="", statuses=[])
    if rows:
        messages = _case_messages(case, STATUS_TASK.format(
            classification=classification, schema=json.dumps(Rating.model_json_schema()),
            obligations="## Legal texts\n\n" + _format(shown.values()) + "\n\n## Obligations\n\n" + listed))
        messages.append(chat(messages))
        rating = _parsed(messages, Rating)
    given = {s.id: s for s in rating.statuses if s.id in {o.id for o in rows}}  # call ② cannot add obligations
    evidence = [Claim(id=f"S{s.id}", kind="fact", text=s.explanation, references=s.references)
                for s in given.values() if s.references]
    holder = SimpleNamespace(claims=evidence)
    problems += check_references(holder, pack)
    verdicts = {v.claim_id: v for v in verify(holder, pack)} if evidence else {}
    supported = {c.id for c in evidence if c.references and verdicts[c.id].status == "supported"}

    requirements = []
    for o in rows:
        s = given.get(o.id) or Status(id=o.id, status="unclear", explanation="Not rated.")
        status = "unclear" if s.status == "met" and f"S{o.id}" not in supported else s.status  # unproven met fails closed
        requirements.append({"requirement": o.requirement, "status": status, "explanation": s.explanation,
                             "claim_ids": [f"L{o.id}"] + ([f"S{o.id}"] if f"S{o.id}" in supported else [])})
    claims = q["claims"] + legal + [c for c in evidence if c.id in supported]
    rule_verdict = lambda c: Verdict(claim_id=c.id, status="supported", reason="Applies under the rules; quotes its own provision.")  # noqa: E731
    all_verdicts = q["verdicts"] + [rule_verdict(c) for c in legal] + [verdicts[c.id] for c in evidence if c.id in supported]
    asked = decision["open_questions"]
    if len(asked) > MAX_QUESTIONS:
        asked = [q for q in asked if q in GATING]
    questions = [{"topic": GROUPS[qid[0]], "question": rules.BY_ID[qid].text} for qid in asked]
    if len(decision["open_questions"]) > MAX_QUESTIONS:
        questions.insert(0, {"topic": "Description", "question": DESCRIBE})
    assessment = {"summary": rating.summary or "No obligations apply under the rules.", "reasoning": rating.reasoning or classification,
                  **{k: decision[k] for k in ("ai_system", "role", "risk_tier", "gpai_involved", "confidence")},
                  "claims": [c.model_dump() for c in claims], "requirements": requirements, "missing_information": questions}
    cited = sorted({r.chunk_id for c in claims for r in c.references})
    return {"assessment": assessment, "verdicts": [v.model_dump() for v in all_verdicts], "reference_problems": problems,
            "revised": q["revised"], "sources": {i: pack[i] for i in cited},
            "decision": decision | {"answers": q["answers"], "unverified": q["unverified"],
                                    "other_concerns": [c.text for c in q["other_concerns"]]}}


if __name__ == "__main__":
    case, errors = case_passages([(Path(p).name, Path(p).read_bytes()) for p in sys.argv[1:]])
    for error in errors:
        print(f"skipped {error['file']}: {error['error']}", file=sys.stderr)
    print(json.dumps(assess_case(case), indent=2, ensure_ascii=False))
