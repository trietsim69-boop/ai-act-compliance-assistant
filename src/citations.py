"""Deterministic quote check: keep only verbatim quotes from passages of the right kind, with their exact spans.

Offsets are computed here, never taken from the model: ref.start/ref.end index the passage text, and
passage["start"] + ref.start indexes the source Markdown.
"""

from src import law

MIN_QUOTE_CHARS = 15
_FOLD = str.maketrans("‘’“”–—", "''\"\"--")


def _normalise(text: str) -> tuple[str, list[int]]:
    """Lower-case, fold curly quotes/dashes, collapse whitespace; also return each char's raw index."""
    chars, index = [], []
    for i, ch in enumerate(text):
        if ch.isspace():
            if chars and chars[-1] != " ":
                chars.append(" ")
                index.append(i)
            continue
        low = ch.lower()
        chars.append((low if len(low) == 1 else ch).translate(_FOLD))  # keep 1:1 with the raw text
        index.append(i)
    return "".join(chars), index


def find_span(quote: str, text: str) -> tuple[int, int] | None:
    """(start, end) of the first occurrence of quote in text, ignoring case, quote style and whitespace."""
    needle = _normalise(quote)[0].strip()
    haystack, index = _normalise(text)
    at = haystack.find(needle) if len(needle) >= MIN_QUOTE_CHARS else -1
    return None if at < 0 else (index[at], index[at + len(needle) - 1] + 1)


def check_references(assessment, pack: dict) -> list[str]:
    """Drop references that are not verbatim quotes from the right kind of passage; set spans on the rest."""
    problems = []
    for claim in assessment.claims:
        kept = []
        for ref in claim.references:
            chunk = pack.get(ref.chunk_id)
            span = chunk and find_span(ref.quote, chunk["text"])
            if chunk is None:
                problems.append(f"{claim.id}: {ref.chunk_id} was never shown to you")
            elif (ref.chunk_id in law.corpus()) != (claim.kind == "legal"):
                problems.append(f"{claim.id}: {claim.kind} claims must cite {'law' if claim.kind == 'legal' else 'case'} passages")
            elif span is None:
                problems.append(f"{claim.id}: quote is not verbatim from {ref.chunk_id}")
            else:
                ref.start, ref.end = span
                kept.append(ref)
        claim.references = kept
    return problems
