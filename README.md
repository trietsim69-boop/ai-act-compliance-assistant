# AI Act Compliance Assistant

Upload documents describing one AI use case and get a preliminary, citation-backed assessment against the EU AI Act and Commission guidance: whether it is an AI system, its risk tier, your role, which obligations apply, whether your documents show they are met, and what information is missing. Every statement quotes its source, and every quote is checked.

**Live:** https://ai-act-compliance-assistant.vercel.app (access code required; ask the maintainer).

Decision support only. It is not legal advice and does not certify compliance.

## How it works

1. **Ingest.** Uploads (PDF, DOCX, PPTX, HTML, CSV, TXT, MD; 4 MB total) and/or a free-text description are converted to Markdown with MarkItDown and split into citable passages (`doc1:3`). Scans without a text layer are rejected; run OCR first. Nothing is stored.
2. **Assessor agent.** Reads the case and calls a `search_law` tool as often as it needs (SQLite FTS5/BM25 over `corpus/*.md`; everyday words are expanded with the Act's vocabulary, Act and guidance hits alternate, and provisions named in the query come first). It returns structured JSON: claims with verbatim quotes, obligations (met / gap / unclear / not applicable) and open questions.
3. **Quote check.** Deterministic: every quote must appear verbatim in a passage the model was shown; facts must quote the case, legal claims must quote the law. Exact offsets are computed here, never taken from the model.
4. **Verifier agent.** Judges each claim against its quoted passages: supported, contradicted or insufficient. A missing or unusable verdict counts as insufficient.
5. **One revision.** If a quote or verdict failed, the Assessor gets the feedback once and the result is checked again.
6. **Report.** `src/report.py` turns the result into display sections and warnings without any model call; the UI renders it, with the exact quoted span highlighted in each source.

The model is DeepSeek (`deepseek-chat`) through its OpenAI-compatible API; any compatible endpoint works via `LLM_BASE_URL` / `LLM_MODEL`.

## Built-in corpus

- Regulation (EU) 2024/1689 (AI Act), consolidated text of 27.7.2026 including the Digital Omnibus, Regulation (EU) 2026/1744 (recitals from the original Official Journal text, which consolidations omit)
- Commission guidelines: AI system definition; prohibited AI practices; general-purpose AI models; Article 50 transparency obligations
- Draft Commission guidelines on high-risk classification (consultation draft, May 2026, labelled DRAFT in citations)

Guidance is non-binding; the UI labels every citation as your document, the AI Act, guidance or draft guidance.

## Quality (measured 2026-10-01)

- **Retrieval in the live app:** in 20 reference cases, the Assessor's own searches found the key provision each case needed in 19 of 20 (95%).
- **Retrieval benchmark:** on 86 hand-reviewed gold quotes, search returns the right passage in its top 12 (what the Assessor sees per search) 80.2% of the time: 96.6% for queries in legal terms, 71.9% for everyday-language queries. Both sets were written by the developer, so results on independent data may be lower.
- **Live assessments:** 20 of 20 reference cases correct on risk tier, AI-system status, GPAI involvement and role in the latest run (earlier runs: 18–19 of 20; the misses are run-to-run variance), with nearly every claim verified as supported.

## Known limitations

- No follow-up chat yet: the UI's "Answer Questions and Re-run" starts a fresh assessment with your answers added.
- Model output varies between runs; borderline cases can change tier or role.
- Uploaded text reaches the model directly; a document could try to steer the assessment (quotes cannot be invented, conclusions can be nudged).
- Access is protected by one shared code with no rate limit.

## Run locally

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                              # add DEEPSEEK_API_KEY; ACCESS_CODE optional
uvicorn api.index:app --reload                     # UI at http://localhost:8000
python -m src.agents path/to/case.pdf other.docx   # or: print the JSON result for files
```

**API:** `POST /api/assess` (multipart `files[]` and/or `description`, header `x-access-code` when `ACCESS_CODE` is set) returns the raw result plus `report`. Errors: 401 access code, 413 uploads over 4 MB, 422 no readable input or over 100,000 characters, 502 the model failed (safe to retry).

**UI:** React + Vite in `web/`; `npm run build` rewrites `public/index.html`, one self-contained file. See [web/README.md](web/README.md).

## Test and evaluate

```bash
pip install pytest httpx
python -m pytest -q          # offline, no API key
python -m evals.retrieval    # corpus search recall@8 on the gold quotes, split lay/legal
python -m evals.cases        # live: 20 reference cases through DeepSeek (costs API credit)
```

`evals.cases` also reports `saw`: whether the Assessor's own searches ever returned each case's `must_see` provision (e.g. Annex III point 4(a) for HR screening), and logs every query to `data/eval_queries.jsonl`.

**Held-out set:** to measure retrieval without tuning bias, have someone who has not worked on the ranking write questions in the same format as `evals/retrieval_gold.json` (query, expected source and verbatim quote) into `evals/retrieval_heldout.json`, then run `python -m evals.retrieval evals/retrieval_heldout.json`. Never tune against it.

## Deploy (Vercel)

The Vercel project is connected to this GitHub repository: every push to `main` deploys to production, and every other branch gets a preview URL. `vercel.json` deploys `api/index.py` as a Python function with `corpus/*.md` bundled; Vercel serves `public/` statically. `.vercelignore` keeps `.env`, local data and dev-only files out of uploads.

```bash
vercel deploy                    # manual preview deployment from your working tree
```

Set `DEEPSEEK_API_KEY` and `ACCESS_CODE` for Production and Preview in the Vercel project (`vercel env add`). There is no database: the corpus index is built in memory on cold start and uploads are never stored.

## Repository

| Path | Contents |
|---|---|
| `src/` | Pipeline: `ingest.py`, `law.py` (search), `agents.py` (Assessor, Verifier), `citations.py` (quote check), `report.py`, `config.py` |
| `api/index.py` | FastAPI endpoint; also serves the UI locally |
| `public/index.html` | Built UI (generated from `web/`) |
| `web/` | UI source |
| `corpus/` | Generated Markdown corpus |
| `tests/`, `evals/` | Offline tests; retrieval gold set and live reference cases |

**Corpus updates** happen on the `corpus-build` branch, which alone holds the downloaded sources and `scripts/build_corpus.py`:

```bash
git switch corpus-build && git merge main
# add the source to corpus/src/ and its title to TITLES in scripts/build_corpus.py
python -m scripts.build_corpus && python -m pytest -q && python -m evals.retrieval
git add corpus && git commit -m "corpus: ..."
git switch -c corpus-update main && git checkout corpus-build -- "corpus/*.md"   # commit, push, open a PR
```

## License

See [LICENSE](LICENSE).
