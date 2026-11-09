"""Runtime configuration. Values come from environment variables (or the repo-root .env file)."""
from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = REPO_ROOT / "data"
LOG_DIR = REPO_ROOT / "logs"
VAR_DIR = BACKEND_DIR / "var"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv is optional
        return
    load_dotenv(REPO_ROOT / ".env", override=False)


_load_dotenv()


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


# --- LLM -------------------------------------------------------------------------------------
# Pinned model ID (README section 9: never use -latest aliases).
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
# Free tier: an API key from Google AI Studio (no billing needed).
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
# Vertex AI (needs a Google Cloud project with billing or credits): USE_VERTEX=true + GCP_PROJECT.
USE_VERTEX = _flag("USE_VERTEX")
GCP_PROJECT = os.getenv("GCP_PROJECT", "").strip()
GCP_REGION = os.getenv("GCP_REGION", "global").strip()
# Force the deterministic offline mode (no LLM calls), e.g. for tests and the eval baseline.
PUNCA_OFFLINE = _flag("PUNCA_OFFLINE")
LLM_TIMEOUT_MS = int(os.getenv("LLM_TIMEOUT_MS", "30000"))

# --- Storage ---------------------------------------------------------------------------------
STORE_PATH = Path(os.getenv("PUNCA_STORE", str(VAR_DIR / "store.json")))

# --- Diagnosis (README section 8) ------------------------------------------------------------
MAX_PROBES = int(os.getenv("PUNCA_MAX_PROBES", "5"))
SOLID = 0.7      # pKnown at or above this = solid (green)
GAP = 0.4        # pKnown below this = gap (red); in between = shaky (amber)
P_INIT = 0.5     # prior pKnown for an untested concept
P_GUESS = 0.25   # four-option multiple choice
P_SLIP = 0.1
P_LEARN = 0.05

# --- Circles and lecturer analytics (README sections 10 and 11) -----------------------------
MIN_GROUP_SIZE = 3
MAX_GROUP_SIZE = 6
MIN_COUNT_SHOWN = 3   # aggregates below this are hidden from lecturers
