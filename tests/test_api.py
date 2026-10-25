import json

import httpx
import openai
from fastapi.testclient import TestClient

import api.index as api
import src.agents as agents


def test_assess_endpoint_returns_result_report_and_file_errors(monkeypatch, result):
    seen = []
    monkeypatch.setattr(api, "assess_case", lambda case: seen.append(case) or result)
    response = TestClient(api.app).post("/api/assess", data={"description": "A spam filter."},
                                        files=[("files", ("scan.pdf", b"", "application/pdf"))])
    assert response.status_code == 200 and len(seen[0]) == 1
    body = response.json()
    assert body["assessment"] == result["assessment"] and body["file_errors"][0]["file"] == "scan.pdf"
    assert body["report"]["warnings"][0].startswith("Skipped scan.pdf")


def test_end_to_end_with_scripted_model(monkeypatch):
    quote = "spam filter sorts incoming email"
    ref = [{"chunk_id": "doc1:1", "quote": quote}]

    def chat(messages, tools=None):
        if messages[0]["content"] == agents.VERIFIER_PROMPT:
            return {"role": "assistant", "content": json.dumps({"verdicts": [
                {"claim_id": c["claim_id"], "status": "supported", "reason": "ok"} for c in json.loads(messages[1]["content"])]})}
        if "## Task: rate the obligations" in messages[-1]["content"]:
            return {"role": "assistant", "content": json.dumps({"summary": "A spam filter.", "reasoning": "r", "statuses": []})}
        return {"role": "assistant", "content": json.dumps({"answers": [
            {"question": q, "answer": "yes", "statement": "It filters email.", "references": ref} for q in ("A1", "A3", "B2")]})}
    monkeypatch.setattr(agents, "chat", chat)
    body = TestClient(api.app).post("/api/assess", data={"description": "A spam filter sorts incoming email."}).json()
    assert body["report"]["overview"]["risk_tier"] == "minimal_risk" and body["report"]["decision"]["role"] == "deployer"
    evidence = next(c for c in body["report"]["claims"] if c["id"] == "A1")["evidence"][0]
    assert evidence["passage"][evidence["start"]:evidence["end"]] == quote


def test_empty_or_oversized_case_is_422():
    assert TestClient(api.app).post("/api/assess", data={"description": " "}).status_code == 422
    assert TestClient(api.app).post("/api/assess", data={"description": "x " * (agents.MAX_CASE_CHARS // 2 + 1)}).status_code == 422


def test_model_failures_are_502_without_internals(monkeypatch):
    client = TestClient(api.app, raise_server_exceptions=False)
    monkeypatch.setattr(agents, "chat", lambda messages, tools=None: {"role": "assistant", "content": "not json"})
    garbage = client.post("/api/assess", data={"description": "A spam filter."})
    assert garbage.status_code == 502 and "validation" not in garbage.text.lower()
    assert garbage.json()["detail"]["file_errors"] == []

    def down(messages, tools=None):
        raise openai.APIConnectionError(request=httpx.Request("POST", "https://api.deepseek.com"))
    monkeypatch.setattr(agents, "chat", down)
    assert client.post("/api/assess", data={"description": "A spam filter."}).status_code == 502


def test_access_code_and_upload_cap(monkeypatch, result):
    monkeypatch.setenv("ACCESS_CODE", "s3cret")
    monkeypatch.setattr(api, "assess_case", lambda case: result)
    client = TestClient(api.app)
    assert client.post("/api/assess", data={"description": "x"}).status_code == 401
    ok = client.post("/api/assess", data={"description": "x"}, headers={"x-access-code": "s3cret"})
    assert ok.status_code == 200
    big = [("files", ("big.txt", b"a" * (api.MAX_UPLOAD_BYTES + 1), "text/plain"))]
    assert client.post("/api/assess", files=big, headers={"x-access-code": "s3cret"}).status_code == 413


QUOTE = "spam filter sorts incoming email"
PREVIOUS = {"answers": {"A1": "yes", "B1": "yes", "B2": "yes", "A3": "not_mentioned"},
            "claims": [{"id": q, "kind": "fact", "text": "t", "references": [{"chunk_id": "doc1:1", "quote": quote}]}
                       for q, quote in (("A1", QUOTE), ("B2", QUOTE), ("B1", "a quote the documents do not contain"))]}


def test_rerun_with_answers_skips_the_questionnaire(monkeypatch):
    calls = []

    def chat(messages, tools=None):
        calls.append(messages[-1]["content"])
        if messages[0]["content"] == agents.VERIFIER_PROMPT:
            return {"role": "assistant", "content": json.dumps({"verdicts": [
                {"claim_id": c["claim_id"], "status": "supported", "reason": "ok"} for c in json.loads(messages[1]["content"])]})}
        return {"role": "assistant", "content": json.dumps({"summary": "s", "reasoning": "r", "statuses": [
            {"id": "26", "status": "met", "explanation": "e", "references": [{"chunk_id": "doc1:1", "quote": QUOTE}]}]})}
    monkeypatch.setattr(agents, "chat", chat)
    body = TestClient(api.app).post("/api/assess", data={
        "description": "A spam filter sorts incoming email.", "previous": json.dumps(PREVIOUS),
        "answers": json.dumps({"A3": {"answer": "yes", "text": "We are in Berlin."}, "E4a": {"answer": "yes", "text": "It ranks applicants."}})}).json()
    assert len(calls) == 2 and not any("## Task: answer every question" in c for c in calls)  # call ② and its Verifier only
    d = body["decision"]
    assert (d["risk_tier"], d["answers"]["A3"], d["answers"]["B1"]) == ("high_risk", "yes", "not_mentioned")  # B1 quote failed
    yours = next(c for c in body["report"]["claims"] if c["id"] == "E4a")["evidence"][0]
    assert yours["source"] == "Your answers" and "It ranks applicants." in yours["quote"]


def test_malformed_answers_are_422():
    client = TestClient(api.app)
    for answers, previous in (("not json", ""), ('{"ZZ": {"answer": "yes"}}', ""), ('{"A1": {"answer": "maybe"}}', ""),
                              ('{"A1": {"answer": "yes"}}', '{"claims": [{"id": "A1"}]}')):
        response = client.post("/api/assess", data={"description": "x" * 30, "answers": answers, "previous": previous})
        assert response.status_code == 422, (answers, previous)
