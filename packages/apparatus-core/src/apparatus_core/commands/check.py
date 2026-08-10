"""The ``apparatus check`` command."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from apparatus_core.check import CheckResult, check_workspace
from apparatus_core.receipts import write_receipt


def register(subparsers: Any) -> None:
    """Register the check verb through the standard entry-point path."""
    parser = subparsers.add_parser("check", help="check a workspace")
    parser.add_argument("workspace", metavar="WORKSPACE")
    parser.add_argument("--no-receipt", action="store_true", help="do not write a check receipt")
    parser.set_defaults(func=run)


def _receipt_fields(result: CheckResult) -> dict[str, str]:
    codes = sorted({finding.code for finding in result.findings})
    outcome = "passed" if result.ok else "found problems"
    summary = f"Check {outcome}: {len(result.findings)} finding(s) across {result.records_checked} record(s); {result.ignored_paths} path(s) ignored."
    body = "Finding codes: " + (", ".join(codes) if codes else "none") + f". Ignore rules excluded {result.ignored_paths} path(s)."
    return {"summary": summary, "body": body}


def run(
    args: argparse.Namespace,
    *,
    engine: Callable[[str | Path], CheckResult] = check_workspace,
    write: Callable[[str | Path, str, dict[str, str]], Path] = write_receipt,
) -> int:
    """Run the check, print findings, and write its receipt unless disabled."""
    workspace = Path(args.workspace)
    if not workspace.exists():
        print("check: workspace path does not exist")
        return 2
    if not workspace.is_dir():
        print("check: workspace path is not a directory")
        return 2
    result = engine(workspace)
    for finding in result.findings:
        print(f"{finding.path}: {finding.code}: {finding.hint}")
    if result.ok:
        print(f"check passed: {result.records_checked} record(s) checked; {result.ignored_paths} path(s) ignored")
    else:
        print(f"check found {len(result.findings)} finding(s)")
    if not getattr(args, "no_receipt", False):
        try:
            write(workspace, "check", _receipt_fields(result))
        except (OSError, ValueError) as error:
            print(f"check: could not write receipt: {error}")
            return 2
    return 0 if result.ok else 1
