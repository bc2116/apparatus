"""Shared writer for human-legible, collision-safe workspace receipts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from apparatus_core import records


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _timestamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _filename(now: datetime, event: str, collision: int) -> str:
    stem = now.astimezone(timezone.utc).strftime("%Y-%m-%d-%H%M%S") + f"-{event}"
    suffix = "" if collision == 1 else f"-{collision}"
    return f"{stem}{suffix}.md"


def _render(event: str, timestamp: str, fields: Mapping[str, Any]) -> str:
    protected = {"schema", "event", "timestamp"}
    attempted_overrides = protected.intersection(fields)
    if attempted_overrides:
        names = ", ".join(sorted(attempted_overrides))
        raise ValueError(f"receipt fields cannot override protected fields: {names}")
    summary = fields.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("receipt fields must include a non-empty summary")
    frontmatter: dict[str, Any] = {
        "schema": records.SCHEMAS["receipt"].schema_id,
        "event": event,
        "timestamp": timestamp,
        "summary": summary,
    }
    frontmatter.update(
        (name, value)
        for name, value in fields.items()
        if name not in {"summary", "body"}
    )
    problems = records.validate("receipt", frontmatter)
    if problems:
        raise ValueError("invalid receipt fields: " + "; ".join(problems))
    body = fields.get("body", "")
    if not isinstance(body, str):
        raise ValueError("receipt body must be text")
    return "---\n" + records.yaml.safe_dump(
        frontmatter, sort_keys=False, allow_unicode=True
    ) + "---\n" + body.rstrip() + "\n"


def write_receipt(workspace: str | Path, event: str, fields: Mapping[str, Any]) -> Path:
    """Write one unique receipt for *event* and return its workspace path."""
    if event not in records.RECEIPT_EVENTS:
        raise ValueError(f"unknown receipt event: {event!r}")
    now = _utcnow()
    content = _render(event, _timestamp(now), fields)
    receipts = Path(workspace) / "System" / "receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    for collision in range(1, 1_000_000):
        path = receipts / _filename(now, event, collision)
        try:
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
        except FileExistsError:
            continue
        return path
    raise OSError("could not allocate a unique receipt filename")
