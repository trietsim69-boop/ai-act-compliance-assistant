"""Build corpus/*.md from the downloaded sources in corpus/src/. Deterministic: re-running gives no diff.

    python -m scripts.build_corpus

EUR-Lex acts are built from their HTML, which marks every recital, article and annex. The OJ PDF of the AI Act is kept
in corpus/src/ for reference only: its two-column layout separates recital numbers from their text.
"""
import re
import sys

from bs4 import BeautifulSoup, Tag
from markitdown import MarkItDown

from src.config import CORPUS_DIR

TITLES = {
    "eu_ai_act": "Regulation (EU) 2024/1689 — Artificial Intelligence Act, consolidated 27.7.2026 (incl. Digital Omnibus, Regulation (EU) 2026/1744)",
    "guidelines_prohibited_practices": "Commission Guidelines on prohibited AI practices (C(2025) 5052 final, 29.7.2025, non-binding)",
    "guidelines_ai_system_definition": "Commission Guidelines on the definition of an AI system (C(2025) 5053 final, 29.7.2025, non-binding)",
    "guidelines_transparency_art50": "Commission Guidelines on the transparency obligations of Article 50 AI Act (C(2026) 5054 final, 20.7.2026, non-binding)",
    "guidelines_gpai_models": "Commission Guidelines on the scope of the obligations for general-purpose AI models (C(2025) 5045 final, 18.7.2025, non-binding)",
    # The high-risk draft ships as three PDFs whose section numbers restart per part, so each is its own document.
    "guidelines_high_risk_draft_1_general": "DRAFT Commission guidelines on high-risk classification (Article 6), part 1: general principles (consultation draft, 19.5.2026, non-binding)",
    "guidelines_high_risk_draft_2_annex_i": "DRAFT Commission guidelines on high-risk classification (Article 6), part 2: Article 6(1) and Annex I (consultation draft, 19.5.2026, non-binding)",
    "guidelines_high_risk_draft_3_annex_iii": "DRAFT Commission guidelines on high-risk classification (Article 6), part 3: Article 6(2) and Annex III (consultation draft, 19.5.2026, non-binding)",
}
NUMBER_ONLY = re.compile(r"\(\d+\)|(?:\d+\.)+|[IVX]+\.")
FURNITURE = re.compile(r"EN|\d+|[IVXL]+")  # running header, page numbers
HEADING = re.compile(r"((?:\d+\.)+|[IVX]+\.)\s+(\S.*)")
LEADER = re.compile(r"\.{5,}")


def structure(text: str) -> str:
    """PDF text -> Markdown body: TOC and page furniture removed, numbered sections as ## headings."""
    blocks = [" ".join(b.split()) for b in re.split(r"\n\s*\n", text)]
    blocks = [b for b in blocks if b and not FURNITURE.fullmatch(b)]
    toc_numbers = set()
    toc = [i for i, b in enumerate(blocks) if b.upper() in ("CONTENTS", "TABLE OF CONTENTS")]
    if toc:
        start = toc[0]
        end = max(i for i, b in enumerate(blocks) if LEADER.search(b))
        toc_numbers = {n.rstrip(".") for n in re.findall(r"(?<![\d.])(?:\d+\.)+", " ".join(blocks[start + 1:end + 1]))}
        blocks = blocks[:start] + blocks[end + 1:]

    merged = []  # "2.1." / "(12)" alone, or a heading wrapped after a comma, belongs with the next block
    for b in blocks:
        wrapped = merged and HEADING.fullmatch(merged[-1]) and merged[-1].endswith(",") and len(b) < 80 and not b.startswith("(")
        stray = merged and NUMBER_ONLY.fullmatch(merged[-1]) and not HEADING.fullmatch(b)  # "(46)" before "2.3.5. Title" stays alone
        if stray or wrapped:
            merged[-1] += " " + b
        else:
            merged.append(b)

    out, found = [], []
    for b in merged:
        m = HEADING.fullmatch(b)
        number = m and m[1].rstrip(".")
        if (m and len(b) <= 250 and not b.endswith((".", ":", ";", ","))
                and (not toc_numbers or (number in toc_numbers and number not in found))):
            found.append(number)
            b = f"## {number} {m[2]}"
        out.append(b)
    if toc_numbers and sorted(found) != sorted(toc_numbers):
        raise ValueError(f"TOC sections without a body heading: {sorted(toc_numbers - set(found))}")
    return "\n\n".join(out)


_BLOCKS = {"p", "div", "table", "tbody", "tr", "td"}
_SKIP = {"oj-ti-art", "oj-sti-art", "oj-doc-ti", "title-article-norm", "stitle-article-norm",  # titles (OJ / consolidated)
         "title-annex-1", "title-annex-2", "modref", "footnote"}                              # amendment notes
_AMENDMENT = re.compile(r"[►▼◄](?:B|M\d+)?")  # consolidated-text markers such as ►M1 ◄
_MARKER = re.compile(r"[‘']?(?:\(?(?:\d+[a-z]?|[a-z]{1,3})\)?\.?|—)")  # "1.", "1a.", "(a)", "(ba)", "(12)", "‘(68)", "—"


def _text(node) -> str:
    return " ".join(_AMENDMENT.sub("", node.get_text()).split())  # also folds non-breaking spaces


def _leaves(node) -> list[str]:
    """Text of each innermost block in document order (inline text between blocks counts as one)."""
    out, inline = [], []

    def flush():
        if text := " ".join(_AMENDMENT.sub("", "".join(inline)).split()):
            out.append(text)
        inline.clear()

    for child in node.children:
        if isinstance(child, Tag) and set(child.get("class", [])) & _SKIP:
            continue
        if isinstance(child, Tag) and child.name in _BLOCKS:
            flush()
            out += _leaves(child)
        else:
            inline.append(child.get_text() if isinstance(child, Tag) else str(child))
    flush()
    return out


def _paragraphs(node) -> list[str]:
    """A marker on its own ('(a)' table cell, '1.' span) joins the text that follows it."""
    out = []
    for text in _leaves(node):
        if out and _MARKER.fullmatch(out[-1]):
            out[-1] += " " + text
        elif out and re.fullmatch(r"[;:,.]+", text):  # punctuation left after a nested list
            out[-1] += text
        else:
            out.append(text)
    return out


def eurlex(html: str, kinds: str = "rct art anx") -> str:
    """EUR-Lex HTML (OJ or consolidated) -> '## Recital N' / '## Chapter X › Article N — Title' / '## Annex X — Title'."""
    out = []
    for root in BeautifulSoup(html, "html.parser").find_all("div", id=re.compile(r"^(rct_\d+|art_\d+[a-z]?|anx_[IVXLC]+)$")):
        kind, number = root["id"].split("_")
        if kind not in kinds.split():
            continue
        if kind == "rct":
            out.append(f"## Recital {number}")
        elif kind == "art":
            chapter = root.find_parent("div", id=re.compile(r"^cpt_[IVXLC]+$"))["id"][4:]
            title = _text(root.find(class_=["oj-sti-art", "stitle-article-norm"])).rstrip("`")  # '`': EUR-Lex typo in Art. 1
            out.append(f"## Chapter {chapter} › Article {number} — {title}")
        else:
            titles = root.find_all(class_="title-annex-2") or root.find_all(class_="title-annex-1")[1:] or root.find_all(class_="oj-doc-ti")[1:]
            out.append(f"## Annex {number} — {_text(titles[0])}" if titles else f"## Annex {number}")  # Annex XIV has no title
        out += _paragraphs(root)
    return "\n\n".join(out)


def ai_act() -> tuple[str, str]:
    """Articles and annexes from the consolidated text when present; recitals always from the OJ (consolidations omit them)."""
    src = CORPUS_DIR / "src"
    oj = (src / "eu_ai_act.html").read_text(encoding="utf-8")
    if not (src / "eu_ai_act_consolidated.html").exists():
        return eurlex(oj), "eu_ai_act.html"
    consolidated = (src / "eu_ai_act_consolidated.html").read_text(encoding="utf-8")
    return eurlex(oj, "rct") + "\n\n" + eurlex(consolidated, "art anx"), "eu_ai_act.html (recitals), eu_ai_act_consolidated.html"


def main() -> None:
    md = MarkItDown()
    for stem, title in TITLES.items():
        if stem == "eu_ai_act":
            body, source = ai_act()
        else:
            body, source = structure(md.convert(str(CORPUS_DIR / "src" / f"{stem}.pdf")).text_content), f"{stem}.pdf"
        text = f"# {title}\n\nSource: corpus/src/{source}, converted by scripts/build_corpus.py.\n\n{body}\n"
        (CORPUS_DIR / f"{stem}.md").write_text(text, encoding="utf-8", newline="\n")
        print(f"{stem}.md: {body.count('## ')} headings", file=sys.stderr)


if __name__ == "__main__":
    main()
