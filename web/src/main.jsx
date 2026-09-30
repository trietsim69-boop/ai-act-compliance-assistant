import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Toaster } from "sonner";
import { loadSample } from "./store";
import { EvidenceSheet } from "./shared";
import Report from "./Report";
import "./styles.css";

// Development only: /?sample=hr or /?sample=bot renders a real-shaped result without calling the API.
if (import.meta.env.DEV) {
  const sample = new URLSearchParams(location.search).get("sample");
  if (sample) loadSample(sample);
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <Report />
    <EvidenceSheet />
    <Toaster position="top-center" richColors closeButton />
  </StrictMode>,
);
