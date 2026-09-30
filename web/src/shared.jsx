// Building blocks for the report page. Data contract: the `report` object from src/report.py (build_report).
import { useRef } from "react";
import clsx from "clsx";
import { Dialog } from "@base-ui/react/dialog";
import { useCase, ERRORS, FORMATS, MAX_BYTES, totalBytes } from "./store";

export const TIER = {
  prohibited: { label: "Prohibited", icon: "⛔", tone: "bad" },
  high_risk: { label: "High risk", icon: "▲", tone: "bad" },
  limited_risk: { label: "Limited risk", icon: "◆", tone: "warn" },
  minimal_risk: { label: "Minimal risk", icon: "●", tone: "ok" },
  unclear: { label: "Unclear", icon: "?", tone: "muted" },
};
export const STATUS = {
  met: { label: "Met", icon: "✓", tone: "ok" },
  gap: { label: "Gap", icon: "✕", tone: "bad" },
  unclear: { label: "Unclear", icon: "?", tone: "warn" },
  not_applicable: { label: "Not applicable", icon: "–", tone: "muted" },
  supported: { label: "Supported", icon: "✓", tone: "ok" },
  contradicted: { label: "Contradicted", icon: "✕", tone: "bad" },
  insufficient: { label: "Not established", icon: "?", tone: "warn" },
};
export const words = (s) => String(s ?? "").replaceAll("_", " ");
export const ROLE = { provider: "Provider", deployer: "Deployer", both: "Provider and deployer", unclear: "Unclear" };

export function Chip({ value, map = STATUS, className }) {
  const m = map[value] ?? { label: words(value), icon: "", tone: "muted" };
  return (
    <span className={clsx("chip", `tone-${m.tone}`, className)}>
      <span aria-hidden="true">{m.icon}</span> {m.label}
    </span>
  );
}

// UI-EV-3: source type is derivable from the chunk id; draft status lives in the source title.
export function sourceType(ev) {
  if (/^doc\d+:/.test(ev.chunk_id)) return { key: "case", label: "Your document" };
  if (ev.chunk_id.startsWith("eu_ai_act/")) return { key: "law", label: "AI Act" };
  if (/draft/i.test(ev.source)) return { key: "draft", label: "Draft guidance" };
  return { key: "guidance", label: "Guidance" };
}
export function SourceTag({ ev }) {
  const t = sourceType(ev);
  return <span className={`src src-${t.key}`}>{t.label}</span>;
}
export const shortSource = (ev) => ev.source.replace(/\s*\(.*$/, "").replace(/^Regulation \(EU\) 2024\/1689 — /, "");
export const where = (ev) => (ev.label === ev.source ? shortSource(ev) : ev.label);

// UI-EV-2: offsets are Python code points; Array.from splits by code point, so emoji don't shift the highlight.
export function Passage({ ev, className }) {
  const cps = Array.from(ev.passage);
  return (
    <p className={clsx("passage", className)} translate="no">
      {cps.slice(0, ev.start).join("")}
      <mark>{cps.slice(ev.start, ev.end).join("")}</mark>
      {cps.slice(ev.end).join("")}
    </p>
  );
}

export function Evidence({ ev }) {
  return (
    <div className="ev">
      <div className="ev-head">
        <SourceTag ev={ev} />
        <span className="ev-where">{where(ev)}</span>
      </div>
      <blockquote>“{ev.quote}”</blockquote>
      <details>
        <summary>Full passage · <code translate="no">{ev.chunk_id}</code></summary>
        <Passage ev={ev} />
      </details>
    </div>
  );
}

export function ClaimBody({ c }) {
  return (
    <>
      <div className="claim-line">
        <b className="mono" translate="no">{c.id}</b> <Chip value={c.status} />{" "}
        <span className="kind">{c.kind === "fact" ? "From your documents" : "Legal"}</span>
      </div>
      <p className="claim-text">{c.text}</p>
      <p className="hint">Verifier: {c.reason}</p>
      {c.evidence.length ? c.evidence.map((ev, i) => <Evidence key={i} ev={ev} />)
        : <p className="noquote"><span aria-hidden="true">⚠</span> No verified quote. Treat this claim as unsupported.</p>}
    </>
  );
}

// Side sheet for a claim, or an obligation and the claims behind it (UI-EV-1, UI-EV-6).
export function EvidenceSheet() {
  const { focus, data, setFocus } = useCase();
  const r = data?.report;
  let title = "", body = null;
  if (r && focus?.type === "claim") {
    const c = r.claims.find((x) => x.id === focus.id);
    title = `Claim ${c?.id}`;
    body = c && <ClaimBody c={c} />;
  } else if (r && focus?.type === "requirement") {
    const q = r.requirements[focus.id];
    title = q?.requirement;
    body = q && (
      <>
        <p><Chip value={q.status} /> {q.unverified && <span className="chip tone-warn"><span aria-hidden="true">⚠</span> Not backed by supported claims</span>}</p>
        <p>{q.explanation}</p>
        <h3 className="eyebrow">Backing Claims</h3>
        {q.claim_ids.length ? q.claim_ids.map((id) => {
          const c = r.claims.find((x) => x.id === id);
          return c && <div className="sheet-claim" key={id}><ClaimBody c={c} /></div>;
        }) : <p className="hint">No claims cited.</p>}
      </>
    );
  }
  return (
    <Dialog.Root open={!!focus} onOpenChange={(o) => !o && setFocus(null)}>
      <Dialog.Portal>
        <Dialog.Backdrop className="sheet-backdrop" />
        <Dialog.Popup className="sheet">
          <div className="sheet-top">
            <Dialog.Title className="sheet-title">{title}</Dialog.Title>
            <Dialog.Close className="btn ghost" aria-label="Close evidence">✕</Dialog.Close>
          </div>
          <div className="sheet-body">{body}</div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function useFilePicker() {
  const ref = useRef(null);
  const addFiles = useCase((s) => s.addFiles);
  const input = (
    <input ref={ref} id="case-files" name="files" type="file" multiple hidden accept={FORMATS.join(",")}
           onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }} />
  );
  return { input, open: () => ref.current?.click(), onDrop: (e) => { e.preventDefault(); addFiles(e.dataTransfer.files); } };
}

const MB = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });
export const mb = (n) => `${MB.format(n / 1_000_000)} MB`;

export function FileRows({ disabled }) {
  const { files, removeFile } = useCase();
  if (!files.length) return null;
  const total = totalBytes(files);
  return (
    <ul className="files">
      {files.map((f) => (
        <li key={f.name}>
          <span className="file-name" title={f.name}>{f.name}</span>
          <span className="hint num">{mb(f.size)}</span>
          <button type="button" className="btn ghost sm" onClick={() => removeFile(f.name)} disabled={disabled}
                  aria-label={`Remove ${f.name}`}>Remove</button>
        </li>
      ))}
      <li className={clsx("files-total num", total > MAX_BYTES && "over")}>
        {mb(total)} of 4 MB{total > MAX_BYTES && " — over the limit"}
      </li>
    </ul>
  );
}

export function Progress() {
  const { startedAt, now } = useCase();
  const secs = Math.max(0, Math.round((now - startedAt) / 1000));
  return (
    <div className="progress" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <b>Assessing…</b>
      <span className="hint num">{secs} s · usually 15–60 s</span>
    </div>
  );
}

export function ErrorBox() {
  const { error, run } = useCase();
  if (!error) return null;
  const e = ERRORS[error.status] ?? ERRORS[500];
  return (
    <div className="errorbox" role="alert">
      <b>{e.title}{error.status ? ` (${error.status})` : ""}</b>
      <p>{error.message || e.body}</p>
      {error.file_errors?.length > 0 && (
        <ul>{error.file_errors.map((f) => <li key={f.file}><b>{f.file}</b>: {f.error}</li>)}</ul>
      )}
      <button type="button" className="btn" onClick={run}>Try again</button>
    </div>
  );
}

export function Warnings({ warnings }) {
  if (!warnings.length) return null;
  return (
    <div className="warnings" role="note">
      <b><span aria-hidden="true">⚠</span> Check before relying on this</b>
      <ul>{warnings.map((w) => <li key={w}>{w}</li>)}</ul>
    </div>
  );
}

export function LowConfidence({ o }) {
  if (o.confidence !== "low" && o.risk_tier !== "unclear") return null;
  return (
    <div className="lowconf">
      <b>This is not a conclusion yet.</b> Confidence is {o.confidence} and key facts are missing. Answer the open questions (section 5) and run it again.
    </div>
  );
}

export const CORPUS = [
  "EU AI Act, consolidated 27.7.2026 (incl. the Digital Omnibus, Regulation (EU) 2026/1744)",
  "Commission guidelines: AI system definition · prohibited practices · general-purpose AI models · Article 50 transparency",
  "Draft Commission guidelines: high-risk classification (consultation draft, May 2026)",
];
