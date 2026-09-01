"""LLM reconciliation pass for the matcher (provider-agnostic).

Fully degradable: if no provider is configured or the call fails, the
deterministic match stands.
"""
from __future__ import annotations

import json

from ..config import LLM_MAX_DOCS, LLM_SNIPPET_CHARS
from ..schemas import ExtractedDoc, MatchedFile, MatchRow
from . import llm_client

_SYSTEM = (
    "You are an audit manager at a UAE chartered-accountancy firm reconciling a "
    "client's submitted documents against a RERA interim-audit requirements "
    "checklist. You are given the current algorithmic match and the list of "
    "available documents. Correct clear mistakes: promote to 'Received' when a "
    "listed document plainly satisfies a requirement, demote to 'Pending' when "
    "the mapped file is unrelated, use 'Partial' when a document is on-topic but "
    "incomplete. Only change rows you are confident about."
)


def available() -> bool:
    return llm_client.available()


def _docs_blob(documents: list[ExtractedDoc]) -> str:
    out = []
    for d in documents[:LLM_MAX_DOCS]:
        out.append(json.dumps({
            "doc_id": d.id,
            "filename": d.filename,
            "folder": d.folder,
            "snippet": (d.text_excerpt or "").replace("\n", " ")[:LLM_SNIPPET_CHARS],
        }, ensure_ascii=False))
    return "\n".join(out)


def _rows_blob(rows: list[MatchRow]) -> str:
    return "\n".join(json.dumps({
        "ref": r.ref,
        "requirement": r.requirement,
        "evidence_type": r.evidence_type,
        "status": r.status,
        "matched_doc_ids": [m.doc_id for m in r.matched_files],
    }, ensure_ascii=False) for r in rows)


def reconcile(rows: list[MatchRow], documents: list[ExtractedDoc]) -> bool:
    """Mutates ``rows`` in place. Returns True if the pass ran."""
    if not rows or not documents or not llm_client.available():
        return False

    by_ref = {r.ref: r for r in rows}
    by_doc = {d.id: d for d in documents}

    user = (
        "DOCUMENTS (one JSON per line):\n" + _docs_blob(documents) + "\n\n"
        "CURRENT MATCH (one JSON per line):\n" + _rows_blob(rows) + "\n\n"
        'Return JSON: {"changes":[{"ref":"5.1","status":"Received",'
        '"doc_ids":["ab12..."],"rationale":"short reason"}]}. '
        "Omit rows that should not change; doc_ids must come from DOCUMENTS."
    )
    data = llm_client.chat_json(_SYSTEM, user, max_tokens=4000)

    for ch in data.get("changes", []):
        row = by_ref.get(str(ch.get("ref", "")))
        if not row:
            continue
        if ch.get("status") in {"Received", "Partial", "Pending", "Not applicable"}:
            row.status = ch["status"]  # type: ignore[assignment]
        row.llm_rationale = str(ch.get("rationale", ""))[:300]
        for did in [d for d in ch.get("doc_ids", []) if d in by_doc]:
            if not any(m.doc_id == did for m in row.matched_files):
                row.matched_files.append(
                    MatchedFile(doc_id=did, filename=by_doc[did].filename, score=0.9, method="llm")
                )
    return True
