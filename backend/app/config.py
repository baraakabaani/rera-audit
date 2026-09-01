"""Runtime configuration.

All settings are plain environment variables so the app runs with zero config in
development.  Copy ``.env.example`` to ``.env`` (loaded automatically) to override.
"""
from __future__ import annotations

import os
from pathlib import Path

try:  # optional - only needed if a .env file is present
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


BASE_DIR = Path(__file__).resolve().parent.parent          # .../backend
PROJECT_ROOT = BASE_DIR.parent                             # .../rera site

# Persisted files (uploads, generated workbooks, the learning store). On Railway
# point STORAGE_DIR at a mounted Volume (e.g. /data) so it survives redeploys;
# fall back to a local folder if that path is not writable.
_want_storage = Path(os.environ.get("STORAGE_DIR", BASE_DIR / "storage"))
try:
    _want_storage.mkdir(parents=True, exist_ok=True)
    _probe = _want_storage / ".write-test"
    _probe.write_text("ok")
    _probe.unlink()
    STORAGE_DIR = _want_storage
except OSError:
    STORAGE_DIR = BASE_DIR / "storage"
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Built React app served by FastAPI in production (single Railway service).
STATIC_DIR = Path(os.environ.get("STATIC_DIR", BASE_DIR.parent / "frontend" / "dist"))

# ---------------------------------------------------------------------------
# CORS / frontend
# ---------------------------------------------------------------------------
# Single-service deploy is same-origin so CORS is a non-issue; these entries
# only matter when the frontend is hosted separately.
_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
ALLOWED_ORIGINS = [o.strip() for o in _origins.split(",") if o.strip()]
_railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()
if _railway_domain:
    ALLOWED_ORIGINS.append(f"https://{_railway_domain}")

# ---------------------------------------------------------------------------
# LLM - entirely optional, used for (a) match reconciliation and (b) an
# "understand each sheet, write the exact cells" workbook-mapping pass.
# ---------------------------------------------------------------------------
# Everything works offline with deterministic logic.  Provide ONE of:
#   GROQ_API_KEY      -> free, OpenAI-compatible (default model llama-3.3-70b)
#   OPENAI_API_KEY    -> OpenAI or any OpenAI-compatible endpoint (OPENAI_BASE_URL)
#   ANTHROPIC_API_KEY -> Claude (or an `ant auth login` profile)
LLM_ENABLED = _bool("LLM_ENABLED", True)
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "auto").strip().lower()  # auto|groq|openai|anthropic|off
LLM_MODEL = os.environ.get("LLM_MODEL", "").strip()                    # blank -> provider default
LLM_EXTRACT_MODEL = os.environ.get("LLM_EXTRACT_MODEL", "").strip()    # blank -> LLM_MODEL / default
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "").strip()
LLM_WORKBOOK = _bool("LLM_WORKBOOK", True)     # let the LLM map the annexure sheets
LLM_MAX_DOCS = int(os.environ.get("LLM_MAX_DOCS", "80"))
LLM_SNIPPET_CHARS = int(os.environ.get("LLM_SNIPPET_CHARS", "900"))

_PROVIDER_DEFAULT_MODEL = {
    "groq": "llama-3.3-70b-versatile",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-opus-5",
}

# ---------------------------------------------------------------------------
# Local sample data (developer convenience)
# ---------------------------------------------------------------------------
ALLOW_LOCAL_SAMPLES = _bool("ALLOW_LOCAL_SAMPLES", True)
SAMPLE_REQUIREMENTS = os.environ.get(
    "SAMPLE_REQUIREMENTS",
    str(PROJECT_ROOT / "OA_DLD_RERA_Interim Audit_Requirements_PROA_30 June 2026.xlsx"),
)
SAMPLE_TEMPLATE = os.environ.get("SAMPLE_TEMPLATE", str(PROJECT_ROOT / "template.xlsx"))
SAMPLE_DOCUMENTS_DIR = os.environ.get(
    "SAMPLE_DOCUMENTS_DIR",
    str(Path.home() / "Desktop" / "rerea" / "annual interm documents"),
)

# ---------------------------------------------------------------------------
# Upload limits
# ---------------------------------------------------------------------------
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "50"))
ALLOWED_DOC_EXT = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv"}
