from __future__ import annotations

import argparse
from contextlib import nullcontext
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from apparatus_core.commands import restore, snapshot
from apparatus_core import records
from apparatus_core import snapshots


HAS_GIT = shutil.which("git") is not None


def _files(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


def _receipt_events(workspace: Path) -> list[str]:
    return [
        records.parse_record(path.read_text(encoding="utf-8"))[0]["event"]
        for path in sorted((workspace / "System" / "receipts").glob("*.md"))
    ]


def _clean_environment() -> dict[str, str]:
    return {name: value for name, value in os.environ.items() if not name.casefold().startswith("git_")}


def _git(workspace: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(workspace), *arguments],
        capture_output=True,
        text=True,
        check=check,
        env=_clean_environment(),
    )


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_snapshot_restore_exact_target_plus_the_surviving_restore_receipt(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "kept.txt").write_bytes(b"first\x00state")
    (workspace / "remove.txt").write_bytes(b"remove me")

    assert snapshot.run(argparse.Namespace(workspace=str(workspace), label="First")) == 0
    first_id = snapshots.list_snapshots(workspace)[0].identifier
    first_state = _files(workspace)

    (workspace / "kept.txt").write_bytes(b"second state")
    (workspace / "remove.txt").unlink()
    (workspace / "added.txt").write_bytes(b"later")
    assert snapshot.run(argparse.Namespace(workspace=str(workspace), label="Second")) == 0
    second_state = _files(workspace)

    assert restore.run(argparse.Namespace(workspace=str(workspace), snapshot_id=first_id, list=False)) == 0
    restored = _files(workspace)
    restore_receipts = [
        path for path in (workspace / "System" / "receipts").glob("*-restore*.md")
    ]
    assert len(restore_receipts) == 1
    restore_frontmatter, _ = records.parse_record(restore_receipts[0].read_text(encoding="utf-8"))
    assert restore_frontmatter["event"] == "restore"
    assert restore_frontmatter["snapshot_id"] == first_id
    assert restore_frontmatter["label"] == "First"
    restored.pop(str(restore_receipts[0].relative_to(workspace)))
    assert restored == first_state

    pre_restore = snapshots.list_snapshots(workspace)[0]
    assert pre_restore.label == f"Before restore to {first_id[:12]}"
    assert restore.run(
        argparse.Namespace(workspace=str(workspace), snapshot_id=pre_restore.identifier, list=False)
    ) == 0
    # The second state is retained by the automatic pre-restore snapshot;
    # the newly written restore receipt is the only intentional difference.
    final = _files(workspace)
    assert final["kept.txt"] == second_state["kept.txt"]
    assert final["added.txt"] == second_state["added.txt"]
    assert "remove.txt" not in final
    assert "snapshot" in capsys.readouterr().out.casefold()


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_no_changes_does_not_create_another_snapshot_or_receipt(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "sample.txt").write_text("sample\n", encoding="utf-8")
    assert snapshot.run(argparse.Namespace(workspace=str(workspace), label="Initial")) == 0
    before = snapshots.list_snapshots(workspace)
    receipts = _receipt_events(workspace)

    assert snapshot.run(argparse.Namespace(workspace=str(workspace), label=None)) == 0
    assert snapshots.list_snapshots(workspace) == before
    assert _receipt_events(workspace) == receipts
    assert "no changes since the last snapshot" in capsys.readouterr().out


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_unknown_id_and_non_directory_use_expected_exit_codes(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "sample.txt").write_text("sample\n", encoding="utf-8")
    snapshot.run(argparse.Namespace(workspace=str(workspace), label="Initial"))

    assert restore.run(
        argparse.Namespace(workspace=str(workspace), snapshot_id="deadbeef", list=False)
    ) == 1
    assert "--list" in capsys.readouterr().out
    assert len(snapshots.list_snapshots(workspace)) == 1
    file_path = tmp_path / "not-a-workspace"
    file_path.write_text("x", encoding="utf-8")
    assert snapshot.run(argparse.Namespace(workspace=str(file_path), label=None)) == 2
    assert "not a directory" in capsys.readouterr().out


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_list_is_newest_first_and_uses_snapshot_vocabulary(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "sample.txt").write_text("one\n", encoding="utf-8")
    snapshot.run(argparse.Namespace(workspace=str(workspace), label="First"))
    (workspace / "sample.txt").write_text("two\n", encoding="utf-8")
    snapshot.run(argparse.Namespace(workspace=str(workspace), label="Second"))

    assert restore.run(argparse.Namespace(workspace=str(workspace), snapshot_id=None, list=True)) == 0
    output = capsys.readouterr().out
    assert output.index("Label: Second") < output.index("Label: First")
    assert "Snapshot id:" in output
    assert "UTC date:" in output
    for banned in ("commit", "revert", "reset", "repository", "checkout"):
        assert banned not in output.casefold()


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_snapshot_receipt_precedes_save_and_names_itself(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "sample.txt").write_text("sample\n", encoding="utf-8")
    result = snapshots.take_snapshot(workspace, label="Receipt ordering")
    receipt = next((workspace / "System" / "receipts").glob("*-snapshot.md"))
    frontmatter, _ = records.parse_record(receipt.read_text(encoding="utf-8"))
    assert frontmatter["snapshot_id"] == "self"
    assert frontmatter["label"] == "Receipt ordering"
    saved = snapshots._run_git(
        workspace, ["show", "--format=", "--name-only", result.snapshot.identifier]
    )
    assert str(receipt.relative_to(workspace)) in saved.stdout


def test_unavailable_writes_invoking_receipt_and_updates_only_existing_report(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    report = workspace / "System" / "machine-report.md"
    report.parent.mkdir()
    report.write_text(
        "---\nsnapshots: \"available\"\nother: preserved\n---\n\n# Machine report\n\nSnapshots: available.\n",
        encoding="utf-8",
    )
    assert snapshot.run(
        argparse.Namespace(workspace=str(workspace), label=None),
        available=lambda: snapshots.git_available(which=lambda command: None),
    ) == 1
    assert "Snapshots are unavailable on this machine" in capsys.readouterr().out
    assert _receipt_events(workspace) == ["snapshot"]
    text = report.read_text(encoding="utf-8")
    assert 'snapshots: "unavailable"' in text
    assert "Snapshots: unavailable." in text
    assert "other: preserved" in text

    without_report = tmp_path / "without-report"
    without_report.mkdir()
    assert restore.run(
        argparse.Namespace(workspace=str(without_report), snapshot_id=None, list=True),
        available=lambda: False,
    ) == 1
    assert not (without_report / "System" / "machine-report.md").exists()
    assert _receipt_events(without_report) == ["restore"]


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_nested_workspace_is_contained_despite_hostile_git_environment(tmp_path, monkeypatch):
    parent = tmp_path / "parent"
    parent.mkdir()
    _git(parent, "init")
    _git(parent, "config", "--local", "user.name", "Parent identity")
    _git(parent, "config", "--local", "user.email", "parent@example.invalid")
    (parent / "outside.txt").write_text("outside\n", encoding="utf-8")
    _git(parent, "add", "outside.txt")
    _git(parent, "commit", "-m", "Parent state")
    workspace = parent / "nested-workspace"
    workspace.mkdir()
    (workspace / "inside.txt").write_text("inside\n", encoding="utf-8")
    global_config = tmp_path / "hostile-config"
    global_config.write_text("[user]\nname = Hostile\nemail = hostile@example.invalid\n", encoding="utf-8")
    global_config_before = global_config.read_bytes()
    monkeypatch.setenv("GIT_DIR", str(parent / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(parent))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    monkeypatch.setenv("git_index_file", str(parent / "hostile-index"))
    parent_status_before = _git(parent, "status", "--porcelain").stdout

    assert snapshot.run(argparse.Namespace(workspace=str(workspace), label="Nested")) == 0
    assert (workspace / ".git").is_dir()
    assert _git(parent, "status", "--porcelain").stdout == parent_status_before
    assert _git(parent, "config", "--local", "--get", "user.name").stdout.strip() == "Parent identity"
    assert _git(workspace, "config", "--local", "--get", "user.name").stdout.strip() == "Apparatus"
    assert _git(workspace, "config", "--local", "--get", "user.email").stdout.strip() == snapshots.GENERIC_EMAIL
    assert _git(workspace, "config", "--local", "--get", "commit.gpgsign").stdout.strip() == "false"
    assert global_config.read_bytes() == global_config_before


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_restore_removes_nested_store_created_after_target(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "sample.txt").write_text("first\n", encoding="utf-8")
    first = snapshots.take_snapshot(workspace, label="First").snapshot
    nested = workspace / "later-store"
    nested.mkdir()
    _git(nested, "init")
    _git(nested, "config", "--local", "user.name", "Nested")
    _git(nested, "config", "--local", "user.email", "nested@example.invalid")
    (nested / "nested.txt").write_text("nested\n", encoding="utf-8")
    _git(nested, "add", "nested.txt")
    _git(nested, "commit", "-m", "Nested state")
    assert (nested / ".git").is_dir()

    assert restore.run(
        argparse.Namespace(workspace=str(workspace), snapshot_id=first.identifier, list=False)
    ) == 0
    assert not nested.exists()


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_list_uses_head_history_only_and_never_mutates(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "sample.txt").write_text("first\n", encoding="utf-8")
    snapshots.take_snapshot(workspace, label="First")
    (workspace / "sample.txt").write_text("second\n", encoding="utf-8")
    snapshots.take_snapshot(workspace, label="Second")
    alternate = _git(workspace, "commit-tree", "HEAD^{tree}", "-m", "Hidden snapshot").stdout.strip()
    _git(workspace, "update-ref", "refs/heads/alternate", alternate)
    before_status = _git(workspace, "status", "--porcelain").stdout
    before_ids = [entry.identifier for entry in snapshots.list_snapshots(workspace)]

    assert restore.run(argparse.Namespace(workspace=str(workspace), snapshot_id=None, list=True)) == 0
    output = capsys.readouterr().out
    assert "Hidden snapshot" not in output
    assert "Hidden snapshot" not in [entry.label for entry in snapshots.list_snapshots(workspace)]
    assert _git(workspace, "status", "--porcelain").stdout == before_status
    assert [entry.identifier for entry in snapshots.list_snapshots(workspace)] == before_ids


def test_internal_receipt_and_report_failures_return_two_and_do_not_leak_details(tmp_path, capsys, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    events: list[str] = []

    def bad_write(*args):
        events.append("receipt")
        raise OSError("raw tool output: commit repository reset")

    def report(*args):
        events.append("report")
        return True

    assert snapshot.run(
        argparse.Namespace(workspace=str(workspace), label=None),
        available=lambda: False,
        write=bad_write,
        update_report=report,
    ) == 2
    assert events == ["receipt", "report"]
    output = capsys.readouterr().out.casefold()
    assert "raw tool output" not in output
    for banned in ("commit", "revert", "reset", "repository", "checkout"):
        assert banned not in output

    calls: list[str] = []
    assert restore.run(
        argparse.Namespace(workspace=str(workspace), snapshot_id=None, list=True),
        available=lambda: False,
        write=lambda *args: calls.append("receipt") or Path("receipt.md"),
        update_report=lambda *args: calls.append("report") or False,
    ) == 2
    assert calls == ["receipt", "report"]
    assert "could not record" in capsys.readouterr().out

    restore_events: list[str] = []
    assert restore.run(
        argparse.Namespace(workspace=str(workspace), snapshot_id=None, list=True),
        available=lambda: False,
        write=lambda *args: restore_events.append("receipt")
        or (_ for _ in ()).throw(OSError("raw receipt failure")),
        update_report=lambda *args: restore_events.append("report") or True,
    ) == 2
    assert restore_events == ["receipt", "report"]
    assert "raw receipt failure" not in capsys.readouterr().out

    assert snapshot.run(
        argparse.Namespace(workspace=str(workspace), label=None),
        available=lambda: False,
        write=lambda *args: Path("receipt.md"),
        update_report=lambda *args: (_ for _ in ()).throw(OSError("raw report failure")),
    ) == 2
    assert "raw report failure" not in capsys.readouterr().out

    assert snapshot.run(
        argparse.Namespace(workspace=str(workspace), label=None),
        available=lambda: True,
        take=lambda *args, **kwargs: (_ for _ in ()).throw(snapshots.SnapshotReceiptError("raw")),
    ) == 2
    assert "raw" not in capsys.readouterr().out

    target = snapshots.Snapshot("a" * 40, "2026-08-09T00:00:00Z", "Target")
    # This boundary test injects every recovery dependency; its synthetic target
    # has no Git tree to preflight. Actual target/control behavior is tested with Git.
    monkeypatch.setattr(restore, "restore_control_guard", lambda *_args, **_kwargs: nullcontext())
    assert restore.run(
        argparse.Namespace(workspace=str(workspace), snapshot_id=target.identifier, list=False),
        available=lambda: True,
        list_saved=lambda *args: [target],
        resolve=lambda *args: target.identifier,
        take=lambda *args, **kwargs: snapshots.SnapshotResult(target),
        restore=lambda *args: None,
        write=bad_write,
    ) == 2
    assert "raw tool output" not in capsys.readouterr().out

    def hostile_run(arguments, **kwargs):
        return subprocess.CompletedProcess(
            arguments, 1, stdout="", stderr="fatal: commit reset repository"
        )

    assert snapshot.run(
        argparse.Namespace(workspace=str(workspace), label=None),
        available=lambda: True,
        take=lambda *args, **kwargs: snapshots.take_snapshot(*args, run=hostile_run, **kwargs),
    ) == 1
    output = capsys.readouterr().out.casefold()
    assert "fatal:" not in output
    for banned in ("commit", "revert", "reset", "repository", "checkout"):
        assert banned not in output


def test_availability_probe_receives_only_controlled_git_environment(monkeypatch):
    monkeypatch.setenv("GIT_DIR", "/hostile/store")
    monkeypatch.setenv("git_work_tree", "/hostile/workspace")
    captured: dict[str, str] = {}

    def run(arguments, **kwargs):
        captured.update(kwargs["env"])
        return subprocess.CompletedProcess(arguments, 0, stdout="git version test\n", stderr="")

    assert snapshots.git_available(which=lambda command: "/fake/git", run=run)
    assert "GIT_DIR" not in captured
    assert "git_work_tree" not in captured
    assert captured["GIT_AUTHOR_NAME"] == "Apparatus"
    assert captured["GIT_CONFIG_GLOBAL"] == os.devnull
