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
