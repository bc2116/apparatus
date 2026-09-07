"""Grounded Library recall with explicit abstention and current-source evidence."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from apparatus_core.ignore import IgnoreReport
from apparatus_core.library import index
from apparatus_core.receipts import write_receipt
from apparatus_core.retention import operation


RECALL_ABSTAIN_THRESHOLD = 0.0


NoExtractionsError = index.NoExtractionsError


class Evidence(TypedDict):
    source: str
    snippet: str
    score: float


class RecallEnvelope(TypedDict):
    status: str
    question: str
    threshold: float
    evidence: list[Evidence]
    generated_at: str
    coverage: dict


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _timestamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def recall(
    workspace: str | Path,
    question: str,
    limit: int = 5,
    *,
    write: Callable[[str | Path, str, dict[str, Any]], object] = write_receipt,
    report_ignore: Callable[[IgnoreReport], None] | None = None,
    task_id: str | None = None,
) -> RecallEnvelope:
    """Retrieve evidence under one frozen task context."""
    with operation(workspace, task_id=task_id):
        return _recall(workspace, question, limit, write=write, report_ignore=report_ignore)


def _recall(
    workspace: str | Path, question: str, limit: int, *,
    write: Callable[[str | Path, str, dict[str, Any]], object],
    report_ignore: Callable[[IgnoreReport], None] | None,
) -> RecallEnvelope:
    """Retrieve evidence without persisting questions or routine receipts."""
    workspace_path = Path(workspace)
    if not workspace_path.exists() or not workspace_path.is_dir():
        raise ValueError("workspace path is not a directory")
    if limit < 1:
        raise ValueError("limit must be positive")

    result = index.retrieve(workspace_path, question, limit)
    hits, ignore_report = result
    qualifying = [hit for hit in hits if hit.score >= RECALL_ABSTAIN_THRESHOLD]
    evidence: list[Evidence] = [
        {"source": hit.source_path, "snippet": hit.snippet, "score": hit.score}
        for hit in qualifying
    ]
    envelope: RecallEnvelope = {
        "status": "grounded" if evidence else "abstained",
        "question": question,
        "threshold": RECALL_ABSTAIN_THRESHOLD,
        "evidence": evidence,
        "generated_at": _timestamp(_utcnow()),
        "coverage": result.coverage.as_dict(),
    }
    if report_ignore is not None:
        report_ignore(ignore_report)
    return envelope
