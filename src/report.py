"""Deterministic report: an assess_case result -> display sections with warnings.

Pure function, no LLM and no I/O. Every value is copied from the result or is a fixed template, so the report
never adds a legal conclusion; it only flags where the assessment's own evidence falls short.
"""

DISCLAIMER = ("Preliminary decision support generated from the uploaded documents and the bundled EU AI Act corpus. "
              "It is not legal advice and does not certify compliance.")


def build_report(result: dict, file_errors: list[dict]) -> dict:
    a, sources = result["assessment"], result["sources"]
    verdicts = {v["claim_id"]: v for v in result["verdicts"]}
    claims = []
    for c in a["claims"]:
        verdict = verdicts.get(c["id"], {"status": "insufficient", "reason": "No verdict."})
        claims.append({
            "id": c["id"], "kind": c["kind"], "text": c["text"], "status": verdict["status"], "reason": verdict["reason"],
            "evidence": [{"chunk_id": r["chunk_id"], "source": sources[r["chunk_id"]]["source"],
                          "label": sources[r["chunk_id"]]["label"], "quote": r["quote"],
                          "passage": sources[r["chunk_id"]]["text"], "start": r["start"], "end": r["end"]}
                         for r in c["references"]],
        })
    supported = {c["id"] for c in claims if c["status"] == "supported" and c["evidence"]}
    requirements = [{**r, "unverified": r["status"] == "met" and not (r["claim_ids"] and set(r["claim_ids"]) <= supported)}
                    for r in a["requirements"]]

    warnings = [f"Skipped {e['file']}: {e['error']}" for e in file_errors]
    counts = [
        (len(result["reference_problems"]), "citation(s) were removed because the quote is not verbatim from a passage the model was shown."),
        (sum(c["status"] == "contradicted" for c in claims), "claim(s) are contradicted by their quoted sources."),
        (sum(c["status"] == "insufficient" for c in claims), "claim(s) are not established by their quoted sources."),
        (sum(not c["evidence"] for c in claims), "claim(s) have no verified quote."),
        (sum(r["unverified"] for r in requirements), "requirement(s) marked met are not backed by supported claims."),
    ]
    warnings += [f"{n} {text}" for n, text in counts if n]
    if a["confidence"] == "low":
        warnings.append("Confidence is low: key facts are missing from the documents (see the questions).")
    if result["revised"]:
        warnings.append("The assessment was revised once after review; remaining issues are listed above.")

    return {
        "overview": {k: a[k] for k in ("summary", "ai_system", "role", "risk_tier", "gpai_involved", "confidence", "reasoning")},
        "requirements": requirements, "claims": claims, "questions": a["missing_information"],
        "warnings": warnings, "disclaimer": DISCLAIMER,
    }
