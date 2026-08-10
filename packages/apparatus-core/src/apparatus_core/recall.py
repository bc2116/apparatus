"""Grounded Library recall with explicit abstention and durable receipts."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from apparatus_core.cache import library_cache_root
from apparatus_core.credentials import RedactionFinding, redact
from apparatus_core.library import index
from apparatus_core.receipts import write_receipt


RECALL_ABSTAIN_THRESHOLD = 0.0


class NoExtractionsError(RuntimeError):
    """The workspace has no Library extraction records yet."""


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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _timestamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _redact_receipt_values(
    question: str, sources: list[str]
) -> tuple[str, list[str], tuple[RedactionFinding, ...]]:
    redacted_question, question_findings = redact(question)
    redacted_sources: list[str] = []
    findings = list(question_findings)
    for source in sources:
        redacted_source, source_findings = redact(source)
        redacted_sources.append(redacted_source)
        findings.extend(source_findings)
    counts = Counter[str]()
    for finding in findings:
        counts[finding.credential_class] += finding.count
    merged = tuple(RedactionFinding(name, counts[name]) for name in sorted(counts))
    return redacted_question, redacted_sources, merged


def _receipt_fields(envelope: RecallEnvelope) -> dict[str, Any]:
    sources = [item["source"] for item in envelope["evidence"]]
    question, safe_sources, findings = _redact_receipt_values(
        envelope["question"], sources
    )
    counts = {finding.credential_class: finding.count for finding in findings}
    source_details = "\n".join(f"- {source}" for source in safe_sources) or "- none"
    redaction_details = (
        "\n".join(f"- {name}: {counts[name]}" for name in sorted(counts))
        or "- none"
    )
    return {
        "summary": f"Recall {envelope['status']} with {len(safe_sources)} evidence source(s).",
        "question": question,
        "status": envelope["status"],
        "threshold": envelope["threshold"],
        "evidence_sources": safe_sources,
        "credential_classes": sorted(counts),
        "credential_counts": counts,
        "body": (
            "Evidence sources:\n"
            + source_details
            + "\n\nCredential-floor redactions:\n"
            + redaction_details
        ),
    }


def recall(
    workspace: str | Path,
    question: str,
    limit: int = 5,
    *,
    write: Callable[[str | Path, str, dict[str, Any]], Path] = write_receipt,
) -> RecallEnvelope:
    """Retrieve Library evidence, abstain honestly, and write one receipt."""
    workspace_path = Path(workspace)
    if not workspace_path.exists() or not workspace_path.is_dir():
        raise ValueError("workspace path is not a directory")
    if limit < 1:
        raise ValueError("limit must be positive")

    cache = library_cache_root(workspace_path)
    if not index.has_extractions(cache):
        raise NoExtractionsError
    index.refresh(cache)
    hits = index.search(cache, question, limit)
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
    }
    write(workspace_path, "recall", _receipt_fields(envelope))
    return envelope
