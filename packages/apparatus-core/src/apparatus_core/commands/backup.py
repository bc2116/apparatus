"""The ``apparatus backup export`` command."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Any

from apparatus_core.backup import BackupError, BackupResult, BackupUsageError, export_backup
from apparatus_core.snapshots import git_available


def register(subparsers: Any) -> None:
    """Register the backup verb through the standard entry-point path."""
    parser = subparsers.add_parser("backup", help="export a one-way workspace backup")
    commands = parser.add_subparsers(dest="backup_command", required=True)
    export = commands.add_parser("export", help="write one workspace backup archive")
    export.add_argument("workspace", metavar="WORKSPACE")
    export.add_argument("destination", metavar="DESTINATION")
    export.set_defaults(func=run)


def run(
    args: argparse.Namespace,
    *,
    available: Callable[[], bool] = git_available,
    export: Callable[..., BackupResult] = export_backup,
) -> int:
    """Write one archive, with a fresh snapshot when that capability is available."""
    try:
        result = export(args.workspace, args.destination, available=available)
    except BackupUsageError as error:
        print(f"backup export: {error}")
        return 2
    except BackupError as error:
        print(f"backup export: {error}")
        return 1
    except OSError:
        print("backup export: could not write the backup archive")
        return 1
    size = result.size
    print(f"Backup archive: {result.archive.name}")
    print(f"Destination: {result.archive.parent}")
    print(f"Size: {size} bytes")
    if not result.snapshots_available:
        print(
            "Snapshots are unavailable, so this backup contains the workspace "
            "exactly as it is now."
        )
    print("To restore, unzip this archive into a fresh folder.")
    return 0
