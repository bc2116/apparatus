from __future__ import annotations

from datetime import datetime, timezone

import pytest

from apparatus_core import records
from apparatus_core import receipts


def _clock():
    return datetime(2026, 8, 9, 14, 15, 30, tzinfo=timezone.utc)


def test_write_receipt_is_parseable_and_collision_safe(tmp_path, monkeypatch):
    monkeypatch.setattr(receipts, "_utcnow", _clock)
    first = receipts.write_receipt(
        tmp_path, "check", {"summary": "Check passed.", "body": "Finding codes: none."}
    )
    second = receipts.write_receipt(
        tmp_path, "check", {"summary": "Check passed.", "body": "Finding codes: none."}
    )
    assert first.name == "2026-08-09-141530-check.md"
    assert second.name == "2026-08-09-141530-check-2.md"
    data, body = records.parse_record(first.read_text(encoding="utf-8"))
    assert records.validate("receipt", data, filename=first.name) == []
    assert data["timestamp"] == "2026-08-09T14:15:30Z"
    assert body == "Finding codes: none."


def test_write_receipt_preserves_caller_fields_in_frontmatter(tmp_path, monkeypatch):
    monkeypatch.setattr(receipts, "_utcnow", _clock)
    path = receipts.write_receipt(
        tmp_path,
        "snapshot",
        {
            "summary": "Snapshot saved.",
            "body": "Snapshot details.",
            "label": "before-edit",
            "snapshot_id": "sample-123",
            "pre_restore_snapshot_id": None,
            "outcome": "success",
        },
    )
    data, body = records.parse_record(path.read_text(encoding="utf-8"))
    assert data == {
        "schema": "apparatus/receipt@v0",
        "event": "snapshot",
        "timestamp": "2026-08-09T14:15:30Z",
        "summary": "Snapshot saved.",
        "label": "before-edit",
        "snapshot_id": "sample-123",
        "pre_restore_snapshot_id": None,
        "outcome": "success",
    }
    assert body == "Snapshot details."


@pytest.mark.parametrize("protected", ["schema", "event", "timestamp"])
def test_write_receipt_rejects_protected_field_overrides(tmp_path, protected):
    fields = {"summary": "Check passed.", protected: "caller value"}
    with pytest.raises(ValueError, match="cannot override protected fields"):
        receipts.write_receipt(tmp_path, "check", fields)
    assert not (tmp_path / "System" / "receipts").exists()


def test_write_receipt_requires_a_known_event_and_summary(tmp_path):
    with pytest.raises(ValueError, match="unknown receipt event"):
        receipts.write_receipt(tmp_path, "other", {"summary": "No."})
    with pytest.raises(ValueError, match="non-empty summary"):
        receipts.write_receipt(tmp_path, "check", {})
