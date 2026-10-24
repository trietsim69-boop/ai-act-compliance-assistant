"""Run the live pipeline on evals/cases.json and compare with expectations. Needs DEEPSEEK_API_KEY (costs credit).

    python -m evals.cases [case_name ...]

Besides tier / GPAI / AI system / role, it measures retrieval as the Assessor actually uses it: `saw` is how many of a
case's `must_see` provisions appeared in any search_law result during the run. Every query the Assessor wrote is
appended to data/eval_queries.jsonl (git-ignored) for analysis.

Obligations, for cases with `expected_obligations` ([{"article": "26", "status": "gap"|"met"|"unclear"|"any"}]):
`obl` is how many gold articles some requirement covers, `false_met` how many gold gap/unclear articles a requirement
marks met. A requirement covers an article it quotes (via its claims) or names ("Article 26", "Art. 26").
"""
import json
import re
import sys
import time
from pathlib import Path

import src.agents as agents
from src import law
from src.config import ROOT
from src.ingest import case_passages

PRIVATE = Path(__file__).parent / "private" / "cases.json"  # git-ignored: documents we may not republish
CASES = [c for path in (Path(__file__).parent / "cases.json", PRIVATE) if path.exists()
         for c in json.loads(path.read_text(encoding="utf-8"))]
LOG = ROOT / "data" / "eval_queries.jsonl"
_flat = lambda s: " ".join(s.split())  # noqa: E731
_NAMED = re.compile(r"\bArt(?:icles?|\.)?\s*(\d+[a-z]?)\b", re.I)  # ponytail: first number only, "Articles 9-15" -> 9


def obligations(result: dict) -> dict[str, set[str]]:
    """Act article -> statuses of the requirements that cover it."""
    a = result["assessment"]
    claims = {c["id"]: c for c in a["claims"]}
    found: dict[str, set[str]] = {}
    for r in a["requirements"]:
        if r["status"] == "not_applicable":  # saying it does not apply is not covering it
            continue
        quoted = [ref["chunk_id"] for i in r["claim_ids"] for ref in claims.get(i, {}).get("references", [])]
        articles = {i.split("/")[1].removeprefix("art-") for i in quoted if i.startswith(f"{law.ACT}/art-")}
        for article in articles | set(_NAMED.findall(f"{r['requirement']} {r['explanation']}")):
            found.setdefault(article, set()).add(r["status"])
    return found


def score_obligations(gold: list[dict], result: dict) -> tuple[int, int]:
    """(gold articles covered, gold gap/unclear articles marked met)."""
    found = obligations(result)
    return (sum(o["article"] in found for o in gold),
            sum(o["status"] in ("gap", "unclear") and "met" in found.get(o["article"], ()) for o in gold))


def main(names: list[str]) -> int:
    calls, searches = [], []
    chat, search = agents.chat, law.search
    agents.chat = lambda *args, **kwargs: calls.append(1) or chat(*args, **kwargs)

    def logged_search(query, *args, **kwargs):
        hits = search(query, *args, **kwargs)
        searches.append({"query": query, "ids": [c["id"] for c in hits], "texts": [_flat(c["text"]) for c in hits]})
        return hits
    law.search = logged_search

    LOG.parent.mkdir(exist_ok=True)
    failures = seen_total = must_total = obl_hit = obl_total = false_met = 0
    for case in CASES:
        if names and case["name"] not in names:
            continue
        docs = [(d["name"], d["text"].encode()) for d in case["documents"]]
        calls.clear()
        searches.clear()
        started = time.monotonic()
        try:
            result = agents.assess_case(case_passages(docs)[0])
        except Exception as error:  # report and keep going: one broken case must not hide the others
            failures += 1
            print(f"{case['name']:30} ERROR {type(error).__name__}: {str(error)[:120]} ({time.monotonic() - started:.0f}s)")
            continue
        a = result["assessment"]
        supported = sum(v["status"] == "supported" for v in result["verdicts"])
        shown = [t for s in searches for t in s["texts"]]
        must = case.get("must_see", [])
        seen = sum(any(_flat(q) in t for t in shown) for q in must)
        seen_total, must_total = seen_total + seen, must_total + len(must)
        gold = case.get("expected_obligations")
        if gold:
            hit, wrong = score_obligations(gold, result)
            obl_hit, obl_total, false_met = obl_hit + hit, obl_total + len(gold), false_met + wrong
        obl = f"obl={hit}/{len(gold)} false_met={wrong}" if gold else "obl=n/a"
        with LOG.open("a", encoding="utf-8") as f:
            for s in searches:
                f.write(json.dumps({"case": case["name"], "query": s["query"], "ids": s["ids"]}, ensure_ascii=False) + "\n")
        checks = {"tier": case["expected_risk_tier"] in (None, a["risk_tier"]),
                  "gpai": case["expected_gpai"] in (None, a["gpai_involved"]),
                  "ai_system": case.get("expected_ai_system") in (None, a["ai_system"]),
                  "role": case.get("expected_role") in (None, a["role"])}
        failures += not all(checks.values())
        print(f"{case['name']:30} tier={a['risk_tier']:13} gpai={a['gpai_involved']:7} ai={a['ai_system']:7} role={a['role']:8} "
              f"supported={supported}/{len(result['verdicts'])} saw={seen}/{len(must)} {obl} searches={len(searches)} "
              f"revised={result['revised']} calls={len(calls)} {time.monotonic() - started:.0f}s "
              f"{'PASS' if all(checks.values()) else 'FAIL ' + str([k for k, ok in checks.items() if not ok])}", flush=True)
    if must_total:
        print(f"must-see provisions found by the Assessor's own searches: {seen_total}/{must_total}")
    if obl_total:
        print(f"gold obligations covered: {obl_hit}/{obl_total}; gap/unclear marked met: {false_met}")
    return failures


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
