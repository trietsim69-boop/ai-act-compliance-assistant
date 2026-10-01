"""Recall of corpus search on hand-reviewed questions. No API key needed.

    python -m evals.retrieval                              # the tuned gold set
    python -m evals.retrieval evals/retrieval_heldout.json # a held-out set (same format), never used for tuning

The headline is recall@K, the number of passages the Assessor actually sees per search (src.law.K). A hit counts only
when the quote is found in the expected source document, so guidance quoting the Act does not count as finding the Act.
"""
import json
import re
import sys
from pathlib import Path

from src.law import K, search


def load(path: str | Path = Path(__file__).parent / "retrieval_gold.json") -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["queries"]


GOLD = load()


def _flat(text: str) -> str:
    return " ".join(text.split())


def _stem(source: str) -> str:
    return source.lower().removesuffix(".html")  # gold labels the Act "EU_AI_Act" or "EU_AI_Act.html"


def style(query: str) -> str:
    """'legal' if the query cites a provision (how the Assessor searches), else 'lay'."""
    return "legal" if re.search(r"\b(Article|Annex|Recital)\b", query) else "lay"


def recall(k: int = K, only: str | None = None, gold: list[dict] = GOLD) -> float:
    hits = total = 0
    for q in gold:
        if only and style(q["query"]) != only:
            continue
        top = [(c["id"].split("/")[0], _flat(c["text"])) for c in search(q["query"], k)]
        for ref in q["expected"]:
            total += 1
            hits += any(stem == _stem(ref["source"]) and _flat(ref["quote"]) in text for stem, text in top)
    return hits / total if total else float("nan")


if __name__ == "__main__":
    gold = load(sys.argv[1]) if len(sys.argv) > 1 else GOLD
    print(f"{len(gold)} queries, {sum(len(q['expected']) for q in gold)} quotes; the Assessor sees {K} passages per search")
    for k in (5, K, 10):
        mark = "  <- headline" if k == K else ""
        print(f"recall@{k}: {recall(k, gold=gold):.1%}  (lay {recall(k, 'lay', gold):.1%}, legal {recall(k, 'legal', gold):.1%}){mark}")
