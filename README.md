# Norrin AI Act Compliance Assistant

Upload documents describing an AI use case (PDF, DOCX, PPTX, HTML, CSV, TXT, MD) and get a preliminary, citation-backed assessment against the EU AI Act and Commission guidance: whether it is an AI system, risk tier, your role, which obligations apply, and whether your documents show they are met.

Decision support only — not legal advice.

## How it works

1. **Ingest** — every upload is converted to Markdown with MarkItDown and split into citable passages (`doc1:3`). Scans without a text layer are rejected (run OCR first).
2. **Assessor agent** — reads the case and calls a `search_law` tool (SQLite FTS5/BM25 over `corpus/*.md`) as often as it needs, then returns structured JSON: claims with verbatim quotes, requirements (met / gap / unclear), and open questions.
3. **Quote check** — deterministic: every quote must appear verbatim in a passage the model was shown; facts must quote the case, legal claims must quote the law.
4. **Verifier agent** — judges each claim against its quoted passages (supported / contradicted / insufficient).
5. **One revision** — if anything failed, the assessor gets the feedback once and the result is re-checked.

## Setup

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt pytest httpx
cp .env.example .env                              # add DEEPSEEK_API_KEY
```

## Use

```bash
python -m src.agents path/to/case.pdf other.docx   # prints the JSON result
uvicorn api.index:app --reload                     # UI at http://localhost:8000, API at POST /api/assess
```

`POST /api/assess` (multipart `files[]`, `description`) returns the raw result plus `report`: deterministic display sections with warnings and the exact span of every quote. Bad input is 422; a failing or unusable model answer is 502.

## Test and evaluate

```bash
python -m pytest -q          # offline, no API key
python -m evals.retrieval    # corpus search recall on 71 hand-reviewed quotes, split lay/legal queries
python -m evals.cases        # live: runs the 20 reference cases through DeepSeek (tier, GPAI, AI system, role)
```

## Corpus

`corpus/` holds Markdown versions of the AI Act (converted from the EUR-Lex HTML, one `##` heading per article, recital and annex) and the Commission guidelines on the AI-system definition and on prohibited practices (one `##` heading per numbered section). All downloaded sources live in `corpus/src/`: the AI Act as EUR-Lex HTML (plus the Official Journal PDF for reference; its two-column layout separates recital numbers from their text, so the build uses the HTML) and the guideline PDFs. `python -m scripts.build_corpus` regenerates every `.md` deterministically and fails if a section listed in a PDF's table of contents has no heading in the body.

## Deploy

`vercel.json` deploys `api/index.py` as a Python function with the corpus bundled. Set `DEEPSEEK_API_KEY` and `ACCESS_CODE` in the Vercel project; clients send the code in the `x-access-code` header. Uploads are capped at 4 MB total. No database or vector store: the corpus index is rebuilt in memory on cold start (<1 s) and uploads are never stored.

To add a source: put the EUR-Lex HTML (for legislation) or the PDF (for guidance) in `corpus/src/`, add its `# Title (status, date)` to `TITLES` in `scripts/build_corpus.py`, and run the build.
