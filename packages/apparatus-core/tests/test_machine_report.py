from __future__ import annotations

from datetime import datetime, timezone

import yaml

from apparatus_core.machine_report import render_machine_report, write_machine_report


def _detections(*, git_present=True, risk=False):
    return {
        "os": {"name": "Darwin", "version": "15.0"},
        "python": {"version": "3.12.4", "executable": "/python"},
        "git": {"present": git_present, "version": "git version 2.50" if git_present else None},
        "uv": {"present": True, "version": "uv 0.9"},
        "ai_apps": ["Cursor"],
        "sync_redirection": {
            "at_risk": risk,
            "reason": "The path contains a OneDrive sync-location marker." if risk else "No common sync-redirection marker was found.",
        },
        "workspace": "/Projects/Apparatus",
    }


def _clock():
    return datetime(2026, 8, 9, 12, 34, 56, tzinfo=timezone.utc)


def test_report_is_parseable_yaml_with_stable_key_order_and_plain_language_body():
    report = render_machine_report(_detections(), clock=_clock)
    frontmatter = report.split("---", 2)[1]
    data = yaml.safe_load(frontmatter)
    assert list(data) == [
        "generated_at", "generator", "version", "os", "python", "git", "uv", "snapshots",
        "detected_ai_apps", "sync_redirection",
    ]
    assert data["generated_at"] == "2026-08-09T12:34:56Z"
    assert data["snapshots"] == "available"
    assert "Operating system: Darwin 15.0." in report
    assert "repository" not in report.casefold()


def test_report_uses_null_and_unavailable_when_git_is_missing():
    report = render_machine_report(_detections(git_present=False), clock=_clock)
    data = yaml.safe_load(report.split("---", 2)[1])
    assert data["git"] is None
    assert data["snapshots"] == "unavailable"


def test_write_machine_report_creates_system_and_is_idempotent(tmp_path):
    first = write_machine_report(tmp_path, _detections(), clock=_clock)
    initial = first.read_text(encoding="utf-8")
    second = write_machine_report(tmp_path, _detections(), clock=_clock)
    assert second == tmp_path / "System/machine-report.md"
    assert second.read_text(encoding="utf-8") == initial
