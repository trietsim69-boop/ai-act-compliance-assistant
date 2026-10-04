from src.report import build_report


def test_report_copies_the_assessment_and_flags_every_weakness(result):
    report = build_report(result, [{"file": "scan.pdf", "error": "No readable text"}])

    assert report["overview"]["risk_tier"] == "limited_risk" and report["questions"] == result["assessment"]["missing_information"]
    met, unclear = report["requirements"]
    assert (met["status"], met["unverified"]) == ("met", True)  # c2 unsupported: flagged, status untouched
    assert unclear["unverified"] is False
    evidence = report["claims"][0]["evidence"][0]
    assert evidence["passage"][evidence["start"]:evidence["end"]] == "chatbot answers customer questions"
    assert report["warnings"] == [
        "Skipped scan.pdf: No readable text",
        "1 citation(s) were removed because the quote is not verbatim from a passage the model was shown.",
        "1 claim(s) are not established by their quoted sources.",
        "1 claim(s) have no verified quote.",
        "1 requirement(s) marked met are not backed by supported claims.",
        "Confidence is low: key facts are missing from the documents (see the questions).",
        "The assessment was revised once after review; remaining issues are listed above.",
    ]
    assert "not legal advice" in report["disclaimer"]


def test_clean_result_has_no_warnings_and_missing_verdicts_count_as_insufficient(result):
    a = result["assessment"]
    a.update(confidence="high", claims=a["claims"][:1], requirements=a["requirements"][:1])
    a["requirements"][0]["claim_ids"] = ["c1"]
    result.update(reference_problems=[], revised=False, verdicts=result["verdicts"][:1])
    assert build_report(result, [])["warnings"] == []

    result["verdicts"] = []
    report = build_report(result, [])
    assert report["claims"][0]["status"] == "insufficient" and report["requirements"][0]["unverified"] is True
