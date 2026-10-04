"""Recall of corpus search. No API key needed.

    python -m evals.retrieval                              # legal-style gold queries, then the external held-out set
    python -m evals.retrieval evals/retrieval_heldout.json # any other set in the same format, every query measured

The headline is recall@K on the gold queries that cite a provision (how the Assessor searches), at K, the number of
passages the Assessor actually sees per search (src.law.K). Everyday-language gold queries stay in the file but are not
measured (decided 2026-10-04). A quote counts only when found in the expected source document, so guidance quoting the
Act does not count as finding the Act. An "article" ref (the external set) counts when any passage of that article is
returned. The external set comes from other projects: report it, never tune against it.
"""
import json
import re
import sys
from pathlib import Path

from src.law import ACT, K, search


def load(path: str | Path = Path(__file__).parent / "retrieval_gold.json") -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["queries"]


GOLD = load()
EXTERNAL = load(Path(__file__).parent / "retrieval_external.json")


def _flat(text: str) -> str:
    return " ".join(text.split())


def _stem(source: str) -> str:
    return source.lower().removesuffix(".html")  # gold labels the Act "EU_AI_Act" or "EU_AI_Act.html"


def style(query: str) -> str:
    """'legal' if the query cites a provision (how the Assessor searches), else 'lay'."""
    return "legal" if re.search(r"\b(Article|Annex|Recital)\b", query) else "lay"


def _hit(ref: dict, top: list[tuple[str, str]]) -> bool:
    if "article" in ref:
        return any(id_.startswith(f"{ACT}/art-{ref['article']}/") for id_, _ in top)
    return any(id_.split("/")[0] == _stem(ref["source"]) and _flat(ref["quote"]) in text for id_, text in top)


def recall(k: int = K, only: str | None = "legal", gold: list[dict] = GOLD) -> float:
    hits = total = 0
    for q in gold:
        if only and style(q["query"]) != only:
            continue
        top = [(c["id"], _flat(c["text"])) for c in search(q["query"], k)]
        for ref in q["expected"]:
            total += 1
            hits += _hit(ref, top)
    return hits / total if total else float("nan")


if __name__ == "__main__":
    sets = ([(sys.argv[1], load(sys.argv[1]), None)] if len(sys.argv) > 1 else
            [("gold, legal-style", GOLD, "legal"), ("external held-out, article level", EXTERNAL, None)])
    print(f"the Assessor sees {K} passages per search")
    for name, gold, only in sets:
        measured = [q for q in gold if not only or style(q["query"]) == only]
        print(f"{name}: {len(measured)} queries, {sum(len(q['expected']) for q in measured)} expected")
        print("  " + "  ".join(f"recall@{k} {recall(k, only, gold):.1%}" for k in sorted({10, K})) + "  <- @12 is the headline")
