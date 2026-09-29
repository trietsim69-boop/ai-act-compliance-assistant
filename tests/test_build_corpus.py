import pytest

from scripts.build_corpus import eurlex, structure

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


CONSOLIDATED = """<div id="cpt_II"><div class="eli-subdivision" id="art_5">
 <p class="title-article-norm">Article 5</p><div class="eli-title"><p class="stitle-article-norm">Prohibited AI practices</p></div>
 <div class="norm"><span class="no-parag">1. </span><div class="norm inline-element">The following AI practices shall be prohibited:
  <p class="modref"><a>▼M1</a></p>
  <div class="grid-container grid-list"><div class="list grid-list-column-1"><span>(ba) </span></div>
   <div class="grid-list-column-2"><p class="norm">►M1 a new prohibition; ◄</p></div></div></div></div></div></div>
<div class="eli-container" id="anx_XIV"><p class="title-annex-1">ANNEX XIV</p><p class="title-annex-2">New annex</p><p class="norm">Text.</p></div>"""


def test_consolidated_markup_drops_amendment_markers_and_joins_markers():
    assert eurlex(CONSOLIDATED).split("\n\n") == [
        "## Chapter II › Article 5 — Prohibited AI practices", "1. The following AI practices shall be prohibited:",
        "(ba) a new prohibition;", "## Annex XIV — New annex", "Text."]


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
