"""The ``apparatus backup export`` command."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from apparatus_core.backup import BackupError, BackupResult, export_backup
from apparatus_core.snapshots import git_available


def register(subparsers: Any) -> None:
    """Register the backup verb through the standard entry-point path."""
    parser = subparsers.add_parser("backup", help="export a one-way workspace backup")
    commands = parser.add_subparsers(dest="backup_command", required=True)
    export = commands.add_parser("export", help="write one workspace backup archive")
    export.add_argument("workspace", metavar="WORKSPACE")
    export.add_argument("destination", metavar="DESTINATION")
    export.set_defaults(func=run)


def _paths_or_usage_error(workspace_value: str, destination_value: str) -> tuple[Path, Path] | None:
    workspace = Path(workspace_value)
    destination = Path(destination_value)
    if not workspace.is_dir():
        print("backup export: workspace path is not a directory")
        return None
    if not destination.is_dir():
        print("backup export: destination path does not exist or is not a directory")
        return None
    try:
        root = workspace.resolve()
        target = destination.resolve()
    except OSError:
        print("backup export: could not resolve the workspace or destination path")
        return None
    if target == root or root in target.parents:
        print("backup export: destination must be outside the workspace")
        return None
    return root, target


def run(
    args: argparse.Namespace,
    *,
    available: Callable[[], bool] = git_available,
    export: Callable[..., BackupResult] = export_backup,
) -> int:
    """Write one archive, with a fresh snapshot when that capability is available."""
    paths = _paths_or_usage_error(args.workspace, args.destination)
    if paths is None:
        return 2
    workspace, destination = paths
    try:
        result = export(workspace, destination, available=available)
    except BackupError as error:
        print(f"backup export: {error}")
        return 1
    except OSError:
        print("backup export: could not write the backup archive")
        return 1
    size = result.size
    print(f"Backup archive: {result.archive.name}")
    print(f"Destination: {destination}")
    print(f"Size: {size} bytes")
    if not result.snapshots_available:
        print("Snapshots are unavailable, so this backup contains the workspace exactly as it is now.")
    print("To restore, unzip this archive into a fresh folder.")
    return 0
