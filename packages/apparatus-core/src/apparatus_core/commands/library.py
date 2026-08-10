"""The ``apparatus library ingest`` command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
import unicodedata

from apparatus_core.cache import library_cache_root
from apparatus_core.library.ingest import ingest_library
from apparatus_core.library import index


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser("library", help="work with Library sources")
    actions = parser.add_subparsers(dest="library_action")
    ingest = actions.add_parser("ingest", help="extract Library text into the local cache")
    ingest.add_argument("workspace", metavar="WORKSPACE")
    ingest.set_defaults(func=run)
    search = actions.add_parser("search", help="search extracted Library text")
    search.add_argument("workspace", metavar="WORKSPACE")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--json", action="store_true", dest="as_json")
    search.add_argument("--rebuild", action="store_true")
    search.set_defaults(func=run_search)


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


def run_search(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    if not workspace.exists() or not workspace.is_dir():
        print("library search: workspace path is not a directory")
        return 2
    if args.limit < 1:
        print("library search: --limit must be positive")
        return 2
    try:
        cache = library_cache_root(workspace)
        if not index.has_extractions(cache):
            print("Nothing from your Library has been ingested yet. Run apparatus library ingest first.")
            return 1
        if args.rebuild:
            index.rebuild(cache)
        else:
            index.refresh(cache)
        hits = index.search(cache, args.query, args.limit)
    except index.FtsUnavailable as error:
        print(f"library search: {_safe(str(error))}")
        return 1
    except index.IndexError as error:
        print(f"library search: {_safe(str(error))}")
        return 2
    except ValueError as error:
        print(f"library search: {_safe(str(error))}")
        return 1
    if args.as_json:
        print(json.dumps([{"source_path": hit.source_path, "snippet": hit.snippet, "score": hit.score} for hit in hits], ensure_ascii=False))
    else:
        for hit in hits:
            print(f"{_safe(hit.source_path)} ({hit.score:.6f}): {_safe(hit.snippet)}")
    return 0
