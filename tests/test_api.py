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


def test_end_to_end_with_scripted_model(monkeypatch, result):
    a = result["assessment"]
    a.update(claims=[{"id": "c1", "kind": "fact", "text": "It filters email.",
                      "references": [{"chunk_id": "doc1:1", "quote": "spam filter sorts incoming email"}]}], requirements=[])
    replies = [{"role": "assistant", "content": json.dumps(a)},
               {"role": "assistant", "content": json.dumps({"verdicts": [{"claim_id": "c1", "status": "supported", "reason": "ok"}]})}]
    monkeypatch.setattr(agents, "chat", lambda messages, tools=None: replies.pop(0))
    body = TestClient(api.app).post("/api/assess", data={"description": "A spam filter sorts incoming email."}).json()
    evidence = body["report"]["claims"][0]["evidence"][0]
    assert body["report"]["claims"][0]["status"] == "supported" and not body["revised"]
    assert evidence["passage"][evidence["start"]:evidence["end"]] == "spam filter sorts incoming email"


def test_empty_or_oversized_case_is_422():
    assert TestClient(api.app).post("/api/assess", data={"description": " "}).status_code == 422
    assert TestClient(api.app).post("/api/assess", data={"description": "x " * 60_000}).status_code == 422


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
