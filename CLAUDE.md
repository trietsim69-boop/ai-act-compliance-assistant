# Contributor instructions

Setup, commands and the corpus-update recipe are in [README.md](README.md).

## Pipeline invariants

- Pipeline: `src/ingest.py` (files → Markdown → passages) → `src/agents.py` (Assessor with `search_law` tool → verbatim-quote check → Verifier → at most one revision) → `src/report.py`. `src/law.py` searches `corpus/*.md`. `api/index.py` is the HTTP entry point and serves the UI: `public/index.html`, built from `web/` with `npm run build` (commit source and built file together).
- Every claim must quote a passage the model was shown; facts quote case documents, legal claims quote the corpus. Keep that check deterministic (`src/citations.py`).
- Quote offsets are computed by `check_references`, never taken from the model: `ref.start/end` index the passage text, and every passage is an exact slice `source[start:end]`.
- Corpus passage ids are `{stem}/{heading key}/{n}` (e.g. `eu_ai_act/art-50/1`, `art-4a` for lettered articles) so saved citations survive corpus edits. Changing `heading_key` renames ids; treat it as a breaking change.
- `law.search` alternates Act and guidance hits, and a provision named in the query ("Article 53(1)(b)") leads the Act results. Both exist because commentary otherwise outranks the law it discusses; measure any ranking change with `evals.retrieval`.
- `src/report.py::build_report` is the deterministic Presenter: pure, no LLM calls, no I/O, no new conclusions (only result fields and fixed templates). The UI renders `report`, not the raw assessment; `build_report`'s return value is the UI contract.
- Errors: `CaseError` (bad input) → 422; model/provider failures → 502 with a plain message. An unusable Verifier reply makes every verdict `insufficient`; a missing verdict never counts as supported.
- Keep eval case names, fixtures and mock answers out of `src/`. Tests fake `src.agents.chat` with monkeypatch.

## Corpus and evaluation

- `corpus/*.md` is generated on the `corpus-build` branch, which alone holds the downloaded sources (`corpus/src/`) and `scripts/build_corpus.py`. The AI Act is the consolidated EUR-Lex text of 27.7.2026 (incl. the Digital Omnibus, Regulation (EU) 2026/1744) with recitals from the original OJ; guidelines are Commission PDFs. Copy regenerated files into `main`; hand-edits are overwritten by the next build.
- Gold quotes in `evals/retrieval_gold.json` are picked by reading the provision a question needs, never from search output. When the law changes, requote from the new text. The recall floors in `tests/test_law.py` stay where they are; fix the ranking instead.
- `python -m pytest -q` and `python -m evals.retrieval` are offline and free. `python -m evals.cases` calls the live DeepSeek API and costs money: run it before merging agent or prompt changes, or when asked, and report the table.

## Git workflow

- Commits and PRs belong to the user: author Triet Le, plain one-line messages, no `Co-Authored-By` trailer and no "Generated with …" line.
- By default a change goes on its own branch and reaches `main` as a GitHub PR the user merges; commit directly on `main` when the user asks for it. UI work lives on `frontend`; corpus rebuilds on `corpus-build`. Merge `main` into `corpus-build`, never the reverse (it would bring the sources into `main`).
- The Windows checkout uses `core.autocrlf=true`, so files written with LF show as modified. Judge real changes with `git diff`, which normalises line endings.
- `.env` stays local; it holds the API keys.
