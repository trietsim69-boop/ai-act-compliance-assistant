import json
import logging
import os
from secrets import compare_digest

from fastapi import FastAPI, Form, Header, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from openai import OpenAIError
from pydantic import ValidationError

from src.agents import CaseError, Claim, assess_case, reassess
from src.config import ROOT
from src.ingest import case_passages
from src.report import build_report
from src.rules import BY_ID

MAX_UPLOAD_BYTES = 4_000_000  # Vercel rejects request bodies over 4.5 MB anyway

app = FastAPI()
log = logging.getLogger(__name__)


@app.post("/api/assess")
def assess(files: list[UploadFile] = [], description: str = Form(""), previous: str = Form(""), answers: str = Form(""),
           x_access_code: str = Header("")):
    # Sync on purpose: FastAPI runs it in a thread pool, so minutes of LLM calls don't block the server.
    code = os.getenv("ACCESS_CODE", "")  # unset = open, for local dev
    if code and not compare_digest(x_access_code.encode(), code.encode()):
        raise HTTPException(401, "Wrong or missing access code.")
    uploads = [(f.filename or "upload", f.file.read()) for f in files]
    if sum(len(data) for _, data in uploads) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Uploads exceed {MAX_UPLOAD_BYTES // 1_000_000} MB in total.")
    rerun = _rerun(previous, answers) if answers else None
    case, errors = case_passages(uploads, description)
    try:
        result = reassess(case, *rerun) if rerun else assess_case(case)
        return {**result, "file_errors": errors, "report": build_report(result, errors)}
    except CaseError as error:
        raise HTTPException(422, {"error": str(error), "file_errors": errors})
    except (OpenAIError, ValidationError):
        log.exception("language model failure")
        raise HTTPException(502, {"error": "The language model failed or returned an unusable answer. Please try again.",
                                  "file_errors": errors})


def _rerun(previous: str, answers: str) -> tuple[dict, dict]:
    """The re-run fields: `previous` = {"answers": decision.answers, "claims": assessment.claims} of the earlier result,
    `answers` = {question id: {"answer": "yes"|"no", "text": "..."}}. 422 when malformed."""
    try:
        prev, given = json.loads(previous or "{}"), json.loads(answers)
        ok = (isinstance(prev, dict) and isinstance(prev.get("answers", {}), dict) and isinstance(given, dict) and given
              and all(q in BY_ID and isinstance(a, dict) and a.get("answer") in ("yes", "no") and isinstance(a.get("text", ""), str)
                      for q, a in given.items()))
        for claim in prev.get("claims", []) if ok else []:
            Claim.model_validate(claim)
    except (ValueError, AttributeError):  # bad JSON or bad claims (pydantic errors are ValueErrors)
        ok = False
    if not ok:
        raise HTTPException(422, {"error": 'Malformed answers: send {"question id": {"answer": "yes" or "no", "text": "..."}}.'})
    return prev, given


app.mount("/", StaticFiles(directory=ROOT / "public", html=True, check_dir=False))  # local dev; Vercel serves public/ itself
