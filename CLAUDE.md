# Contributor instructions

Setup, commands and the corpus-update recipe are in [README.md](README.md).

Stack: Python 3.13, FastAPI, pydantic, the OpenAI SDK pointed at DeepSeek (`deepseek-chat`), MarkItDown for uploads, SQLite FTS5 (BM25) for search; UI in React 19 + Vite (`web/`). No database, no vector store, no server-side state.

Decided, with measurements, so not to redo without new evidence: a vector store/embeddings (2026-10-01: MiniLM hybrid search added at most +1.2 points recall@12 over BM25 + word map, while the Assessor already translates business language into legal queries); the old Chroma pipeline (replaced by the ponytail rewrite; it scored lower).

## Pipeline invariants

- Pipeline: `src/ingest.py` (files → Markdown → passages) → `src/agents.py` (Assessor with `search_law` tool → verbatim-quote check → Verifier → at most one revision) → `src/report.py`. `src/law.py` searches `corpus/*.md`. `api/index.py` is the HTTP entry point and serves the UI: `public/index.html`, built from `web/` with `npm run build` (commit source and built file together).
- Every claim must quote a passage the model was shown; facts quote case documents, legal claims quote the corpus. Keep that check deterministic (`src/citations.py`).
- Quote offsets are computed by `check_references`, never taken from the model: `ref.start/end` index the passage text, and every passage is an exact slice `source[start:end]`.
- Corpus passage ids are `{stem}/{heading key}/{n}` (e.g. `eu_ai_act/art-50/1`, `art-4a` for lettered articles) so saved citations survive corpus edits. Changing `heading_key` renames ids; treat it as a breaking change.
- `law.search` expands everyday words with the Act's vocabulary (`_PLAIN_TO_ACT`, hand-written: add general translations, never phrases copied from gold answers), alternates Act and guidance hits, and puts a provision named in the query ("Article 53(1)(b)") first among the Act results. The alternation and citation boost exist because commentary otherwise outranks the law it discusses. `law.K` (12) is both the passages per search and the k that recall is reported at; measure any ranking change with `evals.retrieval`.
- `src/report.py::build_report` is the deterministic Presenter: pure, no LLM calls, no I/O, no new conclusions (only result fields and fixed templates). The UI renders `report`, not the raw assessment; `build_report`'s return value is the UI contract.
- Errors: `CaseError` (bad input) → 422; model/provider failures → 502 with a plain message. An unusable Verifier reply makes every verdict `insufficient`; a missing verdict never counts as supported.
- Keep eval case names, fixtures and mock answers out of `src/`. Tests fake `src.agents.chat` with monkeypatch.

## Corpus and evaluation

- `corpus/*.md` is generated on the `corpus-build` branch, which alone holds the downloaded sources (`corpus/src/`) and `scripts/build_corpus.py`. The AI Act is the consolidated EUR-Lex text of 27.7.2026 (incl. the Digital Omnibus, Regulation (EU) 2026/1744) with recitals from the original OJ; guidelines are Commission PDFs. Copy regenerated files into `main`; hand-edits are overwritten by the next build.
- Gold quotes in `evals/retrieval_gold.json` are picked by reading the provision a question needs, never from search output. When the law changes, requote from the new text. The recall floors in `tests/test_law.py` stay where they are; fix the ranking instead.
- `python -m pytest -q` and `python -m evals.retrieval` are offline and free. `python -m evals.cases` calls the live DeepSeek API and costs money: run it before merging agent or prompt changes, or when asked, and report the table. `evals.cases` also reports `saw`: whether the Assessor's own searches returned each case's `must_see` provision, and logs every query to `data/eval_queries.jsonl`.

## Git workflow

- Commits and PRs belong to the user: author Triet Le, plain one-line messages, no `Co-Authored-By` trailer and no "Generated with …" line.
- By default a change goes on its own branch and reaches `main` as a GitHub PR the user merges; commit directly on `main` when the user asks for it. UI work lives on `frontend`; corpus rebuilds on `corpus-build`. Merge `main` into `corpus-build`, never the reverse (it would bring the sources into `main`).
- The Windows checkout uses `core.autocrlf=true`, so files written with LF show as modified. Judge real changes with `git diff`, which normalises line endings.
- `.env` stays local; it holds the API keys.
- History starts at the ponytail rewrite (2026-09-28). The full earlier history is the archived repo `ai-act-compliance-assistant-history` (git remote `history`); look there for the old Chroma pipeline, never merge it back.

## Deployment

- Production: https://ai-act-compliance-assistant.vercel.app (Vercel project `ai-act-compliance-assistant`, connected to the GitHub repo since 2026-10-04). Every push to `main` deploys to production, so pushing or merging to `main` is a release; every other branch gets a preview URL. `vercel deploy` still makes a manual preview. `DEEPSEEK_API_KEY` and `ACCESS_CODE` are set in Vercel for Production and Preview; never write the access code into the repo.
- `.vercelignore` keeps `.env`, `data/` and dev-only folders out of CLI uploads (they ignore `.gitignore`).
