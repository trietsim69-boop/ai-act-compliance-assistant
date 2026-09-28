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
