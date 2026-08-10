from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from apparatus_core import receipts, records


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
    assert first.path.name == "2026-08-09-141530-check.md"
    assert second.path.name == "2026-08-09-141530-check-2.md"
    data, body = records.parse_record(first.path.read_text(encoding="utf-8"))
    assert records.validate("receipt", data, filename=first.path.name) == []
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
    data, body = records.parse_record(path.path.read_text(encoding="utf-8"))
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


def test_explicit_invocation_binds_digest_and_rolls_back_only_its_receipt(tmp_path):
    fields = {"summary": "Check passed.", "body": "Finding codes: none.\n"}
    invocation = receipts.prepare_receipt_invocation(tmp_path, "check", fields)
    publication = receipts.write_receipt(
        tmp_path,
        "check",
        fields,
        invocation=invocation,
    )
    path = publication.path
    expected_digest = receipts.sha256(path.read_bytes()).hexdigest()

    assert publication.content_digest == expected_digest
    assert publication.is_bound_to(invocation)
    publication.claim(invocation)
    publication.rollback()
    publication.close()

    assert not path.exists()
    assert not list((tmp_path / "System/receipts").iterdir())


@pytest.mark.parametrize("mismatch", ("event", "content", "workspace"))
def test_invocation_rejects_wrong_binding_before_publication(tmp_path, mismatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    fields = {"summary": "Expected check receipt."}
    invocation = receipts.prepare_receipt_invocation(workspace, "check", fields)
    target = other if mismatch == "workspace" else workspace
    event = "snapshot" if mismatch == "event" else "check"
    supplied = (
        {"summary": "Substituted check receipt."}
        if mismatch == "content"
        else fields
    )

    with pytest.raises(OSError, match="does not match"):
        receipts.write_receipt(
            target,
            event,
            supplied,
            invocation=invocation,
        )

    assert not (workspace / "System/receipts").exists()
    assert not (other / "System/receipts").exists()


def test_invocation_freshness_is_consumed_once(tmp_path):
    fields = {"summary": "Check passed."}
    invocation = receipts.prepare_receipt_invocation(tmp_path, "check", fields)
    publication = receipts.write_receipt(
        tmp_path,
        "check",
        fields,
        invocation=invocation,
    )
    try:
        with pytest.raises(OSError, match="freshness was already consumed"):
            receipts.write_receipt(
                tmp_path,
                "check",
                fields,
                invocation=invocation,
            )
    finally:
        publication.claim(invocation)
        publication.rollback()
        publication.close()


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


def test_failed_atomic_publication_removes_its_exact_partial(tmp_path, monkeypatch):
    original = receipts._write_complete

    def fail_after_partial(descriptor, content):
        os.write(descriptor, content[:12])
        raise OSError("fictional write failure")

    monkeypatch.setattr(receipts, "_write_complete", fail_after_partial)
    with pytest.raises(OSError):
        receipts.write_receipt(tmp_path, "check", {"summary": "Check passed."})
    receipt_dir = tmp_path / "System/receipts"
    assert receipt_dir.is_dir()
    assert list(receipt_dir.iterdir()) == []
    monkeypatch.setattr(receipts, "_write_complete", original)


@pytest.mark.skipif(os.name != "posix", reason="POSIX create/open race probe")
def test_failed_receipt_never_deletes_a_preopen_substituted_directory(
    tmp_path, monkeypatch
):
    original_open_directory = receipts._open_directory
    original_write = receipts._write_complete
    substituted = False

    def substitute_before_return(parent, name, *, create):
        nonlocal substituted
        descriptor, created = original_open_directory(parent, name, create=create)
        if name == "receipts" and created and not substituted:
            substituted = True
            os.close(descriptor)
            os.rename(
                "receipts",
                "held-receipts",
                src_dir_fd=parent,
                dst_dir_fd=parent,
            )
            os.mkdir("receipts", 0o700, dir_fd=parent)
            replacement = os.open(
                "receipts", os.O_RDONLY | os.O_DIRECTORY, dir_fd=parent
            )
            try:
                sentinel = os.open(
                    "concurrent-sentinel",
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=replacement,
                )
                os.close(sentinel)
            finally:
                os.close(replacement)
            descriptor = os.open(
                "receipts", os.O_RDONLY | os.O_DIRECTORY, dir_fd=parent
            )
        return descriptor, created

    def fail_write(descriptor, content):
        original_write(descriptor, content)
        raise OSError("fictional publication failure")

    monkeypatch.setattr(receipts, "_open_directory", substitute_before_return)
    monkeypatch.setattr(receipts, "_write_complete", fail_write)
    with pytest.raises(OSError):
        receipts.write_receipt(tmp_path, "check", {"summary": "Check passed."})
    system = tmp_path / "System"
    assert (system / "receipts/concurrent-sentinel").is_file()
    assert (system / "held-receipts").is_dir()
    assert list((system / "held-receipts").iterdir()) == []


def test_receipt_publication_does_not_follow_a_swapped_ancestor(tmp_path, monkeypatch):
    system = tmp_path / "System"
    target = system / "receipts"
    target.mkdir(parents=True)
    held = system / "held-receipts"
    outside = tmp_path / "outside"
    outside.mkdir()
    original = receipts._write_complete

    def swap_then_write(descriptor, content):
        target.rename(held)
        target.symlink_to(outside, target_is_directory=True)
        original(descriptor, content)

    monkeypatch.setattr(receipts, "_write_complete", swap_then_write)
    with pytest.raises(OSError, match="destination changed"):
        receipts.write_receipt(tmp_path, "check", {"summary": "Check passed."})
    assert list(outside.iterdir()) == []
    assert list(held.iterdir()) == []


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory-handle race probe")
def test_failed_receipt_cleanup_keeps_a_substituted_created_directory(
    tmp_path, monkeypatch
):
    target = tmp_path / "System/receipts"
    held = tmp_path / "System/held-receipts"
    original = receipts._write_complete

    def substitute_then_fail(descriptor, content):
        target.rename(held)
        target.mkdir()
        (target / "concurrent-sentinel").write_bytes(b"concurrent")
        original(descriptor, content)
        raise OSError("fictional post-write failure")

    monkeypatch.setattr(receipts, "_write_complete", substitute_then_fail)
    with pytest.raises(OSError):
        receipts.write_receipt(tmp_path, "check", {"summary": "Check passed."})
    assert (target / "concurrent-sentinel").read_bytes() == b"concurrent"
    assert list(held.iterdir()) == []


def test_receipt_collision_with_a_symlink_retries_without_following_it(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(receipts, "_utcnow", _clock)
    receipt_dir = tmp_path / "System/receipts"
    receipt_dir.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    outside.write_text("outside sentinel", encoding="utf-8")
    first = receipt_dir / "2026-08-09-141530-check.md"
    first.symlink_to(outside)
    written = receipts.write_receipt(tmp_path, "check", {"summary": "Check passed."})
    assert written.path.name == "2026-08-09-141530-check-2.md"
    assert outside.read_text(encoding="utf-8") == "outside sentinel"


@pytest.mark.skipif(os.name != "posix", reason="POSIX hard-link race probe")
def test_receipt_does_not_delete_a_substituted_final_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(receipts, "_utcnow", _clock)
    receipt_dir = tmp_path / "System/receipts"
    receipt_dir.mkdir(parents=True)
    held = receipt_dir / "held-owned-link"
    substituted = b"concurrent receipt sentinel"
    original = receipts._link_at

    def substitute_after_link(parent, source, target):
        original(parent, source, target)
        os.rename(
            target,
            held.name,
            src_dir_fd=parent,
            dst_dir_fd=parent,
        )
        descriptor = os.open(
            target,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=parent,
        )
        try:
            os.write(descriptor, substituted)
        finally:
            os.close(descriptor)

    monkeypatch.setattr(receipts, "_link_at", substitute_after_link)
    with pytest.raises(OSError, match="destination changed"):
        receipts.write_receipt(tmp_path, "check", {"summary": "Check passed."})
    final = receipt_dir / "2026-08-09-141530-check.md"
    assert final.read_bytes() == substituted
    assert held.is_file()
    assert not list(receipt_dir.glob(".apparatus-receipt-*.tmp"))
