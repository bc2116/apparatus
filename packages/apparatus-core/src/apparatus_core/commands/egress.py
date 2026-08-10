"""The ``apparatus egress`` command."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from apparatus_core.egress import (
    CREDENTIAL_REFUSAL_CODE,
    DECISIONS,
    EgressError,
    check_egress,
)


def register(subparsers: Any) -> None:
    """Register the egress verb through the standard entry-point path."""
    parser = subparsers.add_parser("egress", help="check content before it leaves a workspace")
    actions = parser.add_subparsers(dest="egress_action")
    check = actions.add_parser("check", help="inspect outbound workspace files")
    check.add_argument("workspace", metavar="WORKSPACE")
    check.add_argument("files", nargs="+", metavar="FILE")
    check.add_argument("--decision", choices=DECISIONS)
    check.set_defaults(func=run, egress_action="check")


def run(args: argparse.Namespace) -> int:
    """Run the deterministic egress check with calm, value-free output."""
    if getattr(args, "egress_action", None) != "check":
        print("egress: choose check")
        return 2
    try:
        result = check_egress(
            args.workspace,
            args.files,
            decision=getattr(args, "decision", None),
        )
    except EgressError as error:
        print(f"egress: {error}")
        return 2
    except Exception:  # noqa: BLE001 - CLI boundary hides environment details
        print("egress: could not complete the egress check safely")
        return 2

    for finding in result.findings:
        print(f"{finding.file}:{finding.line}: {finding.source}/{finding.kind}")
    for path in result.redacted_copies:
        print(f"redacted copy: {path}")
    if result.outcome == "clean":
        print("egress check passed: no sensitive items found")
    elif result.outcome == "decision-required":
        print(
            "egress check stopped: present the findings and redacted copy to "
            "the human, then ask for an explicit choice"
        )
    elif result.outcome == "credential-original-refused":
        print(f"refusal-code: {CREDENTIAL_REFUSAL_CODE}")
        print("egress check stopped: credentials may leave only in a redacted copy")
    else:
        print(f"egress decision recorded: {result.decision}")
    print(f"egress receipt: {Path(result.receipt).relative_to(Path(args.workspace).resolve())}")
    return result.exit_code
