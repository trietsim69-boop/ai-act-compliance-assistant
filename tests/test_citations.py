from evals.retrieval import GOLD
from types import SimpleNamespace

from src.agents import Answers, Claim
from src.citations import _normalise, check_references, find_span
from src.law import corpus

TEXT = "Intro.\n\nProviders shall ensure that “AI systems”\r\ninteract   directly — with natural persons. Again: providers shall ensure that"


def test_span_survives_case_quote_style_dashes_and_line_breaks():
    quote = 'providers shall ensure that "AI SYSTEMS" interact directly - with'
    start, end = find_span(quote, TEXT)
    assert TEXT[start:end] == "Providers shall ensure that “AI systems”\r\ninteract   directly — with"


def test_repeated_quote_maps_to_first_occurrence_and_short_or_absent_quotes_fail():
    assert find_span("providers shall ensure that", TEXT)[0] == TEXT.index("Providers")
    assert find_span("shall ensure", TEXT) is None  # below MIN_QUOTE_CHARS
    assert find_span("providers must never ensure", TEXT) is None


def test_every_gold_quote_gets_an_exact_span_in_its_passage():
    flat = lambda s: " ".join(s.split())
    for q in GOLD:
        for ref in q["expected"]:
            for p in corpus().values():
                if flat(ref["quote"]) in flat(p["text"]):
                    start, end = find_span(ref["quote"], p["text"])
                    assert _normalise(p["text"][start:end])[0] == _normalise(ref["quote"])[0].strip()


def test_spans_are_set_by_the_checker_and_hidden_from_the_model():
    assert {"start", "end"}.isdisjoint(Answers.model_json_schema()["$defs"]["Reference"]["properties"])
    law = corpus()["eu_ai_act/art-50/1"]
    claim = Claim.model_validate({"id": "c1", "kind": "legal", "text": "t", "references": [
        {"chunk_id": law["id"], "quote": "Providers shall ensure that AI systems intended to interact", "start": 0, "end": 1}]})
    assert check_references(SimpleNamespace(claims=[claim]), {law["id"]: law}) == []
    ref = claim.references[0]
    assert law["text"][ref.start:ref.end] == "Providers shall ensure that AI systems intended to interact"
