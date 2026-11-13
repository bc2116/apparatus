"""The ``apparatus check`` command."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from apparatus_core.check import CheckResult, Finding, check_workspace
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
            project_root: Path | None = None
            relative_workspace: str | None = None
            if context is not None:
                context.validate()
                check_project_pointer(workspace, context=context)
                project_root = workspace
                relative_workspace = context.binding.relative_workspace
                workspace = context.workspace
            return _run_selected(
                args,
                workspace,
                engine,
                write,
                project_root=project_root,
                relative_workspace=relative_workspace,
            )
    except BindingError as error:
        print(f"check: {error}")
        return 2


def _run_selected(
    args,
    workspace,
    engine,
    write,
    *,
    project_root: Path | None = None,
    relative_workspace: str | None = None,
) -> int:
    result = engine(workspace)
    if project_root is not None and relative_workspace is not None:
        from apparatus_core.ignore import load_ignore_rules
        from apparatus_core.skill_adapters import check_adapter_findings
        rules = load_ignore_rules(workspace, respect_feature=False)
        project_findings = tuple(
            Finding(item.code, item.path, item.hint)
            for item in check_adapter_findings(
                project_root,
                workspace,
                relative_workspace=relative_workspace,
                excluded=rules.matches if rules.valid else None,
            )
        )
        if project_findings:
            result = CheckResult(
                result.findings + project_findings,
                result.records_checked,
                result.ignore_report,
            )
    for finding in result.findings:
        print(f"{finding.path}: {finding.code}: {finding.hint}")
    if result.ok:
        print(f"check passed: {result.records_checked} record(s) checked; {result.ignored_paths} path(s) ignored")
    else:
        print(f"check found {len(result.findings)} finding(s)")
    print(result.ignore_report.sentence())
    return 0 if result.ok else 1
