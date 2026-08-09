"""The doctor command: inspect local capabilities and report them honestly."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from apparatus_core.detect import detect_machine
from apparatus_core.machine_report import render_machine_report, write_machine_report


def register(subparsers: Any) -> None:
    """Register the built-in doctor verb through the standard entry-point path."""
    parser = subparsers.add_parser("doctor", help="inspect local capabilities")
    parser.add_argument("workspace", nargs="?", metavar="WORKSPACE")
    parser.set_defaults(func=run)


def run(
    args: argparse.Namespace,
    *,
    detect: Callable[..., dict[str, Any]] = detect_machine,
    render: Callable[[dict[str, Any]], str] = render_machine_report,
    write: Callable[[str | Path, dict[str, Any]], Path] = write_machine_report,
) -> int:
    """Print a report and optionally write it into the requested workspace."""
    workspace = getattr(args, "workspace", None)
    detections = detect(workspace=workspace)
    print(render(detections), end="")
    if workspace is not None:
        write(workspace, detections)
    required_tools = (detections["python"], detections["git"], detections["uv"])
    healthy = all(item.get("present", True) for item in required_tools)
    return 0 if healthy and not detections["sync_redirection"]["at_risk"] else 1
