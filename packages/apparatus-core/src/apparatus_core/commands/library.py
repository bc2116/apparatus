"""Select, extract and search local Library sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
import unicodedata

from apparatus_core.features import (
    FeatureProfileError,
    enabled as feature_enabled,
)
from apparatus_core.ignore import load_ignore_rules
from apparatus_core.library.ingest import ingest_library, ingest_source
from apparatus_core.library.sources import register_source, unregister_source, list_sources
from apparatus_core.library import index
from apparatus_core.receipts import write_receipt
from apparatus_core.retention import RetentionSuppressed, TaskRetentionError


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser("library", help="work with Library sources")
    actions = parser.add_subparsers(dest="library_action")
    ingest = actions.add_parser("ingest", help="extract Library text into the local cache")
    ingest.add_argument("workspace", metavar="WORKSPACE")
    ingest.add_argument("--requested", action="store_true", help="apply a separately requested Library write")
    ingest.set_defaults(func=run)
    search = actions.add_parser("search", help="search extracted Library text")
    search.add_argument("workspace", metavar="WORKSPACE")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--json", action="store_true", dest="as_json")
    search.add_argument("--rebuild", action="store_true")
    search.add_argument("--requested", action="store_true", help="apply a separately requested index rebuild")
    search.set_defaults(func=run_search)
    for action, help_text in (
        ("add", "register one project original and extract its text"),
        ("remove", "remove a registration while preserving its original"),
    ):
        command = actions.add_parser(action, help=help_text)
        command.add_argument("workspace", metavar="WORKSPACE")
        command.add_argument("source", metavar="RELATIVE_PATH", help="path relative to the shared work area, including when called from a bound project")
        command.add_argument("--requested", action="store_true", help="apply this separately requested Library operation")
        command.set_defaults(func=run_registration)
    listing = actions.add_parser("list", help="list registered project sources and current availability")
    listing.add_argument("workspace", metavar="WORKSPACE")
    listing.add_argument("--json", action="store_true", dest="as_json")
    listing.set_defaults(func=run_list)

    card = actions.add_parser("card", help="read selected evidence or save an assistant-written card")
    card.add_argument("workspace", metavar="WORKSPACE")
    card.add_argument("source", metavar="RELATIVE_PATH", help="path relative to the shared work area")
    card.add_argument("--stdin", action="store_true", help="save supplied summary/topics and exact evidence provenance")
    card.set_defaults(func=run_card)


def run_card(args, *, input_stream=None, write=write_receipt):
    from apparatus_core.library import cards
    try:
        if getattr(args, "stdin", False):
            result = cards.write_card(args.workspace, args.source, sys.stdin if input_stream is None else input_stream,
                                      task_id=getattr(args, "task", None), write=write)
        else:
            result = cards.read_card(args.workspace, args.source)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["card_status"] in {"current", "absent"} else 1
    except RetentionSuppressed:
        print("library card: this task does not save cards; explicit Library registration does not enable card capture.")
        return 1
    except (cards.CardError, TaskRetentionError) as error:
        print(f"library card: {_safe(str(error))}")
        return 2
    except (ValueError, OSError, index.IndexError):
        print("library card: source evidence, card input or publication is unavailable or invalid; preserve existing files and repair before retrying.")
        return 2


def run_registration(args: argparse.Namespace) -> int:
    options = {"task_id": getattr(args, "task", None), "requested": getattr(args, "requested", False)}
    try:
        engine = register_source if args.library_action == "add" else unregister_source
        registration = engine(args.workspace, args.source, **options)
    except RetentionSuppressed:
        print("Library registration skipped: this task does not save Memory. A separate explicit Library request is needed.")
        return 1
    except (OSError, ValueError) as error:
        print(f"library {args.library_action}: {_safe(str(error))}")
        return 2
    path = registration.source.source_path
    if args.library_action == "remove":
        if registration.implicit:
            print("This source is selected by its Library location. Use an ignore rule to exclude it.")
            return 1
        print(f"Registration {'removed' if registration.changed else 'already absent'}: {_safe(path)}")
        return 0
    print(f"Registration: {'already selected' if not registration.changed else 'added'} {_safe(path)}")
    try:
        result = ingest_source(args.workspace, path, **options)
    except (OSError, ValueError) as error:
        print(f"Registration remains selected; extraction unavailable: {_safe(str(error))}")
        print("Card: unavailable; no card was generated.")
        return 1
    print("Extraction: " + ", ".join(f"{name}={value}" for name, value in result.counts.items()))
    for source, status, reason in result.flagged:
        print(f"flagged {_safe(source)}: {_safe(status)}: {_safe(reason)}")
    from apparatus_core.library.cards import read_card
    try:
        card = read_card(args.workspace, path, include_text=False)
        print(f"Card: {card['card_status']}; card generation requires the current assistant.")
    except (ValueError, OSError, index.IndexError):
        print("Card: unavailable; no card was generated.")
    return 0 if result.ok else 1


def run_list(args: argparse.Namespace) -> int:
    try:
        statuses = list_sources(args.workspace)
    except (OSError, ValueError) as error:
        print(f"library list: {_safe(str(error))}")
        return 2
    if getattr(args, "as_json", False):
        print(json.dumps([{"source_path": item.source_path, "availability": item.status}
                          for item in statuses], ensure_ascii=False))
    else:
        for item in statuses:
            print(f"{_safe(item.source_path)}: {_safe(item.status)}")
        print("Availability does not establish extraction or search coverage.")
    return 0


def run(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    if not workspace.exists():
        print("library ingest: workspace path does not exist")
        return 2
    if not workspace.is_dir():
        print("library ingest: workspace path is not a directory")
        return 2
    try:
        feature_is_enabled = feature_enabled(workspace, "library_indexing")
    except FeatureProfileError as error:
        print(f"library ingest: {_safe(str(error))}")
        return 2
    if not feature_is_enabled:
        print("This feature is off; say the word and I'll enable it.")
        return 1
    try:
        options = {}
        if getattr(args, "task", None) is not None:
            options["task_id"] = args.task
        if getattr(args, "requested", False):
            options["requested"] = True
        result = ingest_library(workspace, **options)
    except RetentionSuppressed:
        print("Library ingest skipped: this task does not save Memory.")
        return 1
    except ValueError as error:
        print(f"library ingest: {_safe(str(error))}")
        return 2
    print(f"Library cache: {_safe(str(result.cache))}")
    print("Library ingest: " + ", ".join(f"{name}={result.counts[name]}" for name in result.counts))
    print(result.ignore_report.sentence())
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
        feature_is_enabled = feature_enabled(workspace, "library_indexing")
    except FeatureProfileError as error:
        print(f"library search: {_safe(str(error))}")
        return 2
    if not feature_is_enabled:
        print("This feature is off; say the word and I'll enable it.")
        return 1
    try:
        result = index.retrieve(
            workspace, args.query, args.limit,
            task_id=getattr(args, "task", None),
            rebuild_index=getattr(args, "rebuild", False),
            requested=getattr(args, "requested", False),
        )
        hits, ignore_report = result
    except RetentionSuppressed:
        print("Library index write skipped: this task does not save Memory.")
        return 1
    except TaskRetentionError as error:
        print(f"library search: {_safe(str(error))}")
        return 2
    except index.NoExtractionsError as error:
        if error.reason == "invalid":
            print("Existing Library extraction evidence is invalid. Run apparatus library ingest to repair it; a no-save task needs a separate explicit Library request.")
        elif error.readonly:
            print("Existing Library extractions are unavailable. A separate Library ingest is needed.")
        else:
            print("Nothing from your Library has been ingested yet. Run apparatus library ingest first.")
            _print_ignore_report(load_ignore_rules(workspace).require_valid().report(), args.as_json)
        return 1
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
        print(json.dumps({"hits": [{"source_path": hit.source_path, "snippet": hit.snippet, "score": hit.score} for hit in hits],
                          "coverage": result.coverage.as_dict()}, ensure_ascii=False))
    else:
        for hit in hits:
            print(f"{_safe(hit.source_path)} ({hit.score:.6f}): {_safe(hit.snippet)}")
        print(result.coverage.sentence())
        for path, reason in result.coverage.issues:
            print(f"{_safe(path)}: {_safe(reason)}")
    _print_ignore_report(ignore_report, args.as_json)
    return 0


def _print_ignore_report(report: Any, as_json: bool) -> None:
    print(report.sentence(), file=sys.stderr if as_json else sys.stdout)
