"""Inspect / reset the matcher's learning store (auditor-correction history)."""
from __future__ import annotations

from fastapi import APIRouter

from ..services import feedback

router = APIRouter(prefix="/api", tags=["learning"])


@router.get("/learning")
def learning_stats() -> dict:
    return feedback.stats()


@router.delete("/learning")
def reset_learning() -> dict:
    feedback.reset()
    return {"ok": True, **feedback.stats()}
