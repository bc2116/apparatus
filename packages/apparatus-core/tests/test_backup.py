from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import time
import zipfile

import pytest

from apparatus_core import records, snapshots
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
    with pytest.raises(BackupError, match="Destination path changed"):
        export_backup(workspace, destination, available=lambda: False, clock=_clock)
    assert swapped
    assert _archives(moved_destination) == []
    assert _archives(workspace) == []


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
    result = export_backup(
        workspace,
        destination,
        available=lambda: False,
        write=lambda *_args, **_kwargs: workspace / "unused-receipt.md",
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


def test_export_receipt_failure_removes_completed_archive(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "backups"
    workspace.mkdir()
    destination.mkdir()
    (workspace / "note.txt").write_bytes(b"saved")

    def fail_receipt(*_args, **_kwargs):
        raise OSError("injected receipt failure")

    with pytest.raises(BackupError, match="receipt could not be recorded"):
        export_backup(
            workspace,
            destination,
            available=lambda: False,
            write=fail_receipt,
            clock=_clock,
        )
    assert _archives(destination) == []


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
    export_backup(
        workspace,
        destination,
        available=lambda: False,
        write=lambda *_args, **_kwargs: workspace / "unused-receipt.md",
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
        write=lambda *_args, **_kwargs: workspace / "unused-receipt.md",
        clock=_clock,
    )
    assert raced
    assert result.archive.name == "apparatus-backup-2026-08-10-123456-2.zip"
    assert (destination / first_name).read_bytes() == b"race-winner"


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
