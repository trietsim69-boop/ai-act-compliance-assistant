import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { EvidenceSheet } from "./shared";
import Report from "./Report";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <Report />
    <EvidenceSheet />
  </StrictMode>,
);
