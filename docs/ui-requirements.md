# UI functional requirements

What the user interface must do, and why. This document deliberately makes **no design choices**: layout, visual style, navigation pattern, component library and framework are left open (see [Open design decisions](#open-design-decisions)).

Sources: the challenge brief (*Norrin hackathon challenge, May 2026*, "AI Act Compliance Assistant") and the current backend (`POST /api/assess`, `src/report.py`). Requirement IDs (`UI-…`) are for reference in issues and PRs. Each requirement is marked:

- **Now**: the backend already provides what the UI needs.
- **Gap**: needs backend work before the UI can offer it (listed in [Backend gaps](#backend-gaps)).
- **Bonus**: optional capability from the brief's bonus list.

## 1. Purpose and users

The product is a **decision-support tool for structured review of one AI use case**, not a compliance authority. A user (typically a product owner, compliance lead or legal reviewer) supplies documents describing one AI system and gets a preliminary, citation-backed EU AI Act assessment they can check, question and refine.

The interface succeeds when a reviewer can, without writing a prompt:

1. supply the case documents,
2. understand the preliminary assessment and its confidence,
3. verify every statement against the exact source text it relies on,
4. see what is missing or uncertain, and
5. follow up to refine the assessment.

## 2. Primary flow

1. Start a session for one use case (enter the access code where required).
2. Add case material: one or more documents and/or a free-text description.
3. Start the analysis. No prompt or query is required.
4. Wait while the analysis runs (typically 15–60 s).
5. Review the result: summary, facts, assessment, obligations, governance, questions, evidence.
6. Follow up: answer open questions or ask questions in chat; the assessment is revised. **(Gap)**
7. Export or save the result.

## 3. Case input

| ID | Requirement | Status |
|---|---|---|
| UI-IN-1 | One session analyses exactly **one** AI use case. Starting a new case clears (or separates) the previous one. | Now |
| UI-IN-2 | Upload **multiple documents** for the same case in one submission. | Now |
| UI-IN-3 | Accept the supported formats: PDF, DOCX, PPTX, HTML/HTM, CSV, TXT, MD. Tell the user the list before they upload. | Now |
| UI-IN-4 | Offer a free-text description as an alternative or addition to files. | Now |
| UI-IN-5 | Show the chosen files before submission, with the ability to remove one. | Now (client-side) |
| UI-IN-6 | Communicate the limits up front and check them before sending: **4 MB total upload**, **100,000 characters of extracted text**. | Now |
| UI-IN-7 | Explain that scanned PDFs without a text layer are rejected and need OCR first. | Now |
| UI-IN-8 | Never require the user to upload the EU AI Act or guidance; state that the reference corpus is built in, and which documents it contains. | Now |
| UI-IN-9 | Access code entry when the deployment requires one (`x-access-code` header); the code may be remembered on the device. | Now |

## 4. Running the analysis

| ID | Requirement | Status |
|---|---|---|
| UI-RUN-1 | One action starts the analysis; the user writes no prompt. | Now |
| UI-RUN-2 | Show that work is in progress, with elapsed time and an expected duration (15–60 s), and prevent duplicate submissions. | Now |
| UI-RUN-3 | Show which stage is running (searching the law, checking quotes, verifying, revising). | Gap (needs streamed stage events) |
| UI-RUN-4 | Map every error to a plain, actionable message and keep the user's input so they can retry: **401** wrong/missing access code; **413** uploads over 4 MB; **422** no readable content or too much text (show per-file reasons); **502** the language model failed (safe to retry); network failure. | Now |
| UI-RUN-5 | Report per-file problems (`file_errors`) even when the analysis succeeds on the remaining files. | Now |

## 5. Result

The six output sections required by the brief, mapped to the API's `report` object (built by `src/report.py`; this is the UI's data contract).

| ID | Brief section | Requirement | Data | Status |
|---|---|---|---|---|
| UI-RES-1 | 1. Use-case summary | Show a concise summary of the case. | `report.overview.summary` | Now |
| UI-RES-2 | 2. Extracted facts | Show the key facts (purpose, users, affected persons, sector, input data, outputs, automation level, human oversight, deployment context, AI-generated content, GPAI use, impact on people), each linked to its source quote. | Facts exist as `report.claims` with `kind = "fact"`, not as the named fields | Partly (named fact fields are a gap) |
| UI-RES-3 | 3. Preliminary assessment | Show: AI system yes/no/unclear, risk tier, role (provider/deployer/both/unclear), GPAI involvement, confidence, and the reasoning. | `report.overview.*` | Now |
| UI-RES-4 | 3. Preliminary assessment | Show the legal claims behind the assessment, each with its verification status and citations. | `report.claims` with `kind = "legal"` | Now |
| UI-RES-5 | 3. / 4. Obligations and governance | Show each obligation with status **met / gap / unclear / not applicable**, the explanation, and the claims backing it. Flag obligations marked *met* that aren't backed by supported claims. | `report.requirements[*]`, `unverified` | Now |
| UI-RES-6 | 4. Governance observations | Group practical governance measures (documentation, risk management, transparency, human oversight, monitoring, logging, accountability, role clarity). | Currently mixed into `requirements` | Partly (a governance grouping is a gap) |
| UI-RES-7 | 5. Missing information | List the gaps and the follow-up questions an expert would ask, each with its topic. | `report.questions[*]` (`topic`, `question`) | Now |
| UI-RES-8 | 5. / 6. Warnings | Show every warning before the user relies on the result: skipped files, removed citations, contradicted/unsupported claims, unquoted claims, unverified obligations, low confidence, revision used. | `report.warnings[*]` | Now |
| UI-RES-9 | Disclaimer | Keep the "preliminary, not legal advice" disclaimer visible with every result, including exports. | `report.disclaimer` | Now |

**Enumerated values** the UI must display unambiguously: `risk_tier` ∈ prohibited, high_risk, limited_risk, minimal_risk, unclear; `ai_system` and `gpai_involved` ∈ yes, no, unclear; `role` ∈ provider, deployer, both, unclear; `confidence` ∈ low, medium, high; claim `status` ∈ supported, contradicted, insufficient; requirement `status` ∈ met, gap, unclear, not_applicable. Status must never be conveyed by colour alone.

## 6. Evidence and citations

This is the core of "regulatory grounding" and "transparency of output" in the brief's evaluation criteria.

| ID | Requirement | Status |
|---|---|---|
| UI-EV-1 | Every claim shows its quote(s) and lets the user open the full source passage. | Now (`claims[*].evidence[*].passage`) |
| UI-EV-2 | Highlight the **exact** quoted span inside the passage. Offsets (`start`, `end`) are Python code-point positions; count code points, not UTF-16 units. | Now |
| UI-EV-3 | Label every citation with its **source type**: uploaded case document; legislation (the AI Act, consolidated incl. the Digital Omnibus); official guidance; **draft** guidance (the high-risk classification guidelines are a consultation draft). | Derivable now from `chunk_id`: `doc…` = upload, `eu_ai_act/…` = legislation, `guidelines_…` = guidance; draft status is in the source title |
| UI-EV-4 | Show where the passage sits: document name and section label (e.g. "Chapter IV › Article 50 — Transparency obligations…"). | Now (`source`, `label`) |
| UI-EV-5 | Show each claim's verification status and the verifier's reason; claims without a verified quote are visibly marked as such. | Now |
| UI-EV-6 | Let the user move between an obligation and the claims (and sources) that back it. | Now (`requirements[*].claim_ids`) |
| UI-EV-7 | Citation IDs are stable (`eu_ai_act/art-50/1`); saved results stay resolvable after corpus updates. The UI should show or link by these IDs. | Now |

## 7. Separation of evidence types

The brief requires a clear distinction between **uploaded-document facts, regulatory references, optional sources, assumptions, uncertainties and system reasoning**. The UI must keep these visually and structurally distinct, never blended into one prose block.

| Category | Where it comes from today | Status |
|---|---|---|
| Uploaded-document facts | `claims` with `kind = "fact"` (cite `doc…` passages) | Now |
| Regulatory references | `claims` with `kind = "legal"` (cite corpus passages) | Now |
| Optional / non-core sources | Not produced; adjacent frameworks (GDPR, national law) must be shown separately from the AI Act analysis if added | Gap / Bonus |
| Assumptions | No dedicated field | Gap |
| Uncertainties | `overview.confidence`, `ai_system` / `risk_tier` = unclear, `questions`, `warnings` | Partly |
| System reasoning / interpretation | `overview.reasoning`, requirement explanations | Now |

## 8. Follow-up chat and revision

The brief makes this a **core requirement** ("support follow-up chat in the same session") and an evaluation criterion ("useful follow-up chat").

| ID | Requirement | Status |
|---|---|---|
| UI-CHAT-1 | The user can ask questions about the current assessment in the same session; answers stay grounded in the same case documents and corpus, with citations. | Gap |
| UI-CHAT-2 | The user can answer the system's open questions (`questions`), and the assessment is revised using the answers. | Gap |
| UI-CHAT-3 | After a revision, show what changed (tier, role, obligations, claims) compared with the previous version. | Gap |
| UI-CHAT-4 | The user can add another document to the same case and re-run. | Gap (today a re-run is a new, independent request) |
| UI-CHAT-5 | Chat answers follow the same separation and disclaimer rules as the report. | Gap |

## 9. Session, export and persistence

| ID | Requirement | Status |
|---|---|---|
| UI-SES-1 | The result stays available while the user reviews it, including after chat turns. | Gap (API is stateless; state lives only in the client) |
| UI-SES-2 | Uploaded documents are not stored by the server; say so in the UI. | Now (by design) |
| UI-EXP-1 | Download the full result as JSON. | Now |
| UI-EXP-2 | Export a readable report (e.g. PDF or Markdown) containing all sections, citations and the disclaimer. | Bonus |

## 10. States

Every view needs defined behaviour for: **empty** (no case yet), **ready** (inputs chosen), **running**, **success**, **success with warnings or skipped files**, **error** (each of UI-RUN-4), and **low-confidence or mostly unclear** results, which must not read like a confident answer.

## 11. Accessibility and device support

Functional requirements, independent of visual design:

- Every action is keyboard-operable, with a visible focus indicator.
- Progress, errors and newly rendered results are announced to screen readers.
- Statuses and tiers are conveyed by text or icon, not colour alone, with WCAG 2.1 AA contrast.
- Usable from 320 px wide phones to desktop; long quotes, legal headings and tables stay readable without horizontal page scrolling.
- Content from uploaded documents and model output is rendered as text, never as HTML (it is untrusted).
- Output is in the language of the case documents; law quotes stay verbatim in English. The UI must handle both.

## 12. Bonus capabilities (from the brief)

Optional; each needs backend support unless noted:

- Confidence or uncertainty display (**partly Now**: `overview.confidence`).
- Checklist of next steps and documentation needs (derivable now from `gap`/`unclear` obligations and `questions`).
- Report export (UI-EXP-2).
- Role-based views (provider vs deployer obligations).
- Dedicated GPAI analysis path.
- Flagging source quality and type (**partly Now**: UI-EV-3).
- Adjacent frameworks (EU data law, Finnish implementation) shown separately from the core AI Act analysis.
- Comparing several use cases at portfolio level.
- Showing the agents' work (Assessor searches, quote check, Verifier verdicts, revision) for transparency about the multi-agent workflow.

## Backend gaps

What the backend must add before the UI can meet the gaps above, in rough order of value against the brief:

1. **Follow-up turn endpoint** (UI-CHAT-1…5, UI-SES-1): accepts the previous result, the case passages or documents, and the user's message or answers; returns a revised result or a cited answer.
2. **Structured extracted facts** (UI-RES-2): named fact fields, each with evidence.
3. **Assumptions** as an explicit list (section 7).
4. **Governance grouping** of requirements (UI-RES-6).
5. **Streamed stage events** for progress (UI-RUN-3).
6. **Diff between assessment versions** (UI-CHAT-3), which can be computed client-side once revisions exist.

## Open design decisions

Left to the design phase, deliberately not decided here:

- Framework (keep the static page, or a framework such as Next.js) and hosting of the UI.
- Page structure and navigation: single page vs steps; where chat lives relative to the report.
- Visual language, typography, colour system, iconography, and how tiers and statuses are represented.
- How much of the evidence is shown by default vs on demand.
- Where session state lives (client only, or a server-side session once chat exists).
- Whether to expose the agents' intermediate steps, and at what level of detail.
