"""Public command routing and scope, with real dirty project repositories."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from uuid import uuid4
import zipfile

import pytest

from apparatus_core import snapshots
from apparatus_core.commands import backup, restore, snapshot
from apparatus_core.retention import start_task


def area(tmp_path):
    root = tmp_path / "area"
    (root / "System").mkdir(parents=True)
    (root / "System/workspace.yaml").write_text(
        f"schema: apparatus/workspace@v0\nid: {uuid4()}\n"
        "layout: sibling-projects\nrecovery: managed-state\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("Original instructions\n", encoding="utf-8")
    (root / "System/profile.yaml").write_text(
        "schema: apparatus/profile@v0\nstatus: configured\nprivacy_mode: standard\n"
        "work_types: []\nreview_day: null\n", encoding="utf-8")
    return root


def arguments(root, **kwargs):
    return argparse.Namespace(workspace=str(root), **kwargs)


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, env=snapshots._git_environment()).stdout


def dirty_repo(root):
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q")
    (root / "tracked.txt").write_text("initial\n", encoding="utf-8")
    git(root, "add", "tracked.txt")
    git(root, "-c", "commit.gpgsign=false", "commit", "-qm", "Synthetic baseline")
    (root / "tracked.txt").write_text("staged\n", encoding="utf-8")
    git(root, "add", "tracked.txt")
    (root / "tracked.txt").write_text("unstaged\n", encoding="utf-8")
    (root / "untracked.txt").write_text("project sentinel\n", encoding="utf-8")


def proof(root):
    return (git(root, "rev-parse", "HEAD"),
            *((root / path).read_bytes() for path in
              (".git/index", ".git/config", "tracked.txt", "untracked.txt")))


@pytest.mark.skipif(shutil.which("git") is None, reason="actual Git integration")
def test_commands_preserve_three_dirty_repositories_and_describe_actual_scope(tmp_path, capsys):
    root = area(tmp_path)
    repos = [root, root / "project-a", root / "project-b"]
    for repo in repos:
        dirty_repo(repo)
    before = [proof(repo) for repo in repos]
    (root / "Library").mkdir()
    (root / "Library/source.txt").write_text("Library sentinel", encoding="utf-8")
    assert snapshot.run(arguments(root, label="Initial")) == 0
    first = snapshots.list_snapshots(root)[0]
    assert first.scope == "managed-state"
    assert "Project files and Library originals are not included" in capsys.readouterr().out

    def forbidden(*_args, **_kwargs):
        pytest.fail("managed preparation called a legacy root capture")

    transaction = snapshots.prepare_snapshot(root, label=None, capture=forbidden)
    try:
        assert transaction.result.no_changes
        transaction.commit()
    finally:
        transaction.close()
    (root / "AGENTS.md").write_text("Changed instructions\n", encoding="utf-8")
    assert restore.run(arguments(root, snapshot_id=first.short_id, list=False)) == 0
    output = capsys.readouterr().out
    assert first.timestamp in output
    assert "Files added since that snapshot" in output
    assert (root / "AGENTS.md").read_text() == "Original instructions\n"
    # Managed restore owns exactly one receipt inside its file transaction.
    assert len(list((root / "System/receipts").glob("*-restore*.md"))) == 1
    assert [proof(repo) for repo in repos] == before

    destination = tmp_path / "exports"
    destination.mkdir()
    assert backup.run(arguments(root, destination=str(destination))) == 0
    assert "project files and Library originals are not included" in capsys.readouterr().out
    with zipfile.ZipFile(next(destination.glob("*.zip"))) as archive:
        names = archive.namelist()
        assert not any(name.startswith((".git/", "project-a/", "project-b/", "Library/")) for name in names)
    assert [proof(repo) for repo in repos] == before


@pytest.mark.parametrize("verb", [snapshot, restore])
@pytest.mark.parametrize("git_present", [False, True])
def test_invalid_enrollment_is_actionable_before_capability_receipts(tmp_path, capsys, verb, git_present):
    root = area(tmp_path)
    (root / "System/workspace.yaml").write_text("schema: invalid\n", encoding="utf-8")
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    def forbidden(*_args, **_kwargs):
        pytest.fail("invalid routing reached a recovery or capability writer")

    assert verb.run(arguments(root, snapshot_id=None, list=True),
                    available=lambda: git_present, write=forbidden, update_report=forbidden) == 2
    assert "repair System/workspace.yaml" in capsys.readouterr().out
    assert {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    assert not (root / "System/recovery").exists()


@pytest.mark.parametrize("listing", [False, True])
def test_restore_reports_invalid_history_without_mutation_or_traceback(tmp_path, capsys, listing):
    root = area(tmp_path)
    store = root / "System/recovery/store"
    store.mkdir(parents=True)
    (store / "sentinel.txt").write_text("unrelated", encoding="utf-8")
    assert restore.run(arguments(root, snapshot_id="abc123", list=listing),
                       available=lambda: True) == 1
    assert "restore:" in capsys.readouterr().out
    assert not (root / "System/receipts").exists()
    assert not (root / ".git").exists()


def test_no_save_automatic_command_stops_before_capability_probe(tmp_path, capsys):
    root = area(tmp_path)
    task = start_task(root, save_memory=False)

    def forbidden():
        pytest.fail("automatic no-save snapshot probed Git")

    assert snapshot.run(arguments(root, task=task.task_id), available=forbidden) == 1
    assert "does not save Memory" in capsys.readouterr().out
    assert not (root / "System/recovery").exists()


def test_current_state_only_backup_reports_missing_history(tmp_path, capsys):
    root = area(tmp_path)
    destination = tmp_path / "exports"
    destination.mkdir()
    assert backup.run(arguments(root, destination=str(destination)), available=lambda: False) == 0
    assert "only current Apparatus state is included" in capsys.readouterr().out
