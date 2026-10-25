# Decision-tree assessment: agreed architecture (grilling rounds 1–3, 2026-10-24)

Diagram: `../decision-tree-architecture.html` (artifact https://claude.ai/artifact/UVAdw94prRBwkgymSmm5Ps).
Tasks: [todo.md](todo.md). Branch `decision-tree` off `main` (687611c, includes PR #2).

## Phases (each ends in a PR into `main`; merging = production deploy)
| PR | Phase | Production effect |
|---|---|---|
| 1 | Baseline evals on `testing` + pin `deepseek-flash` | Model changes (only if flash ≥ chat on the baseline) |
| 2 | `src/rules.py`: questions, `classify()`, obligations table | None (inert) |
| 3 | `assess_case_tree` beside the old Assessor | None (inert) |
| 4 | Comparison passes the Q15 bar → switch, delete the old Assessor | The release |
| 5 | API re-run from your answers | New optional field |
| 6 | UI from `frontend`: decision path, `out_of_scope` label, answer inputs | UI |

## Risks
| Risk | Impact | Mitigation |
|---|---|---|
| `deepseek-flash` thinks by default and may break JSON mode or tool calls | High | Task 4 tests it before PR 1 |
| 4–5 calls on a 100k-char case exceed Vercel's 300 s | High | Case documents first for the prefix cache; long cases timed in Tasks 4, 12, 13 |
| ~40 answers with quotes make a large JSON reply that fails validation | Med | Existing one-retry-on-invalid-JSON; split by group if Task 11 shows failures |
| Gold lists encode my reading of the Act | Med | You review at Checkpoint A; each case names its deciding article |
| `testing` falls behind `main` | Low | Merge `main` and `decision-tree` into `testing` before every run |

## Decided (2026-10-24)
- Re-run trust (Task 14): earlier answers come back from the browser, pass `check_references` again, skip the Verifier. Accepted: it is the user's own report.
- Model: if flash is worse than chat in Task 4, stay on `deepseek-chat` (no PR 1 model change) and run the comparison on chat.

## Context
Today one free-form Assessor call decides tier, role and obligations; code only checks quotes. That is the
"LLM wrapper" problem. The plan "Norrin decision-tree assessment plan" moves the Act's logic into pure code
(`classify()` + obligations table); the LLM only answers fixed factual questions with verbatim case quotes and
writes the prose. Goals (Q1): auditable legal logic, complete and correct obligations; long documents as stress test.
The current eval cannot show improvement (last run 20/20, all cases ≤3k chars), so the eval comes first.

Retrieval verdict: law-side BM25 stays (96.6% gold legal, 87.1% external; embeddings +0.0–1.2). After this change,
search no longer decides the tier at all. The real "R" gap is case-side (whole upload in one prompt); decided by
measurement on the long cases (Q7), not now.

## Decisions
| # | Decision |
|---|---|
| Q1 | Step 0 = harder eval before code: ~8 new cases (Art 6(3) with/without profiling, Art 5 exceptions, borderline tiers), 2+ long real documents, gold obligation list per case |
| Q2 | One questionnaire call answers all questions; `classify()` returns the answers it used; only on-path (or tier-raising) `not_mentioned` become open questions |
| Q3 | "no" cites what the system does instead; Verifier checks "this rules out X"; failure → `not_mentioned` |
| Q4 | User answers to open questions become a case passage and re-run `classify()` without the questionnaire call |
| Q5 | Add questions: Art 5 exceptions, deployer type (public body / credit-insurance → Art 27), Art 2 open-source + pre-market exclusions, Art 25 triggers. Art 111 transitional: fixed note only |
| Q6 | `build_report` gains an additive `decision` key (path taken, articles, `could_be`); UI rendering later on `frontend` |
| Q7 | Keep whole document in context; case-side retrieval decided after long-case measurements |
| Q8 | Pin `LLM_MODEL=deepseek-flash`; compare old vs new on it |
| Q9 | No free-assessment fallback; questionnaire returns `other_concerns` (quoted) → warnings / open questions, never the tier |
| Q10 | Two calls (questionnaire, then obligation status + prose), case documents first in each for DeepSeek's prefix cache |
| Q11 | Drop `search_law` from the pipeline; `law.search` stays (evals, future chat); passages by id from `law.corpus()` |
| Q12 | Legal claims = code templates citing fixed passages (no Verifier). Verifier: questionnaire answers + obligation-status quotes, one call per round. One revision for failed on-path answers only; then fail closed |
| Q13 | Questions/tests/obligations as Python data in `src/rules.py`; legal test = passage id, text read from `law.corpus()`; test fails if an id disappears |
| Q14 | `risk_tier` keeps its values; `unclear` only for unknown gating facts; `decision.could_be` carries the possible higher tier |
| Q15 | Adopt if, on the new set and `deepseek-flash`: tier/role/GPAI ≥ old; obligation recall ≥ 90% with zero false "met"; cost ≤ 2× old; long cases < 300 s |
| Q16 | Claude drafts gold obligation lists from the provisions (never from output); user reviews before any run |
| Q17 | Committed eval uses public documents Claude finds; private docs only in git-ignored `evals/private/` |
| Q18 | Add `out_of_scope` to `risk_tier` (Art 2 exclusions, territorial); UI shows "Unclear" until `frontend` adds a label |
| Q19 | Long-case test: both an organisation's own documents combined (e.g. DUO reports + letters) and a needle-in-haystack case (short case inside a long unrelated public document) |
| Q20 | Branch `decision-tree` off `main`. Order: 1 eval expansion on `testing` (gold lists for user review) → 2 `rules.py` + tests → 3 questionnaire call → 4 obligations call + `decision` key → 5 re-run from answers → 6 comparison vs `main`. Steps 1–2 cost nothing |

**Open, not decided:** expand the corpus (user, round 3). First check what the Act and the bundled guidance already
cover for each question and obligation; add a source only where a question's legal test has no passage to cite.

## Long public documents (approved by the user; download and verify in step 1)
- GOV.UK Chat ATRS record (DSIT/GDS, OGL v3, English, ~4.5k words): RAG chatbot on Claude Sonnet 4 via Bedrock (Ireland),
  built in-house, public users. Exercises Art 2 territorial scope, Art 50(1), GPAI downstream, role "both".
  https://www.gov.uk/algorithmic-transparency-records/dsit-gov-dot-uk-chat
- DUO "controle uitwonendenbeurs" risk profile (Dutch government publications; Algorithm Audit + PwC reports, Dutch, long):
  rule-based risk scoring for student-finance checks. Exercises the AI-system definition borderline and Annex III 5(a).
  Links found: duo.nl/organisatie/controle-uitwonendenbeurs.jsp, zoek.officielebekendmakingen.nl/kst-24724-240.pdf (verify)
- Amsterdam "Slimme Check" register entry (welfare-fraud model, historical data, 15 features, human decides):
  Annex III 5(a), profiling → no Art 6(3) exception, public-body FRIA. https://algoritmes.overheid.nl/en/algoritme/95794697
  (DPIA on open.amsterdam returned 403)
- For the ~100k-character latency/needle test: open question Q19.

## Code changes (branch off `main`; tests/evals on `testing`)
| File | Change |
|---|---|
| `src/rules.py` (new) | questions (id, group, text, legal-test passage id, gating flag), `classify(answers) -> decision`, obligations table (tier × role × trigger → passage id), confidence rule |
| `src/agents.py` | `assess_case`: questionnaire call → `check_references` + `verify` → one revision → `classify` → obligations call → same `Assessment` + `decision`. Remove ASSESSOR_PROMPT search loop and SEARCH_TOOL. Keep `chat`, `_parse`, `_format`, `verify`, `CaseError` |
| `src/report.py` | add `decision` to the return value (additive) |
| `api/index.py` | accept prior `answers` for the deterministic re-run (Q4) |
| `src/citations.py`, `src/law.py`, `web/` | unchanged (UI falls back to "Unclear" for unknown tier values, `web/src/Report.jsx:98`) |
| `testing` | `tests/test_rules.py` (~20 table tests, every tier path, ids exist in `law.corpus()`); new cases in `evals/cases.json` with `expected_obligations`; `evals.cases` scores obligation recall and false "met" |

## Verification
`python -m pytest -q` on `testing` (offline); `python -m evals.cases` on main vs branch, both on `deepseek-flash`
(live, cost reported); time the longest case against the 300 s limit; check the adoption bar (Q15).

## Task 4 smoke test (2026-10-24, old pipeline, `deepseek-flash`, first run with thinking ON by mistake)
| Case | Result | Time | Calls / searches | Tokens hit / miss / out | Cost (peak) |
|---|---|---|---|---|---|
| hr_screening (3k chars) | PASS, obl 3/3, false met 0, supported 44/46 | 183 s | 12 / 14 | 132k / 114k / 39k | $0.082 |
| duo_student_finance_profile (192k) | FAIL: high_risk, ai_system unclear (gold: not an AI system) | 502 s | 9 / 40 | 567k / 327k / 105k | $0.228 |

Rerun with PR 1 settings (`deepseek-flash`, `thinking: disabled` = what the retired `deepseek-chat` alias served, i.e. production today):

| Case | Result | Time | Calls / searches | Tokens hit / miss / out | Cost (peak) |
|---|---|---|---|---|---|
| hr_screening | PASS, obl 2/3, false met 0, supported 35/35 | 68 s | 12 / 13 | 164k / 82k / 16k | $0.045 |
| duo_student_finance_profile | PASS: ai_system no (tier minimal_risk) | 67 s | 12 / 13 | 627k / 209k / 13k | $0.083 |

- Probe: `deepseek-chat` answers as `deepseek-flash` without reasoning; `deepseek-flash` thinks by default; `{"thinking": {"type": "disabled"}}` turns it off. PR 1 pins flash with thinking off (like for like).
- Thinking on made both cases 3–7× slower, dearer, and the DUO case wrong. Keep it off; testing it on is a separate question.
- With thinking off the 192k-char case takes 67 s, well inside 300 s.
- Cost: ~$0.05 per short case at peak, half off-peak. A full Task 12 run of both pipelines on 33 cases is roughly $2–4 at peak; run it off-peak (outside 01–04 and 06–10 UTC on weekdays).

## Task 11 smoke test (2026-10-24, tree pipeline, `deepseek-flash`, thinking off)
First run: every answer unmatched (the model echoed "A1: <question text>" as the id) → fixed in `Answer` (`id_only`) and the prompt.

| Case | Result | Time | Calls | Tokens hit / miss / out | Cost (peak) | Old pipeline (Task 4 rerun) |
|---|---|---|---|---|---|---|
| hr_screening | PASS, obl 3/3, supported 52/52 | 33 s | 4 | 1k / 22k / 8k | $0.017 | PASS, 68 s, $0.045 |
| cv_parser_procedural | FAIL gpai (unclear vs gold no); tier minimal right; obl 1/3 | 31 s | 5 | 17k / 24k / 8k | $0.017 | not run |
| duo_student_finance_profile | PASS, not an AI system, supported 39/39 | 36 s | 2 | 60k / 50k / 9k | $0.026 | PASS, 67 s, $0.083 |

- About half the time and a third of the cost of the old pipeline, with no search rounds.
- Watch in Task 12: cv_parser obl 1/3 means the Art 6(4)/49(2) rows were not listed, so the model probably answered Annex III 4(a) "no" (CV parsing as "analysing applications"), reaching minimal risk without the exception. GPAI `unclear` when the documents name a specific trained model and never mention a general-purpose one.

## Task 12, part 1: tree pipeline, all 33 cases (2026-10-24, Saturday off-peak, `deepseek-flash`, thinking off)
23/33 pass; obligations covered 124/143 (86.7%); 1 gap/unclear marked met; 14 min in total, slowest case 39 s; $0.49 at peak rates (≈ $0.25 billed off-peak). Failed checks: gpai 8, tier 4, ai_system 3, role 2.

| Cause | Cases | Effect |
|---|---|---|
| A1 (AI system) fails verification → gating → whole case unclear | smart_toy_challenges, university_emotion_research, white_label_hiring | tier, ai_system, role wrong; 14 obligations lost |
| GPAI `unclear` vs gold `no` (documents name a custom model, never a GPAI one) | 8 (sole failure in 5) | gold vs question wording |
| A3 answered yes (hosted in AWS Ireland) | govuk_chat_record | limited_risk vs gold out_of_scope (contestable) |
| B6 public body not recognised | welfare_fraud_risk_score | misses 27, 49.3 |
| Provider not recognised for an in-house chatbot on a third-party LLM | customer_chatbot | misses 50(1) |
| False met | amsterdam_slimme_check | likely Art 4 met (staff training documented): gold may be wrong |

Bar so far: long cases < 300 s ✓, cost ✓; obligation recall 86.7% < 90%, false met 1 > 0; accuracy vs old pending (old run 2026-10-25).

## Task 12: comparison (2026-10-24/25, `deepseek-flash`, thinking off, all 33 cases)
Fixes between tree runs, all general (no case wording): unknown A1 assumed and asked (like A3); "no" = nothing in the documents indicates it, with a tree Verifier that accepts a description as ruling a question out; output cap 32k tokens (the ~8k default truncated the questionnaire); deployer question says selling or hosting for customers is not use; GPAI "no" when the system's own model is not general-purpose. Gold changed by user decision: GOV.UK Chat in scope (limited risk).

| | Old (free Assessor) | Tree run 1 | Tree run 2 | Tree run 3 | **Tree final** |
|---|---|---|---|---|---|
| Pass | 24/33 | 23/33 | 25/33 | 28/32 + 1 crash | **30/33** |
| Failed checks | gpai 8, tier 2, role 1, ai 1 | gpai 8, tier 4, ai 3, role 2 | gpai 6, role 4, ai 1 | gpai 2, role 3 | **gpai 2, role 1** |
| Obligations covered | 127/145 (87.6%) | 124/143 (86.7%) | 138/145 (95.2%) | 139/144 (96.5%) | **138/145 (95.2%)** |
| Gap/unclear marked met | 2 | 1 | 1 | 1 | **1** (Amsterdam Art 4: staff training documented, gold may be wrong) |
| Open questions mean / max | – | – | 5.1 / 37 | 1.0 / 5 | **1.0 / 4** |
| Low confidence | – | – | 20/33 | 7/33 | **9/33** |
| Slowest case | 72 s | 39 s | 43 s | 51 s | **47 s** |
| Cost at peak rates | $1.10 | $0.49 | $0.42 | $0.59 | **$0.54** |

Bar (Q15): tier 0 vs 2 ✓, role 1 vs 1 ✓, GPAI 2 vs 8 ✓, obligations 95.2% ≥ 90% ✓, cost 0.49× ✓, slowest 47 s < 300 s ✓; false met 1 > 0 ✗ unless the Amsterdam Art 4 gold is corrected (user's call).
Remaining misses: public body not recognised for municipalities (welfare_fraud_risk_score, amsterdam_slimme_check: Art 27 / 49(3)); CV parsing not treated as Annex III 4(a), so no Art 6(4)/49(2) rows; in-house chatbot on a third-party LLM read as deployer (Art 50(1) missed).

## Metrics: both full runs re-scored against today's gold (2026-10-25, offline from data/eval_results/)
| Metric | Old (free Assessor) | Decision tree |
|---|---|---|
| All four checks correct | 24/33 (73%) | 30/33 (91%) |
| Risk tier / AI system / GPAI / role | 93% / 96% / 53% / 95% | 100% / 100% / 88% / 95% |
| Obligation recall | 127/145 (87.6%) | 138/145 (95.2%) |
| Obligation precision (vs key-obligation gold, pessimistic for the old pipeline) | 127/286 (44.4%) | 138/153 (90.2%) |
| Obligation F1 | 58.9% | 92.6% |
| Status agreement (covered, gold not "any") | 79/120 (66%) | 117/133 (88%) |
| False met | 1/137 | 0/137 |
| Open questions per case | 6.2 | 1.0 |
| Confidence high / medium / low | 0 / 16 / 17 | 12 / 12 / 9 |
| Time median / max | 48 s / 72 s | 33 s / 47 s |
| Cost per run (peak) | $1.10 | $0.54 |

Long documents only (4): all four checks 2/4 → 4/4; recall 86.4% → 90.9%; precision 47.5% → 100%; status agreement 13/15 → 13/17 (Dutch documents); open questions 6.5 → 0.5.
Production after PR #6: live call HTTP 200 in 38 s (in-house credit scoring: high-risk, both, 16 obligations, no warnings).
