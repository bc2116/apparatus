"""One-way snapshot export support for workspace backups."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import os
import subprocess
import zipfile

from apparatus_core.receipts import write_receipt
from apparatus_core.snapshots import SnapshotResult, git_available, take_snapshot


class BackupError(RuntimeError):
    """A backup archive could not be written."""


@dataclass(frozen=True)
class BackupResult:
    """Details of one completed one-way backup export."""

    archive: Path
    snapshot_id: str | None
    snapshots_available: bool
    size: int


def utc_archive_timestamp(clock: Callable[[], datetime] | None = None) -> str:
    """Return the UTC timestamp used in a backup archive filename."""
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    return now.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%d-%H%M%S")


def archive_path(destination: str | Path, timestamp: str) -> Path:
    """Choose an unused archive name without inspecting destination contents."""
    directory = Path(destination)
    stem = f"apparatus-backup-{timestamp}"
    for collision in range(1, 1_000_000):
        suffix = "" if collision == 1 else f"-{collision}"
        candidate = directory / f"{stem}{suffix}.zip"
        # An existence check is the only information requested from the destination.
        if not candidate.exists():
            return candidate
    raise BackupError("Could not choose a backup archive name.")


def _archive_workspace(workspace: Path, archive: Path) -> int:
    """Write every workspace file, including dotfiles, without reading the destination."""
    try:
        with archive.open("xb") as archive_file:
            with zipfile.ZipFile(archive_file, mode="w", compression=zipfile.ZIP_DEFLATED) as output:
                for directory, folders, filenames in os.walk(workspace, followlinks=False):
                    base = Path(directory)
                    if base != workspace:
                        output.write(base, base.relative_to(workspace).as_posix() + "/")
                    for folder in folders:
                        if (base / folder).is_symlink():
                            raise BackupError(
                                "Workspace contains a symbolic link that cannot be safely archived."
                            )
                    for filename in filenames:
                        source = base / filename
                        relative = source.relative_to(workspace)
                        if source.is_symlink():
                            raise BackupError("Workspace contains a symbolic link that cannot be safely archived.")
                        output.write(source, relative.as_posix())
            return archive_file.tell()
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
        raise BackupError("Could not write the backup archive.") from error


def _receipt_fields(result: BackupResult, destination: Path) -> dict[str, str | int]:
    fields: dict[str, str | int] = {
        "summary": f"Backup exported: {result.archive.name}.",
        "archive_filename": result.archive.name,
        "destination": str(destination),
        "archive_size": result.size,
        "body": "This receipt was written after the backup archive landed.\n",
    }
    if result.snapshot_id is not None:
        fields["snapshot_id"] = result.snapshot_id
    return fields


def export_backup(
    workspace: str | Path,
    destination: str | Path,
    *,
    available: Callable[[], bool] = git_available,
    take: Callable[..., SnapshotResult] = take_snapshot,
    write: Callable[[str | Path, str, dict[str, str | int]], Path] = write_receipt,
    clock: Callable[[], datetime] | None = None,
) -> BackupResult:
    """Export the current workspace to one new archive and then write its receipt."""
    root = Path(workspace)
    destination_path = Path(destination)
    snapshot_id: str | None = None
    timestamp = utc_archive_timestamp(clock)
    snapshots_available = available()
    if snapshots_available:
        snapshot = take(root, label=f"Before backup export {timestamp}")
        if snapshot.snapshot is not None:
            snapshot_id = snapshot.snapshot.identifier
    archive = archive_path(destination_path, timestamp)
    size = _archive_workspace(root, archive)
    result = BackupResult(
        archive=archive,
        snapshot_id=snapshot_id,
        snapshots_available=snapshots_available,
        size=size,
    )
    try:
        write(root, "backup-export", _receipt_fields(result, destination_path))
    except (OSError, ValueError) as error:
        raise BackupError("Backup archive was written, but its receipt could not be recorded.") from error
    return result
