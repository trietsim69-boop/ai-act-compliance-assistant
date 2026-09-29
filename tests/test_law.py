import re
from collections import defaultdict

from evals.retrieval import GOLD, recall
from src.config import CORPUS_DIR
from src.law import corpus, document_passages, search


def test_ai_act_has_every_recital_article_and_annex_in_order():
    text = (CORPUS_DIR / "eu_ai_act.md").read_text(encoding="utf-8")
    assert [int(n) for n in re.findall(r"(?m)^## Recital (\d+)$", text)] == list(range(1, 181))
    assert [int(n) for n in re.findall(r"(?m)^## Chapter [IVXLC]+ › Article (\d+) — ", text)] == list(range(1, 114))
    assert len(re.findall(r"(?m)^## Annex [IVXLC]+( — |$)", text)) == 14  # Annex XIV (2026/1744) has no title


def test_ids_are_stable_heading_keys_and_passages_are_exact_source_slices():
    headings = defaultdict(set)
    sources = {f.stem: f.read_text(encoding="utf-8") for f in CORPUS_DIR.glob("*.md")}
    for id_, p in corpus().items():
        assert re.fullmatch(r"[a-z0-9_]+/(intro|art-\d+[a-z]?|rec-\d+|anx-[IVXLC]+|s-[\dIVX.]+)/\d+", id_), id_
        headings[id_.rsplit("/", 1)[0]].add(p["label"])
        assert sources[id_.split("/")[0]][p["start"]:p["end"]] == p["text"]
    assert all(len(labels) == 1 for labels in headings.values())  # one heading per key


def test_editing_one_article_leaves_other_ids_unchanged():
    doc = "# Act\n\n## Article 4 — Literacy\n\nShort.\n\n## Article 5 — Prohibited\n\n" + "\n\n".join(["x " * 300] * 3)
    before = [(p["id"], p["text"]) for p in document_passages(doc, "act") if "/art-5/" in p["id"]]
    edited = doc.replace("Short.", "\n\n".join(["Much longer text. " * 40] * 4))
    after = [(p["id"], p["text"]) for p in document_passages(edited, "act") if "/art-5/" in p["id"]]
    assert before == after and len(before) == 3


def test_corpus_loads_every_source():
    sources = {c["source"] for c in corpus().values()}
    assert any("Artificial Intelligence Act" in s for s in sources) and len(sources) >= 3


def test_search_finds_the_right_provision():
    labels = [c["label"] for c in search("Article 50 inform natural persons interacting with an AI system")]
    assert any("Article 50" in label for label in labels[:3])
    assert search("the of and") == []
    assert search("Article 53(1)(b) documentation for downstream providers")[0]["id"].startswith("eu_ai_act/art-53/")


def test_every_gold_quote_is_in_the_corpus():
    texts = [" ".join(c["text"].split()) for c in corpus().values()]
    missing = [q["id"] for q in GOLD for r in q["expected"] if not any(" ".join(r["quote"].split()) in t for t in texts)]
    assert missing == []


def test_retrieval_recall_does_not_regress():
    # 2026-09-29 (consolidated Act, 72 queries / 86 quotes): 74.4% overall, lay 63.2%, legal 96.6%
    assert recall(10) >= 0.70
    assert recall(10, "lay") >= 0.50
    assert recall(10, "legal") >= 0.95
