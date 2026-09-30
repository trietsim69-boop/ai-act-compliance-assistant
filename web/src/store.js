// Case state for one analysis session. The server is stateless: files, description and the last result live
// here, in memory, and nothing is stored server-side.
import { create } from "zustand";
import { toast } from "sonner";

export const FORMATS = [".pdf", ".docx", ".pptx", ".html", ".htm", ".csv", ".txt", ".md"];
export const MAX_BYTES = 4_000_000;

export const ERRORS = {
  401: { title: "Access code not accepted", body: "Check the code you were given and try again." },
  413: { title: "Uploads are over 4 MB", body: "Remove a file or upload only the relevant pages." },
  422: { title: "Nothing we could assess", body: "None of the input had readable text. Scanned PDFs need OCR first." },
  502: { title: "The language model failed", body: "This happens occasionally. Your input is kept; it is safe to try again." },
  0: { title: "No connection", body: "The request did not reach the server. Check your connection and try again." },
  500: { title: "Something went wrong on the server", body: "Your input is kept. Try again in a moment." },
};

const CODE_KEY = "ai-act-access-code";
const readCode = () => { try { return localStorage.getItem(CODE_KEY) || ""; } catch { return ""; } };
const saveCode = (code) => { try { localStorage.setItem(CODE_KEY, code); } catch { /* private mode */ } };

let timer = null;

export const useCase = create((set, get) => ({
  code: readCode(),
  files: [], // {name, size, file}
  description: "",
  phase: "empty", // empty | ready | running | done | error
  startedAt: 0,
  now: 0,
  error: null, // {status, message, file_errors}
  data: null, // /api/assess response: {assessment, verdicts, sources, file_errors, report, ...}
  focus: null, // {type: 'claim' | 'requirement', id}: what the evidence sheet shows

  setCode: (code) => set({ code }),
  setDescription: (description) => set((s) => ({ description, phase: phaseFor(s.files, description, s.phase) })),
  addFiles: (list) => {
    const s = get();
    const next = [...s.files];
    for (const file of list) {
      const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
      if (!FORMATS.includes(ext)) {
        toast.error(`${file.name} is not a supported format`, { description: "Use PDF, DOCX, PPTX, HTML, CSV, TXT or MD." });
        continue;
      }
      if (!next.some((x) => x.name === file.name)) next.push({ name: file.name, size: file.size, file });
    }
    set({ files: next, phase: phaseFor(next, s.description, s.phase) });
  },
  removeFile: (name) => set((s) => {
    const files = s.files.filter((f) => f.name !== name);
    return { files, phase: phaseFor(files, s.description, s.phase) };
  }),

  run: async () => {
    const s = get();
    if (s.phase === "running") return;
    if (totalBytes(s.files) > MAX_BYTES) {
      toast.error("Uploads are over 4 MB", { description: "Remove a file before starting." });
      return;
    }
    saveCode(s.code);
    const startedAt = Date.now();
    set({ phase: "running", startedAt, now: startedAt, error: null });
    clearInterval(timer);
    timer = setInterval(() => set({ now: Date.now() }), 1000);

    const body = new FormData();
    for (const f of s.files) body.append("files", f.file, f.name);
    body.append("description", s.description);
    try {
      const res = await fetch("/api/assess", { method: "POST", body, headers: { "x-access-code": s.code } });
      const json = await res.json().catch(() => null);
      if (res.ok) {
        set({ phase: "done", data: json, focus: null });
        window.scrollTo({ top: 0 });
      } else {
        const detail = json?.detail;
        set({ phase: "error", error: {
          status: ERRORS[res.status] ? res.status : 500,
          message: typeof detail === "string" ? detail : detail?.error,
          file_errors: detail?.file_errors ?? [],
        } });
      }
    } catch {
      set({ phase: "error", error: { status: 0, file_errors: [] } });
    } finally {
      clearInterval(timer);
    }
  },

  // Follow-up with today's stateless API: back to the input with files kept and the open questions appended as a
  // template to answer; the next run is a fresh assessment. (A real follow-up endpoint is backend gap 1.)
  answerAndRerun: () => set((s) => {
    const qs = s.data?.report?.questions ?? [];
    const template = qs.map((q) => `${q.topic}: ${q.question}\nAnswer: `).join("\n\n");
    const description = [s.description.trim(), template && `Answers to the open questions:\n\n${template}`].filter(Boolean).join("\n\n");
    return { description, phase: "ready", focus: null };
  }),
  reset: () => {
    clearInterval(timer);
    const { files, description, phase, data, error } = get();
    set({ files: [], description: "", phase: "empty", data: null, error: null, focus: null });
    toast("Started a new case", { action: { label: "Undo", onClick: () => set({ files, description, phase, data, error }) } });
  },
  setFocus: (focus) => set({ focus }),
}));

function phaseFor(files, description, current) {
  if (current === "running" || current === "done") return current;
  return files.length || description.trim() ? "ready" : "empty";
}

export const totalBytes = (files) => files.reduce((n, f) => n + f.size, 0);

export function downloadJSON(data) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  Object.assign(document.createElement("a"), { href: url, download: "ai-act-assessment.json" }).click();
  URL.revokeObjectURL(url);
  toast("Downloaded ai-act-assessment.json");
}

// Development only (tree-shaken from builds): render a real-shaped sample result without calling the API.
export async function loadSample(name = "hr") {
  const { default: sample } = await import("./sample.json");
  useCase.setState({ phase: "done", data: structuredClone(sample[name]), focus: null });
}

// Leaving mid-run or with an unsaved result loses it (the server keeps nothing): ask first.
addEventListener("beforeunload", (e) => {
  const { phase } = useCase.getState();
  if (phase === "running" || phase === "done") e.preventDefault();
});
