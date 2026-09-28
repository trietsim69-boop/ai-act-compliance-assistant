"""Recall@k of corpus search on hand-reviewed questions. No API key needed.

    python -m evals.retrieval
"""
import json
import re
from pathlib import Path

from src.law import search

GOLD = json.loads((Path(__file__).parent / "retrieval_gold.json").read_text(encoding="utf-8"))["queries"]


def _flat(text: str) -> str:
    return " ".join(text.split())


def style(query: str) -> str:
    """'legal' if the query cites a provision (how the Assessor searches), else 'lay'."""
    return "legal" if re.search(r"\b(Article|Annex|Recital)\b", query) else "lay"


def recall(k: int = 10, only: str | None = None) -> float:
    hits = total = 0
    for q in GOLD:
        if only and style(q["query"]) != only:
            continue
        texts = [_flat(c["text"]) for c in search(q["query"], k)]
        for ref in q["expected"]:
            total += 1
            hits += any(_flat(ref["quote"]) in t for t in texts)
    return hits / total


if __name__ == "__main__":
    for k in (5, 10):
        print(f"recall@{k}: {recall(k):.1%}  (lay {recall(k, 'lay'):.1%}, legal {recall(k, 'legal'):.1%})")
