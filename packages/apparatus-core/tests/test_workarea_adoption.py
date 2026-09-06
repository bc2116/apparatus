from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import pytest

from apparatus_core.commands import init
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.retention import start_task
from apparatus_core.snapshots import SnapshotError, SnapshotResult, _git_environment, list_snapshots, take_snapshot
from apparatus_core.workspace_layout import MARKER, new_layout_bytes, read_layout


def args(root: Path, *, adopt=False, task=None, **options):
    return argparse.Namespace(workspace=str(root), adopt=adopt, task=task,
                              privacy_mode=options.get("privacy_mode"),
                              work_types=options.get("work_types"), payload=None)


def tree(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


def git(root: Path, *values: str) -> bytes:
    return subprocess.run(["git", "-C", str(root), *values], check=True,
                          capture_output=True, env=_git_environment()).stdout


def dirty_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q")
    (root / "tracked.txt").write_text("original\n")
    git(root, "add", "tracked.txt")
    git(root, "-c", "commit.gpgsign=false", "commit", "-qm", "Synthetic baseline")
    (root / "tracked.txt").write_text("staged\n")
    git(root, "add", "tracked.txt")
    (root / "tracked.txt").write_text("unstaged\n")
    (root / "untracked.txt").write_text("untracked\n")


def git_proof(root: Path) -> tuple[bytes, ...]:
    return (git(root, "rev-parse", "HEAD"), (root / ".git/index").read_bytes(),
            (root / ".git/config").read_bytes(), (root / "tracked.txt").read_bytes(),
            (root / "untracked.txt").read_bytes())


def test_fresh_and_empty_enrollment_preserve_uuid_and_snapshot_noop(tmp_path, capsys):
    root = tmp_path / "area"
    root.mkdir()
    assert init.run(args(root)) == 0
    layout = read_layout(root)
    assert layout is not None
    before = tree(root)
    assert {"Goals", "Library", "Memory", "System"} <= {p.name for p in root.iterdir()}
    for path in (".git", "Projects", "Deliverables", "Decisions"):
        assert not (root / path).exists()
    assert (root / "Memory/Decisions").is_dir()
    assert init.run(args(root)) == 0
    assert tree(root) == before
    assert read_layout(root).workspace_id == layout.workspace_id
    assert "Managed snapshot unchanged" in capsys.readouterr().out
    assert len(list_snapshots(root)) == 1


def test_existing_nonempty_requires_explicit_adoption_with_zero_writes(tmp_path, capsys):
    root = tmp_path / "area"
    root.mkdir()
    (root / "existing.txt").write_bytes(b"existing synthetic work")
    before = tree(root)
    assert init.run(args(root), available=lambda: False) == 2
    assert "--adopt" in capsys.readouterr().out
    assert tree(root) == before
    assert read_layout(root) is None


def test_adoption_and_repair_preserve_three_dirty_repositories_and_custom_canon(tmp_path):
    root = tmp_path / "area"
    repositories = [root, root / "first-project", root / "other-name"]
    for repo in repositories:
        dirty_repo(repo)
    canon = b"# Custom instructions\r\nPreserve this project's rules.\r\n"
    (root / "AGENTS.md").write_bytes(canon)
    before = [git_proof(repo) for repo in repositories]
    commands = []
    def guarded_run(command, **options):
        commands.append(command)
        assert "-C" not in command
        return subprocess.run(command, **options)
    def save(workspace, **options):
        return take_snapshot(workspace, run=guarded_run, **options)
    assert init.run(args(root, adopt=True), take=save) == 0
    assert (root / "AGENTS.md").read_bytes() == canon
    assert [git_proof(repo) for repo in repositories] == before
    assert commands
    assert init.run(args(root), take=save) == 0
    assert [git_proof(repo) for repo in repositories] == before
    assert (root / "AGENTS.md").read_bytes() == canon


@pytest.mark.parametrize("git_kind", ["file", "symlink"])
def test_adoption_never_inspects_or_rewrites_root_git_metadata(tmp_path, git_kind):
    root = tmp_path / "area"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sentinel").write_bytes(b"outside Git metadata")
    metadata = root / ".git"
    if git_kind == "file":
        metadata.write_bytes(b"gitdir: an-unrelated-user-store\n")
    else:
        try:
            metadata.symlink_to(outside, target_is_directory=True)
        except OSError:
            pytest.skip("host cannot create symbolic links")
    before = os.readlink(metadata) if metadata.is_symlink() else metadata.read_bytes()
    assert init.run(args(root, adopt=True)) == 0
    assert (os.readlink(metadata) if metadata.is_symlink() else metadata.read_bytes()) == before
    assert tree(outside) == {"sentinel": b"outside Git metadata"}


def test_existing_profile_formatting_and_legacy_directories_survive_adoption(tmp_path):
    root = tmp_path / "area"
    (root / "System").mkdir(parents=True)
    profile = (b"# Existing profile comment\r\nprivacy_mode: private\r\n"
               b"schema: apparatus/profile@v0\r\nstatus: configured\r\n"
               b"work_types: []\r\nreview_day: null\r\n")
    (root / "System/profile.yaml").write_bytes(profile)
    for directory in ("Projects", "Deliverables", "Decisions"):
        (root / directory).mkdir()
        (root / directory / "original.bin").write_bytes(b"original")
    assert init.run(args(root, adopt=True), available=lambda: False) == 0
    assert (root / "System/profile.yaml").read_bytes() == profile
    assert init.run(args(root), available=lambda: False) == 0
    assert (root / "System/profile.yaml").read_bytes() == profile
    for directory in ("Projects", "Deliverables", "Decisions"):
        assert (root / directory / "original.bin").read_bytes() == b"original"


def test_no_save_repair_skips_snapshot_and_profile_changes_are_guarded(tmp_path, capsys):
    root = tmp_path / "area"
    assert init.run(args(root), available=lambda: False) == 0
    task = start_task(root, save_memory=False)
    controls = (root / f"System/tasks/{task.task_id}.yaml").read_bytes()
    (root / "Goals").rmdir()
    def forbidden(*_args, **_kwargs):
        pytest.fail("automatic snapshot called for a no-save task")
    assert init.run(args(root, task=task.task_id), available=lambda: True, take=forbidden) == 0
    assert "snapshot skipped" in capsys.readouterr().out
    assert not (root / "System/recovery").exists()
    before = tree(root)
    assert init.run(args(root, task=task.task_id, privacy_mode="private"), available=lambda: False) == 1
    assert tree(root) == before
    assert (root / f"System/tasks/{task.task_id}.yaml").read_bytes() == controls


@pytest.mark.parametrize("selectors", [{"privacy_mode": "private"}, {"work_types": "writing"}])
def test_no_save_missing_profile_rejects_explicit_answers_but_allows_default_repair(tmp_path, selectors):
    root = tmp_path / "area"
    assert init.run(args(root), available=lambda: False) == 0
    profile = root / "System/profile.yaml"
    defaults = profile.read_bytes()
    task = start_task(root, save_memory=False)
    control = root / f"System/tasks/{task.task_id}.yaml"
    control_bytes = control.read_bytes()
    profile.unlink()
    (root / "Goals").rmdir()
    before = tree(root)
    def forbidden():
        pytest.fail("no-save explicit profile answer reached deployment capability checks")
    assert init.run(args(root, task=task.task_id, **selectors), available=forbidden) == 1
    assert tree(root) == before
    assert not profile.exists() and not (root / "Goals").exists()
    assert init.run(args(root, task=task.task_id), available=lambda: False) == 0
    assert profile.read_bytes() == defaults
    assert (root / "Goals").is_dir()
    assert control.read_bytes() == control_bytes
    assert not (root / "System/recovery").exists()


def test_init_rejects_preselected_project_before_rereading_destination(tmp_path, monkeypatch, capsys):
    root = tmp_path / "project"
    root.mkdir()
    (root / "work.txt").write_bytes(b"Existing project work")
    before = tree(root)
    arguments = args(root, adopt=True)
    arguments._project_context_selected = True
    arguments._project_context = object()
    def forbidden(*_args, **_kwargs):
        pytest.fail("bound-project selection was discarded before init planning")
    monkeypatch.setattr(init, "resolve_payload", forbidden)
    assert init.run(arguments) == 2
    assert "selected a bound project" in capsys.readouterr().out
    assert tree(root) == before
    assert not (root / "System").exists()


def test_unchanged_profile_proof_allows_native_and_retained_snapshot_reads(tmp_path):
    root = tmp_path / "area"
    assert init.run(args(root), available=lambda: False) == 0
    expected = (root / "System/profile.yaml").read_bytes()
    observed = []
    def inspect_profile(workspace, **_options):
        with WorkspaceAnchor(workspace) as anchor:
            proof = anchor.capture_file("System/profile.yaml", publication_compatible=True)
            try:
                result = subprocess.run([sys.executable, "-I", "-c",
                    "import pathlib,sys;sys.stdout.buffer.write(pathlib.Path(sys.argv[1]).read_bytes())",
                    str(root / "System/profile.yaml")], capture_output=True)
                observed.append((result.returncode, result.stdout, result.stderr))
                assert observed[-1] == (0, expected, b""), observed[-1]
                assert anchor.matches_owned(proof)
            finally:
                proof.close()
        return SnapshotResult(snapshot=None, no_changes=True)
    assert init.run(args(root), available=lambda: True, take=inspect_profile) == 0
    assert len(observed) == 1


def test_explicit_profile_replacement_releases_read_pin_and_retains_rollback(tmp_path, monkeypatch):
    root = tmp_path / "area"
    assert init.run(args(root), available=lambda: False) == 0
    before = tree(root)
    original = WorkspaceAnchor.matches_owned
    published = []
    def reject_new_profile(anchor, owned):
        if owned.relative == Path("profile.yaml") and b"privacy_mode: private" in owned.content:
            published.append(owned.content)
            return False
        return original(anchor, owned)
    with monkeypatch.context() as patch:
        patch.setattr(WorkspaceAnchor, "matches_owned", reject_new_profile)
        assert init.run(args(root, privacy_mode="private"), available=lambda: False) == 2
    assert published
    assert tree(root) == before
    assert init.run(args(root, privacy_mode="private"), available=lambda: False) == 0
    assert b"privacy_mode: private" in (root / "System/profile.yaml").read_bytes()


@pytest.mark.parametrize("control", ["invalid-marker", "residual-recovery", "marker-directory"])
def test_bad_enrollment_controls_fail_before_any_deployment(tmp_path, control):
    root = tmp_path / "area"
    (root / "System").mkdir(parents=True)
    if control == "invalid-marker":
        (root / MARKER).write_bytes(b"schema: unknown\n")
    elif control == "residual-recovery":
        (root / "System/recovery").mkdir()
        (root / "System/recovery/sentinel").write_bytes(b"preserve")
    else:
        (root / MARKER).mkdir()
    before = tree(root)
    assert init.run(args(root, adopt=True), available=lambda: False) == 2
    assert tree(root) == before
    assert not (root / "AGENTS.md").exists()


def test_late_failure_after_marker_creation_rolls_back_enrollment_and_payload(tmp_path, monkeypatch):
    root = tmp_path / "area"
    root.mkdir()
    (root / "existing.bin").write_bytes(b"existing work")
    before = tree(root)
    original = WorkspaceAnchor.matches_owned
    witness = []
    def fail_marker(anchor, owned):
        if owned.relative == Path("workspace.yaml"):
            witness.append(owned.content)
            return False
        return original(anchor, owned)
    monkeypatch.setattr(WorkspaceAnchor, "matches_owned", fail_marker)
    assert init.run(args(root, adopt=True), available=lambda: False) == 2
    assert witness
    assert tree(root) == before
    assert read_layout(root) is None


def test_snapshot_failure_keeps_committed_enrollment_for_safe_retry(tmp_path, capsys):
    root = tmp_path / "area"
    def fail(*_args, **_kwargs):
        raise SnapshotError("synthetic snapshot failure")
    assert init.run(args(root), available=lambda: True, take=fail) == 2
    layout = read_layout(root)
    assert layout is not None
    assert "deployment completed" in capsys.readouterr().out
    assert not (root / ".git").exists()
    assert init.run(args(root)) == 0
    assert read_layout(root).workspace_id == layout.workspace_id


def test_init_rejects_bound_project_without_redirecting_deployment(tmp_path, capsys):
    from apparatus_core.project_binding import bind_project
    root = tmp_path / "area"
    assert init.run(args(root), available=lambda: False) == 0
    project = root / "existing-project"
    project.mkdir()
    bind_project(project, root)
    before = tree(root)
    assert init.run(args(project, adopt=True), available=lambda: False) == 2
    assert "bound project" in capsys.readouterr().out
    assert tree(root) == before
    assert not (project / MARKER).exists()


def test_concurrent_marker_change_blocks_repair_before_other_writes(tmp_path):
    root = tmp_path / "area"
    assert init.run(args(root), available=lambda: False) == 0
    (root / "Goals").rmdir()
    before = tree(root)
    replacement = new_layout_bytes()
    def change_marker():
        # Atomic replacement works with retained readers on both platforms.
        with WorkspaceAnchor(root / "System") as anchor:
            content, identity = anchor.read_file("workspace.yaml")
            change = anchor.replace_if_unchanged("workspace.yaml", identity, content, replacement)
            try:
                change.commit()
            finally:
                change.close()
        return False
    assert init.run(args(root), available=change_marker) == 2
    assert tree(root) == {**before, MARKER: replacement}
    assert not (root / "Goals").exists()


def test_new_marker_bytes_are_fresh_closed_controls():
    first, second = new_layout_bytes(), new_layout_bytes()
    assert first != second
    assert b"schema: apparatus/workspace@v0" in first
    assert b"layout: sibling-projects" in first
