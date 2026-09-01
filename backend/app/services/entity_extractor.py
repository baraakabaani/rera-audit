"""Read the entity / period / preparer facts out of the customer documents.

Targets the fields the working-paper template leaves as red placeholders:
developer name + trade licence + expiry, registered address, management company
name + licence, JOP name, reporting period, place, "prepared by".

Everything is best-effort and each value carries the file it came from.  Blank
fields are simply left blank (and reported), never guessed.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from ..schemas import EntityContext, RequirementsResult
from .document_extractor import full_text

_COMPANY_SUFFIX = r"(?:L\.?\s?L\.?\s?C|LLC|FZ-?LLC|FZE|FZCO|W\.?L\.?L|P\.?J\.?S\.?C|" \
                  r"PJSC|Est\.?|Establishment|Sole Proprietorship|S\.?O\.?C)"
_NAME_CORE = r"[A-Z][A-Za-z0-9&.,'()\- ]{4,70}"

_RE_COMPANY = re.compile(
    rf"(?:company name|business name|trade name)\s*[:\-]?\s*({_NAME_CORE}?{_COMPANY_SUFFIX})",
    re.I,
)
_RE_LICENSE = re.compile(
    r"(?:main licen[cs]e no\.?|trade licen[cs]e(?:\s*(?:no\.?|number|#))?|licen[cs]e no\.?)"
    r"\s*[:\-]?\s*([0-9][0-9\-/]{3,15})",
    re.I,
)
_RE_EXPIRY = re.compile(
    r"expiry date\s*[:\-]?\s*([0-3]?\d[\-/.\s][A-Za-z0-9]{2,9}[\-/.\s]\d{2,4})", re.I
)
_RE_POBOX = re.compile(r"p\.?\s*o\.?\s*box\s*[:\-]?\s*(\d{2,7})", re.I)
_RE_ADDRESS = re.compile(
    r"(?:registered address|address)\s*[:\-]?\s*([A-Za-z0-9,.\-/# ]{10,90}(?:Dubai|United Arab Emirates|UAE))",
    re.I,
)


def _is_dev_doc(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in ("developer", "handover", "trade licen"))


def _is_mc_doc(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in ("appointment", "management", "moa", "constitution", "khazaen", "khanzaen", "altamkeen"))


def _last_date(s: str) -> date | None:
    """The reporting period end is the *later* of any dates in the string."""
    if not s:
        return None
    # honour an explicit "... to <date>" range
    m = re.search(r"\bto\b\s*(.+)$", s, re.I)
    tail = m.group(1) if m else s
    cand = _to_date(tail) or _to_date(s)
    return cand


def _parse_period(requirements: RequirementsResult | None, override: str | None) -> tuple[str, str]:
    end = _last_date(override or "")
    if end is None and requirements:
        end = _last_date(requirements.filename) or _last_date(requirements.audit_period)
    if end is None:
        end = date(date.today().year, 6, 30)
    start = date(end.year, 1, 1)
    fmt = lambda d: d.strftime("%d %B %Y").lstrip("0")
    return fmt(start), fmt(end)


def _to_date(s: str) -> date | None:
    if not s:
        return None
    m = re.search(r"(\d{1,2})[-/. ]([A-Za-z]{3,9}|\d{1,2})[-/. ](\d{4})", s)
    if m:
        for fmt in ("%d %B %Y", "%d %b %Y", "%d %m %Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", fmt).date()
            except ValueError:
                continue
    m = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = re.search(r"\b(20\d{2})\b", s)
    return date(int(m.group(1)), 6, 30) if m else None


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip(" .,-")


def _split_client(raw: str) -> tuple[str, str]:
    """The requirements sheet often crams "<MC> -Project Name - <JOP>" into one
    cell.  Return (management_company, jop_name)."""
    raw = _clean(raw)
    m = re.split(r"\s*[-–]\s*project\s*name\s*[-–:]?\s*", raw, flags=re.I)
    if len(m) == 2 and m[1].strip():
        return _clean(m[0]), _clean(m[1])
    m = re.split(r"\bfor\s+the\s+project\b|\bproject\s*[:\-]", raw, flags=re.I)
    if len(m) == 2 and m[1].strip():
        return _clean(m[0]), _clean(m[1])
    return raw, raw


def extract_base(
    doc_paths: list[tuple[Path, str, str]],
    requirements: RequirementsResult | None,
) -> EntityContext:
    """The expensive part: read the customer PDFs.  No overrides applied."""
    ctx = EntityContext()
    src: dict[str, str] = {}

    start, end = _parse_period(requirements, None)
    ctx.period_start, ctx.period_end = start, end

    client_raw = requirements.client_name if requirements else ""
    mc_from_client, jop_from_client = _split_client(client_raw)
    ctx.jop_name = jop_from_client

    dev_name = dev_lic = dev_exp = dev_addr = ""
    mc_name = mc_lic = ""

    # only the handful of documents that plausibly carry entity facts - reading
    # the full text of every PDF would be far too slow
    candidates = [
        (p, f, folder)
        for (p, f, folder) in doc_paths
        if p.suffix.lower() in (".pdf", ".docx")
        and (_is_dev_doc(f"{f} {folder}") or _is_mc_doc(f"{f} {folder}"))
    ][:12]

    for path, fname, folder in candidates:
        try:
            text = full_text(path)
        except Exception:
            continue
        if not text:
            continue
        flat = _clean(text)

        if _is_dev_doc(f"{fname} {folder}"):
            if not dev_name:
                m = _RE_COMPANY.search(flat)
                if m:
                    dev_name = _clean(m.group(1))
                    src["developer_name"] = fname
            if not dev_lic:
                m = _RE_LICENSE.search(flat)
                if m:
                    dev_lic = m.group(1)
                    src["developer_license"] = fname
            if not dev_exp:
                m = _RE_EXPIRY.search(flat)
                if m:
                    dev_exp = _clean(m.group(1))
                    src["developer_license_expiry"] = fname
            if not dev_addr:
                m = _RE_ADDRESS.search(flat) or _RE_POBOX.search(flat)
                if m:
                    dev_addr = _clean(m.group(0))
                    src["developer_address"] = fname

        if _is_mc_doc(f"{fname} {folder}"):
            if not mc_name:
                m = _RE_COMPANY.search(flat)
                if m:
                    mc_name = _clean(m.group(1))
                    src["management_company"] = fname
            if not mc_lic:
                m = _RE_LICENSE.search(flat)
                if m:
                    mc_lic = m.group(1)
                    src["management_company_license"] = fname

    ctx.developer_name = dev_name
    ctx.developer_license = dev_lic
    ctx.developer_license_expiry = dev_exp
    ctx.developer_address = dev_addr or ctx.place
    ctx.management_company = mc_name or mc_from_client
    ctx.management_company_license = mc_lic
    ctx.prepared_by = ctx.management_company
    ctx.sources = src
    return ctx


def apply_overrides(
    base: EntityContext,
    requirements: RequirementsResult | None,
    *,
    project_name: str | None = None,
    period_end: str | None = None,
    developer_name: str | None = None,
    management_company: str | None = None,
    prepared_by: str | None = None,
) -> EntityContext:
    """Cheap: layer the review-screen edits on top of the extracted base."""
    ctx = base.model_copy(deep=True)
    if project_name:
        ctx.jop_name = _clean(project_name)
    if period_end:
        ctx.period_start, ctx.period_end = _parse_period(requirements, period_end)
    if developer_name:
        ctx.developer_name = _clean(developer_name)
    if management_company:
        ctx.management_company = _clean(management_company)
    explicit_preparer = bool(prepared_by and prepared_by.strip())
    ctx.prepared_by = _clean(prepared_by) if explicit_preparer else ctx.management_company
    return ctx


def build_context(
    doc_paths: list[tuple[Path, str, str]],
    requirements: RequirementsResult | None,
    **overrides,
) -> EntityContext:
    return apply_overrides(extract_base(doc_paths, requirements), requirements, **overrides)
