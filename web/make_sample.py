"""Builds sample /api/assess responses from real corpus passages via the real
check_references + build_report, so offsets, ids and labels match the production contract.

    python web/make_sample.py   # writes web/src/sample.json
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import law  # noqa: E402
from src.agents import Assessment  # noqa: E402
from src.citations import check_references  # noqa: E402
from src.ingest import passages  # noqa: E402
from src.report import build_report  # noqa: E402

HR_BRIEF = """# TalentLens rollout at Kivi Logistics Oy

## Purpose

Kivi Logistics Oy will use TalentLens, a SaaS product licensed from Brightpath AB, to rank incoming applications for warehouse and driver roles. TalentLens scores each CV against the job profile and shows recruiters a shortlist of the top 20 candidates.

## Users and affected persons

Our six in-house recruiters use the ranked shortlist. Applicants are job seekers in Finland and Estonia; about 4,000 applications per year.

## Human oversight

Recruiters review every shortlisted candidate before an interview invitation is sent. Candidates below the shortlist are not reviewed manually unless a recruiter searches for them.

## Model

Brightpath states that TalentLens uses a fine-tuned large language model from a third-party model provider to extract skills from CVs."""

HR_DPIA = """# DPIA extract (draft)

## Logging

The vendor keeps system logs for 30 days. Kivi has no access to the logs.

## Training

Recruiters completed a one-hour vendor onboarding session on how to read TalentLens scores and their limits.

## Information to candidates

The job advertisement will mention that applications are processed with software. Works council not yet informed."""

BOT_DESC = """We want to add an AI assistant to our webshop that answers customer questions about orders and returns. It might also suggest products."""


def claim(id, kind, text, *refs):
    return {"id": id, "kind": kind, "text": text, "references": [{"chunk_id": c, "quote": q} for c, q in refs]}


def build(case_docs, assessment, verdicts, file_errors, revised):
    case = [p for n, (name, text) in enumerate(case_docs, 1) for p in passages(text, f"doc{n}", name)]
    pack = {c["id"]: c for c in case} | law.corpus()
    a = Assessment.model_validate(assessment)
    problems = check_references(a, pack)
    assert not [p for p in problems if "dropped" in p], problems
    cited = sorted({r.chunk_id for c in a.claims for r in c.references})
    result = {"assessment": a.model_dump(), "verdicts": verdicts, "reference_problems": problems,
              "revised": revised, "sources": {i: pack[i] for i in cited}}
    return {**result, "file_errors": file_errors, "report": build_report(result, file_errors)}


def ids(prefix):  # helper to print passage ids while writing claims
    return [c for c in law.corpus() if c.startswith(prefix)]


hr = build(
    [("talentlens_brief.pdf", HR_BRIEF), ("dpia_extract.docx", HR_DPIA)],
    {
        "summary": "Kivi Logistics Oy plans to use TalentLens, a third-party SaaS tool, to score and rank job applications for warehouse and driver roles and show recruiters a top-20 shortlist.",
        "ai_system": "yes", "role": "deployer", "risk_tier": "high_risk", "gpai_involved": "yes", "confidence": "medium",
        "reasoning": "The tool infers a ranking from CVs, which appears to meet the AI system definition in Article 3(1). Ranking and filtering applications falls under Annex III point 4(a), so the system is likely high-risk under Article 6(2). Kivi uses a system provided by Brightpath under its own authority and is therefore likely a deployer. A third-party large language model is involved, but GPAI model obligations fall on its provider, not on Kivi.",
        "claims": [
            claim("F1", "fact", "Kivi uses TalentLens to score CVs and rank applicants into a shortlist.",
                  ("doc1:1", "TalentLens scores each CV against the job profile and shows recruiters a shortlist of the top 20 candidates")),
            claim("F2", "fact", "TalentLens is provided by Brightpath AB and licensed to Kivi.",
                  ("doc1:1", "a SaaS product licensed from Brightpath AB")),
            claim("F3", "fact", "Applicants below the shortlist are not reviewed by a human by default.",
                  ("doc1:3", "Candidates below the shortlist are not reviewed manually unless a recruiter searches for them")),
            claim("F4", "fact", "Kivi has no access to the system logs.",
                  ("doc2:1", "Kivi has no access to the logs")),
            claim("F5", "fact", "Recruiters received training on reading scores and their limits.",
                  ("doc2:2", "Recruiters completed a one-hour vendor onboarding session")),
            claim("F6", "fact", "Workers' representatives have not been informed.",
                  ("doc2:3", "Works council not yet informed")),
            claim("L1", "legal", "A system that infers from input how to generate recommendations or decisions is an AI system.",
                  ("eu_ai_act/art-3/1", "infers, from the input it receives, how to generate outputs such as predictions, content, recommendations, or decisions")),
            claim("L2", "legal", "AI systems used to analyse and filter job applications are high-risk under Annex III point 4(a).",
                  ("guidelines_high_risk_draft_3_annex_iii/s-3.4.2/2", "to analyse and filter job applications, and to evaluate candidates")),
            claim("L3", "legal", "Deployers must assign human oversight to competent, trained persons.",
                  ("eu_ai_act/art-26/1", "Deployers shall assign human oversight to natural persons who have the necessary competence, training and authority")),
            claim("L4", "legal", "Deployers must keep automatically generated logs under their control.",
                  ("eu_ai_act/art-26/3", "Deployers of high-risk AI systems shall keep the logs automatically generated by that high-risk AI system to the extent such logs are under their control")),
            claim("L5", "legal", "Employers must inform workers' representatives before using a high-risk AI system at the workplace.",
                  ("eu_ai_act/art-26/4", "deployers who are employers shall inform workers’ representatives and the affected workers")),
            claim("L6", "legal", "Deployers must ensure AI literacy of their staff.",
                  ("eu_ai_act/art-4/1", "Providers and deployers of AI systems shall take measures to support the development of AI literacy of their staff")),
            claim("L7", "legal", "Affected persons have a right to an explanation of decisions based on high-risk AI output.",
                  ("eu_ai_act/art-86/1", "shall have the right to obtain from the deployer clear and meaningful explanations of the role of the AI system in the decision-making procedure")),
        ],
        "requirements": [
            {"requirement": "Use according to the instructions for use (Art. 26(1))", "status": "unclear", "explanation": "The documents do not mention the provider's instructions for use.", "claim_ids": ["F2"]},
            {"requirement": "Human oversight (Art. 26(2))", "status": "gap", "explanation": "Candidates below the shortlist are filtered out without human review.", "claim_ids": ["F3", "L3"]},
            {"requirement": "Log retention (Art. 26(6))", "status": "gap", "explanation": "Kivi cannot access logs; retention of at least six months is not ensured.", "claim_ids": ["F4", "L4"]},
            {"requirement": "Inform workers' representatives (Art. 26(7))", "status": "gap", "explanation": "The works council has not been informed yet.", "claim_ids": ["F6", "L5"]},
            {"requirement": "AI literacy (Art. 4)", "status": "met", "explanation": "Recruiters completed onboarding on reading scores and their limits.", "claim_ids": ["F5", "L6"]},
            {"requirement": "Right to explanation for candidates (Art. 86)", "status": "unclear", "explanation": "No process for explaining rejections is described.", "claim_ids": ["L7"]},
            {"requirement": "Fundamental rights impact assessment (Art. 27)", "status": "not_applicable", "explanation": "Kivi is a private company not providing public services; Art. 27 likely does not apply.", "claim_ids": []},
        ],
        "missing_information": [
            {"topic": "Instructions for use", "question": "Has Brightpath provided instructions for use, and do recruiters follow them?"},
            {"topic": "Human oversight", "question": "Can a recruiter override or review the ranking for candidates below the top 20?"},
            {"topic": "Logging", "question": "Can Kivi obtain the logs from Brightpath and keep them for at least six months?"},
            {"topic": "Candidates", "question": "How are rejected candidates told about the role of TalentLens and how can they ask for an explanation?"},
        ],
    },
    [
        {"claim_id": "F1", "status": "supported", "reason": "The brief states this directly."},
        {"claim_id": "F2", "status": "supported", "reason": "The brief names Brightpath AB as licensor."},
        {"claim_id": "F3", "status": "supported", "reason": "Quoted verbatim from the oversight section."},
        {"claim_id": "F4", "status": "supported", "reason": "The DPIA states Kivi has no log access."},
        {"claim_id": "F5", "status": "insufficient", "reason": "A one-hour vendor session shows onboarding, not that staff have sufficient AI literacy."},
        {"claim_id": "F6", "status": "supported", "reason": "Stated in the DPIA extract."},
        {"claim_id": "L1", "status": "supported", "reason": "Matches the Article 3(1) definition."},
        {"claim_id": "L2", "status": "supported", "reason": "The draft guidelines restate Annex III point 4(a)."},
        {"claim_id": "L3", "status": "supported", "reason": "Article 26(2) says this."},
        {"claim_id": "L4", "status": "supported", "reason": "Article 26(6) says this."},
        {"claim_id": "L5", "status": "supported", "reason": "Article 26(7) says this."},
        {"claim_id": "L6", "status": "supported", "reason": "Article 4 says this."},
        {"claim_id": "L7", "status": "supported", "reason": "Article 86(1) says this."},
    ],
    [{"file": "org_chart_scan.pdf", "error": "No readable text was extracted. Scanned PDFs need OCR first."}],
    revised=True,
)
hr["reference_problems"] = ["L8: quote is not verbatim from eu_ai_act/art-13/1"]
hr["report"] = build_report(hr, hr["file_errors"])

bot = build(
    [("description", BOT_DESC)],
    {
        "summary": "A webshop plans an AI assistant that answers customer questions about orders and returns and may suggest products.",
        "ai_system": "yes", "role": "unclear", "risk_tier": "unclear", "gpai_involved": "unclear", "confidence": "low",
        "reasoning": "A conversational assistant likely meets the AI system definition and, as it interacts with customers, Article 50(1) transparency duties likely apply. Nothing indicates an Annex III use. The description does not say who builds the assistant or which model it uses, so the role and GPAI involvement are unclear.",
        "claims": [
            claim("F1", "fact", "The assistant will answer customer questions about orders and returns.",
                  ("doc1:1", "an AI assistant to our webshop that answers customer questions about orders and returns")),
            claim("L1", "legal", "AI systems that interact directly with people must be designed so people know they are talking to an AI.",
                  ("eu_ai_act/art-50/1", "natural persons concerned are informed that they are interacting with an AI system")),
            claim("L2", "legal", "Product suggestions to customers are a limited-risk use.", ),
        ],
        "requirements": [
            {"requirement": "Transparency: disclose AI interaction (Art. 50(1))", "status": "unclear", "explanation": "Not described whether customers are told they talk to an AI.", "claim_ids": ["F1", "L1"]},
            {"requirement": "AI literacy (Art. 4)", "status": "unclear", "explanation": "No information about staff training.", "claim_ids": []},
        ],
        "missing_information": [
            {"topic": "Role", "question": "Will you build the assistant yourself or buy it from a vendor?"},
            {"topic": "Model", "question": "Which language model powers the assistant?"},
            {"topic": "Decisions", "question": "Can the assistant approve refunds or make other decisions about customers?"},
        ],
    },
    [
        {"claim_id": "F1", "status": "supported", "reason": "Stated in the description."},
        {"claim_id": "L1", "status": "supported", "reason": "Article 50(1) requires this of providers."},
        {"claim_id": "L2", "status": "insufficient", "reason": "No passage quoted."},
    ],
    [], revised=False,
)

out = ROOT / "web" / "src" / "sample.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"hr": hr, "bot": bot}, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", {k: len(v["report"]["claims"]) for k, v in {"hr": hr, "bot": bot}.items()}, hr["report"]["warnings"], bot["report"]["warnings"])
