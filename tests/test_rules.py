import pytest

from src.rules import BY_ID, QUESTIONS, classify, legal_test, render

NO = {q.id: "no" for q in QUESTIONS} | {"A1": "yes", "A3": "yes", "B2": "yes"}  # an in-scope AI system, used, nothing else


def run(**changed):
    return classify(NO | changed)


@pytest.mark.parametrize("changed, tier, role", [
    ({}, "minimal_risk", "deployer"),
    ({"A1": "no"}, "out_of_scope", "deployer"),                     # not an AI system
    ({"A2": "yes"}, "out_of_scope", "deployer"),                    # basic data processing
    ({"A3": "no"}, "out_of_scope", "deployer"),                     # no EU link
    ({"A5": "yes"}, "out_of_scope", "deployer"),                    # scientific research only
    ({"C5": "yes"}, "prohibited", "deployer"),                      # social scoring
    ({"C9": "yes"}, "prohibited", "deployer"),                      # emotions at work
    ({"C9": "yes", "C10": "yes"}, "minimal_risk", "deployer"),      # ... for safety reasons
    ({"C6": "yes", "C7": "yes"}, "minimal_risk", "deployer"),       # supports a fact-based human assessment
    ({"C13": "yes", "C14": "yes", "E1a": "yes"}, "high_risk", "deployer"),  # authorised RBI stays Annex III
    ({"D1": "yes", "D2": "yes"}, "high_risk", "deployer"),
    ({"D1": "yes", "D2": "yes", "D3": "yes"}, "minimal_risk", "deployer"),  # not a safety component (6(1a))
    ({"E4a": "yes"}, "high_risk", "deployer"),
    ({"E4a": "yes", "F1": "yes"}, "minimal_risk", "deployer"),      # Art 6(3)(a), no profiling
    ({"E4a": "yes", "F1": "yes", "F5": "yes"}, "high_risk", "deployer"),  # profiling overrides
    ({"G1": "yes"}, "limited_risk", "deployer"),
    ({"G1": "yes", "E5b": "yes"}, "high_risk", "deployer"),
    ({"A8": "yes"}, "out_of_scope", "deployer"),                    # open source, nothing higher (2(12))
    ({"A8": "yes", "G2": "yes"}, "limited_risk", "deployer"),
    ({"B1": "yes"}, "minimal_risk", "both"),
    ({"B1": "yes", "B2": "no"}, "minimal_risk", "provider"),
    ({"B2": "no", "B3": "yes", "E4a": "yes"}, "high_risk", "provider"),  # Art 25(1)(a) rebrand
    ({"B2": "no", "B3": "yes"}, "minimal_risk", "unclear"),         # Art 25 only for high-risk systems
])
def test_tier_and_role(changed, tier, role):
    d = run(**changed)
    assert (d["risk_tier"], d["role"]) == (tier, role)


def test_clean_answers_give_high_confidence_and_no_questions():
    d = run()
    assert (d["confidence"], d["open_questions"], d["could_be"]) == ("high", [], None)


def test_unknown_gating_fact_makes_the_tier_unclear():
    d = run(A1="not_mentioned")
    assert (d["risk_tier"], d["ai_system"], d["confidence"]) == ("unclear", "unclear", "low") and "A1" in d["open_questions"]


def test_unknown_eu_link_assumes_scope_and_asks():
    d = run(A3="not_mentioned")
    assert (d["risk_tier"], d["confidence"], d["open_questions"]) == ("minimal_risk", "medium", ["A3"])


def test_unknown_exception_keeps_the_prohibition_and_asks():
    d = run(C9="yes", C10="not_mentioned")
    assert d["risk_tier"] == "prohibited" and d["open_questions"] == ["C10"]


def test_unknown_profiling_keeps_annex_iii_high_risk():
    d = run(E4a="yes", F1="yes", F5="not_mentioned")
    assert d["risk_tier"] == "high_risk" and "F5" in d["open_questions"] and not d["annex_iii_exception"]


def test_exception_is_recorded_for_art_6_4_duties():
    d = run(E4a="yes", F1="yes")
    assert d["annex_iii_exception"] and {"E4a", "F1", "F5"} <= {p["question"] for p in d["path"]}


def test_unknown_that_could_raise_the_tier_sets_could_be_and_the_highest_wins():
    d = run(E4a="not_mentioned", C5="not_mentioned")
    assert (d["risk_tier"], d["could_be"], d["confidence"]) == ("minimal_risk", "prohibited", "low")
    assert {"E4a", "C5"} <= set(d["open_questions"])


def test_unknowns_below_the_final_tier_are_not_asked():
    d = run(C5="yes", E4a="not_mentioned", D1="not_mentioned", A4="not_mentioned")
    assert d["risk_tier"] == "prohibited" and d["open_questions"] == [] and d["could_be"] is None


def test_unknown_role_is_asked_but_not_for_out_of_scope():
    assert "B1" in run(B1="not_mentioned")["open_questions"]
    assert run(A3="no", B1="not_mentioned")["open_questions"] == []


def test_path_names_the_deciding_provision_and_transparency_is_listed_at_any_tier():
    d = run(E4a="yes", G1="yes")
    assert {"question": "E4a", "answer": "yes", "ref": "eu_ai_act/anx-III"} in d["path"] and d["transparency"] == ["G1"]


def test_every_question_anchor_finds_exactly_one_passage():
    assert len(BY_ID) == len(QUESTIONS)  # ids unique
    for q in QUESTIONS:
        legal_test(q)  # raises LookupError otherwise


def test_every_art5_and_annex_iii_point_has_a_question():
    art5 = {legal_test(q)["id"] for q in QUESTIONS if q.group == "C"}
    annex = {q.id for q in QUESTIONS if q.group == "E"}
    assert len(art5) >= 3  # Art 5(1)(a)-(h) spans several passages, all reached
    assert annex == {"E1a", "E1b", "E1c", "E2", "E3a", "E3b", "E3c", "E3d", "E4a", "E4b", "E5a", "E5b", "E5c", "E5d",
                     "E6a", "E6b", "E6c", "E6d", "E6e", "E7a", "E7b", "E7c", "E7d", "E8a", "E8b"}


def test_render_lists_each_legal_passage_once():
    text = render()
    assert text.count("[eu_ai_act/art-5/1]") == 1 and "A1: Does the system infer" in text
