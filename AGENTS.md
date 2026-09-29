# Contributor instructions

- Pipeline: `src/ingest.py` (files → Markdown → passages) → `src/agents.py` (Assessor with `search_law` tool → verbatim-quote check → Verifier → at most one revision). `src/law.py` searches `corpus/*.md`. `api/index.py` is the HTTP entry point.
- Every claim must quote a passage the model was shown; facts quote case documents, legal claims quote the corpus. Keep that check deterministic (`src/citations.py`).
- Quote offsets are computed by `check_references`, never taken from the model: `ref.start/end` index the passage text, and every passage is an exact slice `source[start:end]`.
- Corpus passage ids are `{stem}/{heading key}/{n}` (e.g. `eu_ai_act/art-50/1`) so saved citations survive corpus edits. Changing `heading_key` renames ids; treat it as a breaking change.
- `src/report.py::build_report` is the deterministic Presenter: pure, no LLM calls, no I/O, no new conclusions (only result fields and fixed templates). The UI renders `report`, not the raw assessment.
- Errors: `CaseError` (bad input) → 422; model/provider failures → 502 with a plain message. An unusable Verifier reply makes every verdict `insufficient`; never treat a missing verdict as supported.
- Never put eval case names, fixtures or mock answers in `src/`. Tests fake `src.agents.chat` with monkeypatch.
- `main` is the deployable app only. Tests (`tests/`), evals (`evals/`), corpus sources (`corpus/src/`) and `scripts/build_corpus.py` live on the `corpus-build` branch (see README). Test a change by merging its branch into `corpus-build`; open PRs to `main` from the change branch, never from `corpus-build`. Never hand-edit the generated `corpus/*.md`.
- Gold quotes in `evals/retrieval_gold.json` are picked by reading the provision a question needs, never from search output. Do not lower the recall floors in `tests/test_law.py` to make a change pass.
- Before merging agent or prompt changes, run `python -m evals.cases` (live API) and report the table.
- Never commit `.env`.
