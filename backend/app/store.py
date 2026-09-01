"""In-memory session store.

Each session owns a directory under ``STORAGE_DIR/<session_id>`` that holds the
uploaded requirements sheet, master template, customer documents and the
generated workbook.  State is kept in-process which is fine for a single-user
desktop tool; swap this module for Redis/DB to scale out.
"""
from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config import STORAGE_DIR
from .schemas import ExtractedDoc, MatchResult, RequirementsResult


@dataclass
class Session:
    id: str
    dir: Path
    requirements: Optional[RequirementsResult] = None
    requirements_path: Optional[Path] = None
    template_path: Optional[Path] = None
    template_sheets: list[str] = field(default_factory=list)
    documents: list[ExtractedDoc] = field(default_factory=list)
    match: Optional[MatchResult] = None
    workbook_path: Optional[Path] = None
    requirements_filled_path: Optional[Path] = None
    context_cache: dict = field(default_factory=dict)   # key -> EntityContext

    @property
    def docs_dir(self) -> Path:
        d = self.dir / "documents"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def doc(self, doc_id: str) -> Optional[ExtractedDoc]:
        return next((d for d in self.documents if d.id == doc_id), None)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        sid = uuid.uuid4().hex[:12]
        sdir = STORAGE_DIR / sid
        sdir.mkdir(parents=True, exist_ok=True)
        sess = Session(id=sid, dir=sdir)
        self._sessions[sid] = sess
        return sess

    def get(self, sid: str) -> Session:
        sess = self._sessions.get(sid)
        if sess is None:
            raise KeyError(sid)
        return sess

    def delete(self, sid: str) -> None:
        sess = self._sessions.pop(sid, None)
        if sess and sess.dir.exists():
            shutil.rmtree(sess.dir, ignore_errors=True)


store = SessionStore()
