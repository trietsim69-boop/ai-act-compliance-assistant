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


QUOTE = "Our chatbot answers customer questions."


def questionnaire_llm(*replies):
    """Fake chat: the Verifier supports every claim with evidence; other calls get the next reply."""
    calls, queue = [], list(replies)

    def chat(messages, tools=None):
        calls.append({"messages": list(messages), "tools": tools})
        if messages[0]["content"] == agents.VERIFIER_PROMPT:
            claims = json.loads(messages[1]["content"])
            return {"role": "assistant", "content": json.dumps({"verdicts": [
                {"claim_id": c["claim_id"], "status": "supported" if c["evidence"] else "insufficient", "reason": "r"} for c in claims]})}
        return {"role": "assistant", "content": json.dumps({"answers": queue.pop(0)})}
    return chat, calls


def answer(q, a="yes", quote=QUOTE):
    return {"question": q, "answer": a, "statement": "s", "references": [{"chunk_id": "doc1:1", "quote": quote}] if a != "not_mentioned" else []}


def test_questionnaire_keeps_verified_answers_without_search(monkeypatch):
    chat, calls = questionnaire_llm([answer("A1: Does the system infer"), answer("B2"), answer("G1", "not_mentioned"), answer("ZZ")])
    monkeypatch.setattr(agents, "chat", chat)
    out = agents.answer_questions(CASE, {c["id"]: c for c in CASE})
    assert out["answers"] == {"A1": "yes", "B2": "yes", "G1": "not_mentioned"}  # unknown id ZZ ignored
    assert len(calls) == 2 and calls[0]["tools"] is None and not out["revised"]
    first = calls[0]["messages"]
    assert first[0]["content"] == agents.CASE_PROMPT and first[1]["content"].startswith("## Case documents")
    assert "A1: Does the system infer" in first[1]["content"]


def test_bad_quote_on_the_decision_path_gets_one_revision(monkeypatch):
    chat, calls = questionnaire_llm([answer("A1", quote="a quote that is not in the case"), answer("B2")], [answer("A1")])
    monkeypatch.setattr(agents, "chat", chat)
    out = agents.answer_questions(CASE, {c["id"]: c for c in CASE})
    assert out["revised"] and out["answers"]["A1"] == "yes" and out["problems"] == []
    assert "A1: quote is not verbatim" in calls[2]["messages"][-1]["content"] and len(calls) == 4


def test_bad_quote_off_the_path_falls_back_to_not_mentioned_without_revision(monkeypatch):
    chat, calls = questionnaire_llm([answer("A1"), answer("B2"), answer("H1", quote="a quote that is not in the case")])
    monkeypatch.setattr(agents, "chat", chat)
    out = agents.answer_questions(CASE, {c["id"]: c for c in CASE})
    assert out["answers"]["H1"] == "not_mentioned" and not out["revised"] and len(calls) == 2
    assert [c.id for c in out["claims"]] == ["A1", "B2"]


def test_tree_pipeline_rates_only_listed_obligations_and_fails_closed(monkeypatch):
    from src.report import build_report
    status = {"summary": "A chatbot.", "reasoning": "It talks to people.", "statuses": [
        {"id": "50.1", "status": "met", "explanation": "Users are told.", "references": [{"chunk_id": "doc1:1", "quote": QUOTE}]},
        {"id": "99", "status": "met", "explanation": "Invented obligation.", "references": []}]}
    chat, calls = questionnaire_llm([answer("A1"), answer("B1"), answer("B2"), answer("G1")])

    def routed(messages, tools=None):
        if "## Task: rate the obligations" in messages[-1]["content"]:
            calls.append({"messages": list(messages), "tools": tools})
            return {"role": "assistant", "content": json.dumps(status)}
        return chat(messages, tools)
    monkeypatch.setattr(agents, "chat", routed)

    result = agents.assess_case_tree(CASE)

    a = result["assessment"]
    assert (a["risk_tier"], a["role"]) == ("limited_risk", "both")
    assert {r["requirement"]: r["status"] for r in a["requirements"]} == {
        "Tell people they are interacting with an AI system": "met", "AI literacy of staff": "unclear"}  # 99 ignored, 4 unrated
    legal = next(c for c in a["claims"] if c["id"] == "L50.1")["references"][0]
    assert legal["start"] is not None and legal["chunk_id"] in result["sources"]
    assert len(calls) == 4  # questionnaire, verifier, status, verifier
    report = build_report(result, [])
    assert report["decision"]["risk_tier"] == "limited_risk" and report["requirements"][0]["unverified"] is False


def test_tree_pipeline_drops_unproven_met(monkeypatch):
    status = {"summary": "s", "reasoning": "r", "statuses": [
        {"id": "50.1", "status": "met", "explanation": "e", "references": [{"chunk_id": "doc1:1", "quote": "a quote that is not in the case"}]}]}
    chat, _ = questionnaire_llm([answer("A1"), answer("B1"), answer("B2"), answer("G1")])
    monkeypatch.setattr(agents, "chat", lambda m, tools=None: {"role": "assistant", "content": json.dumps(status)}
                        if "## Task: rate the obligations" in m[-1]["content"] else chat(m, tools))
    a = agents.assess_case_tree(CASE)["assessment"]
    assert a["requirements"][0]["status"] == "unclear"
