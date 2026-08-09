"""The ``apparatus snapshot`` command."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from apparatus_core.receipts import write_receipt
from apparatus_core.snapshots import (
    SnapshotError,
    SnapshotReceiptError,
    git_available,
    mark_snapshots_unavailable,
    take_snapshot,
)


def register(subparsers: Any) -> None:
    """Register the snapshot verb through the standard entry-point path."""
    parser = subparsers.add_parser("snapshot", help="save a workspace snapshot")
    parser.add_argument("workspace", metavar="WORKSPACE")
    parser.add_argument("--label", metavar="TEXT", help="a short label for this snapshot")
    parser.set_defaults(func=run)


def _unavailable_fields() -> dict[str, str]:
    return {
        "summary": "Snapshots are unavailable on this machine.",
        "body": "Outcome: unavailable.",
    }


def _workspace_or_usage_error(value: str) -> Path | None:
    workspace = Path(value)
    if not workspace.exists():
        print("snapshot: workspace path does not exist")
        return None
    if not workspace.is_dir():
        print("snapshot: workspace path is not a directory")
        return None
    return workspace


def run(
    args: argparse.Namespace,
    *,
    available: Callable[[], bool] = git_available,
    take: Callable[..., Any] = take_snapshot,
    write: Callable[[str | Path, str, dict[str, str]], Path] = write_receipt,
    update_report: Callable[[str | Path], bool] = mark_snapshots_unavailable,
) -> int:
    """Save a workspace snapshot or report the unavailable capability honestly."""
    workspace = _workspace_or_usage_error(args.workspace)
    if workspace is None:
        return 2
    if not available():
        receipt_written = True
        try:
            write(workspace, "snapshot", _unavailable_fields())
        except (OSError, ValueError):
            receipt_written = False
        try:
            report_updated = update_report(workspace)
        except (OSError, ValueError):
            report_updated = False
        if not receipt_written or not report_updated:
            print("snapshot: could not record the unavailable snapshot state")
            return 2
        print("Snapshots are unavailable on this machine. Run apparatus doctor for details.")
        return 1
    try:
        result = take(workspace, label=getattr(args, "label", None))
    except SnapshotReceiptError:
        print("snapshot: could not write the snapshot receipt")
        return 2
    except SnapshotError:
        print("snapshot: could not save a snapshot for this workspace")
        return 1
    if result.no_changes:
        print("no changes since the last snapshot")
        return 0
    print(f"Snapshot saved. Snapshot id: {result.snapshot.short_id}")
    return 0
