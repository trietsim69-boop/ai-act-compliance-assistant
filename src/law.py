"""EU AI Act corpus search: corpus/*.md passages in an in-memory SQLite FTS5 (BM25) index."""

import re
import sqlite3
from collections import Counter
from functools import lru_cache
from itertools import zip_longest

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


K = 12  # passages per search_law call; evals.retrieval reports recall at this k

# Everyday words → the Act's own vocabulary, so BM25 can match a business description to the provision.
# ponytail: hand-written word map; replace with embedding search if it keeps growing past ~50 entries.
_PLAIN_TO_ACT = {
    r"chat ?bots?|virtual assistants?|voice assistants?": "interact directly with natural persons",
    r"cvs?|resumes?|hiring|applicants?|candidates?|job ads?|interviews?": "recruitment selection of natural persons",
    r"deep ?fakes?|fake (?:videos?|images?|photos?|audio)|face ?swaps?": "deep fake generates manipulates image audio video content",
    r"nudes?|naked|intimate|porn\w*": "intimate parts sexually explicit",
    r"face search|face matching|facial|faces": "facial recognition biometric identification",
    r"cctv|scrap\w+|crawl\w*": "untargeted scraping facial images",
    r"emotions?|mood|anger|angry|stress\w*|feelings?": "emotion recognition infer emotions",
    r"credit ?scores?|loans?|lending|creditworth\w*": "creditworthiness credit score",
    r"insurance|premiums?|underwrit\w+": "risk assessment pricing life health insurance",
    r"police|crimes?|criminal|offen[cs]es?": "law enforcement criminal offence",
    r"schools?|students?|exams?|universit\w+|admissions?|grading": "education vocational training",
    r"employees?|staff|workers?|workplace|gig|couriers?": "workers work-related relationships",
    r"fines?|penalt\w+|sanctions?": "administrative fines",
    r"privately|private use|hobby|personal use": "purely personal non-professional activity",
    r"research|lab|laboratory": "scientific research and development",
    r"children|kids?|child|elderly|older people|seniors?": "vulnerabilities age",
    r"social scor\w*|citizen scor\w*|rat\w+ (?:residents|citizens)": "social score evaluation classification social behaviour",
    r"dashboards?|averages?|statistic\w*|rules? engines?": "basic data processing",
    r"llms?|gpt|chatgpt|foundation models?|language models?": "general-purpose AI model",
    r"machinery|machines?|safety part": "safety component product",
    r"emergency|ambulances?|dispatch\w*": "emergency calls dispatching",
}
_PLAIN = [(re.compile(rf"\b(?:{pattern})\b", re.I), words) for pattern, words in _PLAIN_TO_ACT.items()]


def search(query: str, k: int = K) -> list[dict]:
    """BM25 hits, alternating the Act with guidance so commentary cannot crowd out the law it discusses."""
    expanded = query + "".join(f" {words}" for pattern, words in _PLAIN if pattern.search(query))
    terms = [t for t in re.findall(r"\w+", expanded.lower()) if t not in _STOP]
    if not terms:
        return []
    expression = " OR ".join(f'"{t}"' for t in dict.fromkeys(terms))

    def bm25(within: str, limit: int) -> list[dict]:
        rows = _index().execute("SELECT id FROM p WHERE p MATCH ? AND id GLOB ? ORDER BY bm25(p, 0, 5, 1) LIMIT ?",
                                (expression, within + "*", limit))
        return [corpus()[r[0]] for r in rows]

    hits = bm25("", 6 * k)
    cited = dict.fromkeys(f"{ACT}/{_CITED[kind.lower()]}-{num.upper() if kind.lower() == 'annex' else num}/"
                          for kind, num in re.findall(r"\b(Article|Annex|Recital)\s+(\d+[a-z]?|[IVXLC]+)\b", query, re.I))
    # Provisions named in the query ("Article 53(1)(b)") lead the Act results. Each is searched on its own, so a low
    # overall rank cannot drop it, and they take turns, so one cannot fill every Act slot; BM25 order within each.
    named = [c for turn in zip_longest(*(bm25(prefix, k) for prefix in cited)) for c in turn if c]
    act = named + [c for c in hits if c["id"].startswith(f"{ACT}/") and c not in named]
    guidance = [c for c in hits if not c["id"].startswith(f"{ACT}/")]
    return ([c for pair in zip(act, guidance) for c in pair] + act[len(guidance):] + guidance[len(act):])[:k]
