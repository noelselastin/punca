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
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
GEMINI_FALLBACK_MODELS = [m.strip() for m in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-3.1-flash-lite").split(",") if m.strip()]
LLM_COOLDOWN_S = int(os.getenv("LLM_COOLDOWN_S", "60"))
LLM_DAILY_COOLDOWN_S = int(os.getenv("LLM_DAILY_COOLDOWN_S", "3600"))
GEMINI_ROUTING_MODEL = os.getenv("GEMINI_ROUTING_MODEL", GEMINI_MODEL).strip()
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
USE_VERTEX = _flag("USE_VERTEX")
GCP_PROJECT = os.getenv("GCP_PROJECT", "").strip()
GCP_REGION = os.getenv("GCP_REGION", "global").strip()
PUNCA_OFFLINE = _flag("PUNCA_OFFLINE")
LLM_TIMEOUT_MS = int(os.getenv("LLM_TIMEOUT_MS", "20000"))

# --- Google Workspace (live sign-in) ---------------------------------------------------------
# OAuth client ID (type "Web application") from Google Cloud Console. Empty = live Google sign-in
# is off and Punca uses its built-in workspace store. See docs/google-setup.md.
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
# Time zone used for Calendar events whose start time has no UTC offset.
PUNCA_TIMEZONE = os.getenv("PUNCA_TIMEZONE", "Asia/Kuala_Lumpur").strip() or "Asia/Kuala_Lumpur"

# --- Storage ---------------------------------------------------------------------------------
STORE_PATH = Path(os.getenv("PUNCA_STORE", str(VAR_DIR / "store.json")))

# --- Diagnosis (5-10 confidence-weighted questions) ------------------------------------------
MIN_PROBES = int(os.getenv("PUNCA_MIN_PROBES", "5"))
MAX_PROBES = int(os.getenv("PUNCA_MAX_PROBES", "10"))
SOLID = 0.7      # pKnown at or above this = solid (green)
GAP = 0.4        # pKnown below this = gap (red); in between = shaky (amber)
P_INIT = 0.5     # prior pKnown for an untested concept
P_GUESS = 0.25   # four-option multiple choice
P_SLIP = 0.1
P_LEARN = 0.05

# --- Study Circles ---------------------------------------------------------------------------
MIN_GROUP_SIZE = 3
MAX_GROUP_SIZE = 6
