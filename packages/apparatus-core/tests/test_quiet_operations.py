"""Quiet producers preserve outputs and old history, including unwritable history."""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from apparatus_core import records, recall as recall_engine
from apparatus_core.commands import check, init, library, recall, snapshot, restore
from apparatus_core.library.ingest import ingest_library
from apparatus_core.retention import start_task
from apparatus_core.receipts import write_receipt


def _area(tmp_path, monkeypatch):
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "cache"))
    root = tmp_path / "area"
    assert init.run(argparse.Namespace(workspace=str(root), payload=None,
                                     privacy_mode=None, work_types=None), available=lambda: False) == 0
    (root / "Library/report.txt").write_text("Synthetic cobalt calibration evidence.\n")
    return root


def _history(root):
    return {p.name: p.read_bytes() for p in (root / "System/receipts").glob("*.md")}


@pytest.mark.parametrize("save", [True, False])
def test_reading_checks_and_recall_preserves_prior_history_and_never_logs_query(tmp_path, monkeypatch, save):
    root = _area(tmp_path, monkeypatch)
    ingest_library(root)
    # Historical routine events remain valid and byte-identical.
    write_receipt(root, "recall", {"summary": "Historical synthetic recall."})
    task = start_task(root, save_memory=save)
    before = _history(root)
    query = "cobalt password=synthetic-unlogged-query"

    def forbidden(*args, **kwargs):
        raise AssertionError("routine receipt publication")

    envelope = recall_engine.recall(root, query, task_id=task.task_id, write=forbidden)
    assert envelope["question"] == query
    assert envelope["coverage"]["status"] == "complete"
    assert check.run(argparse.Namespace(workspace=str(root), no_receipt=False), write=forbidden) == 0
    assert _history(root) == before
    assert all(query.encode() not in p.read_bytes() for p in root.rglob("*") if p.is_file())


def test_routine_and_unavailable_operations_work_with_unwritable_receipt_destination(tmp_path, monkeypatch):
    root = _area(tmp_path, monkeypatch)
    receipts = root / "System/receipts"
    saved = root / "old-history"
    receipts.rename(saved)
    receipts.write_text("A file prevents receipt directory creation.\n")
    before = {p.name: p.read_bytes() for p in saved.iterdir()}
    assert library.run(argparse.Namespace(workspace=str(root))) == 0
    assert recall.run(argparse.Namespace(workspace=str(root), question="cobalt", limit=5, as_json=False)) == 0
    # Existing checks tolerate a non-directory history endpoint; they must
    # still return their actual result without attempting receipt publication.
    assert check.run(argparse.Namespace(workspace=str(root), no_receipt=False)) == 0
    assert snapshot.run(argparse.Namespace(workspace=str(root), label=None), available=lambda: False) == 1
    assert restore.run(argparse.Namespace(workspace=str(root), list=True, snapshot_id=None), available=lambda: False) == 1
    profile = records.yaml.safe_load((root / "System/profile.yaml").read_text())
    profile["features"] = {"library_indexing": False, "snapshots": False, "ignore_rules": True}
    (root / "System/profile.yaml").write_text(records.yaml.safe_dump(profile, sort_keys=False))
    assert library.run(argparse.Namespace(workspace=str(root))) == 1
    assert recall.run(argparse.Namespace(workspace=str(root), question="cobalt", limit=5, as_json=False)) == 1
    assert snapshot.run(argparse.Namespace(workspace=str(root), label=None)) == 1
    assert restore.run(argparse.Namespace(workspace=str(root), list=True, snapshot_id=None)) == 1
    assert receipts.read_text() == "A file prevents receipt directory creation.\n"
    assert {p.name: p.read_bytes() for p in saved.iterdir()} == before


def test_repair_check_snapshot_restore_retains_meaningful_history(tmp_path, monkeypatch):
    import shutil
    from apparatus_core import snapshots
    if shutil.which("git") is None:
        pytest.skip("actual Git recovery requires Git")
    root = _area(tmp_path, monkeypatch)
    original = _history(root)
    (root / "Welcome.md").unlink()
    assert init.run(argparse.Namespace(workspace=str(root), payload=None,
                                     privacy_mode=None, work_types=None), available=lambda: False) == 0
    repaired = (root / "Welcome.md").read_bytes()
    assert check.run(argparse.Namespace(workspace=str(root), no_receipt=False)) == 0
    assert snapshot.run(argparse.Namespace(workspace=str(root), label="Repaired synthetic workspace")) == 0
    saved = snapshots.list_snapshots(root)[0].identifier
    (root / "Welcome.md").write_text("Later synthetic orientation\n")
    assert restore.run(argparse.Namespace(workspace=str(root), snapshot_id=saved, list=False)) == 0
    assert (root / "Welcome.md").read_bytes() == repaired
    history = _history(root)
    assert all(history[name] == content for name, content in original.items())
    events = [records.parse_record(content.decode())[0]["event"] for content in history.values()]
    assert events.count("init") == 2
    assert "snapshot" in events and "restore" in events
    assert "check" not in events and "recall" not in events and "library-ingest" not in events
