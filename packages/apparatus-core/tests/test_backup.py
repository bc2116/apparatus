from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import datetime, timezone
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import time
import zipfile

import pytest

from apparatus_core import fs_transactions, records, snapshots
from apparatus_core import backup as backup_engine
from apparatus_core.backup import BackupError, export_backup
from apparatus_core.commands import backup


HAS_GIT = shutil.which("git") is not None


def _files(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _clock() -> datetime:
    return datetime(2026, 8, 10, 12, 34, 56, tzinfo=timezone.utc)


def _archives(destination: Path) -> list[Path]:
    return sorted(destination.glob("apparatus-backup-*.zip"))


def _git(workspace: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = {
        name: value for name, value in os.environ.items() if not name.casefold().startswith("git_")
    }
    return subprocess.run(
        ["git", "-C", str(workspace), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )


def _head_paths(workspace: Path) -> set[str]:
    return set(
        _git(workspace, "ls-tree", "-r", "--name-only", "HEAD")
        .stdout.strip()
        .splitlines()
    )


def _status_paths(workspace: Path) -> set[str]:
    return {
        line[3:]
        for line in _git(workspace, "status", "--porcelain").stdout.splitlines()
        if len(line) > 3
    }


def _head_or_none(workspace: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "--verify", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        env={
            name: value
            for name, value in os.environ.items()
            if not name.casefold().startswith("git_")
        },
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _prepared_failure_state(workspace: Path, *, history: str = "existing") -> dict[str, object]:
    workspace.mkdir()
    tracked = workspace / "tracked.txt"
    if history == "existing":
        tracked.write_bytes(b"initial\n")
        snapshots.take_snapshot(workspace, label="Initial")
        tracked.write_bytes(b"staged\n")
        _git(workspace, "add", "tracked.txt")
        tracked.write_bytes(b"worktree\n")
    elif history == "unborn":
        snapshots.ensure_snapshot_store(workspace)
        tracked.write_bytes(b"unborn worktree\n")
    else:  # pragma: no cover - test helper contract
        raise AssertionError(f"unknown history state: {history}")
    index = workspace / ".git" / "index"
    receipts = workspace / "System" / "receipts"
    return {
        "head": _head_or_none(workspace),
        "index": index.read_bytes() if index.exists() else None,
        "tracked": tracked.read_bytes(),
        "receipts": _files(receipts) if receipts.exists() else {},
        "status": _git(workspace, "status", "--porcelain").stdout,
    }


def _assert_prepared_failure_state(workspace: Path, expected: dict[str, object]) -> None:
    index = workspace / ".git" / "index"
    receipts = workspace / "System" / "receipts"
    assert _head_or_none(workspace) == expected["head"]
    if expected["index"] is None:
        assert not index.exists()
    else:
        assert index.read_bytes() == expected["index"]
    assert (workspace / "tracked.txt").read_bytes() == expected["tracked"]
    assert (_files(receipts) if receipts.exists() else {}) == expected["receipts"]
    assert _git(workspace, "status", "--porcelain").stdout == expected["status"]
    if receipts.exists():
        assert not list(receipts.glob(".apparatus-receipt-*.tmp"))
    assert not list((workspace / ".git").rglob(".apparatus-restore-*.tmp"))


_LATE_DESTINATION_MOVE_STAGES = (
    "after-old-containment-before-archive-finish",
    "after-archive-finish-before-receipt-publication",
    "after-receipt-publication-before-return",
)


def _install_late_destination_move(
    monkeypatch,
    *,
    stage: str,
    move: Callable[[], None],
) -> Callable[..., object]:
    """Inject one move in each late-success window without adding a test hook."""
    _workspace_anchor_type, destination_anchor_type = backup_engine._anchor_types()
    original_require_outside = destination_anchor_type.require_outside
    containment_checks = 0

    def racing_require_outside(self, source, *args, **kwargs):
        nonlocal containment_checks
        result = original_require_outside(self, source, *args, **kwargs)
        containment_checks += 1
        if (
            stage == "after-old-containment-before-archive-finish"
            and containment_checks == 3
        ):
            move()
        return result

    monkeypatch.setattr(
        destination_anchor_type,
        "require_outside",
        racing_require_outside,
    )

    def racing_write(*args, **kwargs):
        if stage == "after-archive-finish-before-receipt-publication":
            move()
        publication = backup_engine.write_receipt(*args, **kwargs)
        if stage == "after-receipt-publication-before-return":
            move()
        return publication

    return racing_write


def test_export_archives_hidden_files_and_writes_a_valid_receipt(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / ".hidden").write_bytes(b"hidden\x00bytes")
    (workspace / "nested").mkdir()
    (workspace / "nested" / "file.txt").write_text("saved\n", encoding="utf-8")
    (workspace / ".empty").mkdir()

    result = export_backup(workspace, destination, available=lambda: False, clock=_clock)
    expected = _files(workspace)
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(result.archive) as archive:
        archive.extractall(extracted)
    # The receipt is intentionally written after the archive lands.
    expected.pop(next(name for name in expected if "-backup-export" in name))
    assert _files(extracted) == expected
    assert (extracted / ".empty").is_dir()
    assert result.archive.name == "apparatus-backup-2026-08-10-123456.zip"
    receipt = next((workspace / "System" / "receipts").glob("*-backup-export.md"))
    frontmatter, _body = records.parse_record(receipt.read_text(encoding="utf-8"))
    assert records.validate("receipt", frontmatter) == []
    assert frontmatter["archive_filename"] == result.archive.name
    assert frontmatter["destination"] == str(destination)
    assert frontmatter["archive_size"] == result.size
    assert "snapshot_id" not in frontmatter


def test_command_without_snapshots_succeeds_with_plain_language_message(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_text("now\n", encoding="utf-8")

    assert backup.run(
        argparse.Namespace(workspace=str(workspace), destination=str(destination)),
        available=lambda: False,
    ) == 0
    output = capsys.readouterr().out
    assert "exactly as it is now" in output
    assert "To restore, unzip this archive into a fresh folder." in output
    for banned in ("git", "commit", "repository", "checkout"):
        assert banned not in output.casefold()


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_export_takes_a_snapshot_first_and_archive_keeps_snapshot_storage(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_text("saved\n", encoding="utf-8")

    result = export_backup(workspace, destination, clock=_clock)
    assert result.snapshot_id is not None
    assert snapshots.list_snapshots(workspace)[0].identifier == result.snapshot_id
    with zipfile.ZipFile(result.archive) as archive:
        assert any(name.startswith(".git/") for name in archive.namelist())
    receipt = next((workspace / "System" / "receipts").glob("*-backup-export.md"))
    frontmatter, _body = records.parse_record(receipt.read_text(encoding="utf-8"))
    assert frontmatter["snapshot_id"] == result.snapshot_id


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_unborn_snapshot_cas_preserves_a_concurrent_first_head(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_text("workspace state\n", encoding="utf-8")
    raced = False
    concurrent_head: str | None = None
    observed_expected: str | None = None

    def racing_run(arguments, **kwargs):
        nonlocal raced, concurrent_head, observed_expected
        if (
            len(arguments) == 7
            and arguments[:4] == ["git", "-C", str(workspace), "update-ref"]
            and arguments[4] == "HEAD"
            and not raced
        ):
            raced = True
            observed_expected = arguments[6]
            empty_tree = subprocess.run(
                ["git", "-C", str(workspace), "mktree"],
                input="",
                check=True,
                capture_output=True,
                text=True,
                env=kwargs["env"],
            ).stdout.strip()
            concurrent_head = subprocess.run(
                [
                    "git",
                    "-C",
                    str(workspace),
                    "-c",
                    "commit.gpgsign=false",
                    "commit-tree",
                    empty_tree,
                    "-m",
                    "Concurrent first snapshot",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=kwargs["env"],
            ).stdout.strip()
            _git(
                workspace,
                "update-ref",
                "HEAD",
                concurrent_head,
                "0" * len(concurrent_head),
            )
        return subprocess.run(arguments, **kwargs)

    def racing_take(*args, **kwargs):
        return snapshots.prepare_snapshot(*args, run=racing_run, **kwargs)

    with pytest.raises(BackupError, match="pre-export snapshot"):
        export_backup(
            workspace,
            destination,
            take=racing_take,
            clock=_clock,
        )

    assert raced
    assert concurrent_head is not None
    assert observed_expected == "0" * len(concurrent_head)
    assert _git(workspace, "rev-parse", "HEAD").stdout.strip() == concurrent_head
    assert _git(workspace, "show", "-s", "--format=%s", "HEAD").stdout.strip() == (
        "Concurrent first snapshot"
    )
    assert list((workspace / "System" / "receipts").glob("*.md")) == []
    assert _archives(destination) == []


def test_destination_collision_uses_suffix_without_changing_unrelated_file(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_text("saved\n", encoding="utf-8")
    existing = destination / "apparatus-backup-2026-08-10-123456.zip"
    existing.write_bytes(b"unrelated bytes")

    result = export_backup(workspace, destination, available=lambda: False, clock=_clock)
    assert result.archive.name == "apparatus-backup-2026-08-10-123456-2.zip"
    assert existing.read_bytes() == b"unrelated bytes"


@pytest.mark.parametrize(
    ("workspace", "destination", "message"),
    [
        ("missing", "destination", "workspace path is not a safe directory"),
        ("workspace", "missing", "destination path does not exist"),
        ("workspace", "inside", "destination must be outside the workspace"),
    ],
)
def test_invalid_paths_are_usage_errors(tmp_path, capsys, workspace, destination, message):
    root = tmp_path / "workspace"
    target = tmp_path / "destination"
    root.mkdir()
    target.mkdir()
    if destination == "inside":
        target = root / "inside"
        target.mkdir()
    workspace_path = tmp_path / workspace if workspace == "missing" else root
    destination_path = tmp_path / destination if destination == "missing" else target
    assert backup.run(
        argparse.Namespace(workspace=str(workspace_path), destination=str(destination_path))
    ) == 2
    assert message in capsys.readouterr().out


def test_archive_creation_never_opens_existing_destination_files_for_reading(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_text("saved\n", encoding="utf-8")
    unrelated = destination / "keep.txt"
    unrelated.write_bytes(b"do not read")
    original_open = Path.open

    def guarded_open(path: Path, *args, **kwargs):
        mode = args[0] if args else kwargs.get("mode", "r")
        if path == unrelated and "r" in mode:
            raise AssertionError("destination content was read")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    export_backup(workspace, destination, available=lambda: False, clock=_clock)
    assert unrelated.stat().st_size == len(b"do not read")


@pytest.mark.skipif(os.name != "posix", reason="descriptor-relative POSIX probe")
def test_source_swap_to_outside_symlink_never_archives_outside_bytes(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    outside = tmp_path / "outside.txt"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "inside.txt").write_bytes(b"inside")
    outside.write_bytes(b"outside-secret")
    original_open = backup_engine.os.open
    swapped = False

    def swapping_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if path == "inside.txt" and kwargs.get("dir_fd") is not None and not swapped:
            swapped = True
            (workspace / "inside.txt").unlink()
            (workspace / "inside.txt").symlink_to(outside)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(backup_engine.os, "open", swapping_open)
    monkeypatch.setattr(
        backup_engine.os,
        "supports_dir_fd",
        backup_engine.os.supports_dir_fd | {swapping_open},
    )
    with pytest.raises(BackupError, match="read safely"):
        export_backup(workspace, destination, available=lambda: False, clock=_clock)
    assert swapped
    assert _archives(destination) == []
    assert outside.read_bytes() == b"outside-secret"


@pytest.mark.skipif(os.name != "posix", reason="descriptor-relative POSIX probe")
def test_destination_swap_to_workspace_is_detected_and_owned_archive_is_removed(
    tmp_path, monkeypatch
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    moved_destination = tmp_path / "moved-backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "inside.txt").write_bytes(b"inside")
    original_open = backup_engine.os.open
    swapped = False

    def swapping_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if (
            isinstance(path, str)
            and path.startswith("apparatus-backup-")
            and flags & os.O_EXCL
            and not swapped
        ):
            swapped = True
            destination.rename(moved_destination)
            destination.symlink_to(workspace, target_is_directory=True)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(backup_engine.os, "open", swapping_open)
    monkeypatch.setattr(
        backup_engine.os,
        "supports_dir_fd",
        backup_engine.os.supports_dir_fd | {swapping_open},
    )
    with pytest.raises(BackupError, match="Destination path changed"):
        export_backup(workspace, destination, available=lambda: False, clock=_clock)
    assert swapped
    assert _archives(moved_destination) == []
    assert _archives(workspace) == []


@pytest.mark.skipif(os.name != "posix", reason="descriptor-relative POSIX snapshot probe")
def test_destination_moved_during_snapshot_is_never_snapshot_input_and_leaves_no_mutation(
    tmp_path, monkeypatch
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    moved_destination = workspace / "moved-backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "inside.txt").write_bytes(b"inside")
    (destination / "destination-sentinel.txt").write_bytes(b"never snapshot or read")
    initial = snapshots.take_snapshot(workspace, label="Initial").snapshot
    assert initial is not None
    head_before = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    index_before = (workspace / ".git/index").read_bytes()
    receipts_before = set((workspace / "System/receipts").iterdir())
    destination_identity = (destination.stat().st_dev, destination.stat().st_ino)
    original_listdir = backup_engine.os.listdir

    def guarded_listdir(path):
        if isinstance(path, int):
            value = os.fstat(path)
            if (value.st_dev, value.st_ino) == destination_identity:
                raise AssertionError("destination content was read during snapshot")
        return original_listdir(path)

    def racing_take(*args, **kwargs):
        destination.rename(moved_destination)
        return snapshots.prepare_snapshot(*args, **kwargs)

    monkeypatch.setattr(backup_engine.os, "listdir", guarded_listdir)
    with pytest.raises(BackupError, match="Destination moved into the workspace"):
        export_backup(workspace, destination, take=racing_take, clock=_clock)

    assert _git(workspace, "rev-parse", "HEAD").stdout.strip() == head_before
    assert (workspace / ".git/index").read_bytes() == index_before
    assert set((workspace / "System/receipts").iterdir()) == receipts_before
    assert (moved_destination / "destination-sentinel.txt").read_bytes() == b"never snapshot or read"
    with pytest.raises(subprocess.CalledProcessError):
        _git(workspace, "cat-file", "-e", "HEAD:moved-backups/destination-sentinel.txt")
    assert _archives(moved_destination) == []


@pytest.mark.skipif(
    os.name != "posix" or not HAS_GIT,
    reason=(
        "POSIX permits a retained destination directory to be renamed; "
        "the rollback proof also requires git"
    ),
)
@pytest.mark.parametrize("stage", _LATE_DESTINATION_MOVE_STAGES)
def test_posix_late_destination_move_inside_workspace_fails_cleanly(
    tmp_path,
    monkeypatch,
    stage,
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    moved_destination = workspace / "moved-backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_bytes(b"clean snapshotted state\n")
    initial = snapshots.take_snapshot(workspace, label="Initial").snapshot
    assert initial is not None
    head_before = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    receipts_before = _files(workspace / "System" / "receipts")
    assert _status_paths(workspace) == set()
    moved = False

    def move_destination() -> None:
        nonlocal moved
        assert not moved
        destination.rename(moved_destination)
        moved = True

    racing_write = _install_late_destination_move(
        monkeypatch,
        stage=stage,
        move=move_destination,
    )

    with pytest.raises(BackupError):
        export_backup(
            workspace,
            destination,
            write=racing_write,
            clock=_clock,
        )

    assert moved
    assert not destination.exists()
    assert moved_destination.is_dir()
    assert _archives(moved_destination) == []
    assert not list(workspace.rglob("apparatus-backup-*.zip"))
    assert not list((workspace / "System" / "receipts").glob("*-backup-export.md"))
    assert _files(workspace / "System" / "receipts") == receipts_before
    assert _git(workspace, "rev-parse", "HEAD").stdout.strip() == head_before
    assert _status_paths(workspace) == set()


@pytest.mark.skipif(
    os.name != "nt",
    reason="native Win32 retained directory-name lock proof",
)
@pytest.mark.parametrize("stage", _LATE_DESTINATION_MOVE_STAGES)
def test_windows_late_destination_move_is_blocked_non_vacuously(
    tmp_path,
    monkeypatch,
    stage,
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    moved_destination = workspace / "moved-backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_bytes(b"saved\n")
    rename_control = tmp_path / "rename-control"
    moved_control = workspace / "rename-control"
    rename_control.mkdir()
    rename_control.rename(moved_control)
    moved_control.rename(rename_control)
    rename_control.rmdir()
    move_errors: list[OSError] = []

    def attempt_destination_move() -> None:
        try:
            destination.rename(moved_destination)
        except OSError as error:
            move_errors.append(error)
        else:
            raise AssertionError("retained destination name moved on Windows")

    racing_write = _install_late_destination_move(
        monkeypatch,
        stage=stage,
        move=attempt_destination_move,
    )

    result = export_backup(
        workspace,
        destination,
        available=lambda: False,
        write=racing_write,
        clock=_clock,
    )

    assert len(move_errors) == 1
    assert result.archive == destination / "apparatus-backup-2026-08-10-123456.zip"
    assert result.archive.is_file()
    assert not moved_destination.exists()
    assert not list(workspace.rglob("apparatus-backup-*.zip"))


@pytest.mark.parametrize(
    ("marker", "content"),
    [
        ("commondir", "../external-history\n"),
        ("objects/info/alternates", "../../../external-objects\n"),
    ],
)
@pytest.mark.skipif(not HAS_GIT, reason="concurrent history-marker probe requires git")
def test_concurrent_history_indirection_inserted_at_archive_traversal_is_rejected(
    tmp_path,
    monkeypatch,
    marker,
    content,
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    destination.mkdir()
    expected = _prepared_failure_state(workspace)
    marker_path = workspace / ".git" / marker
    original_write_archive = backup_engine._write_archive
    injected = False

    def insert_history_marker(source, owned, transient_paths=()):
        nonlocal injected
        assert not injected
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(content, encoding="utf-8")
        injected = True
        return original_write_archive(source, owned, transient_paths)

    monkeypatch.setattr(backup_engine, "_write_archive", insert_history_marker)

    with pytest.raises(BackupError, match="external snapshot history"):
        export_backup(workspace, destination, clock=_clock)

    assert injected
    assert marker_path.read_text(encoding="utf-8") == content
    assert _archives(destination) == []
    assert not list((workspace / "System" / "receipts").glob("*-backup-export.md"))
    marker_path.unlink()
    _assert_prepared_failure_state(workspace, expected)


@pytest.mark.skipif(
    os.name != "posix" or not HAS_GIT,
    reason="POSIX same-inode committed receipt mutation probe requires git",
)
def test_committed_backup_receipt_same_length_mutation_never_returns_success(
    tmp_path,
    monkeypatch,
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    destination.mkdir()
    expected = _prepared_failure_state(workspace)
    original_commit = backup_engine.ReceiptPublication.commit
    mutated_path: Path | None = None
    mutated_content: bytes | None = None
    original_inode: int | None = None

    def commit_then_mutate(publication):
        nonlocal mutated_path, mutated_content, original_inode
        result = original_commit(publication)
        if "-backup-export" in publication.path.name:
            mutated_path = publication.path
            original = mutated_path.read_bytes()
            mutated_content = original.replace(b"Backup exported", b"Backup Exported", 1)
            assert mutated_content != original
            assert len(mutated_content) == len(original)
            original_inode = mutated_path.stat().st_ino
            mutated_path.write_bytes(mutated_content)
            assert mutated_path.stat().st_ino == original_inode
        return result

    monkeypatch.setattr(
        backup_engine.ReceiptPublication,
        "commit",
        commit_then_mutate,
    )

    with pytest.raises(BackupError, match="exact cleanup"):
        export_backup(workspace, destination, clock=_clock)

    assert mutated_path is not None
    assert mutated_content is not None
    assert mutated_path.read_bytes() == mutated_content
    assert mutated_path.stat().st_ino == original_inode
    assert _archives(destination) == []
    assert _head_or_none(workspace) == expected["head"]
    assert (workspace / ".git" / "index").read_bytes() == expected["index"]
    assert (workspace / "tracked.txt").read_bytes() == expected["tracked"]
    for relative, content_before in expected["receipts"].items():
        assert (workspace / "System" / "receipts" / relative).read_bytes() == content_before
    assert not list(
        (workspace / "System" / "receipts").glob(".apparatus-receipt-*.tmp")
    )


@pytest.mark.skipif(
    os.name != "nt" or not HAS_GIT,
    reason="native Win32 committed receipt write-lock proof requires git",
)
def test_windows_committed_backup_receipt_mutation_is_blocked_non_vacuously(
    tmp_path,
    monkeypatch,
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "tracked.txt").write_bytes(b"saved\n")
    control = tmp_path / "mutation-control"
    control.write_bytes(b"original")
    control.write_bytes(b"changed!")
    assert control.read_bytes() == b"changed!"
    original_commit = backup_engine.ReceiptPublication.commit
    mutation_errors: list[OSError] = []

    def commit_then_attempt_mutation(publication):
        result = original_commit(publication)
        if "-backup-export" in publication.path.name:
            original = publication.path.read_bytes()
            mutated = original.replace(b"Backup exported", b"Backup Exported", 1)
            assert mutated != original
            assert len(mutated) == len(original)
            try:
                publication.path.write_bytes(mutated)
            except OSError as error:
                mutation_errors.append(error)
            else:
                raise AssertionError("committed receipt changed while its proof was retained")
        return result

    monkeypatch.setattr(
        backup_engine.ReceiptPublication,
        "commit",
        commit_then_attempt_mutation,
    )

    result = export_backup(workspace, destination, clock=_clock)

    assert len(mutation_errors) == 1
    assert result.archive.is_file()
    receipt = next((workspace / "System/receipts").glob("*-backup-export.md"))
    assert b"Backup exported" in receipt.read_bytes()


@pytest.mark.skipif(not HAS_GIT, reason="receipt claim cleanup probe requires git")
@pytest.mark.parametrize("timing", ["before-claim", "after-claim"])
def test_backup_receipt_claim_failure_removes_exact_publication_and_alias(
    tmp_path,
    monkeypatch,
    timing,
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    destination.mkdir()
    expected = _prepared_failure_state(workspace)
    original_claim = backup_engine.ReceiptPublication.claim
    injected = False

    def fail_backup_claim(publication, invocation):
        nonlocal injected
        if "-backup-export" in publication.path.name:
            injected = True
            if timing == "after-claim":
                original_claim(publication, invocation)
            raise OSError("injected claim failure")
        return original_claim(publication, invocation)

    monkeypatch.setattr(
        backup_engine.ReceiptPublication,
        "claim",
        fail_backup_claim,
    )

    with pytest.raises(BackupError, match="receipt could not be recorded"):
        export_backup(workspace, destination, clock=_clock)

    assert injected
    assert _archives(destination) == []
    _assert_prepared_failure_state(workspace, expected)


@pytest.mark.skipif(
    os.name != "posix" or not HAS_GIT,
    reason="POSIX permits the retained destination to move during receipt release",
)
def test_posix_destination_move_during_actual_receipt_close_is_compensated(
    tmp_path,
    monkeypatch,
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    moved_destination = workspace / "moved-backups"
    destination.mkdir()
    expected = _prepared_failure_state(workspace)
    original_close = backup_engine.ReceiptPublication.close
    moved = False

    def close_then_move(publication):
        nonlocal moved
        is_backup = "-backup-export" in publication.path.name
        result = original_close(publication)
        if is_backup and not moved:
            destination.rename(moved_destination)
            moved = True
        return result

    monkeypatch.setattr(
        backup_engine.ReceiptPublication,
        "close",
        close_then_move,
    )

    with pytest.raises(BackupError):
        export_backup(workspace, destination, clock=_clock)

    assert moved
    assert not destination.exists()
    assert moved_destination.is_dir()
    assert _archives(moved_destination) == []
    assert not list(workspace.rglob("apparatus-backup-*.zip"))
    _assert_prepared_failure_state(workspace, expected)


@pytest.mark.skipif(
    os.name != "nt",
    reason="native Win32 receipt-release destination lock proof",
)
def test_windows_destination_move_during_actual_receipt_close_is_blocked(
    tmp_path,
    monkeypatch,
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    moved_destination = workspace / "moved-backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_bytes(b"saved\n")
    control = tmp_path / "rename-control"
    moved_control = workspace / "rename-control"
    control.mkdir()
    control.rename(moved_control)
    moved_control.rename(control)
    control.rmdir()
    original_close = backup_engine.ReceiptPublication.close
    move_errors: list[OSError] = []

    def close_then_attempt_move(publication):
        is_backup = "-backup-export" in publication.path.name
        result = original_close(publication)
        if is_backup:
            try:
                destination.rename(moved_destination)
            except OSError as error:
                move_errors.append(error)
            else:
                raise AssertionError("retained destination name moved on Windows")
        return result

    monkeypatch.setattr(
        backup_engine.ReceiptPublication,
        "close",
        close_then_attempt_move,
    )

    result = export_backup(
        workspace,
        destination,
        available=lambda: False,
        clock=_clock,
    )

    assert len(move_errors) == 1
    assert result.archive.is_file()
    assert not moved_destination.exists()


@pytest.mark.parametrize("history", ["existing", "unborn"])
@pytest.mark.parametrize("event", ["backup-export", "snapshot"])
@pytest.mark.skipif(not HAS_GIT, reason="receipt release rollback probe requires git")
def test_receipt_close_then_raise_retains_complete_compensation(
    tmp_path,
    monkeypatch,
    history,
    event,
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    destination.mkdir()
    expected = _prepared_failure_state(workspace, history=history)
    original_close = backup_engine.ReceiptPublication.close
    injected = False

    def close_then_raise(publication):
        nonlocal injected
        is_target = f"-{event}" in publication.path.name
        result = original_close(publication)
        if is_target and not injected:
            injected = True
            raise OSError("injected close-after-release failure")
        return result

    monkeypatch.setattr(
        backup_engine.ReceiptPublication,
        "close",
        close_then_raise,
    )

    with pytest.raises(BackupError):
        export_backup(workspace, destination, clock=_clock)

    assert injected
    assert _archives(destination) == []
    _assert_prepared_failure_state(workspace, expected)


@pytest.mark.skipif(
    os.name != "posix" or not HAS_GIT,
    reason="POSIX workspace-root replacement rollback proof requires git",
)
@pytest.mark.parametrize("history", ["existing", "unborn"])
def test_detected_workspace_root_replacement_rolls_back_through_retained_history(
    tmp_path,
    monkeypatch,
    history,
):
    workspace = tmp_path / "workspace"
    detached = tmp_path / "detached-workspace"
    destination = tmp_path / "backups"
    destination.mkdir()
    expected = _prepared_failure_state(workspace, history=history)
    _source_type, destination_type = backup_engine._anchor_types()
    original_require_outside = destination_type.require_outside
    changed_checks = 0
    replaced = False

    def replace_root_at_checkpoint(self, source, *args, **kwargs):
        nonlocal changed_checks, replaced
        result = original_require_outside(self, source, *args, **kwargs)
        if kwargs.get("changed"):
            changed_checks += 1
            if changed_checks == 2:
                workspace.rename(detached)
                workspace.mkdir()
                (workspace / "foreign.txt").write_bytes(b"foreign replacement\n")
                replaced = True
        return result

    monkeypatch.setattr(
        destination_type,
        "require_outside",
        replace_root_at_checkpoint,
    )

    with pytest.raises(BackupError):
        export_backup(workspace, destination, clock=_clock)

    assert replaced
    assert _files(workspace) == {"foreign.txt": b"foreign replacement\n"}
    assert _archives(destination) == []
    assert not list(detached.rglob("apparatus-backup-*.zip"))
    _assert_prepared_failure_state(detached, expected)


@pytest.mark.skipif(
    os.name != "posix" or not HAS_GIT,
    reason="POSIX workspace can move during the actual receipt-release boundary",
)
def test_workspace_root_move_during_actual_receipt_close_is_compensated(
    tmp_path,
    monkeypatch,
):
    workspace = tmp_path / "workspace"
    detached = tmp_path / "detached-workspace"
    destination = tmp_path / "backups"
    destination.mkdir()
    expected = _prepared_failure_state(workspace)
    original_close = backup_engine.ReceiptPublication.close
    moved = False

    def close_then_move_root(publication):
        nonlocal moved
        is_backup = "-backup-export" in publication.path.name
        result = original_close(publication)
        if is_backup and not moved:
            workspace.rename(detached)
            workspace.mkdir()
            (workspace / "foreign.txt").write_bytes(b"foreign replacement\n")
            moved = True
        return result

    monkeypatch.setattr(
        backup_engine.ReceiptPublication,
        "close",
        close_then_move_root,
    )

    with pytest.raises(BackupError):
        export_backup(workspace, destination, clock=_clock)

    assert moved
    assert _files(workspace) == {"foreign.txt": b"foreign replacement\n"}
    assert _archives(destination) == []
    _assert_prepared_failure_state(detached, expected)


@pytest.mark.skipif(
    os.name != "nt",
    reason="native Win32 actual receipt-release workspace lock proof",
)
def test_windows_workspace_move_during_actual_receipt_close_is_blocked(
    tmp_path,
    monkeypatch,
):
    workspace = tmp_path / "workspace"
    moved_workspace = tmp_path / "moved-workspace"
    destination = tmp_path / "backups"
    destination.mkdir()
    _prepared_failure_state(workspace)
    control = tmp_path / "rename-control"
    moved_control = tmp_path / "moved-control"
    control.mkdir()
    control.rename(moved_control)
    moved_control.rename(control)
    control.rmdir()
    original_close = backup_engine.ReceiptPublication.close
    move_errors: list[OSError] = []

    def close_then_attempt_move(publication):
        is_backup = "-backup-export" in publication.path.name
        result = original_close(publication)
        if is_backup:
            try:
                workspace.rename(moved_workspace)
            except OSError as error:
                move_errors.append(error)
            else:
                raise AssertionError("retained workspace name moved on Windows")
        return result

    monkeypatch.setattr(
        backup_engine.ReceiptPublication,
        "close",
        close_then_attempt_move,
    )

    result = export_backup(workspace, destination, clock=_clock)

    assert len(move_errors) == 1
    assert result.archive.is_file()
    assert workspace.is_dir()
    assert not moved_workspace.exists()


@pytest.mark.parametrize("seam", ["receipt-file-proof", "archive-proof"])
@pytest.mark.skipif(not HAS_GIT, reason="final handle-release probe requires git")
def test_final_checkpoint_is_followed_only_by_nonraising_handle_teardown(
    tmp_path,
    monkeypatch,
    seam,
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "tracked.txt").write_bytes(b"clean\n")
    snapshots.take_snapshot(workspace, label="Initial")
    assert _git(workspace, "status", "--porcelain").stdout == ""
    original_checkpoint = backup_engine._require_success_checkpoint
    final_seen = False
    injected = False

    def observe_final_checkpoint(*args, **kwargs):
        nonlocal final_seen
        result = original_checkpoint(*args, **kwargs)
        if kwargs.get("durable"):
            final_seen = True
        return result

    monkeypatch.setattr(
        backup_engine,
        "_require_success_checkpoint",
        observe_final_checkpoint,
    )

    if seam == "receipt-file-proof":
        original_release = fs_transactions.OwnedFile.close

        def release_then_raise(owned):
            nonlocal injected
            result = original_release(owned)
            if final_seen and not injected:
                injected = True
                raise OSError("injected proof-handle close failure")
            return result

        monkeypatch.setattr(
            fs_transactions.OwnedFile,
            "close",
            release_then_raise,
        )
    else:
        archive_type = (
            backup_engine._WindowsOwnedArchive
            if os.name == "nt"
            else backup_engine._PosixOwnedArchive
        )
        original_release = archive_type.finish

        def release_then_raise(owned):
            nonlocal injected
            assert final_seen
            result = original_release(owned)
            if not injected:
                injected = True
                raise OSError("injected archive-handle close failure")
            return result

        monkeypatch.setattr(archive_type, "finish", release_then_raise)

    result = export_backup(workspace, destination, clock=_clock)

    assert final_seen
    assert injected
    assert result.archive.is_file()
    receipts = list((workspace / "System/receipts").glob("*-backup-export.md"))
    assert len(receipts) == 1
    assert _status_paths(workspace) == {receipts[0].relative_to(workspace).as_posix()}
    assert not list(
        (workspace / "System/receipts").glob(".apparatus-receipt-*.tmp")
    )


@pytest.mark.skipif(
    os.name != "posix" or not HAS_GIT,
    reason="POSIX loose-ref identity substitution proof requires git",
)
def test_same_content_ref_substitution_is_preserved_and_fails_loudly(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    destination.mkdir()
    expected = _prepared_failure_state(workspace)
    ref_name = _git(workspace, "symbolic-ref", "HEAD").stdout.strip()
    ref_path = workspace / ".git" / ref_name
    displaced = ref_path.with_name(ref_path.name + ".concurrent")
    replacement = f"{expected['head']}\n".encode("ascii")
    substituted = False

    def substitute_ref(*args, **kwargs):
        nonlocal substituted
        publication = backup_engine.write_receipt(*args, **kwargs)
        if "-backup-export" in publication.path.name:
            ref_path.rename(displaced)
            ref_path.write_bytes(replacement)
            substituted = True
        return publication

    with pytest.raises(BackupError, match="exact cleanup"):
        export_backup(
            workspace,
            destination,
            write=substitute_ref,
            clock=_clock,
        )

    assert substituted
    assert ref_path.read_bytes() == replacement
    assert displaced.is_file()
    assert displaced.read_bytes() != replacement
    assert _archives(destination) == []
    assert not list((workspace / "System/receipts").glob("*-backup-export.md"))
    assert not list(
        (workspace / "System/receipts").glob(".apparatus-receipt-*.tmp")
    )


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_failed_archive_rolls_back_prepared_snapshot_and_preserves_index_and_worktree(
    tmp_path, monkeypatch
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "tracked.txt").write_text("first\n", encoding="utf-8")
    snapshots.take_snapshot(workspace, label="Initial")
    (workspace / "tracked.txt").write_text("staged\n", encoding="utf-8")
    _git(workspace, "add", "tracked.txt")
    (workspace / "tracked.txt").write_text("worktree\n", encoding="utf-8")
    head_before = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    index_before = (workspace / ".git/index").read_bytes()
    receipts_before = set((workspace / "System/receipts").iterdir())

    monkeypatch.setattr(
        backup_engine,
        "_write_chunks",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("injected write failure")),
    )
    with pytest.raises(BackupError, match="could not be read safely"):
        export_backup(workspace, destination, clock=_clock)

    assert _git(workspace, "rev-parse", "HEAD").stdout.strip() == head_before
    assert (workspace / ".git/index").read_bytes() == index_before
    assert (workspace / "tracked.txt").read_text(encoding="utf-8") == "worktree\n"
    assert set((workspace / "System/receipts").iterdir()) == receipts_before
    assert _archives(destination) == []


@pytest.mark.skipif(
    os.name != "posix" or not HAS_GIT,
    reason="POSIX in-place receipt edit probe requires git",
)
def test_failed_export_preserves_same_size_concurrent_snapshot_receipt_edit(
    tmp_path, monkeypatch
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_text("first\n", encoding="utf-8")
    snapshots.take_snapshot(workspace, label="Initial")
    (workspace / "note.txt").write_text("changed\n", encoding="utf-8")
    head_before = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    edited_path: Path | None = None
    edited_content: bytes | None = None

    def edit_owned_receipt(*args, **kwargs):
        nonlocal edited_path, edited_content
        transaction = snapshots.prepare_snapshot(*args, **kwargs)
        assert transaction.receipt is not None
        edited_path = transaction.receipt.path
        original = edited_path.read_bytes()
        edited_content = original.replace(b"Snapshot saved", b"Snapshot Saved", 1)
        assert edited_content != original
        assert len(edited_content) == len(original)
        edited_path.write_bytes(edited_content)
        return transaction

    monkeypatch.setattr(
        backup_engine,
        "_write_chunks",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError("injected write failure")
        ),
    )
    with pytest.raises(BackupError, match="exact cleanup"):
        export_backup(
            workspace,
            destination,
            take=edit_owned_receipt,
            clock=_clock,
        )

    assert _git(workspace, "rev-parse", "HEAD").stdout.strip() == head_before
    assert edited_path is not None
    assert edited_content is not None
    assert edited_path.read_bytes() == edited_content
    assert _archives(destination) == []


@pytest.mark.skipif(
    os.name != "posix" or not HAS_GIT,
    reason="POSIX late-settlement receipt probe requires git",
)
def test_late_snapshot_receipt_edit_compensates_archive_and_success_receipt(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_bytes(b"initial\n")
    snapshots.take_snapshot(workspace, label="Initial")
    (workspace / "note.txt").write_bytes(b"changed\n")
    head_before = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    snapshot_receipt: Path | None = None
    edited_content: bytes | None = None
    transient: Path | None = None

    def observing_take(*args, **kwargs):
        nonlocal snapshot_receipt, transient
        transaction = snapshots.prepare_snapshot(*args, **kwargs)
        assert transaction.receipt is not None
        assert len(transaction.transient_paths) == 1
        snapshot_receipt = transaction.receipt.path
        transient = transaction.transient_paths[0].relative
        return transaction

    def publish_then_edit(*args, **kwargs):
        nonlocal edited_content
        publication = backup_engine.write_receipt(*args, **kwargs)
        assert snapshot_receipt is not None
        original = snapshot_receipt.read_bytes()
        edited_content = original.replace(b"Snapshot saved", b"Snapshot Saved", 1)
        assert edited_content != original
        assert len(edited_content) == len(original)
        snapshot_receipt.write_bytes(edited_content)
        return publication

    with pytest.raises(BackupError, match="exact cleanup"):
        export_backup(
            workspace,
            destination,
            take=observing_take,
            write=publish_then_edit,
            clock=_clock,
        )

    assert _git(workspace, "rev-parse", "HEAD").stdout.strip() == head_before
    assert _archives(destination) == []
    assert not list((workspace / "System" / "receipts").glob("*-backup-export.md"))
    assert snapshot_receipt is not None
    assert edited_content is not None
    assert snapshot_receipt.read_bytes() == edited_content
    assert transient is not None
    assert not (workspace / transient).exists()
    assert transient.as_posix() not in _status_paths(workspace)


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_successful_prepared_snapshot_preserves_index_and_worktree_bytes(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "tracked.txt").write_text("first\n", encoding="utf-8")
    snapshots.take_snapshot(workspace, label="Initial")
    (workspace / "tracked.txt").write_text("staged\n", encoding="utf-8")
    _git(workspace, "add", "tracked.txt")
    (workspace / "tracked.txt").write_text("worktree\n", encoding="utf-8")
    index_before = (workspace / ".git/index").read_bytes()

    result = export_backup(workspace, destination, clock=_clock)

    assert result.snapshot_id is not None
    assert (workspace / ".git/index").read_bytes() == index_before
    assert (workspace / "tracked.txt").read_text(encoding="utf-8") == "worktree\n"
    assert _git(workspace, "show", "HEAD:tracked.txt").stdout == "worktree\n"


@pytest.mark.skipif(
    os.name != "posix" or not HAS_GIT,
    reason="POSIX snapshot receipt ownership probe requires git",
)
def test_unborn_export_omits_owned_receipt_alias_and_preserves_caller_state(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_bytes(b"unborn working bytes\n")
    receipts = workspace / "System" / "receipts"
    receipts.mkdir(parents=True)
    lookalike = receipts / ".apparatus-receipt-deadbeef.tmp"
    lookalike.write_bytes(b"pre-existing lookalike\n")
    index = workspace / ".git" / "index"
    assert not index.exists()
    transient: Path | None = None

    def observing_take(*args, **kwargs):
        nonlocal transient
        transaction = snapshots.prepare_snapshot(*args, **kwargs)
        assert len(transaction.transient_paths) == 1
        transient = transaction.transient_paths[0].relative
        return transaction

    result = export_backup(
        workspace,
        destination,
        take=observing_take,
        clock=_clock,
    )

    assert transient is not None
    transient_name = transient.as_posix()
    assert transient_name not in _head_paths(workspace)
    assert transient_name not in _status_paths(workspace)
    assert not (workspace / transient).exists()
    assert not index.exists()
    assert (workspace / "note.txt").read_bytes() == b"unborn working bytes\n"
    assert lookalike.read_bytes() == b"pre-existing lookalike\n"
    with zipfile.ZipFile(result.archive) as archive:
        names = set(archive.namelist())
        assert transient_name not in names
        assert archive.read("note.txt") == b"unborn working bytes\n"
        assert archive.read(lookalike.relative_to(workspace).as_posix()) == (
            b"pre-existing lookalike\n"
        )
    assert lookalike.relative_to(workspace).as_posix() in _head_paths(workspace)
    assert any(name.endswith("-snapshot.md") for name in _head_paths(workspace))


@pytest.mark.skipif(
    os.name != "posix" or not HAS_GIT,
    reason="POSIX snapshot receipt ownership probe requires git",
)
def test_existing_export_omits_owned_receipt_alias_and_preserves_caller_bytes(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "tracked.txt").write_bytes(b"initial\n")
    snapshots.take_snapshot(workspace, label="Initial")
    (workspace / "tracked.txt").write_bytes(b"staged\n")
    _git(workspace, "add", "tracked.txt")
    (workspace / "tracked.txt").write_bytes(b"working\n")
    index_before = (workspace / ".git" / "index").read_bytes()
    transient: Path | None = None

    def observing_take(*args, **kwargs):
        nonlocal transient
        transaction = snapshots.prepare_snapshot(*args, **kwargs)
        assert len(transaction.transient_paths) == 1
        transient = transaction.transient_paths[0].relative
        return transaction

    result = export_backup(
        workspace,
        destination,
        take=observing_take,
        clock=_clock,
    )

    assert transient is not None
    transient_name = transient.as_posix()
    assert transient_name not in _head_paths(workspace)
    assert transient_name not in _status_paths(workspace)
    assert not (workspace / transient).exists()
    assert (workspace / ".git" / "index").read_bytes() == index_before
    assert (workspace / "tracked.txt").read_bytes() == b"working\n"
    assert _git(workspace, "show", "HEAD:tracked.txt").stdout == "working\n"
    with zipfile.ZipFile(result.archive) as archive:
        assert transient_name not in set(archive.namelist())
        assert archive.read("tracked.txt") == b"working\n"


@pytest.mark.skipif(
    os.name != "posix" or not HAS_GIT,
    reason="POSIX clean-filter probe requires git",
)
def test_prepared_snapshot_never_executes_or_applies_clean_filters(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    marker = tmp_path / "filter-ran"
    filter_script = tmp_path / "upper-filter.sh"
    workspace.mkdir()
    destination.mkdir()
    filter_script.write_text(
        "#!/bin/sh\nprintf ran > "
        + shlex.quote(str(marker))
        + "\ntr '[:lower:]' '[:upper:]'\n",
        encoding="utf-8",
    )
    filter_script.chmod(0o755)
    (workspace / ".gitattributes").write_text(
        "note.txt filter=upper\n",
        encoding="utf-8",
    )
    (workspace / "note.txt").write_bytes(b"captured lowercase\n")
    snapshots.ensure_snapshot_store(workspace)
    _git(workspace, "config", "filter.upper.clean", str(filter_script))

    result = export_backup(workspace, destination, clock=_clock)

    assert not marker.exists()
    assert _git(workspace, "show", "HEAD:note.txt").stdout == "captured lowercase\n"
    with zipfile.ZipFile(result.archive) as archive:
        assert archive.read("note.txt") == b"captured lowercase\n"
    (workspace / "note.txt").write_bytes(b"later\n")
    snapshots.restore_snapshot(workspace, result.snapshot_id or "")
    assert (workspace / "note.txt").read_bytes() == b"captured lowercase\n"
    assert not marker.exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX symbolic-link probe")
def test_symbolic_link_content_is_rejected_and_partial_archive_is_removed(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    outside = tmp_path / "outside.txt"
    workspace.mkdir()
    destination.mkdir()
    outside.write_bytes(b"outside")
    (workspace / "linked.txt").symlink_to(outside)

    with pytest.raises(BackupError, match="unsupported filesystem entry"):
        export_backup(workspace, destination, available=lambda: False, clock=_clock)
    assert _archives(destination) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows junction probe")
def test_windows_junction_content_is_rejected_and_partial_archive_is_removed(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    outside = tmp_path / "outside"
    workspace.mkdir()
    destination.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_bytes(b"outside")
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(workspace / "junction"), str(outside)],
        check=True,
        capture_output=True,
        text=True,
    )

    with pytest.raises(BackupError, match="unsupported filesystem entry"):
        export_backup(workspace, destination, available=lambda: False, clock=_clock)
    assert _archives(destination) == []


@pytest.mark.skipif(os.name != "posix", reason="exclusive-create POSIX race probe")
def test_collision_race_retries_without_reading_or_modifying_winner(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_bytes(b"saved")
    first_name = "apparatus-backup-2026-08-10-123456.zip"
    original_open = backup_engine.os.open
    raced = False

    def racing_open(path, flags, *args, **kwargs):
        nonlocal raced
        if path == first_name and flags & os.O_EXCL and not raced:
            raced = True
            winner = original_open(path, flags, 0o600, dir_fd=kwargs["dir_fd"])
            os.write(winner, b"race-winner")
            os.close(winner)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(backup_engine.os, "open", racing_open)
    monkeypatch.setattr(
        backup_engine.os,
        "supports_dir_fd",
        backup_engine.os.supports_dir_fd | {racing_open},
    )
    result = export_backup(
        workspace,
        destination,
        available=lambda: False,
        clock=_clock,
    )
    assert raced
    assert result.archive.name == "apparatus-backup-2026-08-10-123456-2.zip"
    assert (destination / first_name).read_bytes() == b"race-winner"


def test_mid_write_failure_removes_only_the_invocation_owned_archive(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_bytes(b"saved")
    unrelated = destination / "keep.bin"
    unrelated.write_bytes(b"preserved")

    def fail_write(*_args, **_kwargs):
        raise OSError("injected write failure")

    monkeypatch.setattr(backup_engine, "_write_chunks", fail_write)
    with pytest.raises(BackupError, match="could not be read safely"):
        export_backup(workspace, destination, available=lambda: False, clock=_clock)
    assert _archives(destination) == []
    assert unrelated.read_bytes() == b"preserved"


@pytest.mark.skipif(os.name != "posix", reason="POSIX archive ownership probe")
def test_archive_name_substitution_never_returns_foreign_replacement(
    tmp_path, monkeypatch
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    moved = destination / "moved-owned.zip"
    final = destination / "apparatus-backup-2026-08-10-123456.zip"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_bytes(b"saved")
    original_write = backup_engine._write_chunks
    substituted = False

    def substitute_then_write(*args, **kwargs):
        nonlocal substituted
        if not substituted:
            substituted = True
            final.rename(moved)
            final.write_bytes(b"foreign replacement")
        return original_write(*args, **kwargs)

    monkeypatch.setattr(backup_engine, "_write_chunks", substitute_then_write)
    with pytest.raises(BackupError, match="exact cleanup"):
        export_backup(workspace, destination, available=lambda: False, clock=_clock)

    assert substituted
    assert final.read_bytes() == b"foreign replacement"
    assert moved.is_file()
    assert not list((workspace / "System" / "receipts").glob("*-backup-export.md"))


@pytest.mark.skipif(os.name != "posix", reason="POSIX archive ownership probe")
def test_failed_write_after_archive_rename_fails_loudly_and_preserves_substitution(
    tmp_path, monkeypatch
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    moved = destination / "moved-partial.zip"
    final = destination / "apparatus-backup-2026-08-10-123456.zip"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_bytes(b"saved")

    def rename_then_fail(*_args, **_kwargs):
        final.rename(moved)
        final.write_bytes(b"foreign replacement")
        raise OSError("injected write failure")

    monkeypatch.setattr(backup_engine, "_write_chunks", rename_then_fail)
    with pytest.raises(BackupError, match="exact cleanup"):
        export_backup(workspace, destination, available=lambda: False, clock=_clock)

    assert final.read_bytes() == b"foreign replacement"
    assert moved.is_file()
    assert not list((workspace / "System" / "receipts").glob("*-backup-export.md"))


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_export_receipt_failure_removes_archive_and_rolls_back_prepared_snapshot(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_bytes(b"saved")
    snapshots.take_snapshot(workspace, label="Initial")
    (workspace / "note.txt").write_bytes(b"changed")
    head_before = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    receipts_before = set((workspace / "System/receipts").iterdir())

    def fail_receipt(*_args, **_kwargs):
        raise OSError("injected receipt failure")

    with pytest.raises(BackupError, match="receipt could not be recorded"):
        export_backup(
            workspace,
            destination,
            write=fail_receipt,
            clock=_clock,
        )
    assert _archives(destination) == []
    assert _git(workspace, "rev-parse", "HEAD").stdout.strip() == head_before
    assert set((workspace / "System/receipts").iterdir()) == receipts_before
    assert (workspace / "note.txt").read_bytes() == b"changed"


def test_snapshot_receipt_failure_leaves_no_archive(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_bytes(b"saved")

    def fail_snapshot(*_args, **_kwargs):
        raise snapshots.SnapshotReceiptError("injected snapshot receipt failure")

    with pytest.raises(BackupError, match="pre-export snapshot"):
        export_backup(
            workspace,
            destination,
            available=lambda: True,
            take=fail_snapshot,
            clock=_clock,
        )
    assert _archives(destination) == []


def test_linked_snapshot_storage_is_rejected_before_archive_creation(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / ".git").write_text("gitdir: ../external-snapshot-storage\n", encoding="utf-8")

    with pytest.raises(BackupError, match="external snapshot storage"):
        export_backup(workspace, destination, available=lambda: False, clock=_clock)
    assert _archives(destination) == []


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_real_linked_worktree_is_rejected_because_snapshot_storage_is_external(tmp_path):
    main_workspace = tmp_path / "main-workspace"
    linked_workspace = tmp_path / "linked-workspace"
    destination = tmp_path / "backups"
    main_workspace.mkdir()
    destination.mkdir()
    (main_workspace / "note.txt").write_text("saved\n", encoding="utf-8")
    snapshots.take_snapshot(main_workspace, label="Initial")
    _git(main_workspace, "worktree", "add", "--detach", str(linked_workspace), "HEAD")
    assert (linked_workspace / ".git").is_file()

    with pytest.raises(BackupError, match="external snapshot storage"):
        export_backup(linked_workspace, destination, clock=_clock)
    assert _archives(destination) == []


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_real_shared_clone_is_rejected_before_snapshot_or_archive(tmp_path):
    source = tmp_path / "source"
    workspace = tmp_path / "shared-workspace"
    destination = tmp_path / "backups"
    source.mkdir()
    destination.mkdir()
    (source / "note.txt").write_text("source\n", encoding="utf-8")
    snapshots.take_snapshot(source, label="Initial")
    subprocess.run(
        ["git", "clone", "--shared", str(source), str(workspace)],
        check=True,
        capture_output=True,
        text=True,
    )
    alternates = workspace / ".git/objects/info/alternates"
    assert alternates.is_file()
    take_called = False

    def forbidden_take(*_args, **_kwargs):
        nonlocal take_called
        take_called = True
        raise AssertionError("snapshot must not start")

    with pytest.raises(BackupError, match="external snapshot history"):
        export_backup(workspace, destination, take=forbidden_take, clock=_clock)
    assert not take_called
    assert _archives(destination) == []


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_real_commondir_store_is_rejected_before_snapshot_or_archive(tmp_path):
    main = tmp_path / "main"
    workspace = tmp_path / "linked"
    destination = tmp_path / "backups"
    main.mkdir()
    destination.mkdir()
    (main / "note.txt").write_text("source\n", encoding="utf-8")
    snapshots.take_snapshot(main, label="Initial")
    _git(main, "worktree", "add", "--detach", str(workspace), "HEAD")
    pointer = (workspace / ".git").read_text(encoding="utf-8").removeprefix("gitdir: ").strip()
    admin = Path(pointer)
    (workspace / ".git").unlink()
    shutil.copytree(admin, workspace / ".git")
    (workspace / ".git/commondir").write_text(str(main / ".git") + "\n", encoding="utf-8")
    (workspace / ".git/gitdir").write_text(str(workspace / ".git") + "\n", encoding="utf-8")
    assert Path(_git(workspace, "rev-parse", "--git-common-dir").stdout.strip()).is_absolute()

    with pytest.raises(BackupError, match="external snapshot history"):
        export_backup(workspace, destination, clock=_clock)
    assert _archives(destination) == []


@pytest.mark.parametrize(
    ("marker", "content"),
    [
        ("objects/info/alternates", "/absolute/object-store\n"),
        ("objects/info/alternates", "../../../relative-object-store\n"),
        ("objects/info/alternates", "file:///local/object-store\n"),
        ("objects/info/http-alternates", "https://example.invalid/objects\n"),
    ],
)
@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_every_alternate_history_form_is_rejected_without_reading_external_objects(
    tmp_path, marker, content
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_text("saved\n", encoding="utf-8")
    snapshots.take_snapshot(workspace, label="Initial")
    path = workspace / ".git" / marker
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    with pytest.raises(BackupError, match="external snapshot history"):
        export_backup(workspace, destination, clock=_clock)
    assert _archives(destination) == []


@pytest.mark.parametrize(
    "configure",
    [
        lambda workspace: _git(workspace, "config", "extensions.partialClone", "origin"),
        lambda workspace: _git(workspace, "config", "remote.origin.promisor", "true"),
        lambda workspace: (workspace / ".git/objects/pack/sample.promisor").write_bytes(b""),
    ],
)
@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_partial_and_promisor_history_is_rejected(tmp_path, configure):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_text("saved\n", encoding="utf-8")
    snapshots.take_snapshot(workspace, label="Initial")
    configure(workspace)

    with pytest.raises(BackupError, match="external snapshot history"):
        export_backup(workspace, destination, clock=_clock)
    assert _archives(destination) == []


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_nested_snapshot_indirection_is_rejected(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    nested = workspace / "nested"
    workspace.mkdir()
    destination.mkdir()
    nested.mkdir()
    (workspace / "note.txt").write_text("saved\n", encoding="utf-8")
    snapshots.take_snapshot(workspace, label="Initial")
    (nested / ".git").write_text("gitdir: ../../external-store\n", encoding="utf-8")

    with pytest.raises(BackupError, match="external snapshot storage"):
        export_backup(workspace, destination, clock=_clock)
    assert _archives(destination) == []


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_extracted_standalone_backup_keeps_restorable_snapshots(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    restored = tmp_path / "restored"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_text("first\n", encoding="utf-8")
    first = snapshots.take_snapshot(workspace, label="First").snapshot
    (workspace / "note.txt").write_text("second\n", encoding="utf-8")

    result = export_backup(workspace, destination, clock=_clock)
    with zipfile.ZipFile(result.archive) as archive:
        archive.extractall(restored)
    workspace.rename(tmp_path / "original-workspace-moved-away")
    assert first is not None
    assert snapshots.resolve_snapshot_id(restored, first.identifier) == first.identifier
    snapshots.restore_snapshot(restored, first.identifier)
    assert (restored / "note.txt").read_text(encoding="utf-8") == "first\n"


def test_real_empty_path_probe_exports_without_a_snapshot(tmp_path, monkeypatch, capsys):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    empty_path = tmp_path / "empty-path"
    workspace.mkdir()
    destination.mkdir()
    empty_path.mkdir()
    (workspace / "note.txt").write_bytes(b"saved")
    monkeypatch.setenv("PATH", str(empty_path))

    def unavailable() -> bool:
        return snapshots.git_available(
            which=lambda command: shutil.which(command, path=str(empty_path))
        )

    assert backup.run(
        argparse.Namespace(workspace=str(workspace), destination=str(destination)),
        available=unavailable,
    ) == 0
    output = capsys.readouterr().out
    assert "exactly as it is now" in output
    assert len(_archives(destination)) == 1
    assert next((workspace / "System" / "receipts").glob("*-backup-export.md"))


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="process timezone cannot be changed")
def test_zip_member_timestamps_are_utc_even_under_non_utc_process_timezone(
    tmp_path, monkeypatch
):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    source = workspace / "timed.txt"
    source.write_bytes(b"utc")
    timestamp = datetime(2026, 8, 10, 12, 34, 56, tzinfo=timezone.utc).timestamp()
    os.utime(source, (timestamp, timestamp))
    previous = os.environ.get("TZ")
    monkeypatch.setenv("TZ", "Pacific/Honolulu")
    time.tzset()
    try:
        result = export_backup(workspace, destination, available=lambda: False, clock=_clock)
        with zipfile.ZipFile(result.archive) as archive:
            assert archive.getinfo("timed.txt").date_time == (2026, 8, 10, 12, 34, 56)
    finally:
        if previous is None:
            monkeypatch.delenv("TZ", raising=False)
        else:
            monkeypatch.setenv("TZ", previous)
        time.tzset()


@pytest.mark.skipif(os.name != "posix", reason="descriptor-relative POSIX proof")
def test_destination_is_never_listed_or_opened_for_reading(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_bytes(b"saved")
    unrelated = destination / "unrelated.bin"
    unrelated.write_bytes(b"unchanged")
    destination_identity = (destination.stat().st_dev, destination.stat().st_ino)
    original_listdir = backup_engine.os.listdir
    original_open = backup_engine.os.open
    destination_opens: list[int] = []

    def guarded_listdir(path):
        if isinstance(path, int):
            value = os.fstat(path)
            if (value.st_dev, value.st_ino) == destination_identity:
                raise AssertionError("destination was listed")
        elif Path(path) == destination:
            raise AssertionError("destination was listed")
        return original_listdir(path)

    def recording_open(path, flags, *args, **kwargs):
        descriptor = original_open(path, flags, *args, **kwargs)
        if isinstance(path, str) and path.startswith("apparatus-backup-"):
            destination_opens.append(flags)
        return descriptor

    monkeypatch.setattr(backup_engine.os, "listdir", guarded_listdir)
    monkeypatch.setattr(backup_engine.os, "open", recording_open)
    monkeypatch.setattr(
        backup_engine.os,
        "supports_dir_fd",
        backup_engine.os.supports_dir_fd | {recording_open},
    )
    export_backup(
        workspace,
        destination,
        available=lambda: False,
        clock=_clock,
    )
    assert destination_opens
    assert all(flags & os.O_WRONLY and flags & os.O_EXCL for flags in destination_opens)
    assert unrelated.read_bytes() == b"unchanged"


@pytest.mark.skipif(os.name != "nt", reason="Windows exclusive-create race probe")
def test_windows_collision_race_retries_without_modifying_winner(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_bytes(b"saved")
    first_name = "apparatus-backup-2026-08-10-123456.zip"
    original_open = backup_engine._windows_fs._win_open
    raced = False

    def racing_open(path, **kwargs):
        nonlocal raced
        path = Path(path)
        if path.name == first_name and kwargs.get("create") and not raced:
            raced = True
            winner = original_open(path, **kwargs)
            backup_engine._windows_fs._win_write(winner, b"race-winner")
            backup_engine._windows_fs._win_close(winner)
        return original_open(path, **kwargs)

    monkeypatch.setattr(backup_engine._windows_fs, "_win_open", racing_open)
    result = export_backup(
        workspace,
        destination,
        available=lambda: False,
        clock=_clock,
    )
    assert raced
    assert result.archive.name == "apparatus-backup-2026-08-10-123456-2.zip"
    assert (destination / first_name).read_bytes() == b"race-winner"


@pytest.mark.skipif(os.name != "nt", reason="Windows archive name-lock probe")
def test_windows_archive_name_cannot_move_while_export_owns_it(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    final = destination / "apparatus-backup-2026-08-10-123456.zip"
    moved = destination / "moved-owned.zip"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_bytes(b"saved")
    original_write = backup_engine._write_chunks
    rename_error: OSError | None = None

    def attempt_rename_then_write(*args, **kwargs):
        nonlocal rename_error
        if rename_error is None:
            try:
                final.rename(moved)
            except OSError as error:
                rename_error = error
            else:
                raise AssertionError("owned archive name moved while locked")
        return original_write(*args, **kwargs)

    monkeypatch.setattr(backup_engine, "_write_chunks", attempt_rename_then_write)
    result = export_backup(
        workspace,
        destination,
        available=lambda: False,
        clock=_clock,
    )

    assert rename_error is not None
    assert result.archive == final
    assert final.is_file()
    assert not moved.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows no-listing proof")
def test_windows_destination_is_never_listed(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_bytes(b"saved")
    unrelated = destination / "unrelated.bin"
    unrelated.write_bytes(b"unchanged")
    original_listdir = backup_engine.os.listdir

    def guarded_listdir(path):
        if Path(path) == destination:
            raise AssertionError("destination was listed")
        return original_listdir(path)

    monkeypatch.setattr(backup_engine.os, "listdir", guarded_listdir)
    export_backup(workspace, destination, available=lambda: False, clock=_clock)
    assert unrelated.read_bytes() == b"unchanged"
