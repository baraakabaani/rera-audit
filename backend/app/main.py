"""FastAPI application entry point.

Dev:   uvicorn app.main:app --reload --port 8000
Prod:  uvicorn app.main:app --host 0.0.0.0 --port $PORT   (single worker - the
       session store is in-memory)
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import ALLOWED_ORIGINS, LLM_ENABLED, LLM_WORKBOOK, STATIC_DIR
from .routers import documents, learning, outputs, sessions
from .services import llm_client

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="RERA Audit Automation API",
    version="0.1.0",
    description=(
        "Ingest audit requirements + customer documents, detect missing items, "
        "draft the client email, and generate a populated working-paper workbook."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"http://localhost:\d+|http://127\.0\.0\.1:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(documents.router)
app.include_router(outputs.router)
app.include_router(learning.router)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_enabled": LLM_ENABLED,
        "llm_available": llm_client.available(),
        "llm_provider": llm_client.provider_name(),
        "llm_workbook": LLM_WORKBOOK and llm_client.available(),
    }


# --------------------------------------------------------------------------- #
# Serve the built React app (production single-service deploy).
# In local dev STATIC_DIR won't exist - the Vite dev server handles the UI.
# --------------------------------------------------------------------------- #
if (STATIC_DIR / "index.html").is_file():
    if (STATIC_DIR / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    _INDEX = STATIC_DIR / "index.html"

    @app.get("/", include_in_schema=False)
    def _root() -> FileResponse:
        return FileResponse(_INDEX)

    @app.get("/{full_path:path}", include_in_schema=False)
    def _spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_INDEX)          # client-side routing fallback
else:
    logging.info("STATIC_DIR %s not found - API only (use the Vite dev server for the UI)", STATIC_DIR)
