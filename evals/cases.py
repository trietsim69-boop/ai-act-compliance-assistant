"""Run the live pipeline on evals/cases.json and compare with expectations. Needs DEEPSEEK_API_KEY (costs credit).

    python -m evals.cases [case_name ...]           # live run, then the metrics below
    python -m evals.cases --score [case_name ...]   # metrics from the saved results again, no API calls (e.g. after a gold change)

Besides tier / GPAI / AI system / role, `saw` is how many of a case's `must_see` provisions the model was shown (the
questions' legal tests and the cited obligation provisions). Each full result is saved to data/eval_results/<case>.json
(git-ignored).

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
from src import law, rules
from src.config import ROOT
from src.ingest import case_passages

PRIVATE = Path(__file__).parent / "private" / "cases.json"  # git-ignored: documents we may not republish
CASES = [c for path in (Path(__file__).parent / "cases.json", PRIVATE) if path.exists()
         for c in json.loads(path.read_text(encoding="utf-8"))]
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


RESULTS = ROOT / "data" / "eval_results"  # git-ignored
RANK = ["out_of_scope", "minimal_risk", "limited_risk", "high_risk", "prohibited"]  # ascending severity
FIELDS = {"risk_tier": "expected_risk_tier", "ai_system": "expected_ai_system", "gpai_involved": "expected_gpai",
          "role": "expected_role"}


def report(scored: list[tuple]) -> dict:
    """Metrics for a compliance assistant over (case, result, seconds or None, cost or None); printed and returned.

    Under-calling the tier is the dangerous error (fewer duties than the law imposes), so it is counted apart from
    over-calling, with how many under-calls a could-be warning still flagged. False met = claiming compliance the
    documents do not show. Calibration = share of fully correct cases per confidence level."""
    pct = lambda a, b: f"{a}/{b} ({a / b:.0%})" if b else "n/a"  # noqa: E731
    ok = lambda c, r: all(c.get(k) in (None, r["assessment"][f]) for f, k in FIELDS.items())  # noqa: E731
    m = {"all checks": pct(sum(ok(c, r) for c, r, *_ in scored), len(scored))}
    for field, key in FIELDS.items():
        rows = [(c[key], r["assessment"][field]) for c, r, *_ in scored if c.get(key) is not None]
        m[field] = pct(sum(g == p for g, p in rows), len(rows))
    tiers = [(c["expected_risk_tier"], r["assessment"]["risk_tier"], (r.get("decision") or {}).get("could_be"))
             for c, r, *_ in scored if c.get("expected_risk_tier")]
    under = [(g, cb) for g, p, cb in tiers if p in RANK and RANK.index(p) < RANK.index(g)]
    m["tier under-called"] = pct(len(under), len(tiers))
    m["  under-calls flagged by could-be"] = pct(sum(cb in RANK and RANK.index(cb) >= RANK.index(g) for g, cb in under), len(under))
    m["tier over-called"] = pct(sum(p in RANK and RANK.index(p) > RANK.index(g) for g, p, _ in tiers), len(tiers))
    m["tier unclear"] = pct(sum(p not in RANK for _, p, _ in tiers), len(tiers))
    m["tier recall"] = ", ".join(f"{t} {pct(sum(g == p for g, p, _ in tiers if g == t), sum(g == t for g, *_ in tiers))}"
                                 for t in RANK if any(g == t for g, *_ in tiers))
    tp = fn = fp = agree = rated = false_met = negative = 0
    for c, r, *_ in scored:
        if "expected_obligations" not in c:
            continue
        found, gold = obligations(r), {o["article"]: o["status"] for o in c["expected_obligations"]}
        tp, fn, fp = tp + len(gold.keys() & found.keys()), fn + len(gold.keys() - found.keys()), fp + len(found.keys() - gold.keys())
        for art, s in gold.items():
            rated += art in found and s != "any"
            agree += art in found and s != "any" and s in found[art]
            negative += s in ("gap", "unclear")
            false_met += s in ("gap", "unclear") and "met" in found.get(art, ())
    recall, precision = tp / (tp + fn) if tp + fn else 0, tp / (tp + fp) if tp + fp else 0
    m["obligation recall"], m["obligation precision"] = pct(tp, tp + fn), pct(tp, tp + fp)
    m["obligation F1"] = f"{2 * recall * precision / (recall + precision):.0%}" if recall + precision else "n/a"
    m["status agreement"], m["false met"] = pct(agree, rated), pct(false_met, negative)
    levels = {}
    for c, r, *_ in scored:
        levels.setdefault(r["assessment"]["confidence"], []).append(ok(c, r))
    m["calibration (correct by confidence)"] = ", ".join(f"{k} {pct(sum(v), len(v))}" for k, v in sorted(levels.items()))
    verdicts = {(id(r), v["claim_id"]): v["status"] for _, r, *_ in scored for v in r["verdicts"]}
    claims = [(id(r), cl) for _, r, *_ in scored for cl in r["assessment"]["claims"]]
    m["claims verified"] = pct(sum(verdicts.get((i, cl["id"])) == "supported" and bool(cl["references"]) for i, cl in claims), len(claims))
    m["questions shown per case"] = f"{sum(len(r['assessment']['missing_information']) for _, r, *_ in scored) / len(scored):.1f}"
    secs = sorted(s for *_, s, _ in scored if s is not None)
    if secs:
        m["time median / max"] = f"{secs[len(secs) // 2]:.0f} s / {secs[-1]:.0f} s (limit 300 s)"
        m["cost at peak rates"] = f"${sum(c for *_, c in scored):.4f}"
    print("\n".join(f"{k:36} {v}" for k, v in m.items()))
    return m


def rescore(names: list[str]) -> None:
    """The metrics again from the saved results, without API calls."""
    report([(c, json.loads((RESULTS / f"{c['name']}.json").read_text(encoding="utf-8")), None, None)
            for c in CASES if (not names or c["name"] in names) and (RESULTS / f"{c['name']}.json").exists()])


# USD per million tokens, deepseek-flash at peak (off-peak is half); api-docs.deepseek.com pricing, 2026-10-24
PRICE = {"prompt_cache_hit_tokens": 0.006, "prompt_cache_miss_tokens": 0.3, "completion_tokens": 1.2}


def main(names: list[str]) -> int:
    print(f"model {agents.LLM_MODEL}")
    calls, usage = [], []
    chat = agents.chat
    agents.chat = lambda *args, **kwargs: calls.append(1) or chat(*args, **kwargs)
    completions = agents._client().chat.completions
    create = completions.create

    def counted(*args, **kwargs):
        reply = create(*args, **kwargs)
        usage.append({k: getattr(reply.usage, k, 0) or 0 for k in PRICE})
        return reply
    completions.create = counted

    failures = seen_total = must_total = 0
    scored = []
    for case in CASES:
        if names and case["name"] not in names:
            continue
        docs = [(d["name"], d["text"].encode()) for d in case["documents"]]
        calls.clear()
        usage.clear()
        started = time.monotonic()
        try:
            result = agents.assess_case(case_passages(docs)[0])
        except Exception as error:  # report and keep going: one broken case must not hide the others
            failures += 1
            print(f"{case['name']:30} ERROR {type(error).__name__}: {str(error)[:120]} ({time.monotonic() - started:.0f}s)")
            continue
        a = result["assessment"]
        supported = sum(v["status"] == "supported" for v in result["verdicts"])
        # the model is shown the questions' legal tests and the obligations' provisions
        shown = [_flat(rules.render())] + [_flat(p["text"]) for p in result["sources"].values()]
        must = case.get("must_see", [])
        seen = sum(any(_flat(q) in t for t in shown) for q in must)
        seen_total, must_total = seen_total + seen, must_total + len(must)
        gold = case.get("expected_obligations")
        if gold:
            hit, wrong = score_obligations(gold, result)
        obl = f"obl={hit}/{len(gold)} false_met={wrong}" if gold else "obl=n/a"
        tokens = {k: sum(u[k] for u in usage) for k in PRICE}
        cost = sum(tokens[k] * PRICE[k] for k in PRICE) / 1e6
        spent = f"tokens hit/miss/out={'/'.join(f'{v:,}' for v in tokens.values())} ${cost:.4f}"
        scored.append((case, result, time.monotonic() - started, cost))
        saved = RESULTS / f"{case['name']}.json"
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
        checks = {"tier": case["expected_risk_tier"] in (None, a["risk_tier"]),
                  "gpai": case["expected_gpai"] in (None, a["gpai_involved"]),
                  "ai_system": case.get("expected_ai_system") in (None, a["ai_system"]),
                  "role": case.get("expected_role") in (None, a["role"])}
        failures += not all(checks.values())
        print(f"{case['name']:30} tier={a['risk_tier']:13} gpai={a['gpai_involved']:7} ai={a['ai_system']:7} role={a['role']:8} "
              f"supported={supported}/{len(result['verdicts'])} saw={seen}/{len(must)} {obl} "
              f"revised={result['revised']} calls={len(calls)} {spent} {time.monotonic() - started:.0f}s "
              f"{'PASS' if all(checks.values()) else 'FAIL ' + str([k for k, ok in checks.items() if not ok])}", flush=True)
    if must_total:
        print(f"must-see provisions shown to the model: {seen_total}/{must_total}")
    if scored:
        print()
        report(scored)
    return failures


if __name__ == "__main__":
    if sys.argv[1:2] == ["--score"]:
        rescore(sys.argv[2:])
    else:
        raise SystemExit(main(sys.argv[1:]))
