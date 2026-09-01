"""Pydantic models shared across the API."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Status = Literal["Received", "Partial", "Pending", "Not applicable"]
MatchMethod = Literal["keyword", "folder", "filename", "llm", "manual", "learned"]


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------
class RequirementItem(BaseModel):
    ref: str = Field(..., description='Reference number, e.g. "1.2"')
    section: int
    section_title: str
    requirement: str
    evidence_type: str = ""
    responsible: str = ""                   # "Responsible Department" column, if present
    sheet_status: str = "Pending"          # status as authored in the source sheet
    remarks: str = ""
    row: int = 0                            # 1-based row in the source sheet


class RequirementsResult(BaseModel):
    filename: str
    sheet: str
    available_sheets: list[str] = []        # other requirement sheets in the same file
    client_name: str = ""
    audit_period: str = ""
    items: list[RequirementItem]
    section_titles: dict[int, str] = {}


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
class TablePreview(BaseModel):
    sheet: str = ""
    columns: list[str] = []
    rows: list[list[str]] = []


class ExtractedDoc(BaseModel):
    id: str
    filename: str
    rel_path: str
    folder: str = ""                        # top-level folder (section grouping)
    ext: str
    size_bytes: int
    page_count: int = 0
    sheet_names: list[str] = []
    char_count: int = 0
    text_excerpt: str = ""
    keywords: list[str] = []
    tables: list[TablePreview] = []
    error: str = ""


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------
class MatchedFile(BaseModel):
    doc_id: str
    filename: str
    score: float
    method: MatchMethod


class MatchRow(BaseModel):
    ref: str
    section: int
    section_title: str
    requirement: str
    evidence_type: str
    row: int = 0                    # 1-based row in the source requirements sheet
    status: Status
    confidence: float
    matched_files: list[MatchedFile] = []
    comment: str = ""
    llm_rationale: str = ""
    learned_note: str = ""          # set when past auditor corrections influenced this row
    overridden: bool = False


class MatchStats(BaseModel):
    total: int
    received: int
    partial: int
    pending: int
    not_applicable: int
    llm_used: bool = False
    learned_applied: int = 0        # rows nudged by past auditor corrections


class MatchResult(BaseModel):
    stats: MatchStats
    rows: list[MatchRow]
    unmatched_docs: list[str] = []          # doc ids not mapped to any requirement


class MatchOverride(BaseModel):
    status: Optional[Status] = None
    comment: Optional[str] = None
    add_doc_ids: list[str] = []
    remove_doc_ids: list[str] = []


class RunMatchRequest(BaseModel):
    use_llm: bool = True


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
class EmailDraft(BaseModel):
    subject: str
    to: str = ""
    body_text: str
    body_html: str


# ---------------------------------------------------------------------------
# Workbook
# ---------------------------------------------------------------------------
class EntityContext(BaseModel):
    jop_name: str = ""
    developer_name: str = ""
    developer_license: str = ""
    developer_license_expiry: str = ""
    developer_address: str = ""
    management_company: str = ""
    management_company_license: str = ""
    place: str = "Dubai, United Arab Emirates"
    period_end: str = ""
    period_start: str = ""
    prepared_by: str = ""
    sources: dict[str, str] = {}          # field -> filename it was read from


class WorkbookRequest(BaseModel):
    project_name: Optional[str] = None
    period_end: Optional[str] = None      # e.g. "30 June 2026" or "2026-06-30"
    developer_name: Optional[str] = None
    management_company: Optional[str] = None
    prepared_by: Optional[str] = None


class CellWrite(BaseModel):
    sheet: str
    cell: str
    value: str
    source: str


class WorkbookReport(BaseModel):
    filename: str
    sheets_touched: list[str]
    writes: list[CellWrite]
    formulas_written: int
    warnings: list[str] = []
    context: Optional[EntityContext] = None


class RequirementsFilledReport(BaseModel):
    filename: str
    rows_written: int
    status_counts: dict[str, int] = {}
    period_updated: str = ""


class SessionInfo(BaseModel):
    id: str
    has_requirements: bool
    has_template: bool
    document_count: int
    has_match: bool
    has_workbook: bool
