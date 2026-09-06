"""The ``apparatus check`` command."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from apparatus_core.check import CheckResult, check_workspace
from apparatus_core.receipts import write_receipt


def register(subparsers: Any) -> None:
    """Register the check verb through the standard entry-point path."""
    parser = subparsers.add_parser("check", help="check a workspace")
    parser.add_argument("workspace", metavar="WORKSPACE")
    parser.add_argument("--no-receipt", action="store_true", help="compatibility option; checks do not write receipts")
    parser.set_defaults(func=run)


def run(
    args: argparse.Namespace,
    *,
    engine: Callable[[str | Path], CheckResult] = check_workspace,
    write: Callable[[str | Path, str, dict[str, str]], object] = write_receipt,
) -> int:
    """Print findings without publishing routine history."""
    workspace = Path(args.workspace)
    if not workspace.exists():
        print("check: workspace path does not exist")
        return 2
    if not workspace.is_dir():
        print("check: workspace path is not a directory")
        return 2
    from apparatus_core.project_binding import BindingError, check_project_pointer, read_project_binding, resolve_project_context
    try:
        with ExitStack() as stack:
            context = getattr(args, "_project_context", None)
            if (not getattr(args, "_project_context_selected", False)
                    and read_project_binding(workspace) is not None):
                context = stack.enter_context(resolve_project_context(workspace))
            if context is not None:
                context.validate()
                check_project_pointer(workspace, context=context)
                workspace = context.workspace
            return _run_selected(args, workspace, engine, write)
    except BindingError as error:
        print(f"check: {error}")
        return 2


def _run_selected(args, workspace, engine, write) -> int:
    result = engine(workspace)
    for finding in result.findings:
        print(f"{finding.path}: {finding.code}: {finding.hint}")
    if result.ok:
        print(f"check passed: {result.records_checked} record(s) checked; {result.ignored_paths} path(s) ignored")
    else:
        print(f"check found {len(result.findings)} finding(s)")
    print(result.ignore_report.sentence())
    return 0 if result.ok else 1
