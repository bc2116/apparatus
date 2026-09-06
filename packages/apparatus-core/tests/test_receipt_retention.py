"""No-save receipts bind only the metadata bytes they actually publish."""

from __future__ import annotations

import argparse
from hashlib import sha256

import pytest

from apparatus_core import receipts, records
from apparatus_core.commands import init
from apparatus_core.retention import operation, set_no_memory, start_task


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "workspace"
    assert init.run(argparse.Namespace(workspace=str(root), payload=None,
                                      privacy_mode=None, work_types=None),
                    available=lambda: False) == 0
    return root


def fields():
    return {"summary": "Synthetic sensitive summary", "body": "Synthetic body",
            "query": "Synthetic query", "path": "Synthetic/path.txt",
            "label": "Synthetic label", "error": "Synthetic exception",
            "count": 3, "failed": False, "status": "completed",
            "snapshot_id": "a" * 40, "commit_id": "Synthetic invalid ID"}


@pytest.mark.parametrize("identified", [False, True])
def test_no_save_metadata_is_shaped_before_digest_and_publication(workspace, identified):
    task = start_task(workspace, save_memory=False)
    with operation(workspace, task_id=task.task_id if identified else None):
        invocation = receipts.prepare_receipt_invocation(workspace, "check", fields())
    # The invocation remains bound to its entry decision outside the scope.
    publication = receipts.write_receipt(workspace, "check", fields(), invocation=invocation)
    try:
        content = publication.path.read_bytes()
        assert b"Synthetic" not in content
        data, body = records.parse_record(content.decode())
        expected = {"schema", "event", "timestamp", "summary", "count", "status",
                    "snapshot_id"} | ({"task_id"} if identified else set())
        assert set(data) == expected
        assert data["summary"] == "Apparatus check operation."
        assert data["count"] == 3 and data["snapshot_id"] == "a" * 40
        assert not body.strip()
        assert publication.content_digest == sha256(content).hexdigest()
        assert publication.is_bound_to(invocation)
        publication.claim(invocation)
        publication.rollback()
        assert not publication.path.exists()
    finally:
        publication.close()


def test_metadata_mismatch_still_rejects_exact_publication(workspace):
    task = start_task(workspace, save_memory=False)
    with operation(workspace, task_id=task.task_id):
        invocation = receipts.prepare_receipt_invocation(workspace, "check", fields())
        with pytest.raises(OSError, match="does not match"):
            receipts.write_receipt(workspace, "check", {**fields(), "count": 4},
                                   invocation=invocation)
    assert not list((workspace / "System/receipts").glob("*-check*.md"))


def test_inflight_receipt_keeps_entry_decision_and_next_receipt_obeys_optout(workspace):
    task = start_task(workspace, save_memory=True)
    with operation(workspace, task_id=task.task_id):
        invocation = receipts.prepare_receipt_invocation(workspace, "check", fields())
    set_no_memory(workspace, task.task_id)
    publication = receipts.write_receipt(workspace, "check", fields(), invocation=invocation)
    try:
        assert b"Synthetic sensitive summary" in publication.path.read_bytes()
        publication.claim(invocation)
        publication.commit()
    finally:
        publication.close()
    with operation(workspace, task_id=task.task_id):
        later = receipts.write_receipt(workspace, "check", fields())
    assert b"Synthetic" not in later.path.read_bytes()
    later.close()


@pytest.mark.parametrize("protected", ["schema", "event", "timestamp"])
def test_no_save_still_rejects_protected_field_overrides(workspace, protected):
    task = start_task(workspace, save_memory=False)
    with operation(workspace, task_id=task.task_id):
        with pytest.raises(ValueError, match="protected"):
            receipts.write_receipt(workspace, "check", {**fields(), protected: "override"})
    assert not list((workspace / "System/receipts").glob("*-check*.md"))
