"""The ``apparatus snapshot`` command."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from apparatus_core.receipts import write_receipt
from apparatus_core.retention import operation, RetentionSuppressed, TaskRetentionError
from apparatus_core.workspace_layout import LayoutError, read_layout
from apparatus_core.features import (
    FeatureProfileError,
    enabled as feature_enabled,
)
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
    parser.add_argument("--requested", action="store_true", help="save a separately requested snapshot")
    parser.set_defaults(func=run)


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
    write: Callable[[str | Path, str, dict[str, str]], object] = write_receipt,
    update_report: Callable[[str | Path], bool] = mark_snapshots_unavailable,
) -> int:
    """Apply invocation retention before snapshot capability or content changes."""
    workspace = _workspace_or_usage_error(args.workspace)
    if workspace is None:
        return 2
    try:
        with operation(
            workspace, task_id=getattr(args, "task", None),
            requested=("snapshot",) if getattr(args, "requested", False) else (),
        ) as context:
            context.require_snapshot()
            return _run(args, available=available, take=take, write=write, update_report=update_report)
    except RetentionSuppressed:
        print("Snapshot skipped: this task does not save Memory.")
        return 1
    except TaskRetentionError as error:
        print(f"snapshot: {error}")
        return 2


def _run(
    args: argparse.Namespace, *, available: Callable[[], bool], take: Callable[..., Any],
    write: Callable[..., object], update_report: Callable[[str | Path], bool],
) -> int:
    """Save a workspace snapshot or report the unavailable capability honestly."""
    workspace = _workspace_or_usage_error(args.workspace)
    if workspace is None:
        return 2
    try:
        read_layout(workspace)
        feature_is_enabled = feature_enabled(workspace, "snapshots")
    except (FeatureProfileError, LayoutError) as error:
        print(f"snapshot: {error}")
        return 2
    if not feature_is_enabled:
        print("This feature is off; say the word and I'll enable it.")
        return 1
    if not available():
        try:
            report_updated = update_report(workspace)
        except (OSError, ValueError):
            report_updated = False
        if not report_updated:
            print("snapshot: could not update the machine report for unavailable snapshots")
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
    if getattr(result.snapshot, "scope", "workspace") == "managed-state":
        print("Saved Apparatus Memory, goals and settings. Project files and Library originals are not included.")
    return 0
