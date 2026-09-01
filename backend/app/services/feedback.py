"""Learning loop - the matcher improves from auditor corrections.

Every time an auditor overrides a row on the review screen (changes the status,
attaches a document, or detaches one) we append a record here.  Before each
future matching run the matcher consults the accumulated history:

* a document whose filename previously **confirmed** a requirement is boosted
  (strongly, if the exact file name recurs - common across audit periods);
* a document previously **detached** from a requirement is penalised;
* a status the auditor repeatedly sets by hand (e.g. ``Not applicable``) is
  offered as a hint.

The store is a plain append-only JSONL file under ``storage/learned/`` so it
survives restarts and is shared across sessions.  Deterministic, inspectable,
no model training.
"""
from __future__ import annotations

import json
import re
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ..config import STORAGE_DIR

_DIR = STORAGE_DIR / "learned"
_DIR.mkdir(parents=True, exist_ok=True)
_FILE = _DIR / "feedback.jsonl"

_TOK = re.compile(r"[a-z0-9][a-z0-9&/\-]{1,}")
_STOP = {
    "the", "and", "for", "with", "copy", "original", "certified", "signed", "current",
    "valid", "list", "schedule", "report", "statement", "document", "documents", "as",
    "at", "to", "of", "all", "any", "pdf", "xlsx", "xls", "csv", "docx", "final", "v01",
    "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
}

_lock = threading.Lock()
_index_cache: dict | None = None


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _tok(text: str) -> list[str]:
    return [t.strip("-/&") for t in _TOK.findall((text or "").lower()) if t not in _STOP and len(t) > 2]


def req_key(section: int, requirement: str) -> str:
    """Stable identity for a requirement line, robust to wording tweaks/order."""
    toks = sorted(set(_tok(requirement)))
    return f"{section}|{' '.join(toks)}"


def doc_tokens(filename: str, folder: str) -> list[str]:
    return sorted(set(_tok(filename) + _tok(folder)))


# --------------------------------------------------------------------------- #
# write
# --------------------------------------------------------------------------- #
def record(
    *,
    section: int,
    ref: str,
    requirement: str,
    action: str,                 # "map" | "unmap" | "status"
    status: str,
    filename: str = "",
    folder: str = "",
) -> None:
    global _index_cache
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "section": section,
        "ref": ref,
        "req_key": req_key(section, requirement),
        "requirement": requirement[:180],
        "action": action,
        "status": status,
        "filename": filename,
        "folder": folder,
        "tokens": doc_tokens(filename, folder) if filename else [],
    }
    with _lock:
        with _FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        _index_cache = None


# --------------------------------------------------------------------------- #
# read / learn
# --------------------------------------------------------------------------- #
class Learned:
    __slots__ = ("pos", "neg", "confirmed_names", "rejected_names", "status_votes", "n")

    def __init__(self):
        self.pos: Counter = Counter()
        self.neg: Counter = Counter()
        self.confirmed_names: set[str] = set()
        self.rejected_names: set[str] = set()
        self.status_votes: Counter = Counter()
        self.n = 0

    @property
    def status_hint(self) -> str | None:
        if not self.status_votes:
            return None
        top, cnt = self.status_votes.most_common(1)[0]
        # "Not applicable" is safe to honour from a single correction; other
        # statuses need to be seen at least twice before we apply them.
        threshold = 1 if top == "Not applicable" else 2
        return top if cnt >= threshold else None


def _load_records() -> list[dict]:
    if not _FILE.exists():
        return []
    out = []
    for line in _FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def get_index() -> dict[str, Learned]:
    global _index_cache
    if _index_cache is not None:
        return _index_cache
    idx: dict[str, Learned] = {}
    for rec in _load_records():
        e = idx.setdefault(rec["req_key"], Learned())
        e.n += 1
        act = rec.get("action")
        name = (rec.get("filename") or "").lower()
        toks = rec.get("tokens") or []
        if act == "map":
            for t in toks:
                e.pos[t] += 1
            if name:
                e.confirmed_names.add(name)
                e.rejected_names.discard(name)
            if rec.get("status"):
                e.status_votes[rec["status"]] += 1
        elif act == "unmap":
            for t in toks:
                e.neg[t] += 1
            if name:
                e.rejected_names.add(name)
                e.confirmed_names.discard(name)
        elif act == "status" and rec.get("status"):
            e.status_votes[rec["status"]] += 1
    _index_cache = idx
    return idx


def score_doc(entry: Learned, filename: str, folder: str) -> tuple[float, str, str | None]:
    """Return (score_delta, reason, force) where force in {"strong","none",None}."""
    name = (filename or "").lower()
    if name and name in entry.confirmed_names:
        return 1.6, "Confirmed for this requirement in a previous review.", "strong"
    if name and name in entry.rejected_names:
        return -1.2, "Previously detached from this requirement by the auditor.", "none"
    toks = set(doc_tokens(filename, folder))
    pos = sum(min(entry.pos[t], 3) for t in toks if t in entry.pos)
    neg = sum(min(entry.neg[t], 3) for t in toks if t in entry.neg)
    delta = 0.12 * min(pos, 6) - 0.18 * min(neg, 6)
    if delta >= 0.45:
        return round(delta, 3), "Filename pattern matches earlier auditor confirmations.", "strong"
    if delta <= -0.35:
        return round(delta, 3), "Filename pattern matches earlier auditor rejections.", "none"
    if abs(delta) >= 0.05:
        return round(delta, 3), "Adjusted from prior corrections.", None
    return 0.0, "", None


def stats() -> dict:
    recs = _load_records()
    idx = get_index()
    return {
        "records": len(recs),
        "requirements_learned": len(idx),
        "confirmations": sum(1 for r in recs if r.get("action") == "map"),
        "rejections": sum(1 for r in recs if r.get("action") == "unmap"),
        "status_edits": sum(1 for r in recs if r.get("action") == "status"),
        "last_updated": recs[-1]["ts"] if recs else None,
    }


def reset() -> None:
    global _index_cache
    with _lock:
        if _FILE.exists():
            _FILE.unlink()
        _index_cache = None
