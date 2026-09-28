# Phase 1b: Redesign — citations, corpus, report

Index and decisions: [plan.md](plan.md). Tasks run in order unless marked parallel.

Standard verification (every task):
- `python -m pytest -q`
- `python -m compileall -q src api evals scripts`
- `python -m evals.retrieval` — recall must not drop below the Task 12 baseline

```
12 gold set ──► 13 guideline build ──► 14 stable IDs ──► 15 exact spans ──► 17 report
                        │
                        └──► 18 AI Act build (before Task 5)
16 errors/endpoint: independent, can run parallel to 13–15
19 embeddings: conditional on Task 4 / Task 12 results
```

---

## Task 12: Grow the retrieval gold set (baseline)

**Description:** The gold set has 27 quotes, so one quote moves recall by 3.7 points; that is too coarse to judge corpus or retrieval changes. Grow it before anything touches the corpus, and split recall by query style so lay-language misses are visible.

**Acceptance criteria:**
- [x] ≥ 45 queries and ≥ 60 expected quotes, with ≥ 5 quotes from each guideline document. Quotes are picked by reading the provision the question needs, not from search output.
- [x] Style is derived from the query text (cites Article/Annex/Recital → `legal`, else `lay`), each ≥ 1/3 of queries (22 legal / 36 lay); `evals.retrieval` prints recall@5/@10 overall and per style.
- [x] A test asserts every gold quote appears verbatim (whitespace-normalised) in some corpus passage. The recall threshold in `tests/test_law.py` becomes the measured baseline rounded down to 5 points, and the baseline numbers are recorded in `plan.md`.

**Verification:**
- [x] Tests pass: `python -m pytest tests/test_law.py -q`
- [ ] Manual check: spot-read 10 random gold entries against the source provision

**Dependencies:** None
**Files likely touched:** `evals/retrieval_gold.json`, `evals/retrieval.py`, `tests/test_law.py`, `tasks/plan.md`
**Estimated scope:** S

---

## Task 13: Guideline PDFs → sectioned Markdown (`scripts/build_corpus.py`)

**Description:** Both guideline files are raw PDF dumps: all 558 guideline passages are labelled only with the document title, and the prohibited-practices table of contents (104 dot-leader lines) is indexed as content. Restore the downloaded PDFs to `corpus/src/` (from commit `3f5c3ea`) and add a deterministic build script that converts them with MarkItDown, drops the TOC and page furniture, and emits `## <number> <title>` headings.

**Acceptance criteria:**
- [x] Prohibited-practices guidelines: every TOC entry becomes exactly one `##` heading, in body order, and no dot-leader lines remain. Definition guidelines (no TOC): short lines matching `^\d+\. [A-Z]` become headings.
- [x] ≥ 95% of guideline passages have a label other than the document title. The first line is `# Title (status, date)`.
- [x] Re-running the script produces no `git diff`. Guideline recall on the Task 12 gold set does not drop. `eu_ai_act.md` is untouched (Task 18).

**Verification:**
- [x] Tests pass: `python -m pytest tests/test_build_corpus.py -q` (TOC-driven heading promotion on a small synthetic text)
- [ ] Manual check: skim headings of both generated files against the PDFs' section list

**Dependencies:** Task 12
**Files likely touched:** `scripts/build_corpus.py`, `corpus/src/*.pdf`, `corpus/guidelines_*.md`, `tests/test_build_corpus.py`, `README.md`
**Estimated scope:** M

## Checkpoint A: corpus
- [x] Standard verification passes; per-style recall recorded
- [x] Guideline citations show section numbers in the UI's source labels

---

## Task 14: Stable heading-derived passage IDs

**Description:** Corpus passage IDs are ordinals (`eu_ai_act:412`), so any corpus edit renumbers every later passage and breaks citations in saved results. Derive them from the heading instead, as `{stem}/{key}/{k}` where `k` is the passage's position within that heading.

**Acceptance criteria:**
- [x] Keys: `Article 50` → `art-50`, `Recital 12` → `rec-12`, `Annex III` → `anx-III`, guideline section `2.2` → `s-2.2`, anything else → a slug of the heading. IDs are unique across the corpus (test).
- [x] Editing text under one heading leaves the IDs under every other heading unchanged (test on a synthetic document).
- [x] Case passages keep per-request IDs (`doc1:3`). The Assessor prompt's ID examples show both forms.

**Verification:**
- [x] Tests pass: `python -m pytest tests/test_ingest.py tests/test_law.py tests/test_agents.py -q`

**Dependencies:** Task 13 (guideline headings must exist first)
**Files likely touched:** `src/ingest.py`, `src/agents.py`, `tests/test_ingest.py`, `tests/test_law.py`
**Estimated scope:** S

---

## Task 15: Exact source spans on verified references

**Description:** References currently carry only a quote that matched after normalisation. Make every passage an exact slice of its source Markdown, with `start`/`end` and no whitespace flattening, and have the quote check compute the span of each kept quote. The model never supplies offsets.

**Acceptance criteria:**
- [x] For every passage, `source[p.start:p.end] == p.text`. For every kept reference, `normalise(p.text[r.start:r.end]) == normalise(r.quote)`. Property tests cover case differences, curly quotes, dash variants and line breaks inside a quote; a repeated quote maps to its first occurrence.
- [x] `start`/`end` are absent from the JSON schema shown to the model (test on `ASSESSOR_PROMPT`) and present on every reference in the result.
- [x] `AGENTS.md` records the invariant: offsets are computed by the checker, never by the model.

**Verification:**
- [x] Tests pass: `python -m pytest tests/test_agents.py tests/test_ingest.py -q`
- [x] `python -m evals.retrieval` unchanged (passage text change must not move BM25)

**Dependencies:** Task 14
**Files likely touched:** `src/ingest.py`, `src/agents.py`, `tests/test_agents.py`, `tests/test_ingest.py`, `AGENTS.md`
**Estimated scope:** M

---

## Task 16: Input errors vs model errors; sync endpoint; client timeout (parallel to 13–15)

**Description:** Pydantic `ValidationError` and `JSONDecodeError` subclass `ValueError`, so a malformed model reply currently returns HTTP 422, which blames the user, with pydantic internals in the message. Provider errors return a bare 500. `async def assess` also blocks the event loop for minutes, and the OpenAI client has its 600-second default timeout.

**Acceptance criteria:**
- [x] Input problems raise a dedicated `CaseError` → 422 `{error, file_errors}`. Model/provider failures (invalid JSON after the one repair, `openai.OpenAIError`) → 502 `{error, file_errors}` with a plain message and no pydantic text. Tests cover each case.
- [x] Malformed tool-call arguments produce a tool reply ("invalid arguments") and the loop continues (test).
- [x] The endpoint is a sync `def` (FastAPI runs it in a thread pool). One module-level OpenAI client uses an explicit `timeout` and `max_retries=2`.

**Verification:**
- [x] Tests pass: `python -m pytest tests/test_api.py tests/test_agents.py -q`
- [ ] Manual check: `uvicorn api.index:app`; the UI page still loads while an assessment request is pending

**Dependencies:** None
**Files likely touched:** `src/agents.py`, `api/index.py`, `tests/test_api.py`, `tests/test_agents.py`
**Estimated scope:** M

---

## Task 17: Deterministic server-side report; UI renders it

**Description:** Reinstate the deterministic Presenter as a pure function. `build_report(result, file_errors)` turns the assessment into report sections: overview, obligations, claims with verdicts and exact quoted spans, questions, warnings, and disclaimer. The API returns it and the UI renders only it.

**Acceptance criteria:**
- [x] Pure function, no I/O and no LLM: a test with `agents.chat` patched to raise still builds the report. Every value comes from the result or a fixed template string, so the report adds no legal conclusions.
- [x] Warnings, each tested: skipped file, remaining reference problems, claim contradicted/insufficient, claim with no verified reference, low confidence, revision used. A requirement marked `met` whose claims are not all `supported` is flagged `unverified`, and its status is left unchanged.
- [x] `/api/assess` returns `report` next to the raw result; `public/index.html` renders `report` and highlights the exact span inside each expanded source; `AGENTS.md` records the Presenter invariant.

**Verification:**
- [x] Tests pass: `python -m pytest tests/test_report.py tests/test_api.py -q`
- [ ] Manual check: open the UI with a saved result JSON (stubbed `assess_case`) at phone and desktop width

**Dependencies:** Task 15 (spans), Task 16 (response shape)
**Files likely touched:** `src/report.py`, `api/index.py`, `public/index.html`, `tests/test_report.py`, `AGENTS.md`
**Estimated scope:** M

## Checkpoint B: before the live run
- [x] Standard verification passes
- [x] Offline end-to-end: `TestClient` POST with a demo case and scripted `chat` → 200 with report, spans and stable IDs
- [ ] Human review of Phase 1b, then run Task 4 (`python -m evals.cases`, live)

---

## Task 18 (before Task 5): AI Act PDF → Markdown in the build script

**Description:** `main` (`aaf0034`) replaced the EUR-Lex HTML with the Official Journal PDF, but `corpus/eu_ai_act.md` was generated from the HTML by a converter that no longer exists. The Digital Omnibus text (Task 5) will need the same conversion. Merge `main`, move the PDF to `corpus/src/`, and teach the build script to emit the current heading format.

**Acceptance criteria:**
- [ ] Output headings equal the current file's 306 headings (`## Recital N`, `## Chapter X › Article N — Title`, `## Annex X — Title`), checked by a test against a committed heading list.
- [ ] ≥ 98% of current passages' text is found, whitespace-normalised, in the new output. Running headers/footers, page numbers and ELI lines are removed.
- [ ] Gold recall (Task 12) does not drop. Re-running produces no diff.

**Verification:**
- [ ] Tests pass: `python -m pytest tests/test_build_corpus.py tests/test_law.py -q`
- [ ] Manual check: diff the old and new `eu_ai_act.md` for Articles 3, 5, 6, 50 and Annex III

**Dependencies:** Task 13. **Open question:** PDF or EUR-Lex HTML as the source (see `plan.md`).
**Files likely touched:** `scripts/build_corpus.py`, `corpus/src/EU_AI_Act.pdf`, `corpus/eu_ai_act.md`, `tests/test_build_corpus.py`
**Estimated scope:** M

---

## Task 19 (conditional): API-embedding hybrid retrieval

**Trigger (do not start otherwise):** Task 4 shows a claim failing because the needed provision was never retrieved, or Task 12's lay-query recall@10 is below 70%.

**Description:** At build time, embed all corpus passages with one batched provider API call into `corpus/vectors.npy`. At query time, embed the query with one API call, take cosine top-k with numpy, and fuse with BM25 by reciprocal-rank fusion (RRF). No Chroma, no torch.

**Acceptance criteria:**
- [ ] Overall recall@10 on the Task 12 gold set is ≥ BM25 + 5 points, and legal-style recall does not drop.
- [ ] Offline tests stub the embedding call. A missing key falls back to BM25 and says so in the result.
- [ ] `vectors.npy` is regenerated by the build script and checked against the passage IDs, so stale vectors fail loudly.

**Verification:**
- [x] Tests pass: `python -m pytest tests/test_law.py -q`
- [ ] `python -m evals.retrieval` with and without the key

**Dependencies:** Task 12, Task 4. **Open question:** embedding provider.
**Files likely touched:** `scripts/build_corpus.py`, `src/law.py`, `src/config.py`, `tests/test_law.py`, `requirements.txt`
**Estimated scope:** M
