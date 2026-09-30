# UI

React + Vite source for the single-page UI. `npm run build` writes one self-contained file, `../public/index.html`, which FastAPI serves locally and Vercel serves in production. Commit the built file together with source changes.

```bash
cd web && npm install
npm run dev       # http://localhost:5173, proxies /api to `uvicorn api.index:app` (port 8000)
npm run build     # rewrites ../public/index.html
```

In `npm run dev`, `/?sample=hr` or `/?sample=bot` renders a real-shaped result without calling the API (no cost). `src/sample.json` is produced by `make_sample.py` from real corpus passages through the real `Assessment` model, `check_references` and `build_report`; rerun it (`npm run sample`) after contract changes.

The page follows the brief's six sections; evidence opens in a side sheet. Follow-up is "answer questions and re-run" until the backend has a follow-up endpoint.

Libraries: base-ui (Dialog), Sonner (toasts), zustand (case state), clsx.
