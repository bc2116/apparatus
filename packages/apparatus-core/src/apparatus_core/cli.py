"""Command-line entry point and entry-point registry for Apparatus."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable
from contextlib import ExitStack
import importlib.metadata
from pathlib import Path
import sys
from typing import Any

from apparatus_core import __version__
from apparatus_core.project_binding import BindingError

ENTRY_POINT_GROUP = "apparatus.commands"
WORKSPACE_VERBS = {"backup", "check", "doctor", "library", "memory", "profile",
                   "recall", "render", "restore", "snapshot", "task", "skill"}


def _dispatch(parsed, handler) -> int:
    """Select an explicit project context before any task decision is resolved."""
    from apparatus_core.project_binding import read_project_binding, resolve_project_context
    from apparatus_core.retention import operation

    with ExitStack() as stack:
        parsed._project_context = None
        parsed._project_context_selected = True
        task_workspace = getattr(parsed, "workspace", None) or "."
        if parsed.verb in WORKSPACE_VERBS or parsed.verb == "init":
            requested = getattr(parsed, "workspace", None) or "."
            if Path(requested).exists() and read_project_binding(requested) is not None:
                context = stack.enter_context(resolve_project_context(requested))
                context.validate()
                parsed._project_context = context
                task_workspace = context.workspace
                if parsed.verb not in {"check", "render", "init"}:
                    parsed.workspace = str(context.workspace)
        elif parsed.verb == "project" and parsed.project_action == "show":
            context = stack.enter_context(resolve_project_context(parsed.project))
            parsed._project_context = context
            task_workspace = context.workspace
        if parsed.verb != "task" and parsed.task is not None:
            stack.enter_context(operation(task_workspace, task_id=parsed.task))
        return int(handler(parsed))


def command_entry_points(
    entry_points: Callable[[], Any] = importlib.metadata.entry_points,
) -> list[Any]:
    """Normalize importlib.metadata entry-point APIs across supported Python versions."""
    available = entry_points()
    if hasattr(available, "select"):
        selected = available.select(group=ENTRY_POINT_GROUP)
    elif isinstance(available, dict):
        selected = available.get(ENTRY_POINT_GROUP, ())
    else:
        selected = (entry for entry in available if entry.group == ENTRY_POINT_GROUP)
    return sorted(selected, key=lambda item: (item.name, getattr(item, "value", "")))


def _registered_verbs(subparsers: Any) -> set[str]:
    return set(getattr(subparsers, "choices", {}))


def register_commands(subparsers: Any, entry_points: Iterable[Any]) -> None:
    """Load each command register function once, skipping duplicate verbs predictably."""
    registered = _registered_verbs(subparsers)
    for entry_point in entry_points:
        if entry_point.name in registered:
            print(
                f"apparatus: skipping duplicate command verb {entry_point.name!r}", file=sys.stderr
            )
            continue
        register = entry_point.load()
        register(subparsers)
        registered = _registered_verbs(subparsers)


def build_parser(entry_points: Callable[[], Any] = importlib.metadata.entry_points) -> argparse.ArgumentParser:
    """Build the root parser and register built-ins and packs through entry points."""
    parser = argparse.ArgumentParser(prog="apparatus", description="Governed workspace tools")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--task", metavar="ID", help="task ID from apparatus task start")
    subparsers = parser.add_subparsers(dest="verb")
    register_commands(subparsers, command_entry_points(entry_points))
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command and return the documented process status."""
    arguments = sys.argv[1:] if argv is None else argv
    try:
        parser = build_parser()
        if not arguments:
            parser.print_help()
            return 2
        parsed = parser.parse_args(arguments)
        handler = getattr(parsed, "func", None)
        if handler is None:
            parser.print_help()
            return 2
        return _dispatch(parsed, handler)
    except SystemExit as error:
        return int(error.code) if isinstance(error.code, int) else 2
    except BindingError as error:
        print(f"apparatus: {error}", file=sys.stderr)
        return 2
    except Exception as error:  # pragma: no cover - exact failures are environment-specific
        print(f"apparatus: internal error: {error}", file=sys.stderr)
        return 2
