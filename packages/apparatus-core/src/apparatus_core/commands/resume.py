"""The read-only ``apparatus resume`` work-area brief."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Callable
import unicodedata

from apparatus_core import records
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.labeler import split_record_exact
from apparatus_core.library.sources import SourceStatus, list_sources
from apparatus_core.payload import PayloadError, preflight_workspace_paths
from apparatus_core.project_binding import BindingError, ResolvedContext
from apparatus_core.snapshots import Snapshot, SnapshotProbe, probe_latest_snapshot


MAX_ITEMS = 20
MAX_DISPLAY_CODEPOINTS = 240
_SNAPSHOT_ID = re.compile(r"^[0-9a-fA-F]{4,64}$")


class ResumeContractError(RuntimeError):
    """An injected or internal resume reader returned an invalid result."""


class GoalReadError(RuntimeError):
    """The goal collection could not be read as one valid collection."""


@dataclass(frozen=True)
class GoalEntry:
    path: str
    status: str
    title: str
    next_action: str


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser("resume", help="show a read-only work-area brief")
    parser.add_argument("workspace", metavar="WORKSPACE")
    parser.set_defaults(func=run)


def _display(value: str) -> str:
    replaced = "".join(
        " " if unicodedata.category(character).startswith("C") else character
        for character in value
    )
    collapsed = " ".join(replaced.split())
    if len(collapsed) > MAX_DISPLAY_CODEPOINTS:
        return collapsed[: MAX_DISPLAY_CODEPOINTS - 3] + "..."
    return collapsed


def _read_goals(anchor: Any) -> tuple[GoalEntry, ...]:
    retained = []
    try:
        paths = anchor.list_memory_records("Goals")
        if any(path.parent != Path("Goals") for path in paths):
            raise GoalReadError("nested goal record")
        entries = []
        for path in paths:
            owned = anchor.capture_file(path)
            retained.append(owned)
            try:
                data, body = split_record_exact(owned.content.decode("utf-8"))
            except (UnicodeError, ValueError, TypeError, records.yaml.YAMLError) as error:
                raise GoalReadError("invalid goal record") from error
            if records.validate("goal", data, filename=path.name, body=body):
                raise GoalReadError("invalid goal record")
            for field in ("title", "owner", "done-when", "next-action"):
                if not isinstance(data.get(field), str) or not data[field].strip():
                    raise GoalReadError("invalid goal display field")
            if data["status"] in {"active", "waiting"}:
                entries.append(
                    GoalEntry(
                        path.as_posix(), data["status"], data["title"], data["next-action"]
                    )
                )
        if any(not anchor.matches_owned(owned) for owned in retained):
            raise GoalReadError("goal collection changed")
        if anchor.list_memory_records("Goals") != paths:
            raise GoalReadError("goal collection changed")
        return tuple(sorted(entries, key=lambda entry: entry.path))
    except GoalReadError:
        raise
    except (OSError, ValueError, TypeError, records.yaml.YAMLError) as error:
        raise GoalReadError("goals unavailable") from error
    finally:
        for owned in retained:
            owned.close()


def _bounded(items: tuple[Any, ...]) -> tuple[tuple[Any, ...], int]:
    return items[:MAX_ITEMS], max(0, len(items) - MAX_ITEMS)


def _goals_text(goals: tuple[GoalEntry, ...] | None) -> list[str]:
    lines = ["Goals"]
    if goals is None:
        return lines + [
            "Status: unavailable",
            "Repair the Goals directory and every direct goal record, then retry.",
        ]
    shown, remaining = _bounded(goals)
    lines.append(f"Status: available; shown: {len(shown)}; remaining: {remaining}")
    if not shown:
        lines.append("- none")
    for goal in shown:
        lines.append(
            f"- {goal.path} | status: {goal.status} | title: {_display(goal.title)} "
            f"| next action: {_display(goal.next_action)}"
        )
    return lines


def _sources_text(sources: tuple[SourceStatus, ...] | None) -> list[str]:
    lines = ["Sources"]
    if sources is None:
        return lines + [
            "Status: unavailable",
            "Repair the selected-source catalog and System/ignore, then retry.",
        ]
    shown, remaining = _bounded(sources)
    lines.append(f"Status: available; shown: {len(shown)}; remaining: {remaining}")
    if not shown:
        lines.append("- none")
    guidance = {
        "missing": "The original remains selected; decide whether to repair its path or re-register it.",
        "ignored": "Review System/ignore before using this selected source.",
        "unavailable": "Provide a safe readable path before using this selected source.",
        "unsafe": "Provide a safe readable path before using this selected source.",
    }
    for source in shown:
        line = f"- {source.source_path} | availability: {source.status}"
        if source.status in guidance:
            line += f" | {guidance[source.status]}"
        lines.append(line)
    return lines


def _snapshot_text(probe: SnapshotProbe | None) -> list[str]:
    lines = ["Latest snapshot"]
    if probe is None or probe.status == "unavailable":
        return lines + [
            "Status: unavailable",
            "Snapshot history could not be safely inspected; repair snapshot availability, then retry.",
        ]
    if probe.status == "none":
        return lines + ["Status: none"]
    if probe.status != "latest" or probe.snapshot is None:
        raise ResumeContractError("invalid snapshot probe")
    snapshot = probe.snapshot
    lines.extend(
        [
            "Status: latest",
            f"- id: {snapshot.identifier} | UTC: {snapshot.timestamp} "
            f"| label: {_display(snapshot.label)} | scope: {snapshot.scope}",
        ]
    )
    if snapshot.scope == "managed-state":
        lines.extend(
            [
                "Coverage records: validated Goals; current, outdated, and forgotten Memory/Facts, Memory/People, Memory/Decisions, and legacy Decisions; System/procedures; non-recovery System/receipts; selected source registrations and cards; and adopted-Skill ownership.",
                "Coverage files: AGENTS.md, CLAUDE.md, Welcome.md, .cursor/rules/apparatus.mdc, .github/copilot-instructions.md, System/profile.yaml, System/ignore, System/README.md, System/guidance/model-guidance.md, System/policy/standard.md, and System/policy/private.md when present.",
                "Coverage Skills: exactly the named apparatus-welcome, apparatus-produce-deliverable, apparatus-research-and-summarize, apparatus-review-against-checklist, apparatus-weekly-review, apparatus-economizer, and apparatus-humanizer Skill bodies when present; .agents/skills is not covered recursively.",
                "Excluded: project files, Library originals, extraction and index caches, task controls, project bindings and routing, recovery storage, and recovery-generated snapshot, restore, and backup-export receipts.",
            ]
        )
    else:
        lines.append("Coverage: this command has no managed-state coverage declaration for a legacy workspace snapshot.")
    return lines


def _validate_sources(value: object) -> tuple[SourceStatus, ...]:
    if not isinstance(value, tuple):
        raise ResumeContractError("invalid source reader result")
    allowed = {"available", "missing", "unavailable", "unsafe", "ignored"}
    for source in value:
        if (
            not isinstance(source, SourceStatus)
            or not isinstance(source.status, str)
            or source.status not in allowed
            or not isinstance(source.source_path, str)
        ):
            raise ResumeContractError("invalid source reader result")
    return tuple(sorted(value, key=lambda source: source.source_path))


def _validate_goals(value: object) -> tuple[GoalEntry, ...]:
    if not isinstance(value, tuple):
        raise ResumeContractError("invalid goal reader result")
    paths = set()
    for goal in value:
        if not isinstance(goal, GoalEntry):
            raise ResumeContractError("invalid goal reader result")
        path = Path(goal.path) if isinstance(goal.path, str) else Path()
        if (
            not isinstance(goal.path, str)
            or path.parent != Path("Goals")
            or path.as_posix() != goal.path
            or not records.KEBAB_FILENAME.fullmatch(path.name)
            or goal.path in paths
            or not isinstance(goal.status, str)
            or goal.status not in {"active", "waiting"}
            or not isinstance(goal.title, str)
            or not goal.title.strip()
            or not isinstance(goal.next_action, str)
            or not goal.next_action.strip()
        ):
            raise ResumeContractError("invalid goal reader result")
        paths.add(goal.path)
    return tuple(sorted(value, key=lambda goal: goal.path))


def _validate_probe(value: object) -> SnapshotProbe:
    if (
        not isinstance(value, SnapshotProbe)
        or not isinstance(value.status, str)
        or value.status not in {"latest", "none", "unavailable"}
    ):
        raise ResumeContractError("invalid snapshot reader result")
    if value.status != "latest":
        if value.snapshot is not None:
            raise ResumeContractError("invalid snapshot reader result")
        return value
    snapshot = value.snapshot
    if (
        not isinstance(snapshot, Snapshot)
        or not isinstance(snapshot.identifier, str)
        or not _SNAPSHOT_ID.fullmatch(snapshot.identifier)
        or not isinstance(snapshot.timestamp, str)
        or not isinstance(snapshot.label, str)
        or not isinstance(snapshot.scope, str)
        or snapshot.scope not in {"workspace", "managed-state"}
    ):
        raise ResumeContractError("invalid snapshot reader result")
    try:
        parsed = datetime.fromisoformat(snapshot.timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise ResumeContractError("invalid snapshot reader result") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ResumeContractError("invalid snapshot reader result")
    timestamp = (
        parsed.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    return SnapshotProbe(
        "latest",
        Snapshot(snapshot.identifier, timestamp, snapshot.label, snapshot.scope),
    )


def run(
    args: argparse.Namespace,
    *,
    goal_reader: Callable[[Any], tuple[GoalEntry, ...]] = _read_goals,
    source_reader: Callable[[Path], tuple[SourceStatus, ...]] = list_sources,
    snapshot_reader: Callable[[Path], SnapshotProbe] = probe_latest_snapshot,
) -> int:
    """Read all sections through one retained root and print only after final validation."""
    with ExitStack() as stack:
        context = getattr(args, "_project_context", None)
        try:
            if context is not None:
                if not isinstance(context, ResolvedContext):
                    raise ResumeContractError("invalid project context")
                anchor = context.workspace_anchor
                workspace = context.workspace
                selection = "linked work area"
            else:
                workspace = preflight_workspace_paths(Path(args.workspace))
                if not workspace.is_dir():
                    raise PayloadError("workspace is not a directory")
                anchor = stack.enter_context(WorkspaceAnchor(workspace))
                selection = "direct work area"

            def boundary() -> None:
                if not anchor.root_is_current():
                    raise ResumeContractError("work-area root changed")
                if context is not None:
                    context.validate()

            sections_unavailable = False

            boundary()
            try:
                goals = _validate_goals(goal_reader(anchor))
            except GoalReadError:
                goals = None
                sections_unavailable = True
            boundary()

            boundary()
            try:
                sources = _validate_sources(source_reader(workspace))
            except ResumeContractError:
                raise
            except Exception:
                sources = None
                sections_unavailable = True
            boundary()

            boundary()
            try:
                probe = _validate_probe(snapshot_reader(workspace))
            except ResumeContractError:
                raise
            except Exception:
                probe = None
                sections_unavailable = True
            boundary()

            if probe is None or probe.status == "unavailable":
                sections_unavailable = True
            if sources is not None and any(source.status != "available" for source in sources):
                sections_unavailable = True
            result = "partial" if sections_unavailable else "complete"
            lines = [
                "Work-area context",
                f"Selection: {selection}",
                f"Result: {result}",
                "Scope: the selected work area; no project ownership or task history is inferred.",
                "",
                *_goals_text(goals),
                "",
                *_sources_text(sources),
                "",
                *_snapshot_text(probe),
            ]
            output = "\n".join(lines)
            boundary()
            print(output)
            return 1 if sections_unavailable else 0
        except (BindingError, PayloadError, OSError, ResumeContractError, ValueError):
            print("resume: the selected work area changed, is unsafe, or is invalid")
            return 2
