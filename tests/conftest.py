import copy

import pytest

_RESULT = {
    "assessment": {
        "summary": "A customer chatbot.", "ai_system": "yes", "role": "deployer", "risk_tier": "limited_risk",
        "gpai_involved": "yes", "confidence": "low", "reasoning": "It talks to customers.",
        "claims": [
            {"id": "c1", "kind": "fact", "text": "It chats with customers.",
             "references": [{"chunk_id": "doc1:1", "quote": "chatbot answers customer questions", "start": 4, "end": 38}]},
            {"id": "c2", "kind": "legal", "text": "Users must be told.", "references": []},
        ],
        "requirements": [
            {"requirement": "Disclose AI interaction", "status": "met", "explanation": "e", "claim_ids": ["c1", "c2"]},
            {"requirement": "AI literacy", "status": "unclear", "explanation": "e", "claim_ids": []},
        ],
        "missing_information": [{"topic": "oversight", "question": "Who reviews answers?"}],
    },
    "verdicts": [{"claim_id": "c1", "status": "supported", "reason": "ok"},
                 {"claim_id": "c2", "status": "insufficient", "reason": "no quote"}],
    "reference_problems": ["c2: quote is not verbatim from eu_ai_act/art-50/1"],
    "revised": True,
    "sources": {"doc1:1": {"id": "doc1:1", "source": "brief.md", "label": "brief.md",
                           "text": "Our chatbot answers customer questions.", "start": 0, "end": 39}},
}


@pytest.fixture
def result():
    """A realistic assess_case result: one supported fact, one unquoted legal claim, one revision."""
    return copy.deepcopy(_RESULT)
