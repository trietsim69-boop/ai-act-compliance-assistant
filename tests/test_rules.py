from src.rules import BY_ID, QUESTIONS, legal_test, render


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
