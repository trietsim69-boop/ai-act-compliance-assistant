# Implementation Plan: Norrin v2 (lean agentic RAG → Vercel)

## Overview
Users upload documents describing an AI use case; the system assesses it against the EU AI Act and Commission guidance and reports risk tier, role, applicable obligations (met / gap / unclear) and open questions, with every claim backed by a verbatim, verified quote.

## Architecture Decisions (settled 2026-09-27)
- **Python stays.** After cleanup the runtime is ~350 lines; Vercel runs Python functions. UI can be a separate frontend later calling `/api/assess`.
- **Agents:** Assessor with a `search_law` tool → deterministic quote check → Verifier → at most one revision. A deterministic `src/report.py` (no LLM) turns the result into report sections with warnings; the UI renders the report (Task 17).
- **Citations (2026-09-27 redesign):** corpus passage IDs are stable, derived from the heading (`eu_ai_act/art-50/1`), so saved results survive corpus edits. The model supplies only `chunk_id` + quote; the quote check computes exact `start`/`end` offsets, and every passage is an exact slice of its source Markdown.
- **Retrieval:** SQLite FTS5 (BM25) over `corpus/*.md`, built in memory on cold start. No vector DB. Measured 2026-09-27 on identical passages and the 27-quote gold set: BM25 R@10 74.1%, MiniLM dense 48.1%, BM25+MiniLM RRF 66.7% (85.2% at R@20). BM25 misses only lay-language queries ("resumes", "chatbot"). The gold set is too small to decide on; grow it first (Task 12). If embeddings are added (Task 19), use one provider embeddings API call plus numpy cosine over a committed `.npy` file: no Chroma, no torch.
- **Stateless:** uploads are converted in memory and never stored. No accounts.
- **LLM:** DeepSeek via the OpenAI-compatible API (`LLM_MODEL`, `LLM_BASE_URL` overridable).
- **Corpus as Markdown:** `# Title` first line, `##` per article/section. Downloaded originals (PDFs) live in `corpus/src/`; `scripts/build_corpus.py` generates `corpus/*.md` from them deterministically, so offsets and IDs never depend on hand edits.
- **Audience:** portfolio demo now, built to become a self-serve tool for businesses.
- **Access:** shared passcode (`ACCESS_CODE` env, `x-access-code` header) + 4 MB upload cap.
- **Language:** output follows the case documents' language; law quotes stay verbatim (English).
- **UI:** single static `public/index.html`; spinner + timer while running.
- **Evals:** `evals/retrieval.py` (offline recall) and `evals/cases.py` (live, 6 cases → grow to ~20). No mock mode in `src/`.

## Task List

### Phase 1: Cleanup and core rewrite — DONE
- [x] Task 1: Convert corpus to Markdown (AI Act from EUR-Lex HTML; two guideline PDFs)
- [x] Task 2: Ingest → passages; FTS5 law search; Assessor/Verifier/revision; FastAPI endpoint
- [x] Task 3: Offline tests (11) + evals; delete ~6,000 lines of old modules, mocks, docs, demo_cases

### Checkpoint: Phase 1
- [x] `python -m pytest -q` passes (11)
- [x] `python -m evals.retrieval` ≥ 70% recall@10
- [ ] Human review of the patch

### Phase 1b: Redesign — citations, corpus, report (details and acceptance criteria in `tasks/todo.md`)
Setup: `python -m pip install -r requirements.txt pytest httpx` into `.venv`. Keep tests offline; this machine has ~1.5 GB free virtual memory, so do not load local embedding models.
- [x] Task 12: Grow the retrieval gold set to ≥ 60 hand-reviewed quotes, lay/legal split (baseline before corpus changes)
  - Done 2026-09-27: 58 queries, 71 quotes (22 from the guidelines); style derived from the query text (cites Article/Annex/Recital → legal). Baseline R@10 70.4% (lay 54.3%, legal 100%), R@5 69.0%. Floors in `tests/test_law.py`: 70 / 50 / 95.
- [x] Task 13: `scripts/build_corpus.py` — guideline PDFs → sectioned Markdown, TOC stripped
  - Done 2026-09-27: 109 + 12 headings, in document order; 99.6% of guideline passages carry a section label; no dot-leader lines; rebuild is byte-identical. R@10 70.4% → 74.6% (lay 60.9%, legal 100%); guideline quotes 16 → 18 of 22 at R@10. R@5 69.0% → 67.6% (one AI Act quote moved from top 5 to top 10). Footnotes stay in the text.
- [x] Checkpoint A: corpus (15 tests pass, `compileall` clean)
  - Task 19's trigger condition is met on the benchmark (lay R@10 60.9% < 70%). Mitigated in practice because the Assessor searches with legal terms (legal R@10 100%); decide after Task 4 whether to start Task 19.
- [x] Task 14: Stable heading-derived passage IDs
  - Done 2026-09-28: `src/law.py::heading_key`; 1,172 passages under 427 keys, one heading per key; recall unchanged.
- [x] Task 15: Exact source spans on verified references
  - Done 2026-09-28: quote check moved to `src/citations.py`; passages are exact source slices; spans verified for all 71 gold quotes. 21 tests pass.
- [x] Task 16: Separate input errors (422) from model errors (502); sync endpoint; client timeout
  - Done 2026-09-28: `CaseError`; 120 s timeout, 2 retries; bad tool args and unusable Verifier replies fail soft (verdicts `insufficient`).
- [x] Task 17: Deterministic server-side report; UI renders it
  - Done 2026-09-28: `src/report.py`; UI highlights exact spans (code-point safe). Render smoke-tested in Node with a stub DOM; not yet checked in a real browser at phone width. 26 tests pass.
- [ ] Checkpoint B: human review, then Task 4 (live run)
- [x] Task 18 (before Task 5): AI Act source → Markdown in the build script
  - Done 2026-09-28: built from the EUR-Lex HTML (restored to `corpus/src/`); the OJ PDF separates recital numbers from their text, so it is kept for reference only. Same 306 headings; 99.0% of previous passage text unchanged (differences: Annex I/VII point markers now stay with their text); recall unchanged; 28 tests pass.
- [ ] Task 19 (conditional): API-embedding hybrid retrieval, only if its trigger fires

### Phase 2: First live run (needs DEEPSEEK_API_KEY)
- [x] Task 4: Run `python -m evals.cases`; fix prompt/schema problems it surfaces.
  - Done 2026-09-28 (DeepSeek `deepseek-chat`, after Tasks 12–18): 6/6 PASS; 105/105 claims verified supported; 4–8 LLM calls and 21–60 s per case. No prompt changes needed. Caveat: the Verifier is the same model as the Assessor, so 'supported' is self-review, not independent legal review.
    ```
    hr_screening                high_risk     gpai=unclear 27/27 revised calls=8 60s PASS
    customer_chatbot            limited_risk  gpai=yes     16/16 revised calls=7 37s PASS
    workplace_emotion_detection prohibited    gpai=unclear 15/15         calls=5 21s PASS
    spam_filter                 minimal_risk  gpai=no      16/16 revised calls=7 41s PASS
    llm_report_generator        unclear       gpai=yes     16/16         calls=4 24s PASS
    predictive_maintenance      minimal_risk  gpai=no      15/15 revised calls=8 44s PASS
    ```
  - Acceptance: all 6 cases complete without errors; ≥ 5/6 PASS; ≥ 80% of claims verified as supported.
  - Verify: paste the eval table in the PR.
  - Files: `src/agents.py` (prompts only). Scope: S.

### Phase 3: Corpus update (Q7b)
- [ ] Task 5 (blocked: EUR-Lex refuses scripted downloads; owner: user downloads the HTML): Add the Digital Omnibus on AI — Regulation (EU) 2026/1744, OJ 24.7.2026, in force 27.7.2026 — (Council final approval 29 June 2026) — ideally the consolidated AI Act text from EUR-Lex once published; otherwise the amending regulation as its own `.md`.
  - Acceptance: corpus states the new high-risk dates (2 Dec 2027 / 2 Aug 2028) and the new prohibition; a gold question for each.
- [x] Task 6: Add final Article 50 transparency guidelines (20 July 2026), draft high-risk classification guidelines (19 May 2026, label as DRAFT in the title), GPAI guidelines (July 2025).
  - Acceptance: each file has a `# Title (status, date)` line; ≥ 2 new gold questions per document; recall@10 stays ≥ 70%.
  - Verify: `python -m evals.retrieval`, `python -m pytest -q`.
  - Done 2026-09-28: Art. 50 (C(2026) 5054), GPAI (C(2025) 5045) and the three-part high-risk draft (19.5.2026, titled DRAFT) built from the Commission's PDFs; 10 new gold questions (11 quotes). Adding ~1,000 guidance passages dropped R@10 to 62% (commentary outranked the Act), so `law.search` now alternates Act and guidance hits: R@10 75.6% (lay 64.8%, legal 96.4%), R@5 64.6%. Build fixes: 'Table of Contents' TOCs, headings wrapped after a comma, stray paragraph numbers before headings, 250-char heading limit.
- [x] Task 7: Grow `evals/cases.json` to ~20 cases (education, credit scoring, biometric ID, deepfake/marketing content, medical device component, a clearly non-AI rules engine).
  - 2026-09-28: 14 cases added (20 total); `evals/cases.py` also checks optional `expected_ai_system` / `expected_role`. First full run: 16/20 — tiers 20/20 and AI-system 20/20 correct; all 4 misses were role=`unclear` because the prompt never defined the roles. Fix: Assessor rule 8 gives the Article 3(3)/(4) provider/deployer definitions. Two fixtures corrected honestly: `life_insurance_pricing` (model built "under contract" for the insurer — Art. 3(3) makes the role depend on facts not given; expectation removed, role added to questions) and `customer_call_emotion` (never said who develops VoicePulse; vendor added). After the fix: 19/20, every claim verified supported, 15–59 s and 4–9 calls per case. `customer_call_emotion` then passed 2 of 3 reruns: one run returned limited_risk instead of high_risk (Annex III 1(c)) — run-to-run variance at temperature 0.1, not yet addressed.

### Checkpoint: Phase 3
- [ ] Retrieval recall and case evals re-run and recorded

### Phase 4: Deploy API
- [ ] Task 8: Deploy `api/index.py` to Vercel; set `DEEPSEEK_API_KEY`.
  - Acceptance: cold start < 5 s; one real assessment completes within `maxDuration`; bundle under the Python size limit.
- [x] Task 9: Passcode + 4 MB upload cap (401 / 413), covered by `tests/test_api.py`.

### Phase 5: UI
- [x] Task 10: `public/index.html` (no build, no deps): upload page + results view (risk tier, requirements table, claims with expandable quoted sources, open questions).
- [x] Task 11: Spinner with elapsed timer. Switch to streamed stage events if real runs regularly exceed ~60 s.

## Risks and Mitigations
| Risk | Impact | Mitigation |
|---|---|---|
| Corpus predates the Digital Omnibus (wrong deadlines, missing prohibition) | High | Task 5 before any public use |
| No live evaluation yet; prompts untested against DeepSeek | High | Task 4 first |
| Run time exceeds function duration | Med | Cap search rounds (6), measure in Task 8, stream in Task 11 |
| Public endpoint spends the API key | Med | Passcode (Task 9); add rate limiting if the code leaks |
| BM25 misses paraphrased questions | Low-Med | Assessor writes its own legal-term queries; lay/legal recall split (Task 12); embeddings only on Task 19's trigger |
| PDF heading detection is brittle (running headers, footnotes, numbered lists mistaken for headings) | Med | Prohibited-practices headings come from its own table of contents; AI Act output is checked against the current 306-heading list (Task 18) |
| Gold set becomes circular (quotes picked from what BM25 returns) | Med | Pick quotes by reading the provision the question needs, before running search |
| Offset mapping bugs under quote normalisation (case, curly quotes, dashes, line breaks) | Med | Property tests: every kept span re-normalises to the quote and equals the source slice (Task 15) |
| Branch has diverged from `main` (`aaf0034` replaced the AI Act HTML with the OJ PDF and committed `ponytail-3-ui.patch`) | Low | Merge `main` at the start of Task 18; move the PDF to `corpus/src/` and drop the patch files |

## Open Questions
- ~~Task 18 source~~: decided 2026-09-28 — EUR-Lex HTML; the OJ PDF's layout detaches recital numbers from their text.
- Task 19: which embeddings provider (DeepSeek has none; needs e.g. an OpenAI, Voyage, Mistral or Gemini key)? Only matters if the trigger fires.
- Case passage IDs stay per-request (`doc1:3`) because uploads are never stored. OK?
- Next.js only when accounts, multiple pages or saved history are needed.
