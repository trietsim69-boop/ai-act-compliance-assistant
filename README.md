# AI Act Compliance Assistant

Upload documents describing one AI use case and get a preliminary, citation-backed assessment against the EU AI Act and Commission guidance: whether it is an AI system, its risk tier, your role, which obligations apply, whether your documents show they are met, and what information is missing. Every statement quotes its source, and every quote is checked.

**Live:** https://ai-act-compliance-assistant.vercel.app (access code required; ask the maintainer).

Decision support only. It is not legal advice and does not certify compliance.

## How it works

1. **Ingest.** Uploads (PDF, DOCX, PPTX, HTML, CSV, TXT, MD; 4 MB total) and/or a free-text description are converted to Markdown with MarkItDown and split into citable passages (`doc1:3`). Scans without a text layer are rejected; run OCR first. Nothing is stored.
2. **Questionnaire.** The model answers 69 fixed questions about the case: AI-system definition and scope, role, every prohibited practice and its exception, Annex I products, every Annex III use, the Article 6(3) exception, transparency and general-purpose AI. Each question comes with its legal test from the corpus, and every yes/no answer quotes the case.
3. **Quote check and Verifier.** Deterministic: every quote must appear verbatim in a passage the model was shown, and exact offsets are computed here, never taken from the model. A Verifier then judges each answer against its quotes. A failed answer that matters for the result gets one revision; anything still failing counts as not mentioned.
4. **Rules.** `src/rules.py` applies the Act in code, without a model: scope, prohibited practices, Annex I, Annex III with the Article 6(3) exception, transparency, then role and general-purpose AI. It lists the obligations that follow from that tier, role and those triggers, each quoting its own provision. Unknown facts that could raise the tier become questions for you.
5. **Obligation status.** A second call rates each listed obligation (met / gap / unclear / not applicable) with quotes from your documents and writes the summary. It cannot add or remove obligations, and a "met" without a verified quote becomes unclear.
6. **Report.** `src/report.py` turns the result into display sections and warnings without any model call; the UI renders it, with the exact quoted span highlighted in each source.

The model is DeepSeek (`deepseek-flash`, thinking off) through its OpenAI-compatible API; any compatible endpoint works via `LLM_BASE_URL` / `LLM_MODEL`.

## Built-in corpus

- Regulation (EU) 2024/1689 (AI Act), consolidated text of 27.7.2026 including the Digital Omnibus, Regulation (EU) 2026/1744 (recitals from the original Official Journal text, which consolidations omit)
- Commission guidelines: AI system definition; prohibited AI practices; general-purpose AI models; Article 50 transparency obligations
- Draft Commission guidelines on high-risk classification (consultation draft, May 2026, labelled DRAFT in citations)

Guidance is non-binding; the UI labels every citation as your document, the AI Act, guidance or draft guidance.

## Quality

Measured on 33 reference cases (20 short cases, 9 borderline cases, and 4 long real documents of up to 192,000 characters), with expected answers read from the Act:

- **Risk tier:** correct in 29 of 29 cases that have one, never lower than the law requires; all checks (tier, AI-system status, general-purpose AI, role) correct in 29 of 33, against 24 of 33 for the earlier free-form assessor.
- **Obligations:** 97% of the obligations the cases trigger are listed, and 90% of those listed are expected (earlier assessor: 88% and 44%); no obligation is marked met that the documents do not show.
- **Speed and cost:** about 30 seconds per case and under 50 seconds for the longest documents; about half the cost of the earlier assessor.
- **Search benchmark:** the corpus search (`src/law.py`, used by the retrieval evals and kept for a follow-up chat) returns the right article in its top 12 for 87.1% of 171 independent questions from two other projects ([AI Act Evaluation Benchmark](https://github.com/davidath/ai-act-evaluation-benchmark), [ActLens](https://github.com/SyedAshhadIbrar/ActLens)), never used for tuning.

## Known limitations

- No follow-up chat yet: the UI's "Answer Questions and Re-run" starts a fresh assessment with your answers added.
- Model output varies between runs; borderline cases can change tier or role.
- Systems outside the Act's scope show as "Unclear" in the UI until it gets an out-of-scope label.
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

**API:** `POST /api/assess` (multipart `files[]` and/or `description`, header `x-access-code` when `ACCESS_CODE` is set) returns the raw result plus `report`. Errors: 401 access code, 413 uploads over 4 MB, 422 no readable input or over 500,000 characters, 502 the model failed (safe to retry).

**UI:** React + Vite in `web/`; `npm run build` rewrites `public/index.html`, one self-contained file. See [web/README.md](web/README.md).

## Deploy (Vercel)

The Vercel project is connected to this GitHub repository: every push to `main` deploys to production, and every other branch gets a preview URL. `vercel.json` deploys `api/index.py` as a Python function with `corpus/*.md` bundled; Vercel serves `public/` statically. `.vercelignore` keeps `.env`, local data and dev-only files out of uploads.

```bash
vercel deploy                    # manual preview deployment from your working tree
```

Set `DEEPSEEK_API_KEY` and `ACCESS_CODE` for Production and Preview in the Vercel project (`vercel env add`). There is no database: the corpus index is built in memory on cold start and uploads are never stored.

## Repository

| Path | Contents |
|---|---|
| `src/` | Pipeline: `ingest.py`, `agents.py` (questionnaire, Verifier, obligation status), `rules.py` (questions, classification, obligations), `citations.py` (quote check), `report.py`, `law.py` (corpus and search), `config.py` |
| `api/index.py` | FastAPI endpoint; also serves the UI locally |
| `public/index.html` | Built UI (generated from `web/`) |
| `web/` | UI source |
| `corpus/` | Generated Markdown corpus |

**Corpus updates** happen on the `corpus-build` branch, which alone holds the downloaded sources and `scripts/build_corpus.py`:

```bash
git switch corpus-build && git merge main
# add the source to corpus/src/ and its title to TITLES in scripts/build_corpus.py
python -m scripts.build_corpus
git add corpus && git commit -m "corpus: ..."
git switch -c corpus-update main && git checkout corpus-build -- "corpus/*.md"   # commit, push, open a PR
```

## License

See [LICENSE](LICENSE).
