import re

import pytest

from scripts.build_corpus import eurlex, structure
from src.config import CORPUS_DIR

EURLEX = """<div id="rct_12"><table><tbody><tr><td><p>(12)</p></td><td><p>The notion of ‘AI system’.</p></td></tr></tbody></table></div>
<div id="cpt_IV"><p class="oj-ti-section-1">CHAPTER IV</p>
 <div id="art_50"><p class="oj-ti-art">Article 50</p><div class="eli-title"><p class="oj-sti-art">Transparency`</p></div>
  <div id="050.001"><p class="oj-normal">1.  Providers shall ensure:</p>
   <table><tbody><tr><td><p>(a)</p></td><td><p>point a;</p><p>second para.</p></td></tr></tbody></table></div></div></div>
<div id="anx_III"><p class="oj-doc-ti">ANNEX III</p><p class="oj-doc-ti">High-risk AI systems</p><p>Intro.</p></div>"""


def test_eurlex_html_becomes_sections_with_points_joined():
    assert eurlex(EURLEX).split("\n\n") == [
        "## Recital 12", "(12) The notion of ‘AI system’.",
        "## Chapter IV › Article 50 — Transparency", "1. Providers shall ensure:", "(a) point a;", "second para.",
        "## Annex III — High-risk AI systems", "Intro."]


def test_built_ai_act_has_every_recital_article_and_annex_in_order():
    text = (CORPUS_DIR / "eu_ai_act.md").read_text(encoding="utf-8")
    assert [int(n) for n in re.findall(r"(?m)^## Recital (\d+)$", text)] == list(range(1, 181))
    assert [int(n) for n in re.findall(r"(?m)^## Chapter [IVXLC]+ › Article (\d+) — ", text)] == list(range(1, 114))
    assert len(re.findall(r"(?m)^## Annex [IVXLC]+ — ", text)) == 13

PDF_TEXT = """EN

CONTENTS

1.  Background ........................ 2

2.1.

Scope and exclusions ................. 3

3

1.  BACKGROUND

(1)

The guidelines explain Article 5.

2.1.  Scope and
exclusions

1. The following AI practices shall be prohibited:

4

EN

(2)  Research is excluded."""


def test_toc_sections_become_headings_and_furniture_goes():
    blocks = structure(PDF_TEXT).split("\n\n")
    assert blocks == ["## 1 BACKGROUND", "(1) The guidelines explain Article 5.", "## 2.1 Scope and exclusions",
                      "1. The following AI practices shall be prohibited:", "(2) Research is excluded."]


def test_toc_section_without_body_heading_fails_loudly():
    with pytest.raises(ValueError, match="2.1"):
        structure(PDF_TEXT.replace("2.1.  Scope and\nexclusions", "Scope and exclusions"))
