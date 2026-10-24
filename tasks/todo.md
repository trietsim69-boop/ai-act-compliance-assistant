# Decision-tree assessment: tasks

Plan and decisions: [plan.md](plan.md). Diagram: [../decision-tree-architecture.html](../decision-tree-architecture.html). These files live on `testing` only (never on a branch bound for `main`).

Every push to `main` deploys production. Each phase ends in one PR into `main` that is safe to deploy:
PRs 2 and 3 add code that nothing in production calls yet, PR 4 is the switch (the release), PRs 5 and 6 add re-running from your answers.
Tests and evals stay on `testing` and never go into `main`: before each run, `git switch testing && git merge decision-tree`
(`testing` is currently behind `main` by PR #2; merge `main` in first).

Commands (on `testing`): `python -m pytest -q` (offline), `python -m evals.retrieval` (offline), `python -m evals.cases` (live DeepSeek, costs money).

---

## Phase 0: Baseline and model pin → PR 1 `model: deepseek-flash`

### Task 1: Score obligations in `evals.cases`
**Description:** `evals/cases.py` gains two metrics so the old and new pipelines can be compared. Obligation recall is gold articles ∩ articles cited by the requirements' claims, at article level (`eu_ai_act/art-26/…` → 26). False "met" counts requirements marked `met` where the gold status is `gap` or `unclear`. A case lists `expected_obligations: [{"article": "26", "status": "gap"|"met"|"unclear"|"any"}]`; cases without it print `n/a`.
**Acceptance criteria:**
- [x] Each case row prints `obl=x/y` and `false_met=n`; the run ends with totals.
- [x] The old pipeline's results are scored without changing `src/` (articles come from the requirement → claim → reference chain).
- Done 2026-10-24 (`c5b1f12` on `testing`); unit-checked with a fake result, live output first seen in Task 4.
**Verification:** a fake run on a hand-made result (monkeypatched `assess_case`) prints the expected numbers; `pytest` passes.
**Dependencies:** none. **Files:** `evals/cases.py`. **Scope:** S

### Task 2: Borderline cases with gold obligations
**Description:** About 8 new short cases in `evals/cases.json` that the current 20 don't cover:
- Art 6(3) exception, once with profiling and once without;
- an Art 5 exception (emotion recognition for medical or safety reasons);
- an Art 2 exclusion (research only; non-EU);
- an Art 25 rebrand that makes a deployer a provider;
- a public-body deployer that needs a rights assessment (Art 27);
- downstream use of a general-purpose model;
- a borderline AI-system-definition case.

Add `expected_obligations` to the existing 20 too. Gold tiers and obligations come from reading the provisions, never from pipeline output.
**Acceptance criteria:**
- [x] Each new case has expected tier, role, AI-system status, GPAI involvement and obligations, with a one-line note naming the deciding article.
- [x] All 29 short cases have `expected_obligations` (124 gold obligations); done 2026-10-24 (`315b8fe`).
**Verification:** JSON loads; **you review the gold lists** (checkpoint below).
**Dependencies:** Task 1 (schema). **Files:** `evals/cases.json`. **Scope:** M

### Task 3: Long real-document cases
**Description:** Download the approved public documents into their own folder, convert them with MarkItDown, and add them as cases:
- GOV.UK Chat record (OGL; out of scope by territory, Art 50, downstream GPAI);
- the DUO risk-profile reports and government letters, combined (Annex III 5(a); is it an AI system at all?);
- the Amsterdam Slimme Check entry (Annex III 5(a), profiling, rights assessment);
- one needle-in-haystack case: an existing short case placed inside a long, unrelated public document (about 100,000 characters).

Record the source URL and licence for each case in `cases.json`.
**Acceptance criteria:**
- [x] 4 long cases: GOV.UK Chat 22k, needle-in-VAT-guide 121k (public, OGL); DUO 192k, Amsterdam 14k (`evals/private/`, git-ignored: no licence stated, repo is public). Done (`698a4fe`).
- [x] Every document's source and licence is recorded.
**Verification:** `case_passages` ingests each document without errors; character counts are printed.
**Dependencies:** Task 1. **Files:** `evals/cases.json`, `evals/sources/` (licence notes). **Scope:** M

### Checkpoint A: you review the gold lists (Tasks 2–3) before Task 12, the full paid run — sheet: [gold_review.md](gold_review.md)

### Task 4: Smoke test on `deepseek-flash` (live, a few cents)
**Description:** Changed 2026-10-24: no full baseline now. Task 12 runs the old and new pipelines side by side once, and that run is the baseline. Here: `evals.cases` captures token usage and cost per case (DeepSeek `usage`: cache hit / miss / output), then today's pipeline runs on `deepseek-flash` for one short case and the longest case (DUO, 192k chars).
**Acceptance criteria:**
- [x] `deepseek-flash` returns valid JSON and tool calls (it thinks by default).
- [x] The DUO case's time is recorded against the 300 s limit, with its tokens and cost: 502 s, over the limit (see plan.md).
**Verification:** the numbers in `plan.md` match the run's output.
**Dependencies:** none. **Files:** `evals/cases.py`, `tasks/plan.md`. **Scope:** XS

### Task 5: Pin `deepseek-flash` → PR 1
**Description:** In `src/config.py`, change the default model to `deepseek-flash` and update the model line in the README. Your `.env` currently sets `LLM_MODEL=deepseek-chat`, so update it too (with your OK). Go ahead if the Task 4 smoke test passes; otherwise stay on `deepseek-chat`, skip this PR, and run Phases 2–3 on chat (decided 2026-10-24).
**Acceptance criteria:**
- [ ] On the branch's preview URL, one live assessment succeeds with flash.
- [ ] After merge, one live production assessment succeeds.
**Verification:** Vercel preview check, then a production check after you merge.
**Dependencies:** Task 4. **Files:** `src/config.py`, `README.md`. **Scope:** XS

---

## Phase 1: Rules in code → PR 2 `rules: questionnaire, classify, obligations table` (inert)

### Task 6: Question bank
**Description:** `src/rules.py` holds the questions as Python data: id, group (A–H plus deployer type), question text, gating flag, and the passage id(s) of its legal test. Cover the Q5 additions: Art 5 exceptions, deployer type, Art 2 open-source and pre-market exclusions, Art 25. Article numbers are checked against the consolidated text in `corpus/eu_ai_act.md`, Omnibus included.
**Acceptance criteria:**
- [x] Every anchor resolves to exactly one passage under its heading (`tests/test_rules.py`); anchors instead of hand-numbered passage ids.
- [x] Every Art 5(1) point and every Annex III point has a question.
- [x] A function renders the questions with their legal-test text read from the corpus, never copied into code.
- Done 2026-10-24 (`5b4f495`): 69 questions, 38 legal passages, ~46k chars rendered; review the question wording at Checkpoint B.
**Verification:** `pytest tests/test_rules.py` on `testing`.
**Dependencies:** none (can start alongside Phase 0). **Files:** `src/rules.py`, `tests/test_rules.py`. **Scope:** M

### Task 7: `classify(answers)`
**Description:** A pure function. It applies scope → Art 5 → Art 6(1) → Annex III with Art 6(3)/(4) → Art 50 → minimal risk, and derives role (group B) and GPAI (group H). It returns `decision`:
- `ai_system`, `risk_tier` (`out_of_scope` included), `role`, `gpai`;
- `path`: each step's question id, answer and article;
- `could_be`, `open_questions` (on-path only), `confidence`.
**Acceptance criteria:**
- [x] About 20 table tests: every tier path, Art 6(3) with and without profiling, `not_mentioned` on a gating fact (tier `unclear`), `not_mentioned` that could only raise the tier (sets `could_be`), and an off-path `not_mentioned` (no question).
- [x] `classify()` does no I/O and calls no LLM (`legal_test`/`render` read the corpus; `classify` never does). Done 2026-10-24 (`dbbf0ef`): 23 table cases + 10 behaviour tests; unknowns below the final tier are never asked.
- [x] A3 (EU link) `not_mentioned` counts as in scope plus an open question, not `unclear`: most cases never state their location. Only an explicit non-EU answer gives `out_of_scope`.
**Verification:** `pytest` on `testing`.
**Dependencies:** Task 6. **Files:** `src/rules.py`, `tests/test_rules.py`. **Scope:** M

### Task 8: Obligations table
**Description:** `obligations(decision)` returns rows of `{id, requirement, articles, passage_id, claim_text}` for the tier × role × trigger combination: high-risk provider and deployer, the Art 6(3) record and registration, Art 50 per trigger, GPAI provider vs downstream user, Art 4 for everyone in scope, and stop-use for prohibited. Each row's legal claim is a fixed sentence whose quote comes verbatim from its passage.
**Acceptance criteria:**
- [ ] Every `passage_id` exists, and every claim's quote passes `find_span` against its passage (test).
- [ ] The Art 27 rights assessment appears only for public-body or credit/insurance deployers; Art 53 duties only for GPAI model providers.
**Verification:** `pytest` on `testing`.
**Dependencies:** Task 7. **Files:** `src/rules.py`, `tests/test_rules.py`. **Scope:** S

### Checkpoint B → open PR 2
- [ ] `pytest` passes on `testing`; nothing in `api/` or `src/agents.py` imports `rules.py`, so production behaviour is unchanged.
- [ ] You review `classify()` against the diagram before Phase 2.

---

## Phase 2: New pipeline beside the old → PR 3 `pipeline: questionnaire and obligation calls` (inert)

### Task 9: Questionnaire call
**Description:** `answer_questions(case)` in `src/agents.py`: a prompt plus the `Answers` schema (`yes` / `no` / `not_mentioned` with quotes, plus `other_concerns`). Case documents come first in the message for DeepSeek's prefix cache. Each yes/no answer becomes a `fact` Claim, so `check_references` and `verify` are reused unchanged. Failures on the decision path get one revision; anything still failing becomes `not_mentioned`.
**Acceptance criteria:**
- [ ] A fake `chat` (monkeypatch) covers: verbatim answers kept; a bad quote dropped to `not_mentioned`; one revision only for on-path failures.
- [ ] No `search_law` tool is offered in this call.
**Verification:** `pytest` on `testing`; live on 3 cases through `evals.cases` (Task 11).
**Dependencies:** Task 7. **Files:** `src/agents.py`, `tests/test_agents.py`. **Scope:** M

### Task 10: Status and prose call; `assess_case_tree`
**Description:** `assess_case_tree(case)`: questionnaire → `classify` → `obligations` → call ② (status per listed obligation with case quotes, summary, reasoning) → Verifier on the status quotes. It returns today's result shape plus `decision`. Legal claims come from the templates and are checked by `check_references`, not the Verifier. `build_report` copies `decision` through when present (additive key).
**Acceptance criteria:**
- [ ] `build_report(tree_result)` returns today's keys plus `decision`, and `build_report(old_result)` is unchanged (test).
- [ ] Call ② cannot add or drop obligations: unknown ids are ignored and missing ones become `unclear`.
**Verification:** `pytest` on `testing`.
**Dependencies:** Tasks 8, 9. **Files:** `src/agents.py`, `src/report.py`, `tests/test_agents.py`, `tests/test_report.py`. **Scope:** M

### Task 11: `evals.cases --tree`
**Description:** A flag that runs `assess_case_tree` instead of `assess_case` and scores it with the same metrics. `saw` is replaced by "passages served" for the tree pipeline.
**Acceptance criteria:** [ ] All 32 cases run without a schema error on `deepseek-flash`.
**Verification:** a live run (estimate $1–3).
**Dependencies:** Task 10. **Files:** `evals/cases.py`. **Scope:** XS

### Checkpoint C → open PR 3
- [ ] `pytest` passes; `api/index.py` still calls `assess_case`, so production is unchanged.

---

## Phase 3: Compare, then switch → PR 4 `assessment: decision tree replaces the free Assessor` (the release)

### Task 12: Comparison and decision
**Description:** The one full paid run (also the baseline, since Task 4 became a smoke test). Run old and new on all 33 cases on `deepseek-flash`, including the old pipeline's requirements that neither quote nor name an article (if more than a few, add a requirement-name → article fallback reusing the Task 8 names). Write both tables into `plan.md`, check them against the bar (Q15), and **you decide**. If the bar isn't met: fix and re-run, no PR.
**Acceptance criteria:**
- [ ] Tier, role and GPAI accuracy are at least the old pipeline's.
- [ ] Obligation recall is at least 90% with 0 false "met".
- [ ] Cost is at most 2× the old pipeline's.
- [ ] Every long case finishes in under 300 seconds.
**Dependencies:** Task 11. **Files:** `tasks/plan.md`. **Scope:** XS

### Task 13: Switch and delete the old Assessor
**Description:**
- `assess_case` becomes the tree pipeline.
- `out_of_scope` joins the `risk_tier` enum.
- Delete `ASSESSOR_PROMPT`'s search loop, `SEARCH_TOOL`, `_assess` and `MAX_SEARCH_ROUNDS`. `law.search` stays.
- Update the README's "How it works" and "Quality" with the Task 12 numbers.
- Update the local CLAUDE.md pipeline invariants.
**Acceptance criteria:**
- [ ] The API response keeps every key the UI reads; the UI shows `out_of_scope` as "Unclear" until Phase 4.
- [ ] `pytest` passes, with the old-Assessor tests rewritten.
**Verification:** a preview deployment with one long case timed under 300 seconds; then production with one case after you merge.
**Dependencies:** Task 12 (adopt). **Files:** `src/agents.py`, `api/index.py`, `README.md`, `tests/test_agents.py`, `tests/test_api.py`. **Scope:** M

### Checkpoint D → open PR 4. Merging releases the new pipeline.

---

## Phase 4: Re-run from your answers → PR 5 (API), PR 6 (UI, from `frontend`)

### Task 14: API accepts answers
**Description:** `POST /api/assess` takes an optional `answers` field (JSON `{question_id: {"answer": "yes"|"no", "text": "..."}}`) and the previous `decision.answers`. The files are re-sent (the server keeps no state) and re-ingested; earlier answers pass `check_references` again, and your answers become a "your answers" passage that the quotes cite. It skips the questionnaire call and runs `classify()` plus call ②.
**Acceptance criteria:**
- [ ] A re-run with answers makes exactly the call ② and Verifier requests (fake `chat` counts calls).
- [ ] Malformed `answers` → 422.
**Verification:** `pytest` on `testing`; one live re-run on the preview.
**Dependencies:** Task 13. **Files:** `api/index.py`, `src/agents.py`, `tests/test_api.py`. **Scope:** M

### Checkpoint E → open PR 5

### Task 15: UI: decision path, out-of-scope label, answer inputs (on `frontend`)
**Description:**
- Show `decision.path` as the reasoning chain.
- Add a `TIER.out_of_scope` label.
- "Answer Questions and Re-run" sends yes/no plus text per open question.
- `npm run build`, then commit the source and `public/index.html` together.
**Acceptance criteria:**
- [ ] A long real case shows its path with articles.
- [ ] A re-run changes the tier when an answer changes it.
**Verification:** run it locally (`uvicorn`), then on the preview.
**Dependencies:** Task 14. **Files:** `web/src/Report.jsx`, `web/src/shared.jsx`, `web/src/store.js`, `public/index.html`. **Scope:** M

### Checkpoint F → open PR 6 from `frontend`. Done.
