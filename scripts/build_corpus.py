"""Build corpus/*.md from the downloaded sources in corpus/src/. Deterministic: re-running gives no diff.

    python -m scripts.build_corpus

EUR-Lex acts are built from their HTML, which marks every recital, article and annex. The OJ PDF of the AI Act is kept
in corpus/src/ for reference only: its two-column layout separates recital numbers from their text.
"""
import re
import sys

from bs4 import BeautifulSoup
from markitdown import MarkItDown

from src.config import CORPUS_DIR

TITLES = {
    "eu_ai_act": "Regulation (EU) 2024/1689 — Artificial Intelligence Act (OJ L, 12.7.2024)",
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


def _text(node) -> str:
    return " ".join(node.get_text().split())  # also folds non-breaking spaces


def _paragraphs(node) -> list[str]:
    """Body paragraphs; a table row (marker cell + text cell) becomes '(a) text'."""
    out = []
    for child in node.find_all(True, recursive=False):
        if child.name == "p":
            if not {"oj-ti-art", "oj-sti-art", "oj-doc-ti"} & set(child.get("class", [])) and _text(child):
                out.append(_text(child))
        elif child.name == "table":
            for row in child.select(":scope > tbody > tr, :scope > tr"):
                cells = row.find_all("td", recursive=False)
                rest = _paragraphs(cells[-1]) or [""]
                marker = _text(cells[0]) if len(cells) > 1 else ""
                out += [f"{marker} {rest[0]}".strip(), *rest[1:]]
        else:
            out += _paragraphs(child)
    return out


def eurlex(html: str) -> str:
    """EUR-Lex HTML -> '## Recital N' / '## Chapter X › Article N — Title' / '## Annex X — Title' sections."""
    out = []
    for root in BeautifulSoup(html, "html.parser").find_all("div", id=re.compile(r"^(rct_\d+|art_\d+|anx_[IVXLC]+)$")):
        kind, number = root["id"].split("_")
        if kind == "rct":
            out.append(f"## Recital {number}")
        elif kind == "art":
            chapter = root.find_parent("div", id=re.compile(r"^cpt_[IVXLC]+$"))["id"][4:]
            out.append(f"## Chapter {chapter} › Article {number} — {_text(root.find(class_='oj-sti-art')).rstrip('`')}")  # '`': EUR-Lex typo in Art. 1
        else:
            out.append(f"## Annex {number} — {_text(root.find_all('p', class_='oj-doc-ti')[1])}")
        out += _paragraphs(root)
    return "\n\n".join(out)


def main() -> None:
    md = MarkItDown()
    for stem, title in TITLES.items():
        html = CORPUS_DIR / "src" / f"{stem}.html"
        source = html if html.exists() else CORPUS_DIR / "src" / f"{stem}.pdf"
        body = eurlex(html.read_text(encoding="utf-8")) if html.exists() else structure(md.convert(str(source)).text_content)
        text = f"# {title}\n\nSource: corpus/src/{source.name}, converted by scripts/build_corpus.py.\n\n{body}\n"
        (CORPUS_DIR / f"{stem}.md").write_text(text, encoding="utf-8", newline="\n")
        print(f"{stem}.md: {body.count('## ')} headings", file=sys.stderr)


if __name__ == "__main__":
    main()
