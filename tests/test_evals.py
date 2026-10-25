from evals.cases import score_obligations


def test_obligations_count_quoted_and_named_articles_and_flag_wrong_met(result):
    a = result["assessment"]
    a["claims"][1]["references"] = [{"chunk_id": "eu_ai_act/art-50/1", "quote": "q"}]  # c2 backs the met requirement
    a["requirements"][1]["explanation"] = "Article 4 applies to every provider and deployer."
    a["requirements"].append({"requirement": "FRIA (Art. 26)", "status": "not_applicable", "explanation": "", "claim_ids": []})
    gold = [{"article": "50", "status": "gap"}, {"article": "4", "status": "any"}, {"article": "26", "status": "gap"}]
    assert score_obligations(gold, result) == (2, 1)  # 50 quoted, 4 named, 26 missing; 50 is a gap marked met


def test_report_counts_under_calls_and_whether_a_warning_caught_them(result):
    import copy
    from evals.cases import report
    under = copy.deepcopy(result) | {"decision": {"could_be": "high_risk"}}  # says limited, gold high, warned
    cases = [{"name": "a", "expected_risk_tier": "high_risk", "expected_gpai": None},
             {"name": "b", "expected_risk_tier": "limited_risk", "expected_gpai": None}]
    m = report([(cases[0], under, 10, 0.01), (cases[1], result, 20, 0.01)])
    assert m["tier under-called"] == "1/2 (50%)" and m["  under-calls flagged by could-be"] == "1/1 (100%)"
    assert m["tier over-called"] == "0/2 (0%)" and m["all checks"] == "1/2 (50%)"
