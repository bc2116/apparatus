"""Grounded Library recall with explicit abstention and durable receipts."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from apparatus_core.credentials import RedactionFinding, redact
from apparatus_core.ignore import IgnoreReport
from apparatus_core.library import index
from apparatus_core.receipts import write_receipt
from apparatus_core.retention import context_for, operation


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


def _receipt_fields(
    envelope: RecallEnvelope, ignore_report: IgnoreReport
) -> dict[str, Any]:
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
        "summary": f"Recall {envelope['status']} with {len(safe_sources)} evidence source(s); {envelope['coverage']['status']} Library coverage.",
        "question": question,
        "status": envelope["status"],
        "threshold": envelope["threshold"],
        "evidence_sources": safe_sources,
        "credential_classes": sorted(counts),
        "credential_counts": counts,
        "ignored_paths": ignore_report.skipped_paths,
        "ignore_rule_provenance": ignore_report.provenance,
        "body": (
            ignore_report.sentence()
            + "\nLibrary coverage: " + envelope["coverage"]["status"] + "."
            + "\n\nEvidence sources:\n"
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
    """Retrieve evidence, persisting no routine receipt for no-save tasks."""
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
    if context_for(workspace_path).save_memory:
        write(workspace_path, "recall", _receipt_fields(envelope, ignore_report))
    if report_ignore is not None:
        report_ignore(ignore_report)
    return envelope
