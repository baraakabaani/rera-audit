"""Customer document upload + extraction, and the audit matcher."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..config import ALLOW_LOCAL_SAMPLES, ALLOWED_DOC_EXT, MAX_UPLOAD_MB, SAMPLE_DOCUMENTS_DIR
from ..schemas import ExtractedDoc, MatchOverride, MatchResult, RunMatchRequest
from ..services.document_extractor import extract_document
from ..services.matcher import apply_override, run_match
from ..store import store

router = APIRouter(prefix="/api", tags=["documents"])


def _get(sid: str):
    try:
        return store.get(sid)
    except KeyError:
        raise HTTPException(404, "session not found")


def _safe_rel(name: str) -> str:
    name = (name or "").replace("\\", "/")
    parts = [p for p in name.split("/") if p not in ("", ".", "..")]
    return "/".join(parts) or "file"


@router.post("/session/{sid}/documents", response_model=list[ExtractedDoc])
async def upload_documents(
    sid: str,
    files: list[UploadFile] = File(...),    # noqa: B008
    paths: list[str] = Form(default=[]),    # noqa: B008
) -> list[ExtractedDoc]:
    sess = _get(sid)
    added: list[ExtractedDoc] = []
    limit = MAX_UPLOAD_MB * 1024 * 1024

    for idx, up in enumerate(files):
        rel = _safe_rel(paths[idx] if idx < len(paths) and paths[idx] else up.filename)
        ext = Path(rel).suffix.lower()
        if ext not in ALLOWED_DOC_EXT:
            added.append(
                ExtractedDoc(
                    id=f"skip{idx}", filename=Path(rel).name, rel_path=rel, ext=ext,
                    size_bytes=0, error=f"unsupported file type {ext or '(none)'}",
                )
            )
            continue
        dest = sess.docs_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as fh:
            shutil.copyfileobj(up.file, fh)
        if dest.stat().st_size > limit:
            dest.unlink(missing_ok=True)
            added.append(
                ExtractedDoc(
                    id=f"big{idx}", filename=dest.name, rel_path=rel, ext=ext,
                    size_bytes=0, error=f"file exceeds {MAX_UPLOAD_MB} MB limit",
                )
            )
            continue
        doc = extract_document(dest, rel)
        sess.documents.append(doc)
        added.append(doc)

    sess.match = None
    return added


@router.post("/session/{sid}/documents/load-samples", response_model=list[ExtractedDoc])
def load_sample_documents(sid: str) -> list[ExtractedDoc]:
    if not ALLOW_LOCAL_SAMPLES:
        raise HTTPException(403, "local samples are disabled")
    sess = _get(sid)
    base = Path(SAMPLE_DOCUMENTS_DIR)
    if not base.exists():
        raise HTTPException(404, f"sample documents folder not found: {base}")
    added: list[ExtractedDoc] = []
    for src in sorted(base.rglob("*")):
        if not src.is_file() or src.suffix.lower() not in ALLOWED_DOC_EXT:
            continue
        rel = _safe_rel(str(src.relative_to(base)))
        dest = sess.docs_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        doc = extract_document(dest, rel)
        sess.documents.append(doc)
        added.append(doc)
    sess.match = None
    return added


@router.get("/session/{sid}/documents", response_model=list[ExtractedDoc])
def list_documents(sid: str) -> list[ExtractedDoc]:
    return _get(sid).documents


@router.delete("/session/{sid}/documents")
def clear_documents(sid: str) -> dict:
    sess = _get(sid)
    sess.documents.clear()
    sess.match = None
    if sess.docs_dir.exists():
        shutil.rmtree(sess.docs_dir, ignore_errors=True)
    return {"ok": True}


@router.post("/session/{sid}/match", response_model=MatchResult)
def run_matcher(sid: str, body: RunMatchRequest | None = None) -> MatchResult:
    sess = _get(sid)
    if not sess.requirements:
        raise HTTPException(400, "upload the requirements checklist first")
    if not sess.documents:
        raise HTTPException(400, "upload customer documents first")
    use_llm = body.use_llm if body else True
    sess.match = run_match(sess.requirements.items, sess.documents, use_llm=use_llm)
    return sess.match


@router.get("/session/{sid}/match", response_model=MatchResult)
def get_matcher(sid: str) -> MatchResult:
    sess = _get(sid)
    if not sess.match:
        raise HTTPException(404, "no match result yet - run the matcher")
    return sess.match


@router.patch("/session/{sid}/match/{ref}", response_model=MatchResult)
def override_match(sid: str, ref: str, body: MatchOverride) -> MatchResult:
    sess = _get(sid)
    if not sess.match:
        raise HTTPException(400, "run the matcher first")
    try:
        return apply_override(
            sess.match, sess.documents, ref,
            status=body.status, comment=body.comment,
            add_doc_ids=body.add_doc_ids, remove_doc_ids=body.remove_doc_ids,
        )
    except KeyError:
        raise HTTPException(404, f"requirement {ref} not found")
