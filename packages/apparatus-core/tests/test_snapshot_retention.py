from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import zipfile

import pytest

from apparatus_core import snapshots
from apparatus_core.backup import export_backup
from apparatus_core.commands import restore, snapshot
from apparatus_core.retention import (
    RetentionSuppressed, TaskRetentionError, context_for, set_no_memory, start_task,
)

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="actual Git recovery proof")


def _workspace(tmp_path):
    root = tmp_path / "workspace"
    (root / "System").mkdir(parents=True)
    (root / "System/profile.yaml").write_text(
        "schema: apparatus/profile@v0\nstatus: configured\nprivacy_mode: standard\n"
        "work_types: []\nreview_day: null\n", encoding="utf-8",
    )
    (root / "ordinary.txt").write_text("old ordinary bytes", encoding="utf-8")
    return root


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, text=True,
        capture_output=True, env=snapshots._git_environment(),
    ).stdout.strip()


def _raw_snapshot(root):
    _git(root, "init")
    _git(root, "add", "--all", "--force")
    _git(root, "commit", "-m", "Fixture recovery point")
    return _git(root, "rev-parse", "HEAD")


def _files(root):
    return {
        path.relative_to(root).as_posix(): None if path.is_dir() else path.read_bytes()
        for path in root.rglob("*")
    }


def _controls(root):
    return _files(root / "System/tasks")


def test_automatic_snapshot_and_preparation_stop_before_git_or_capture(tmp_path, capsys):
    root = _workspace(tmp_path)
    task = start_task(root, save_memory=False)
    before = _files(root)
    with pytest.raises(RetentionSuppressed):
        snapshots.take_snapshot(root, task_id=task.task_id, label="private label sentinel")
    with pytest.raises(RetentionSuppressed):
        snapshots.prepare_snapshot(
            root, task_id=task.task_id, label="private label sentinel",
            capture=lambda *_args: pytest.fail("capture must not start"),
        )
    assert snapshot.run(argparse.Namespace(
        workspace=str(root), task=task.task_id, label="private label sentinel", requested=False,
    ), available=lambda: pytest.fail("capability probe must not start")) == 1
    assert "skipped" in capsys.readouterr().out
    assert _files(root) == before
    assert not (root / ".git").exists()


def test_requested_snapshot_omits_even_previously_tracked_controls_and_raw_label(tmp_path):
    root = _workspace(tmp_path)
    task = start_task(root, save_memory=False)
    _raw_snapshot(root)  # Simulate legacy history containing control metadata.
    controls = _controls(root)
    (root / "ordinary.txt").write_text("new ordinary bytes", encoding="utf-8")
    result = snapshots.take_snapshot(root, task_id=task.task_id, requested=True, label="private label sentinel")
    assert result.snapshot is not None
    assert "System/tasks" not in _git(root, "ls-tree", "-r", "--name-only", "HEAD")
    assert "private label sentinel" not in _git(root, "log", "-1", "--format=%B")
    assert _controls(root) == controls
    receipts = b"".join(path.read_bytes() for path in (root / "System/receipts").glob("*.md"))
    assert b"private label sentinel" not in receipts


def test_controls_only_changes_do_not_trigger_a_snapshot(tmp_path):
    root = _workspace(tmp_path)
    task = start_task(root, save_memory=True)
    first = snapshots.take_snapshot(root, task_id=task.task_id).snapshot
    start_task(root, save_memory=False)
    before = _files(root)
    assert snapshots.take_snapshot(root, task_id=task.task_id).no_changes
    assert _git(root, "rev-parse", "HEAD") == first.identifier
    assert _files(root) == before


def test_requested_backup_keeps_current_controls_but_snapshot_does_not(tmp_path):
    root = _workspace(tmp_path)
    task = start_task(root, save_memory=False)
    destination = tmp_path / "backup-destination"
    destination.mkdir()
    with pytest.raises(TaskRetentionError):
        export_backup(root, destination)
    assert not (root / ".git").exists()
    result = export_backup(root, destination, task_id=task.task_id)
    assert result.snapshot_id is not None
    with zipfile.ZipFile(result.archive) as archive:
        relative = f"System/tasks/{task.task_id}.yaml"
        assert archive.read(relative) == (root / relative).read_bytes()
    assert "System/tasks" not in _git(root, "ls-tree", "-r", "--name-only", "HEAD")
    assert not context_for(root, task_id=task.task_id).save_memory
    with pytest.raises(RetentionSuppressed):
        snapshots.take_snapshot(root, task_id=task.task_id)


def test_restore_target_before_enrollment_keeps_controls_and_skips_automatic_snapshot(tmp_path, capsys):
    root = _workspace(tmp_path)
    shutil.rmtree(root / "System")
    target = _raw_snapshot(root)  # Old target has no System ancestor at all.
    (root / "System").mkdir()
    (root / "System/profile.yaml").write_text(
        "schema: apparatus/profile@v0\nstatus: configured\nprivacy_mode: standard\n"
        "work_types: []\nreview_day: null\n", encoding="utf-8",
    )
    task = start_task(root, save_memory=False)
    controls = _controls(root)
    (root / "ordinary.txt").write_text("new ordinary bytes", encoding="utf-8")
    assert restore.run(argparse.Namespace(
        workspace=str(root), task=task.task_id, snapshot_id=target, list=False,
    ), take=lambda *_args, **_kwargs: pytest.fail("no-save restore must not snapshot")) == 0
    assert "pre-restore snapshot skipped" in capsys.readouterr().out
    assert _git(root, "rev-list", "--count", "HEAD") == "1"
    assert (root / "ordinary.txt").read_text() == "old ordinary bytes"
    assert _controls(root) == controls
    with pytest.raises(TaskRetentionError):
        context_for(root, require_task=True)


def test_restore_never_reinstates_legacy_saving_control(tmp_path):
    root = _workspace(tmp_path)
    task = start_task(root, save_memory=True)
    target = _raw_snapshot(root)
    set_no_memory(root, task.task_id)
    controls = _controls(root)
    (root / "ordinary.txt").write_text("new ordinary bytes", encoding="utf-8")
    snapshots.restore_snapshot(root, target, task_id=task.task_id)
    assert _controls(root) == controls
    assert not context_for(root, task_id=task.task_id).save_memory


@pytest.mark.parametrize("failure", ["restore", "clean"])
def test_restore_failure_keeps_live_controls(tmp_path, failure):
    root = _workspace(tmp_path)
    target = _raw_snapshot(root)
    task = start_task(root, save_memory=False)
    controls = _controls(root)
    def fail(arguments, **kwargs):
        if arguments[3] == failure:
            return subprocess.CompletedProcess(arguments, 1, stdout="", stderr="injected")
        return subprocess.run(arguments, **kwargs)
    with pytest.raises(snapshots.SnapshotError):
        snapshots.restore_snapshot(root, target, task_id=task.task_id, run=fail)
    assert _controls(root) == controls
    assert not context_for(root, task_id=task.task_id).save_memory


def test_concurrent_no_memory_update_survives_restore(tmp_path):
    root = _workspace(tmp_path)
    target = _raw_snapshot(root)
    task = start_task(root, save_memory=True)
    changed = []
    def update(arguments, **kwargs):
        result = subprocess.run(arguments, **kwargs)
        if arguments[3] == "restore":
            set_no_memory(root, task.task_id)
            changed.append(True)
        return result
    snapshots.restore_snapshot(root, target, task_id=task.task_id, run=update)
    assert changed == [True]
    assert not context_for(root, task_id=task.task_id).save_memory


@pytest.mark.parametrize("mode", ["100644", "120000", "160000"])
def test_incompatible_target_ancestor_rejects_before_any_mutation(tmp_path, mode):
    root = _workspace(tmp_path)
    target = _raw_snapshot(root)
    # Construct historical tree entries directly, including symlink/gitlink modes,
    # without requiring platform symlink privileges or external repositories.
    blob = subprocess.run(
        ["git", "-C", str(root), "hash-object", "-w", "--stdin"],
        input="historical ancestor", text=True, capture_output=True, check=True,
    ).stdout.strip()
    object_id = target if mode == "160000" else blob
    object_kind = "commit" if mode == "160000" else "blob"
    tree = subprocess.run(
        ["git", "-C", str(root), "mktree"],
        input=f"{mode} {object_kind} {object_id}\tSystem\n", text=True,
        capture_output=True, check=True,
    ).stdout.strip()
    bad_target = _git(root, "commit-tree", tree, "-p", target, "-m", "Historical conflict")
    task = start_task(root, save_memory=True)
    before = _files(root)
    with pytest.raises(snapshots.SnapshotError):
        snapshots.restore_snapshot(root, bad_target, task_id=task.task_id)
    assert restore.run(argparse.Namespace(
        workspace=str(root), task=task.task_id, snapshot_id=bad_target, list=False,
    ), list_saved=lambda *_args: [snapshots.Snapshot(bad_target, "2026-09-06T00:00:00Z", "Conflict")],
        take=lambda *_args, **_kwargs: pytest.fail("preflight must precede snapshot")) == 1
    assert _files(root) == before


def test_restore_receipt_failure_preserves_controls_after_real_restore(tmp_path, capsys):
    root = _workspace(tmp_path)
    target = _raw_snapshot(root)
    task = start_task(root, save_memory=False)
    controls = _controls(root)
    (root / "ordinary.txt").write_text("new ordinary bytes", encoding="utf-8")
    def fail_receipt(*_args, **_kwargs):
        raise OSError("private error sentinel")
    assert restore.run(argparse.Namespace(
        workspace=str(root), task=task.task_id, snapshot_id=target, list=False,
    ), write=fail_receipt) == 2
    assert (root / "ordinary.txt").read_text() == "old ordinary bytes"
    assert _controls(root) == controls
    assert not context_for(root, task_id=task.task_id).save_memory
    assert "private error sentinel" not in capsys.readouterr().out
