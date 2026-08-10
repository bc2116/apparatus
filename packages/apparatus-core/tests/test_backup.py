from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import zipfile

import pytest

from apparatus_core import records, snapshots
from apparatus_core.backup import export_backup
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
        ("missing", "destination", "workspace path is not a directory"),
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
