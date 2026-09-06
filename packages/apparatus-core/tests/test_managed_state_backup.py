from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4
import zipfile

import pytest

from apparatus_core import backup, managed_state_backup as managed, managed_state_recovery as recovery
from apparatus_core.receipts import ReceiptPublication
from apparatus_core.retention import TaskRetentionError, context_for, operation, set_no_memory, start_task
from apparatus_core.snapshots import _git_environment


def _area(tmp_path):
    root = tmp_path / "area"
    (root / "System").mkdir(parents=True)
    (root / "System/workspace.yaml").write_text(
        f"schema: apparatus/workspace@v0\nid: {uuid4()}\nlayout: sibling-projects\nrecovery: managed-state\n",
        encoding="utf-8",
    )
    (root / "System/profile.yaml").write_text(
        "schema: apparatus/profile@v0\nstatus: configured\nprivacy_mode: standard\n"
        "work_types: []\nreview_day: null\n", encoding="utf-8",
    )
    (root / "AGENTS.md").write_text("Managed instructions\n", encoding="utf-8")
    (root / "project").mkdir()
    (root / "project/private.txt").write_text("project sentinel", encoding="utf-8")
    (root / "Library").mkdir()
    (root / "Library/original.txt").write_text("Library sentinel", encoding="utf-8")
    destination = tmp_path / "exports"
    destination.mkdir()
    return root, destination


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          check=True, env=_git_environment()).stdout.strip()


def _tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _receipts(root):
    return {p.name: p.read_bytes() for p in (root / "System/receipts").glob("*.md")}


def _ref(root):
    path = root / "System/recovery/store/refs/heads/managed"
    return path.read_bytes() if path.exists() else None


def test_no_git_exports_only_declared_state_and_canonical_controls(tmp_path, monkeypatch):
    root, destination = _area(tmp_path)
    task = start_task(root, save_memory=False)
    task_path = root / f"System/tasks/{task.task_id}.yaml"
    task_path.write_bytes(task_path.read_bytes() + b"# private task comment\n")
    marker = root / "System/workspace.yaml"
    marker.write_bytes(marker.read_bytes() + b"# private marker comment\n")
    task_before = task_path.read_bytes()
    # Any reuse of legacy whole-root enumeration/history is a scope violation.
    source_type, _ = backup._anchor_types()
    monkeypatch.setattr(source_type, "write_entries", lambda *_a: pytest.fail("legacy traversal"))
    monkeypatch.setattr(source_type, "snapshot_storage", lambda *_a: pytest.fail("root Git probe"))
    result = managed.export_backup(root, destination, available=lambda: False, task_id=task.task_id)
    assert not result.snapshots_available
    with zipfile.ZipFile(result.archive) as archive:
        assert set(archive.namelist()) == {
            "AGENTS.md", "System/profile.yaml", "System/workspace.yaml", "System/tasks/",
            f"System/tasks/{task.task_id}.yaml", managed.SCOPE_NOTE,
        }
        all_bytes = b"".join(archive.read(name) for name in archive.namelist())
        for forbidden in (b"project sentinel", b"Library sentinel", b"private task comment", b"private marker comment"):
            assert forbidden not in all_bytes
        assert b"unavailable" in archive.read(managed.SCOPE_NOTE)
    assert task_path.read_bytes() == task_before
    assert not context_for(root, task_id=task.task_id).save_memory
    assert not (root / "System/recovery").exists()
    assert b"exports" not in b"".join(_receipts(root).values())


def test_empty_task_enrollment_is_included(tmp_path):
    root, destination = _area(tmp_path)
    task = start_task(root)
    with operation(root, task_id=task.task_id):
        (root / f"System/tasks/{task.task_id}.yaml").unlink()
        result = managed.export_backup(root, destination, available=lambda: False)
    with zipfile.ZipFile(result.archive) as archive:
        assert "System/tasks/" in archive.namelist()
        assert not any(name.endswith(".yaml") and name.startswith("System/tasks/")
                       for name in archive.namelist())


@pytest.mark.parametrize("filename,content", [("other.txt", b"unknown"), (f"{uuid4()}.yaml", b"bad: data")])
def test_invalid_task_metadata_fails_before_archive_or_store(tmp_path, filename, content):
    root, destination = _area(tmp_path)
    task = start_task(root)
    (root / "System/tasks" / filename).write_bytes(content)
    with pytest.raises((backup.BackupError, TaskRetentionError)):
        managed.export_backup(root, destination, task_id=task.task_id)
    assert list(destination.iterdir()) == []
    assert not (root / "System/recovery").exists()


@pytest.mark.skipif(shutil.which("git") is None, reason="actual Git history proof")
def test_archive_rebuilds_reachable_history_and_preserves_dirty_root_and_project_git(tmp_path):
    root, destination = _area(tmp_path)
    for git_root in (root, root / "project"):
        _git(git_root, "init")
        (git_root / "tracked.txt").write_text("base", encoding="utf-8")
        _git(git_root, "add", "tracked.txt")
        _git(git_root, "commit", "-m", "fixture")
        (git_root / "tracked.txt").write_text("staged", encoding="utf-8")
        _git(git_root, "add", "tracked.txt")
        (git_root / "tracked.txt").write_text("unstaged", encoding="utf-8")
        (git_root / "untracked.txt").write_text("untracked", encoding="utf-8")
    git_before = {str(p): _tree(p / ".git") for p in (root, root / "project")}
    project_before = _tree(root / "project")
    task = start_task(root, save_memory=False)
    first = recovery.take_snapshot(root, requested=True, task_id=task.task_id).snapshot
    store = root / "System/recovery/store"
    orphan = subprocess.run(["git", "--git-dir", str(store), "hash-object", "-w", "--stdin"],
                            input=b"unreachable sentinel", capture_output=True, check=True,
                            env=_git_environment()).stdout.decode().strip()
    (root / "AGENTS.md").write_text("Second instructions\n", encoding="utf-8")
    result = managed.export_backup(root, destination, task_id=task.task_id)
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(result.archive) as archive:
        assert f"System/recovery/store/objects/{orphan[:2]}/{orphan[2:]}" not in archive.namelist()
        assert all(not name.startswith((".git/", "project/", "Library/")) for name in archive.namelist())
        archive.extractall(extracted)
    assert {str(p): _tree(p / ".git") for p in (root, root / "project")} == git_before
    assert _tree(root / "project") == project_before
    assert len(recovery.list_snapshots(extracted)) == 2
    recovery.restore_snapshot(extracted, first.identifier, task_id=task.task_id)
    assert (extracted / "AGENTS.md").read_text() == "Managed instructions\n"
    assert not context_for(extracted, task_id=task.task_id).save_memory


@pytest.mark.skipif(shutil.which("git") is None, reason="actual Git history proof")
def test_existing_store_without_git_fails_instead_of_omitting_history(tmp_path):
    root, destination = _area(tmp_path)
    recovery.take_snapshot(root)
    with pytest.raises(backup.BackupError, match="history cannot be validated"):
        managed.export_backup(root, destination, available=lambda: False)
    assert list(destination.iterdir()) == []


@pytest.mark.skipif(shutil.which("git") is None, reason="actual Git history proof")
def test_unknown_store_file_is_not_archived_or_removed(tmp_path):
    root, destination = _area(tmp_path)
    recovery.take_snapshot(root)
    sentinel = root / "System/recovery/store/foreign.txt"
    sentinel.write_bytes(b"foreign store sentinel")
    before = _ref(root)
    with pytest.raises(backup.BackupError):
        managed.export_backup(root, destination)
    assert sentinel.read_bytes() == b"foreign store sentinel"
    assert _ref(root) == before
    assert list(destination.iterdir()) == []


@pytest.mark.parametrize("change", ["task", "layout", "source"])
def test_late_source_change_compensates_archive_receipt_and_preserves_user_change(tmp_path, monkeypatch, change):
    root, destination = _area(tmp_path)
    task = start_task(root)
    original = ReceiptPublication.close
    injected = False

    def close_then_change(receipt):
        nonlocal injected
        result = original(receipt)
        if "-backup-export" in receipt.path.name and not injected:
            injected = True
            if change == "task":
                set_no_memory(root, task.task_id)
            elif change == "layout":
                path = root / "System/workspace.yaml"
                path.write_bytes(path.read_bytes() + b"# changed\n")
            else:
                replacement = root / "replacement.txt"
                replacement.write_text("Concurrent instructions", encoding="utf-8")
                replacement.replace(root / "AGENTS.md")
        return result

    monkeypatch.setattr(ReceiptPublication, "close", close_then_change)
    with pytest.raises(backup.BackupError):
        managed.export_backup(root, destination, available=lambda: False, task_id=task.task_id)
    assert injected
    assert list(destination.iterdir()) == []
    assert _receipts(root) == {}
    if change == "task":
        assert not context_for(root, task_id=task.task_id).save_memory
    elif change == "layout":
        assert (root / "System/workspace.yaml").read_bytes().endswith(b"# changed\n")
    else:
        assert (root / "AGENTS.md").read_text() == "Concurrent instructions"


@pytest.mark.skipif(shutil.which("git") is None, reason="actual Git compensation proof")
@pytest.mark.parametrize("event", ["snapshot", "backup-export"])
def test_late_receipt_close_failure_compensates_ref_archive_and_receipts(tmp_path, monkeypatch, event):
    root, destination = _area(tmp_path)
    recovery.take_snapshot(root)
    before_ref, before_receipts = _ref(root), _receipts(root)
    (root / "AGENTS.md").write_text("Second instructions", encoding="utf-8")
    original = ReceiptPublication.close
    injected = False

    def close_then_fail(receipt):
        nonlocal injected
        result = original(receipt)
        if f"-{event}" in receipt.path.name and not injected:
            injected = True
            raise OSError("injected release failure")
        return result

    monkeypatch.setattr(ReceiptPublication, "close", close_then_fail)
    with pytest.raises(backup.BackupError):
        managed.export_backup(root, destination)
    assert injected
    assert list(destination.iterdir()) == []
    assert _ref(root) == before_ref
    assert _receipts(root) == before_receipts


def test_collision_preserves_existing_archive_and_uses_new_name(tmp_path):
    root, destination = _area(tmp_path)
    clock = lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)
    first = managed.export_backup(root, destination, available=lambda: False, clock=clock)
    old = first.archive.read_bytes()
    second = managed.export_backup(root, destination, available=lambda: False, clock=clock)
    assert second.archive != first.archive
    assert first.archive.read_bytes() == old


def test_unknown_empty_task_directory_is_rejected(tmp_path):
    root, destination = _area(tmp_path)
    task = start_task(root)
    (root / "System/tasks/foreign").mkdir()
    with pytest.raises(backup.BackupError):
        managed.export_backup(root, destination, available=lambda: False, task_id=task.task_id)
    assert list(destination.iterdir()) == []


def test_no_git_final_checkpoint_rejects_new_history_without_deleting_it(tmp_path, monkeypatch):
    root, destination = _area(tmp_path)
    original = ReceiptPublication.close
    injected = False

    def close_then_create(receipt):
        nonlocal injected
        result = original(receipt)
        if "-backup-export" in receipt.path.name and not injected:
            injected = True
            (root / "System/recovery").mkdir()
            (root / "System/recovery/concurrent.txt").write_bytes(b"concurrent history")
        return result

    monkeypatch.setattr(ReceiptPublication, "close", close_then_create)
    with pytest.raises(backup.BackupError, match="history appeared"):
        managed.export_backup(root, destination, available=lambda: False)
    assert list(destination.iterdir()) == []
    assert _receipts(root) == {}
    assert (root / "System/recovery/concurrent.txt").read_bytes() == b"concurrent history"


@pytest.mark.parametrize("move", ["destination", "root"])
def test_late_directory_move_is_blocked_or_compensated(tmp_path, monkeypatch, move):
    import os
    root, destination = _area(tmp_path)
    original = ReceiptPublication.close
    injected = blocked = False
    moved = (root / "exports") if move == "destination" else (tmp_path / "moved-area")

    def close_then_move(receipt):
        nonlocal injected, blocked
        result = original(receipt)
        if "-backup-export" in receipt.path.name and not injected:
            injected = True
            try:
                (destination if move == "destination" else root).rename(moved)
            except PermissionError:
                assert os.name == "nt"
                blocked = True
        return result

    monkeypatch.setattr(ReceiptPublication, "close", close_then_move)
    if os.name == "nt":
        result = managed.export_backup(root, destination, available=lambda: False)
        assert blocked and result.archive.is_file()
    else:
        with pytest.raises(backup.BackupError):
            managed.export_backup(root, destination, available=lambda: False)
        assert list((moved if move == "destination" else destination).iterdir()) == []
        assert _receipts(moved if move == "root" else root) == {}
    assert injected


def test_partial_archive_write_failure_removes_only_owned_archive(tmp_path, monkeypatch):
    root, destination = _area(tmp_path)
    winner = destination / "unrelated.zip"
    winner.write_bytes(b"existing destination bytes")
    before = _tree(root)

    def fail_after_member(source, archive, _transients=()):
        archive.writestr("partial.txt", b"partial managed bytes")
        raise OSError("injected archive write failure")

    monkeypatch.setattr(managed._ArchiveSource, "write_entries", fail_after_member)
    with pytest.raises(backup.BackupError):
        managed.export_backup(root, destination, available=lambda: False)
    assert _tree(destination) == {"unrelated.zip": b"existing destination bytes"}
    assert _tree(root) == before
