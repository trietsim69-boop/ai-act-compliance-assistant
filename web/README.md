# UI

React + Vite source for the single-page UI. `npm run build` writes one self-contained file, `../public/index.html`, which FastAPI serves locally and Vercel serves in production. Commit the built file together with source changes.

```bash
cd web && npm install
npm run dev       # http://localhost:5173, proxies /api to `uvicorn api.index:app` (port 8000)
npm run build     # rewrites ../public/index.html
```

The page follows the brief's six sections; evidence opens in a side sheet. Follow-up is "answer questions and re-run" until the backend has a follow-up endpoint.

Libraries: zustand (case state). The evidence sheet is a native `<dialog>`.
