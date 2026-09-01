"""Email draft, entity context, populated workbook + filled requirements checklist."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse

from ..schemas import (
    EmailDraft,
    EntityContext,
    RequirementsFilledReport,
    WorkbookReport,
    WorkbookRequest,
)
from ..services.email_generator import build_email, to_eml
from ..services.entity_extractor import apply_overrides, extract_base
from ..services.financials import parse_financials
from ..services.requirements_filler import fill_requirements
from ..services.workbook_generator import generate_workbook
from ..store import store

router = APIRouter(prefix="/api", tags=["outputs"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _get(sid: str):
    try:
        return store.get(sid)
    except KeyError:
        raise HTTPException(404, "session not found")


def _require_match(sess):
    if not sess.match:
        raise HTTPException(400, "run the audit matcher first")


def _doc_inputs(sess):
    return [
        (sess.docs_dir / d.rel_path, d.filename, d.folder)
        for d in sess.documents
        if not d.id.startswith(("skip", "big"))
    ]


def _context(sess, body: WorkbookRequest | None) -> EntityContext:
    b = body or WorkbookRequest()
    # the expensive PDF read is cached per document count; edits layer on cheaply
    base = sess.context_cache.get(len(sess.documents))
    if base is None:
        base = extract_base(_doc_inputs(sess), sess.requirements)
        sess.context_cache[len(sess.documents)] = base
    return apply_overrides(
        base,
        sess.requirements,
        project_name=b.project_name,
        period_end=b.period_end,
        developer_name=b.developer_name,
        management_company=b.management_company,
        prepared_by=b.prepared_by,
    )


# --------------------------------------------------------------------------- #
# email
# --------------------------------------------------------------------------- #
@router.get("/session/{sid}/email", response_model=EmailDraft)
def get_email(sid: str) -> EmailDraft:
    sess = _get(sid)
    _require_match(sess)
    return build_email(sess.match, sess.requirements)


@router.get("/session/{sid}/email/download")
def download_email(sid: str, fmt: str = "eml") -> Response:
    sess = _get(sid)
    _require_match(sess)
    draft = build_email(sess.match, sess.requirements)
    if fmt == "txt":
        return Response(
            draft.body_text,
            media_type="text/plain",
            headers={"Content-Disposition": 'attachment; filename="client-followup.txt"'},
        )
    return Response(
        to_eml(draft),
        media_type="message/rfc822",
        headers={"Content-Disposition": 'attachment; filename="client-followup.eml"'},
    )


# --------------------------------------------------------------------------- #
# entity context (dates / names / place read from the customer files)
# --------------------------------------------------------------------------- #
@router.get("/session/{sid}/context", response_model=EntityContext)
def get_context(sid: str) -> EntityContext:
    sess = _get(sid)
    return _context(sess, None)


# --------------------------------------------------------------------------- #
# populated working-paper workbook
# --------------------------------------------------------------------------- #
@router.post("/session/{sid}/workbook", response_model=WorkbookReport)
def build_workbook(sid: str, body: WorkbookRequest | None = None) -> WorkbookReport:
    sess = _get(sid)
    _require_match(sess)
    if not sess.template_path:
        raise HTTPException(400, "upload the master template first")

    financials = parse_financials(_doc_inputs(sess))
    context = _context(sess, body)

    out_path = sess.dir / "populated_workbook.xlsx"
    try:
        report = generate_workbook(
            sess.template_path, out_path, sess.match, sess.requirements, financials,
            project_name=body.project_name if body else None,
            period_end=body.period_end if body else None,
            context=context,
            preparer_explicit=bool(body and body.prepared_by),
            doc_paths=_doc_inputs(sess),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"workbook generation failed: {exc}")
    sess.workbook_path = out_path
    return report


@router.get("/session/{sid}/workbook/download")
def download_workbook(sid: str) -> FileResponse:
    sess = _get(sid)
    if not sess.workbook_path or not sess.workbook_path.exists():
        raise HTTPException(404, "workbook not generated yet")
    return FileResponse(
        sess.workbook_path, media_type=_XLSX, filename="RERA_Interim_Audit_Workpapers.xlsx"
    )


# --------------------------------------------------------------------------- #
# filled requirements checklist
# --------------------------------------------------------------------------- #
@router.post("/session/{sid}/requirements-filled", response_model=RequirementsFilledReport)
def build_requirements_filled(sid: str, body: WorkbookRequest | None = None) -> RequirementsFilledReport:
    sess = _get(sid)
    _require_match(sess)
    if not sess.requirements_path:
        raise HTTPException(400, "upload the requirements checklist first")

    context = _context(sess, body)
    out_path = sess.dir / "requirements_filled.xlsx"
    try:
        info = fill_requirements(
            sess.requirements_path, out_path, sess.match, context,
            sheet_name=sess.requirements.sheet if sess.requirements else None,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"could not fill the requirements checklist: {exc}")
    sess.requirements_filled_path = out_path
    return RequirementsFilledReport(**info)


@router.get("/session/{sid}/requirements-filled/download")
def download_requirements_filled(sid: str) -> FileResponse:
    sess = _get(sid)
    path = getattr(sess, "requirements_filled_path", None)
    if not path or not path.exists():
        raise HTTPException(404, "filled checklist not generated yet")
    return FileResponse(path, media_type=_XLSX, filename="Requirements_Checklist_Filled.xlsx")
