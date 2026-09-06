"""The ``apparatus render`` command."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from apparatus_core.render import RenderError, RenderResult, render_workspace


def register(subparsers: Any) -> None:
    """Register render through the shared command entry-point path."""
    parser = subparsers.add_parser("render", help="regenerate workspace instruction shims")
    parser.add_argument("workspace", metavar="WORKSPACE")
    parser.set_defaults(func=run)


def run(
    args: argparse.Namespace,
    *,
    engine: Callable[[str | Path], RenderResult] = render_workspace,
) -> int:
    """Regenerate every shim and report one result per registered target."""
    workspace = Path(args.workspace)
    if not workspace.exists():
        print("render: workspace path does not exist")
        return 2
    if not workspace.is_dir():
        print("render: workspace path is not a directory")
        return 2
    from apparatus_core.project_binding import BindingError, bind_project, read_project_binding, resolve_project_context
    try:
        with ExitStack() as stack:
            context = getattr(args, "_project_context", None)
            if (not getattr(args, "_project_context_selected", False)
                    and read_project_binding(workspace) is not None):
                context = stack.enter_context(resolve_project_context(workspace))
            if context is not None:
                context.validate()
                bound = bind_project(workspace, context.workspace, context=context)
                print(f"{'written' if bound.changed else 'unchanged'} AGENTS.md")
                return 0
            result = engine(workspace)
    except (RenderError, BindingError) as error:
        print(f"render: {error}")
        return 2
    actions = result.actions or (
        *(("written", target) for target in result.written),
        *(("unchanged", target) for target in result.unchanged),
    )
    for action, target in actions:
        print(f"{action} {target}")
    return 0
