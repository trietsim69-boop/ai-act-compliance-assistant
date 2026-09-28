"""Run the live pipeline on evals/cases.json and compare with expectations. Needs DEEPSEEK_API_KEY.

    python -m evals.cases [case_name ...]
"""
import json
import sys
import time
from pathlib import Path

import src.agents as agents
from src.ingest import case_passages

CASES = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))


def main(names: list[str]) -> int:
    calls = []
    chat = agents.chat
    agents.chat = lambda *args, **kwargs: calls.append(1) or chat(*args, **kwargs)
    failures = 0
    for case in CASES:
        if names and case["name"] not in names:
            continue
        docs = [(d["name"], d["text"].encode()) for d in case["documents"]]
        calls.clear()
        started = time.monotonic()
        try:
            result = agents.assess_case(case_passages(docs)[0])
        except Exception as error:  # report and keep going: one broken case must not hide the others
            failures += 1
            print(f"{case['name']:30} ERROR {type(error).__name__}: {str(error)[:120]} ({time.monotonic() - started:.0f}s)")
            continue
        a = result["assessment"]
        supported = sum(v["status"] == "supported" for v in result["verdicts"])
        checks = {"tier": case["expected_risk_tier"] in (None, a["risk_tier"]),
                  "gpai": case["expected_gpai"] in (None, a["gpai_involved"]),
                  "ai_system": case.get("expected_ai_system") in (None, a["ai_system"]),
                  "role": case.get("expected_role") in (None, a["role"])}
        failures += not all(checks.values())
        print(f"{case['name']:30} tier={a['risk_tier']:13} gpai={a['gpai_involved']:7} ai={a['ai_system']:7} role={a['role']:8} "
              f"supported={supported}/{len(result['verdicts'])} revised={result['revised']} "
              f"calls={len(calls)} {time.monotonic() - started:.0f}s "
              f"{'PASS' if all(checks.values()) else 'FAIL ' + str([k for k, ok in checks.items() if not ok])}", flush=True)
    return failures


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
