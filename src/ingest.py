"""Uploaded files -> Markdown (MarkItDown) -> citable passages."""

import io
import re
from pathlib import Path

from markitdown import MarkItDown, StreamInfo

SUPPORTED = {".pdf", ".docx", ".pptx", ".html", ".htm", ".csv", ".txt", ".md"}
MAX_PASSAGE_CHARS = 1000

_md = MarkItDown()


def to_markdown(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(f"Unsupported file type {ext or '(none)'}; use one of {', '.join(sorted(SUPPORTED))}")
    result = _md.convert_stream(io.BytesIO(data), stream_info=StreamInfo(extension=ext, filename=filename))
    text = result.text_content or ""
    error = extraction_error(text)
    if error:
        raise ValueError(error)
    return text


def extraction_error(text: str) -> str | None:
    # ponytail: catches blank/image-only/garbled output, not OCR quality.
    visible = re.sub(r"!\[[^\]]*\]\([^)]*\)|<img\b[^>]*>", "", text, flags=re.IGNORECASE)
    chars = [c for c in visible if not c.isspace()]
    if not any(c.isalnum() for c in chars):
        return "No readable text was extracted. Scanned PDFs need OCR first."
    damaged = sum(c == "�" or ord(c) < 32 for c in chars)
    if damaged / len(chars) > 0.1:
        return "Extracted text is mostly unreadable characters. Re-export as text or run OCR."
    return None


def passages(text: str, prefix: str, source: str) -> list[dict]:
    """Split Markdown into paragraph-aligned passages labelled by their nearest heading.

    Each passage is an exact slice: text[p["start"]:p["end"]] == p["text"].
    """
    out, label, start, end = [], source, None, None

    def flush():
        nonlocal start
        if start is not None:
            out.append({"id": f"{prefix}:{len(out) + 1}", "source": source, "label": label,
                        "text": text[start:end], "start": start, "end": end})
            start = None

    for block in re.finditer(r"\S.*?(?=\s*\n\s*\n|\s*\Z)", text, re.S):  # blank-line separated
        if block[0].startswith("#"):
            flush()
            if block[0].startswith("## ") or not out:
                label = " ".join(block[0].lstrip("# ").split())
            continue
        if start is not None and block.end() - start > MAX_PASSAGE_CHARS:
            flush()
        start = block.start() if start is None else start
        end = block.end()
    flush()
    return out


def case_passages(files: list[tuple[str, bytes]], description: str = "") -> tuple[list[dict], list[dict]]:
    """Case documents as citable passages (ids doc1:1, doc1:2, ...) plus per-file errors."""
    docs, errors = ([("description", description)] if description.strip() else []), []
    for name, data in files:
        try:
            docs.append((name, to_markdown(name, data)))
        except Exception as error:  # one bad file must not sink the batch
            errors.append({"file": name, "error": str(error)})
    return [p for n, (name, text) in enumerate(docs, 1) for p in passages(text, f"doc{n}", name)], errors
