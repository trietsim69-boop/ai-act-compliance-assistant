import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "corpus"

# DeepSeek speaks the OpenAI API; any OpenAI-compatible endpoint works.
LLM_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or "https://api.deepseek.com"
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
