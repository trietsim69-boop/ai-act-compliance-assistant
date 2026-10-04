import json

import src.agents as agents
from src.law import search

LAW_QUERY = "Article 50 inform natural persons interacting with an AI system"
LAW = search(LAW_QUERY)[0]
CASE = [{"id": "doc1:1", "source": "brief.md", "label": "brief.md", "text": "Our chatbot answers customer questions."}]


def assessment(quote):
    return {"summary": "Chatbot", "ai_system": "yes", "role": "deployer", "risk_tier": "limited_risk",
            "gpai_involved": "unclear", "confidence": "medium", "reasoning": "r",
            "claims": [{"id": "c1", "kind": "fact", "text": "It is a chatbot",
                        "references": [{"chunk_id": "doc1:1", "quote": "Our chatbot answers customer questions."}]},
                       {"id": "c2", "kind": "legal", "text": "Users must be told",
                        "references": [{"chunk_id": LAW["id"], "quote": quote}]}],
            "requirements": [{"requirement": "Disclose AI", "status": "unclear", "explanation": "e", "claim_ids": ["c2"]}],
            "missing_information": []}


def fake_llm(replies):
    calls = []

    def chat(messages, tools=None):
        calls.append({"messages": list(messages), "tools": tools})
        return replies.pop(0)
    return chat, calls


def test_bad_quote_is_dropped_and_triggers_one_revision(monkeypatch):
    good_quote = " ".join(LAW["text"].split()[:12])
    tool_call = {"role": "assistant", "content": "", "tool_calls": [
        {"id": "t1", "type": "function", "function": {"name": "search_law", "arguments": json.dumps({"query": LAW_QUERY})}}]}
    verdicts = lambda s: {"role": "assistant", "content": json.dumps({"verdicts": [
        {"claim_id": "c1", "status": "supported", "reason": "ok"}, {"claim_id": "c2", "status": s, "reason": "r"}]})}
    chat, calls = fake_llm([
        tool_call,
        {"role": "assistant", "content": "```json\n" + json.dumps(assessment("made up text not in the law")) + "\n```"},
        verdicts("insufficient"),
        {"role": "assistant", "content": json.dumps(assessment(good_quote))},
        verdicts("supported"),
    ])
    monkeypatch.setattr(agents, "chat", chat)

    result = agents.assess_case(CASE)

    assert result["revised"] is True
    assert result["reference_problems"] == []
    assert all(v["status"] == "supported" for v in result["verdicts"])
    assert set(result["sources"]) == {"doc1:1", LAW["id"]}
    ref = result["assessment"]["claims"][1]["references"][0]
    assert " ".join(LAW["text"][ref["start"]:ref["end"]].split()) == good_quote
    revision_prompt = calls[3]["messages"][-1]["content"]
    assert "c2: quote is not verbatim" in revision_prompt and "c2: insufficient" in revision_prompt


def test_bad_tool_arguments_and_unusable_verifier_reply_fail_soft(monkeypatch):
    bad_call = {"role": "assistant", "content": "", "tool_calls": [
        {"id": "t1", "type": "function", "function": {"name": "search_law", "arguments": "{not json"}}]}
    good = {"role": "assistant", "content": json.dumps(assessment(" ".join(LAW["text"].split()[:12])))}
    chat, calls = fake_llm([bad_call, good, {"role": "assistant", "content": "no verdicts here"},
                            good, {"role": "assistant", "content": "still nothing"}])
    monkeypatch.setattr(agents, "chat", chat)

    result = agents.assess_case(CASE)

    assert calls[1]["messages"][-1]["content"].startswith("Invalid arguments")
    assert result["revised"] is True
    assert {v["status"] for v in result["verdicts"]} == {"insufficient"}


def test_citing_unseen_or_wrong_kind_passages_is_flagged():
    a = agents.Assessment.model_validate(assessment("anything at all here"))
    a.claims[0].references[0].chunk_id = LAW["id"]
    problems = agents.check_references(a, {c["id"]: c for c in CASE})
    assert any("never shown" in p for p in problems)
    assert all(not c.references for c in a.claims)
