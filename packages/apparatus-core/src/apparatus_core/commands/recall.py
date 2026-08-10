"""The ``apparatus recall`` command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
import unicodedata

from apparatus_core import recall as recall_engine
from apparatus_core.features import enabled as feature_enabled, off_receipt_fields
from apparatus_core.ignore import IgnoreReport
from apparatus_core.library import index
from apparatus_core.receipts import write_receipt


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser("recall", help="recall grounded Library evidence")
    parser.add_argument("workspace", metavar="WORKSPACE")
    parser.add_argument("question")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.set_defaults(func=run)


def _safe(value: str) -> str:
    return "".join(
        " " if unicodedata.category(character).startswith("C") else character
        for character in value
    )


def _render_human(envelope: recall_engine.RecallEnvelope) -> None:
    print(f"Status: {envelope['status']}")
    print(f"Question: {_safe(envelope['question'])}")
    print(f"Threshold: {envelope['threshold']}")
    print(f"Generated at: {envelope['generated_at']}")
    if envelope["status"] == "abstained":
        print("Evidence: none")
        print("Not in your Library.")
        print("Answers from elsewhere are not grounded recall.")
        return
    print("Evidence:")
    for evidence in envelope["evidence"]:
        print(
            f"- {_safe(evidence['source'])} ({evidence['score']:.6f}): "
            f"{_safe(evidence['snippet'])}"
        )


def run(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    if not workspace.exists() or not workspace.is_dir():
        print("recall: workspace path is not a directory")
        return 2
    if args.limit < 1:
        print("recall: --limit must be positive")
        return 2
    if not feature_enabled(workspace, "library_indexing"):
        try:
            write_receipt(
                workspace, "recall", off_receipt_fields("library indexing")
            )
        except (OSError, ValueError):
            print("recall: could not record that this feature is off")
            return 2
        print("This feature is off; say the word and I'll enable it.")
        return 1
    try:
        ignore_reports: list[IgnoreReport] = []
        envelope = recall_engine.recall(
            workspace,
            args.question,
            args.limit,
            report_ignore=ignore_reports.append,
        )
    except recall_engine.NoExtractionsError:
        print(
            "Nothing from your Library has been ingested yet. "
            "Run apparatus library ingest first."
        )
        return 1
    except index.FtsUnavailable as error:
        print(f"recall: {_safe(str(error))}")
        return 1
    except (index.IndexError, OSError, ValueError) as error:
        print(f"recall: {_safe(str(error))}")
        return 2
    if args.as_json:
        print(json.dumps(envelope, ensure_ascii=False))
        print(ignore_reports[0].sentence(), file=sys.stderr)
    else:
        _render_human(envelope)
        print(ignore_reports[0].sentence())
    return 0
