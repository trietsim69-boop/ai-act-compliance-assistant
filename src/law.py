"""EU AI Act corpus search: corpus/*.md passages in an in-memory SQLite FTS5 (BM25) index."""

import re
import sqlite3
from collections import Counter
from functools import lru_cache

from src.config import CORPUS_DIR
from src.ingest import passages

_STOP = set("a an the is are was were be been to of for in on at by with and or as this that these those what which "
            "who how does do did under from it its into about would could should can may any".split())


ACT = "eu_ai_act"  # corpus stem of the regulation itself; everything else is guidance
_CITED = {"article": "art", "annex": "anx", "recital": "rec"}

_KEYS = [(r"(?:Chapter [IVXLC]+ › )?Article (\d+[a-z]?)\b", "art-{}"), (r"Recital (\d+)\b", "rec-{}"),
         (r"Annex ([IVXLC]+)\b", "anx-{}"), (r"(\d+(?:\.\d+)*|[IVX]+) ", "s-{}")]


def heading_key(label: str, title: str) -> str:
    """'Chapter IV › Article 50 — …' -> 'art-50' (4a -> 'art-4a'); guideline '2.5.1 …' -> 's-2.5.1'; text before any ## -> 'intro'."""
    if label == title:
        return "intro"
    for pattern, key in _KEYS:
        if m := re.match(pattern, label):
            return key.format(m[1])
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:40]


def document_passages(text: str, stem: str) -> list[dict]:
    """Corpus passages with stable ids {stem}/{heading key}/{n-th passage under that heading}."""
    title = text.split("\n", 1)[0].lstrip("# ").strip()
    seen = Counter()
    out = passages(text, stem, title)
    for c in out:
        key = heading_key(c["label"], title)
        seen[key] += 1
        c["id"] = f"{stem}/{key}/{seen[key]}"
    return out


@lru_cache(maxsize=1)
def corpus() -> dict[str, dict]:
    return {c["id"]: c for path in sorted(CORPUS_DIR.glob("*.md"))
            for c in document_passages(path.read_text(encoding="utf-8"), path.stem)}


@lru_cache(maxsize=1)
def _index() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute("CREATE VIRTUAL TABLE p USING fts5(id UNINDEXED, label, text, tokenize='porter unicode61')")
    db.executemany("INSERT INTO p VALUES (?, ?, ?)", [(c["id"], c["label"], c["text"]) for c in corpus().values()])
    return db


K = 8  # passages per search_law call; evals.retrieval reports recall at this k


def search(query: str, k: int = K) -> list[dict]:
    """BM25 hits, alternating the Act with guidance so commentary cannot crowd out the law it discusses."""
    terms = [t for t in re.findall(r"\w+", query.lower()) if t not in _STOP]
    if not terms:
        return []
    expression = " OR ".join(f'"{t}"' for t in dict.fromkeys(terms))
    rows = _index().execute("SELECT id FROM p WHERE p MATCH ? ORDER BY bm25(p, 0, 5, 1) LIMIT ?",
                            (expression, 6 * k)).fetchall()
    hits = [corpus()[r[0]] for r in rows]
    cited = tuple(f"{ACT}/{_CITED[kind.lower()]}-{num.upper() if kind.lower() == 'annex' else num}/"
                  for kind, num in re.findall(r"\b(Article|Annex|Recital)\s+(\d+[a-z]?|[IVXLC]+)\b", query, re.I))
    # A provision named in the query ("Article 53(1)(b)") leads the Act results; BM25 order is kept within each group.
    act = sorted((c for c in hits if c["id"].startswith(f"{ACT}/")), key=lambda c: not c["id"].startswith(cited))
    guidance = [c for c in hits if not c["id"].startswith(f"{ACT}/")]
    return ([c for pair in zip(act, guidance) for c in pair] + act[len(guidance):] + guidance[len(act):])[:k]
