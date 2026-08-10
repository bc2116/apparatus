"""The ``apparatus restore`` command."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from apparatus_core.receipts import write_receipt
from apparatus_core.snapshots import (
    Snapshot,
    SnapshotError,
    SnapshotReceiptError,
    UnknownSnapshotError,
    git_available,
    list_snapshots,
    mark_snapshots_unavailable,
    resolve_snapshot_id,
    restore_snapshot,
    take_snapshot,
)


def register(subparsers: Any) -> None:
    """Register the restore verb through the standard entry-point path."""
    parser = subparsers.add_parser("restore", help="restore a workspace snapshot")
    parser.add_argument("workspace", metavar="WORKSPACE")
    parser.add_argument("snapshot_id", nargs="?", metavar="SNAPSHOT_ID")
    parser.add_argument("--list", action="store_true", help="list available snapshots")
    parser.set_defaults(func=run)


def _unavailable_fields() -> dict[str, str]:
    return {
        "summary": "Snapshots are unavailable on this machine.",
        "body": "Outcome: unavailable.",
    }


def _restore_receipt_fields(target: Snapshot) -> dict[str, str]:
    return {
        "summary": f"Restored to snapshot: {target.label}.",
        "label": target.label,
        "snapshot_id": target.identifier,
        "body": "This receipt was written after the workspace content was restored.\n",
    }


def _workspace_or_usage_error(value: str) -> Path | None:
    workspace = Path(value)
    if not workspace.exists():
        print("restore: workspace path does not exist")
        return None
    if not workspace.is_dir():
        print("restore: workspace path is not a directory")
        return None
    return workspace


def _print_snapshots(snapshots: list[Snapshot]) -> None:
    for snapshot in snapshots:
        print(
            f"Snapshot id: {snapshot.short_id} | UTC date: {snapshot.timestamp} | Label: {snapshot.label}"
        )


def run(
    args: argparse.Namespace,
    *,
    available: Callable[[], bool] = git_available,
    list_saved: Callable[..., list[Snapshot]] = list_snapshots,
    resolve: Callable[..., str] = resolve_snapshot_id,
    take: Callable[..., Any] = take_snapshot,
    restore: Callable[..., None] = restore_snapshot,
    write: Callable[[str | Path, str, dict[str, str]], object] = write_receipt,
    update_report: Callable[[str | Path], bool] = mark_snapshots_unavailable,
) -> int:
    """List snapshots or restore one after first saving the current state."""
    workspace = _workspace_or_usage_error(args.workspace)
    if workspace is None:
        return 2
    if not available():
        receipt_written = True
        try:
            write(workspace, "restore", _unavailable_fields())
        except (OSError, ValueError):
            receipt_written = False
        try:
            report_updated = update_report(workspace)
        except (OSError, ValueError):
            report_updated = False
        if not receipt_written or not report_updated:
            print("restore: could not record the unavailable snapshot state")
            return 2
        print("Snapshots are unavailable on this machine. Run apparatus doctor for details.")
        return 1
    if getattr(args, "list", False):
        _print_snapshots(list_saved(workspace))
        return 0
    requested = getattr(args, "snapshot_id", None)
    if not requested:
        print("restore: provide a snapshot id or use --list")
        return 2
    try:
        # Resolve before taking the automatic snapshot: a bad id must not alter
        # the workspace, while every real restore remains reversible.
        target_id = resolve(workspace, requested)
        target = next(
            entry for entry in list_saved(workspace) if entry.identifier == target_id
        )
    except (UnknownSnapshotError, StopIteration):
        print("restore: snapshot id was not found; use --list to choose a snapshot")
        return 1
    try:
        take(workspace, label=f"Before restore to {target.short_id}", force=True)
        restore(workspace, target_id)
        write(workspace, "restore", _restore_receipt_fields(target))
    except SnapshotReceiptError:
        print("restore: could not write the snapshot receipt")
        return 2
    except SnapshotError:
        print("restore: could not restore this workspace")
        return 1
    except (OSError, ValueError):
        print("restore: could not write the restore receipt")
        return 2
    print(f"Workspace restored. Snapshot id: {target.short_id}")
    return 0
