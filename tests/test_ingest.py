import pytest

from src.ingest import case_passages, extraction_error, passages, to_markdown


def test_text_and_html_convert_to_markdown():
    assert "hiring" in to_markdown("a.txt", b"We use AI for hiring.")
    assert "Ranks CVs" in to_markdown("a.html", b"<html><body><h1>Tool</h1><p>Ranks CVs</p></body></html>")


def test_unsupported_and_blank_files_are_rejected():
    with pytest.raises(ValueError, match="Unsupported"):
        to_markdown("a.exe", b"x")
    with pytest.raises(ValueError, match="No readable text"):
        to_markdown("a.txt", b"   ")
    assert extraction_error("![scan](page1.png)")


def test_passages_follow_headings_and_size_limit():
    text = "# Doc\n\nintro\n\n## Article 5 — Prohibited\n\n" + "\n\n".join(["word " * 60] * 6)
    out = passages(text, "d", "Doc")
    assert out[0]["label"] == "Doc" and out[0]["text"] == "intro"
    assert all(p["label"] == "Article 5 — Prohibited" for p in out[1:])
    assert len(out) > 2 and all(len(p["text"]) <= 1000 for p in out[1:])
    messy = "Title line\r\n\r\n  First para  \r\nwraps here \r\n \r\nSecond\tpara\n\n\n"
    out = passages(messy, "d", "Doc")
    assert [messy[p["start"]:p["end"]] for p in out] == [p["text"] for p in out] == ["Title line\r\n\r\n  First para  \r\nwraps here \r\n \r\nSecond\tpara"]


def test_bad_file_does_not_sink_the_batch():
    case, errors = case_passages([("good.md", b"A chatbot answers customers."), ("bad.txt", b"")], "Extra note.")
    assert [p["id"] for p in case] == ["doc1:1", "doc2:1"]
    assert errors[0]["file"] == "bad.txt"
