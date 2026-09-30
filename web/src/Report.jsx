// The page: intake → run → report in the brief's six-section order, with evidence in a side sheet.
import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { useCase, downloadJSON } from "./store";
import {
  Chip, TIER, ROLE, words, SourceTag, sourceType, where, FileRows, useFilePicker, Progress, ErrorBox,
  Warnings, LowConfidence, CORPUS,
} from "./shared";

const SECTIONS = [
  ["summary", "1 Summary"], ["facts", "2 Facts"], ["assessment", "3 Assessment"],
  ["obligations", "4 Obligations"], ["questions", "5 Missing Information"], ["sources", "6 Sources"],
];

export default function Report() {
  const { phase, data, reset } = useCase();
  const done = phase === "done";
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="top">
        <span className="brand">AI Act Compliance Assistant</span>
        {done && <button type="button" className="btn ghost sm no-print" onClick={reset}>New Case</button>}
      </header>
      <div className={clsx("layout", done && "has-toc")}>
        {done && (
          <nav className="toc no-print" aria-label="Report sections">
            {SECTIONS.map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}
          </nav>
        )}
        <main id="main" className="main">
          {done ? <ReportBody data={data} /> : <Intake />}
        </main>
      </div>
    </>
  );
}

function Intake() {
  const { phase, code, setCode, description, setDescription, run } = useCase();
  const [empty, setEmpty] = useState(false);
  const descRef = useRef(null);
  const submit = (e) => {
    e.preventDefault();
    if (phase === "empty") { setEmpty(true); descRef.current?.focus(); return; }
    setEmpty(false);
    run();
  };
  const { input, open, onDrop } = useFilePicker();
  const running = phase === "running";
  return (
    <>
      <h1>Check an AI Use Case Against the EU AI Act</h1>
      <p className="lead">Add documents describing one AI system. You get a preliminary assessment where every statement quotes its source. Decision support, not legal advice.</p>
      <form className="card intake" aria-busy={running} onSubmit={submit}>
        <label htmlFor="access-code">Access code</label>
        <input id="access-code" name="access-code" type="password" value={code} onChange={(e) => setCode(e.target.value)}
               disabled={running} autoComplete="current-password" spellCheck={false} />

        <label htmlFor="case-files">Case documents</label>
        {input}
        <div className="drop" onDragOver={(e) => e.preventDefault()} onDrop={running ? undefined : onDrop}>
          <button type="button" className="btn secondary" onClick={open} disabled={running}>Choose Files…</button>
          <span className="hint">or drop them here · PDF, DOCX, PPTX, HTML, CSV, TXT, MD · 4 MB total · up to 100,000 characters of text · scanned PDFs need OCR first</span>
        </div>
        <FileRows disabled={running} />

        <label htmlFor="case-description">Or describe the use case</label>
        <textarea ref={descRef} id="case-description" aria-invalid={empty || undefined} aria-describedby={empty ? "empty-error" : undefined} name="description" autoComplete="off" value={description} onChange={(e) => setDescription(e.target.value)}
                  disabled={running} placeholder="What does the system do, who is affected, who decides, which models does it use…" />
        {empty && phase === "empty" && <p id="empty-error" className="field-error" role="alert">Add at least one file or a description.</p>}

        <details className="corpus">
          <summary>You don't need to upload the law. What's built in?</summary>
          <ul>{CORPUS.map((c) => <li key={c}>{c}</li>)}</ul>
          <p className="hint">Your files are read in memory and not stored.</p>
        </details>

        <div className="row actions">
          <button type="submit" className="btn primary" disabled={running}>
            {running ? "Assessing…" : "Assess"}
          </button>
        </div>
        {running && <Progress />}
        <ErrorBox />
      </form>
    </>
  );
}

function ReportBody({ data }) {
  const { setFocus, answerAndRerun } = useCase();
  const titleRef = useRef(null);
  useEffect(() => titleRef.current?.focus(), []);
  const r = data.report, o = r.overview;
  const facts = r.claims.filter((c) => c.kind === "fact");
  const legal = r.claims.filter((c) => c.kind === "legal");
  const t = TIER[o.risk_tier] ?? TIER.unclear;
  return (
    <article>
      <div className="title-row">
        <h1 ref={titleRef} tabIndex={-1}>Preliminary Assessment</h1>
        <div className="row no-print">
          <button type="button" className="btn secondary" onClick={() => window.print()}>Print / Save as PDF</button>
          <button type="button" className="btn secondary" onClick={() => downloadJSON(data)}>Download JSON</button>
        </div>
      </div>
      <p className="disclaimer">{r.disclaimer}</p>

      <div className={`verdict tone-${t.tone}`}>
        <div className="tier"><small>Risk tier</small><b><span aria-hidden="true">{t.icon}</span> {t.label}</b></div>
        <dl>
          <div><dt>AI system</dt><dd>{words(o.ai_system)}</dd></div>
          <div><dt>Your role</dt><dd>{ROLE[o.role] ?? words(o.role)}</dd></div>
          <div><dt>General-purpose AI</dt><dd>{words(o.gpai_involved)}</dd></div>
          <div><dt>Confidence</dt><dd>{o.confidence}</dd></div>
        </dl>
      </div>
      <LowConfidence o={o} />
      <Warnings warnings={r.warnings} />

      <h2 id="summary">1 Use-Case Summary</h2>
      <p>{o.summary}</p>

      <h2 id="facts">2 Facts from Your Documents</h2>
      <ClaimList claims={facts} empty="No facts were extracted." onOpen={setFocus} />

      <h2 id="assessment">3 Preliminary Assessment</h2>
      <p className="reasoning"><span className="kind-tag">System reasoning</span> {o.reasoning}</p>
      <h3>Legal Basis</h3>
      <ClaimList claims={legal} empty="No legal claims were made." onOpen={setFocus} />

      <h2 id="obligations">4 Obligations and Governance</h2>
      {r.requirements.length ? (
        <div className="table-wrap">
          <table className="obligations">
            <thead><tr><th scope="col">Obligation</th><th scope="col">Status</th><th scope="col">Why</th></tr></thead>
            <tbody>
              {r.requirements.map((q, i) => (
                <tr key={`${i}-${q.requirement}`}>
                  <td><button type="button" className="linkish" onClick={() => setFocus({ type: "requirement", id: i })}>{q.requirement}</button></td>
                  <td><Chip value={q.status} />{q.unverified && <div className="hint tone-warn"><span aria-hidden="true">⚠</span> Not backed by supported claims</div>}</td>
                  <td>{q.explanation}{q.claim_ids.length > 0 && <div className="hint">Based on {q.claim_ids.join(", ")}</div>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="hint">No obligations were identified.</p>}

      <h2 id="questions">5 Missing Information</h2>
      {r.questions.length ? (
        <>
          <ol className="questions">{r.questions.map((q) => <li key={q.topic + q.question}><b>{q.topic}:</b> {q.question}</li>)}</ol>
          <p className="no-print">
            <button type="button" className="btn primary" onClick={answerAndRerun}>Answer Questions and Re-run</button>
            <span className="hint"> Your files are kept; the questions are added to the description for you to answer.</span>
          </p>
        </>
      ) : <p className="hint">No open questions.</p>}

      <h2 id="sources">6 Sources Cited</h2>
      <SourceIndex r={r} onOpen={setFocus} />

      <p className="disclaimer">{r.disclaimer}</p>
    </article>
  );
}

function ClaimList({ claims, empty, onOpen }) {
  if (!claims.length) return <p className="hint">{empty}</p>;
  return (
    <ul className="claims">
      {claims.map((c) => {
        const ev = c.evidence[0];
        return (
          <li key={c.id} className="claim">
            <div className="claim-line"><b className="mono" translate="no">{c.id}</b> <Chip value={c.status} /></div>
            <p>{c.text}</p>
            {ev ? (
              <button type="button" className="quote" onClick={() => onOpen({ type: "claim", id: c.id })}>
                <SourceTag ev={ev} /> <span className="q">“{ev.quote}”</span>
                <span className="hint">{where(ev)} · open source ›</span>
              </button>
            ) : <p className="noquote"><span aria-hidden="true">⚠</span> No verified quote</p>}
          </li>
        );
      })}
    </ul>
  );
}

function SourceIndex({ r, onOpen }) {
  const groups = {};
  for (const c of r.claims) for (const ev of c.evidence) {
    (groups[sourceType(ev).label] ??= new Map()).set(ev.chunk_id, { ev, claim: c.id });
  }
  if (!Object.keys(groups).length) return <p className="hint">No sources were cited.</p>;
  return (
    <div className="sources">
      {Object.entries(groups).map(([label, m]) => (
        <div key={label}>
          <h3 className="eyebrow">{label}</h3>
          <ul>
            {[...m.values()].map(({ ev, claim }) => (
              <li key={ev.chunk_id}>
                <button type="button" className="linkish" onClick={() => onOpen({ type: "claim", id: claim })}><code translate="no">{ev.chunk_id}</code></button>{" "}
                <span className="hint">{where(ev)}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
