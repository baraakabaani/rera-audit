"""Match customer documents against requirement line items.

Two stages:

1. **Deterministic** keyword / folder / filename scoring (always runs, offline).
2. **LLM reconciliation** (optional) - an Anthropic model reviews the borderline
   rows and the unmatched documents and proposes corrections.  Skipped silently
   when no credential is configured or the call fails.
"""
from __future__ import annotations

import re
from collections import Counter

from ..config import LLM_ENABLED
from ..schemas import (
    ExtractedDoc,
    MatchedFile,
    MatchResult,
    MatchRow,
    MatchStats,
    RequirementItem,
)
from . import feedback, llm

# --------------------------------------------------------------------------- #
# Domain vocabulary - expands a requirement's literal words into the language
# that actually appears in customer files.
# --------------------------------------------------------------------------- #
SYNONYMS: dict[str, list[str]] = {
    "trial balance": ["trial", "balance", "tb", "general ledger", "gl", "chart of accounts"],
    "bank statement": ["bank", "statement", "adcb", "enbd", "emirates nbd", "mashreq",
                       "rakbank", "cbd", "account statement", "ledger"],
    "bank reconciliation": ["reconciliation", "reconcile", "recon", "unrealized", "outstanding cheque"],
    "reserve fund": ["reserve", "fund", "rf", "sinking", "replacement"],
    "general fund": ["general", "fund", "gf", "operating"],
    "service charge": ["service charge", "levy", "collection", "mollak", "invoice", "billing"],
    "budget": ["budget", "approved budget", "variance", "forecast", "budget vs actual"],
    "agm": ["agm", "annual general meeting", "minutes", "attendance", "quorum"],
    "board resolution": ["board", "resolution", "directors", "bom", "bod"],
    "registration": ["registration", "certificate", "rera", "dld", "trakheesi", "membership"],
    "constitution": ["constitution", "articles", "association", "moa", "bylaws", "jop"],
    "management company": ["management company", "mc", "appointment", "contract", "agreement",
                          "khazaen", "khanzaen", "altamkeen"],
    "insurance": ["insurance", "policy", "premium", "liability", "cover", "omega"],
    "vat": ["vat", "fta", "tax return", "tax registration", "trn"],
    "utilities": ["dewa", "empower", "sewa", "etisalat", "du", "telecom", "utility", "chilled water"],
    "payroll": ["payroll", "wps", "salary", "gratuity", "eosb"],
    "invoice": ["invoice", "voucher", "payment", "receipt", "lpo", "purchase order"],
    "contract": ["contract", "agreement", "sla", "tender", "quotation", "rfq", "procurement"],
    "arrears": ["arrears", "aging", "ageing", "outstanding", "debtors", "receivable", "overdue"],
    "receivable": ["receivable", "debtors", "collection register", "aging"],
    "payable": ["payable", "creditors", "supplier", "vendor", "soa", "statement of account"],
    "accrual": ["accrual", "accrued", "provision", "prepaid"],
    "petty cash": ["petty cash", "cash", "custodian", "float"],
    "fixed deposit": ["fixed deposit", "term deposit", "fd", "investment", "wakala"],
    "kyc": ["kyc", "aml", "ubo", "beneficial owner", "passport", "emirates id", "shareholding",
           "shareholder", "trade license"],
    "handover": ["handover", "snag", "snagging", "defect liability", "dlp", "developer"],
    "civil defence": ["civil defence", "civil defense", "dcd", "fire", "noc", "safety"],
    "legal": ["legal", "litigation", "dispute", "case", "court", "claim", "counsel"],
    "crypto": ["crypto", "cryptocurrency", "bitcoin", "digital asset", "token", "wallet"],
    "master community": ["master community", "nakheel", "emaar", "community charge"],
}

_TOKEN_RE = re.compile(r"[a-z][a-z0-9&/\-]{2,}")
_REF_IN_PATH = re.compile(r"(?<!\d)(\d{1,2}\.\d{1,3}(?:\.\d{1,3})?)(?!\d)")
_SECTION_IN_FOLDER = re.compile(r"section\s*[-\s]*?(\d{1,2})", re.I)

_STOP = {
    "and", "or", "the", "for", "with", "from", "any", "all", "per", "current", "valid",
    "copy", "original", "certified", "signed", "dated", "date", "list", "schedule",
    "report", "statement", "document", "evidence", "type", "provided", "pending",
    "most", "recent", "applicable", "each", "other", "its", "your", "our",
}

# scoring weights
W_FILENAME = 3.0
W_FOLDER = 1.6
W_BODY = 1.0
WEAK_FLOOR = 0.18       # min score for a learned nudge to raise a doc to "weak"


def _tok(text: str) -> list[str]:
    return [t.strip("-/&") for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP and len(t) > 2]


def _requirement_terms(item: RequirementItem) -> Counter:
    base = f"{item.requirement} {item.evidence_type} {item.section_title}"
    terms = Counter(_tok(base))
    low = base.lower()
    for concept, words in SYNONYMS.items():
        if concept in low or any(w in low for w in words):
            for w in words:
                for piece in _tok(w):
                    terms[piece] += 1
    return terms


def _doc_terms(doc: ExtractedDoc) -> tuple[dict[str, float], set[str]]:
    """Return (weighted term map, folder-token set)."""
    weighted: dict[str, float] = Counter()
    folder_toks = set(_tok(doc.folder))
    for t in _tok(doc.filename):
        weighted[t] += W_FILENAME
    for t in folder_toks:
        weighted[t] += W_FOLDER
    for t in list(doc.keywords) + _tok(doc.text_excerpt):
        if t in folder_toks:            # already counted at folder weight
            continue
        weighted[t] += W_BODY
    return weighted, folder_toks


def _folder_section(doc: ExtractedDoc) -> int | None:
    m = _SECTION_IN_FOLDER.search(f"{doc.folder} {doc.rel_path}")
    return int(m.group(1)) if m else None


class _Cand:
    __slots__ = ("score", "method", "quality", "hits", "learned_reason")

    def __init__(self, score: float, method: str, quality: str, hits: list[str]):
        self.score = score
        self.method = method
        self.quality = quality      # "strong" | "weak" | "none"
        self.hits = hits
        self.learned_reason = ""


def _score(req_terms: Counter, doc_w: dict[str, float], item: RequirementItem, doc: ExtractedDoc) -> _Cand:
    hits = {t: v for t, v in doc_w.items() if t in req_terms}
    # discount pure section-title words - they match every item in the section
    section_words = set(_tok(item.section_title))
    signal = {t: v for t, v in hits.items() if t not in section_words}
    n = len(signal)
    raw = sum(min(v, W_FILENAME) for v in signal.values())
    denom = max(5.0, len(req_terms) * 1.1)
    kw = raw / denom

    folder_match = bool(item.section) and _folder_section(doc) == item.section
    path_refs = set(_REF_IN_PATH.findall(doc.rel_path))
    ref_match = item.ref in path_refs or any(r.startswith(item.ref + ".") for r in path_refs)

    score = kw * (1.6 if folder_match else 1.0) + (0.05 if folder_match else 0.0)
    method = "keyword"
    if folder_match:
        method = "folder"
    if ref_match:
        score += 1.0
        method = "filename"

    if ref_match or (n >= 2 and kw >= 0.25 and folder_match) or (n >= 3 and kw >= 0.45):
        quality = "strong"
    elif (n >= 2 and kw >= 0.18) or (n >= 3 and kw >= 0.12):
        quality = "weak"
    else:
        quality = "none"

    return _Cand(
        round(min(score, 2.5), 3),
        method,
        quality,
        sorted(signal, key=signal.get, reverse=True)[:6],
    )


def run_match(
    requirements: list[RequirementItem],
    documents: list[ExtractedDoc],
    use_llm: bool = True,
) -> MatchResult:
    rows: list[MatchRow] = []
    used_docs: set[str] = set()
    learned_applied = 0

    doc_weighted = {d.id: _doc_terms(d)[0] for d in documents}
    learned_index = feedback.get_index()

    for item in requirements:
        req_terms = _requirement_terms(item)
        lentry = learned_index.get(feedback.req_key(item.section, item.requirement))
        row_learned_note = ""

        scored: list[tuple[_Cand, ExtractedDoc]] = []
        for d in documents:
            # even an unreadable (scanned) file is matchable by its name / folder,
            # and may be a document the auditor previously confirmed here
            cand = _score(req_terms, doc_weighted[d.id], item, d)
            if lentry is not None:
                delta, reason, force = feedback.score_doc(lentry, d.filename, d.folder)
                if delta or force:
                    cand.score = round(cand.score + delta, 3)
                    cand.learned_reason = reason
                    row_learned_note = reason
                    if force == "strong":
                        cand.quality = "strong"
                        cand.method = "learned"
                    elif force == "none":
                        cand.quality = "none"
                    elif cand.quality == "none" and cand.score >= WEAK_FLOOR:
                        cand.quality = "weak"
            if cand.quality != "none":
                scored.append((cand, d))
        scored.sort(key=lambda x: x[0].score, reverse=True)
        top = scored[:4]

        matched = [
            MatchedFile(doc_id=d.id, filename=d.filename, score=c.score, method=c.method)  # type: ignore[arg-type]
            for c, d in top
        ]
        best = top[0][0].score if top else 0.0
        qualities = {c.quality for c, _ in top}

        if "strong" in qualities:
            status, comment = "Received", ""
        elif "weak" in qualities:
            status = "Partial"
            comment = "Possible match found - auditor to confirm the document fully satisfies this item."
        else:
            status, comment = "Pending", ""

        # a status the auditor has repeatedly set by hand for this line wins,
        # unless the deterministic pass already found a strong document match
        if lentry is not None and lentry.status_hint and "strong" not in qualities:
            status = lentry.status_hint  # type: ignore[assignment]
            comment = "Applied from previous auditor corrections."
            row_learned_note = comment

        if item.sheet_status == "Not applicable":
            status, comment = "Not applicable", "Marked N/A on the requirements checklist."

        if row_learned_note:
            learned_applied += 1
        for m in matched:
            used_docs.add(m.doc_id)

        rows.append(
            MatchRow(
                ref=item.ref,
                section=item.section,
                section_title=item.section_title,
                requirement=item.requirement,
                evidence_type=item.evidence_type,
                row=item.row,
                status=status,  # type: ignore[arg-type]
                confidence=round(best, 3),
                matched_files=matched,
                comment=comment,
                learned_note=row_learned_note,
            )
        )

    llm_used = False
    if use_llm and LLM_ENABLED and llm.available():
        try:
            llm_used = llm.reconcile(rows, documents)
        except Exception:  # noqa: BLE001 - never fail the request over the optional pass
            llm_used = False

    unmatched = [d.id for d in documents if d.id not in used_docs]
    return MatchResult(
        stats=_stats(rows, llm_used, learned_applied), rows=rows, unmatched_docs=unmatched
    )


def _stats(rows: list[MatchRow], llm_used: bool, learned_applied: int = 0) -> MatchStats:
    c = Counter(r.status for r in rows)
    return MatchStats(
        total=len(rows),
        received=c.get("Received", 0),
        partial=c.get("Partial", 0),
        pending=c.get("Pending", 0),
        not_applicable=c.get("Not applicable", 0),
        llm_used=llm_used,
        learned_applied=learned_applied,
    )


def apply_override(
    result: MatchResult,
    documents: list[ExtractedDoc],
    ref: str,
    *,
    status: str | None = None,
    comment: str | None = None,
    add_doc_ids: list[str] | None = None,
    remove_doc_ids: list[str] | None = None,
) -> MatchResult:
    row = next((r for r in result.rows if r.ref == ref), None)
    if row is None:
        raise KeyError(ref)

    doc_by_id = {d.id: d for d in documents}
    eff_status = status or row.status

    for did in remove_doc_ids or []:
        d = doc_by_id.get(did)
        if d and any(m.doc_id == did for m in row.matched_files):
            feedback.record(
                section=row.section, ref=row.ref, requirement=row.requirement,
                action="unmap", status=eff_status, filename=d.filename, folder=d.folder,
            )
    if remove_doc_ids:
        row.matched_files = [m for m in row.matched_files if m.doc_id not in remove_doc_ids]

    for did in add_doc_ids or []:
        d = doc_by_id.get(did)
        if d and not any(m.doc_id == did for m in row.matched_files):
            row.matched_files.append(
                MatchedFile(doc_id=did, filename=d.filename, score=1.0, method="manual")
            )
            feedback.record(
                section=row.section, ref=row.ref, requirement=row.requirement,
                action="map", status=eff_status, filename=d.filename, folder=d.folder,
            )

    if status and status != row.status:
        row.status = status  # type: ignore[assignment]
        if not add_doc_ids and not remove_doc_ids:
            feedback.record(
                section=row.section, ref=row.ref, requirement=row.requirement,
                action="status", status=status,
            )
    if comment is not None:
        row.comment = comment

    row.overridden = True
    result.stats = _stats(result.rows, result.stats.llm_used, result.stats.learned_applied)
    used = {m.doc_id for r in result.rows for m in r.matched_files}
    result.unmatched_docs = [d.id for d in documents if d.id not in used]
    return result
