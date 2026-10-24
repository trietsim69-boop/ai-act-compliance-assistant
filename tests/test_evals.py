from evals.cases import score_obligations


def test_obligations_count_quoted_and_named_articles_and_flag_wrong_met(result):
    a = result["assessment"]
    a["claims"][1]["references"] = [{"chunk_id": "eu_ai_act/art-50/1", "quote": "q"}]  # c2 backs the met requirement
    a["requirements"][1]["explanation"] = "Article 4 applies to every provider and deployer."
    a["requirements"].append({"requirement": "FRIA (Art. 26)", "status": "not_applicable", "explanation": "", "claim_ids": []})
    gold = [{"article": "50", "status": "gap"}, {"article": "4", "status": "any"}, {"article": "26", "status": "gap"}]
    assert score_obligations(gold, result) == (2, 1)  # 50 quoted, 4 named, 26 missing; 50 is a gap marked met
