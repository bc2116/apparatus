"""The ``apparatus library ingest`` command."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any
import unicodedata

from apparatus_core.library.ingest import ingest_library


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser("library", help="work with Library sources")
    actions = parser.add_subparsers(dest="library_action")
    ingest = actions.add_parser("ingest", help="extract Library text into the local cache")
    ingest.add_argument("workspace", metavar="WORKSPACE")
    ingest.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    if not workspace.exists():
        print("library ingest: workspace path does not exist")
        return 2
    if not workspace.is_dir():
        print("library ingest: workspace path is not a directory")
        return 2
    try:
        result = ingest_library(workspace)
    except ValueError as error:
        print(f"library ingest: {_safe(str(error))}")
        return 2
    print(f"Library cache: {_safe(str(result.cache))}")
    print("Library ingest: " + ", ".join(f"{name}={result.counts[name]}" for name in result.counts))
    for path, status, reason in result.flagged:
        print(f"flagged {_safe(path)}: {_safe(status)}: {_safe(reason)}")
    return 0 if result.ok else 1


def _safe(value: str) -> str:
    return "".join(" " if unicodedata.category(character).startswith("C") else character for character in value)
