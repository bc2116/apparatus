"""Deterministic, containment-safe inspection for workspace egress."""

from __future__ import annotations

import os
import re
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apparatus_core import credentials, labeler, receipts, records
from apparatus_core.fs_transactions import WorkspaceAnchor

DECISIONS: tuple[str, ...] = ("use-redacted", "send-original", "stop")
CREDENTIAL_REFUSAL_CODE = "credential-original-forbidden"
REDACTION_UNAVAILABLE_CODE = "deterministic-redaction-unavailable"

_RECORD_FOLDERS: tuple[tuple[Path, str], ...] = (
    (Path("Goals"), "goal"),
    (Path("Decisions"), "decision"),
    (Path("Memory/People"), "person"),
    (Path("Memory/Facts"), "fact"),
    (Path("System/procedures"), "procedure"),
    (Path("System/receipts"), "receipt"),
)
_EMAIL_VALUE_CHARACTER = r"A-Za-z0-9.!#$%&'*+/=?^_`{|}~@-"


class EgressError(ValueError):
    """An egress check could not be prepared without changing the workspace."""


@dataclass(frozen=True)
class Finding:
    """One value-free sensitive-item finding."""

    file: str
    source: str
    kind: str
    line: int


@dataclass(frozen=True)
class EgressResult:
    """The complete result of one inspect-only egress check."""

    findings: tuple[Finding, ...]
    redacted_offers: tuple[str, ...]
    redacted_copies: tuple[str, ...]
    redaction_unavailable: tuple[str, ...]
    destination: str | None
    decision: str | None
    outcome: str
    receipt: Path
    redaction_receipt: Path | None

    @property
    def exit_code(self) -> int:
        if self.outcome in {"clean", "use-redacted", "send-original", "stopped"}:
            return 0
        return 1


@dataclass(frozen=True)
class _PeopleValue:
    kind: str
    value: str


@dataclass(frozen=True)
class _Span:
    start: int
    end: int
    source: str
    kind: str
    placeholder: str
    priority: int


@dataclass
class _CapturedText:
    relative: Path
    owned: Any
    text: str

    def close(self) -> None:
        self.owned.close()


@dataclass(frozen=True)
class _Scan:
    source: _CapturedText
    findings: tuple[Finding, ...]
    redacted: str | None
    opaque: bool


@dataclass(frozen=True)
class _Artifact:
    relative: Path
    content: bytes


def _workspace_path(value: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(value)))


def _relative_argument(root: Path, value: str | Path) -> Path:
    supplied = Path(value)
    if supplied.is_absolute():
        absolute = Path(os.path.abspath(os.fspath(supplied)))
        try:
            relative = absolute.relative_to(root)
        except ValueError as error:
            raise EgressError(f"file is outside the workspace: {value}") from error
    else:
        relative = Path(os.path.normpath(os.fspath(supplied)))
    if (
        relative.is_absolute()
        or not relative.parts
        or relative == Path(".")
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise EgressError(f"file path is not safely workspace-relative: {value}")
    return relative


def _identity_key(identity: Any) -> tuple[int, int]:
    if hasattr(identity, "device"):
        return int(identity.device), int(identity.inode)
    return int(identity.volume), int(identity.index)


def _capture_sources(
    anchor: Any, root: Path, values: Sequence[str | Path]
) -> tuple[_CapturedText, ...]:
    if not values:
        raise EgressError("provide at least one file to check")
    captured: list[_CapturedText] = []
    relative_seen: set[Path] = set()
    identity_seen: set[tuple[int, int]] = set()
    try:
        for value in values:
            relative = _relative_argument(root, value)
            if relative in relative_seen:
                raise EgressError(f"duplicate input file: {relative.as_posix()}")
            try:
                owned = anchor.capture_file(relative)
            except FileNotFoundError as error:
                raise EgressError(f"file does not exist: {value}") from error
            except OSError as error:
                raise EgressError(f"file is not containment-safe: {value}") from error
            identity = _identity_key(owned.identity)
            if identity in identity_seen:
                owned.close()
                raise EgressError(
                    f"duplicate input file identity: {relative.as_posix()}"
                )
            try:
                text = owned.content.decode("utf-8", errors="strict")
            except UnicodeError as error:
                owned.close()
                raise EgressError(
                    f"file must be readable strict UTF-8 text: {value}"
                ) from error
            relative_seen.add(relative)
            identity_seen.add(identity)
            captured.append(_CapturedText(relative, owned, text))
        return tuple(captured)
    except Exception:
        for item in captured:
            item.close()
        raise


def _people_snapshot(
    anchor: Any,
) -> tuple[tuple[Path, ...], tuple[_CapturedText, ...], tuple[_PeopleValue, ...]]:
    try:
        tree = tuple(
            anchor.list_files("Memory/People", suffix=None, include_hidden=True)
        )
    except OSError as error:
        raise EgressError("Memory/People could not be traversed safely") from error
    records_found: list[_CapturedText] = []
    values: set[tuple[str, str]] = set()
    try:
        for relative in tree:
            if relative.name == ".gitkeep":
                continue
            if relative.suffix != ".md":
                raise EgressError(
                    "Memory/People contains an unsupported non-record file"
                )
            owned: Any | None = None
            try:
                owned = anchor.capture_file(relative)
                text = owned.content.decode("utf-8", errors="strict")
                data, _body = records.parse_record(text)
            except (OSError, UnicodeError, ValueError, records.yaml.YAMLError) as error:
                if owned is not None:
                    owned.close()
                raise EgressError(
                    "Memory/People contains an unreadable or invalid record"
                ) from error
            problems = records.validate("person", data, filename=relative.name)
            if problems:
                owned.close()
                raise EgressError(
                    "Memory/People contains a record that does not match its schema"
                )
            records_found.append(_CapturedText(relative, owned, text))
            name = data.get("name")
            if not isinstance(name, str) or not name:
                raise EgressError("Memory/People contains an invalid person name")
            values.add(("person-name", name))
            for kind, pattern in labeler._PATTERNS:
                if kind == labeler.EMAIL:
                    values.update(
                        ("person-email", match.group(0))
                        for match in pattern.finditer(text)
                    )
        people = tuple(
            _PeopleValue(kind, value) for kind, value in sorted(values)
        )
        return tree, tuple(records_found), people
    except Exception:
        for item in records_found:
            item.close()
        raise


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _record_kind(relative: Path) -> str | None:
    for folder, kind in _RECORD_FOLDERS:
        try:
            relative.relative_to(folder)
        except ValueError:
            continue
        return kind
    return None


def _frontmatter(
    source: _CapturedText,
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    starts_frontmatter = source.text.startswith("---\n") or source.text.startswith(
        "---\r\n"
    )
    expected_kind = _record_kind(source.relative)
    if not starts_frontmatter:
        if expected_kind is not None:
            raise EgressError(
                f"record does not have valid frontmatter: {source.relative.as_posix()}"
            )
        return None, ()
    try:
        data, _body = records.parse_record(source.text)
    except (ValueError, records.yaml.YAMLError) as error:
        raise EgressError(
            f"record frontmatter is invalid: {source.relative.as_posix()}"
        ) from error
    if expected_kind is not None:
        problems = records.validate(
            expected_kind, data, filename=source.relative.name
        )
        if problems:
            raise EgressError(
                f"record does not match its schema: {source.relative.as_posix()}"
            )
    declared = data.get("labels", [])
    if declared is None:
        declared = []
    if not isinstance(declared, list) or not all(
        isinstance(item, str) and item for item in declared
    ):
        raise EgressError(
            f"record labels must be non-empty strings: {source.relative.as_posix()}"
        )
    return data, tuple(declared)


def _people_pattern(value: _PeopleValue) -> re.Pattern[str]:
    escaped = re.escape(value.value)
    if value.kind == "person-name":
        return re.compile(rf"(?<!\w){escaped}(?!\w)")
    return re.compile(
        rf"(?<![{_EMAIL_VALUE_CHARACTER}]){escaped}"
        rf"(?![{_EMAIL_VALUE_CHARACTER}])"
    )


def _pattern_scan(source: _CapturedText, people: Iterable[_PeopleValue]) -> tuple[
    list[Finding], list[_Span], set[str]
]:
    findings: list[Finding] = []
    spans: list[_Span] = []
    matched_labels: set[str] = set()
    for kind, pattern in labeler._PATTERNS:
        for match in pattern.finditer(source.text):
            matched_labels.add(kind)
            findings.append(
                Finding(
                    source.relative.as_posix(),
                    "label",
                    kind,
                    _line_number(source.text, match.start()),
                )
            )
            spans.append(
                _Span(
                    match.start(),
                    match.end(),
                    "label",
                    kind,
                    f"[redacted-{kind.removeprefix('pii/')}]",
                    20,
                )
            )
    for candidate in credentials._candidates(source.text):
        findings.append(
            Finding(
                source.relative.as_posix(),
                "credential",
                candidate.credential_class,
                _line_number(source.text, candidate.start),
            )
        )
        spans.append(
            _Span(
                candidate.start,
                candidate.end,
                "credential",
                candidate.credential_class,
                f"[redacted-{candidate.credential_class}]",
                10,
            )
        )
    for person in people:
        for match in _people_pattern(person).finditer(source.text):
            findings.append(
                Finding(
                    source.relative.as_posix(),
                    "people",
                    person.kind,
                    _line_number(source.text, match.start()),
                )
            )
            spans.append(
                _Span(
                    match.start(),
                    match.end(),
                    "people",
                    person.kind,
                    f"[redacted-{person.kind}]",
                    30,
                )
            )
    return findings, spans, matched_labels


def _non_overlapping_spans(spans: Iterable[_Span]) -> tuple[_Span, ...]:
    accepted: list[_Span] = []
    ordered = sorted(
        spans,
        key=lambda item: (item.priority, item.start, -(item.end - item.start)),
    )
    for candidate in ordered:
        if any(
            candidate.start < item.end and item.start < candidate.end
            for item in accepted
        ):
            continue
        accepted.append(candidate)
    return tuple(sorted(accepted, key=lambda item: item.start))


def _apply_spans(text: str, spans: Iterable[_Span]) -> str:
    pieces: list[str] = []
    cursor = 0
    for span in _non_overlapping_spans(spans):
        pieces.append(text[cursor : span.start])
        pieces.append(span.placeholder)
        cursor = span.end
    pieces.append(text[cursor:])
    return "".join(pieces)


def _valid_redacted_record(relative: Path, text: str) -> bool:
    kind = _record_kind(relative)
    if kind is None:
        return True
    try:
        data, _body = records.parse_record(text)
    except (ValueError, records.yaml.YAMLError):
        return False
    output = _redacted_relative(relative)
    return not records.validate(kind, data, filename=output.name)


def _scan(source: _CapturedText, people: Iterable[_PeopleValue]) -> _Scan:
    _data, declared = _frontmatter(source)
    findings, spans, matched_labels = _pattern_scan(source, people)
    for declared_label in declared:
        findings.append(
            Finding(
                source.relative.as_posix(),
                "declared-label",
                declared_label,
                1,
            )
        )
    structural = _record_kind(source.relative) == "person"
    if structural:
        findings.append(
            Finding(source.relative.as_posix(), "structural", "person-data", 1)
        )
    opaque = structural or any(
        declared_label not in matched_labels for declared_label in declared
    )
    findings_tuple = tuple(
        sorted(findings, key=lambda item: (item.line, item.source, item.kind))
    )
    if not findings_tuple or opaque:
        return _Scan(source, findings_tuple, None, opaque)
    redacted = _apply_spans(source.text, spans)
    if not _valid_redacted_record(source.relative, redacted):
        return _Scan(source, findings_tuple, None, True)
    return _Scan(source, findings_tuple, redacted, False)


def _redacted_relative(relative: Path) -> Path:
    separator = "-" if _record_kind(relative) is not None else "."
    return relative.with_name(
        f"{relative.stem}{separator}redacted{relative.suffix}"
    )


def _preflight_outputs(
    anchor: Any, scans: tuple[_Scan, ...]
) -> tuple[tuple[Path, ...], tuple[str, ...]]:
    inputs = {scan.source.relative for scan in scans}
    outputs: list[Path] = []
    unavailable: list[str] = []
    for scan in scans:
        if not scan.findings:
            continue
        if scan.redacted is None:
            unavailable.append(scan.source.relative.as_posix())
            continue
        output = _redacted_relative(scan.source.relative)
        if output in inputs:
            raise EgressError(
                f"redacted output collides with an input: {output.as_posix()}"
            )
        if output in outputs:
            raise EgressError(
                f"duplicate redacted output: {output.as_posix()}"
            )
        try:
            exists = anchor.entry_exists(output)
        except OSError as error:
            raise EgressError(
                f"redacted output path is unsafe: {output.as_posix()}"
            ) from error
        if exists:
            raise EgressError(
                f"redacted output already exists: {output.as_posix()}"
            )
        outputs.append(output)
    return tuple(outputs), tuple(unavailable)


def _finding_counts(findings: Iterable[Finding]) -> dict[str, int]:
    counts = Counter(f"{finding.source}/{finding.kind}" for finding in findings)
    return {name: counts[name] for name in sorted(counts)}


def findings_summary(findings: Iterable[Finding]) -> str:
    """Render a stable value-free summary for conformance fixtures and receipts."""
    counts = _finding_counts(findings)
    if not counts:
        return "none\n"
    return "".join(f"{name}: {count}\n" for name, count in counts.items())


def _outcome(
    findings: tuple[Finding, ...],
    unavailable: tuple[str, ...],
    decision: str | None,
) -> str:
    if decision == "stop":
        return "stopped"
    if decision is None:
        return "clean" if not findings else "decision-required"
    credentials_found = any(item.source == "credential" for item in findings)
    if decision == "send-original" and credentials_found:
        return "credential-original-refused"
    if decision == "use-redacted" and unavailable:
        return "redaction-unavailable-refused"
    return decision


def _redaction_receipt_fields(
    findings: tuple[Finding, ...],
    copies_will_publish: bool,
) -> dict[str, Any]:
    credential_findings = tuple(
        item for item in findings if item.source == "credential"
    )
    counts = Counter(item.kind for item in credential_findings)
    locations = [
        {"file": item.file, "line": item.line, "kind": item.kind}
        for item in credential_findings
    ]
    action = "replaced" if copies_will_publish else "found"
    return {
        "summary": f"Credential floor {action} {len(credential_findings)} value(s).",
        "classes": sorted(counts),
        "counts": {name: counts[name] for name in sorted(counts)},
        "locations": locations,
        "copies_published": copies_will_publish,
        "body": "Credential classes and locations:\n"
        + "".join(
            f"- {item['file']}:{item['line']}: {item['kind']}\n"
            for item in locations
        ),
    }


def _egress_receipt_fields(
    sources: tuple[_CapturedText, ...],
    findings: tuple[Finding, ...],
    offered: tuple[Path, ...],
    published: tuple[Path, ...],
    unavailable: tuple[str, ...],
    destination: str | None,
    decision: str | None,
    outcome: str,
) -> dict[str, Any]:
    file_names = [item.relative.as_posix() for item in sources]
    details = "".join(
        f"- {item.file}:{item.line}: {item.source}/{item.kind}\n"
        for item in findings
    ) or "- none\n"
    authorized = outcome in {"use-redacted", "send-original"}
    return {
        "summary": (
            f"Egress check found {len(findings)} sensitive item(s) "
            f"across {len(sources)} file(s)."
        ),
        "files": file_names,
        "finding_counts": _finding_counts(findings),
        "redacted_offers": [item.as_posix() for item in offered],
        "redacted_copies": [item.as_posix() for item in published],
        "redaction_unavailable": list(unavailable),
        "destination": (
            destination if destination is not None else "not provided"
        ),
        "decision": decision,
        "outcome": outcome,
        "pre_share_authorized": authorized,
        "anything_left_workspace": False,
        "body": (
            "Files checked:\n"
            + "".join(f"- {name}\n" for name in file_names)
            + "Destination: "
            + (destination if destination is not None else "not provided")
            + "\nFindings:\n"
            + details
            + "Decision: "
            + (decision if decision is not None else "none")
            + "\nPre-share authorization: "
            + ("yes" if authorized else "no")
            + "\nAnything left the workspace: no; this command only inspects and records.\n"
        ),
    }


def _available_receipt_path(
    anchor: Any,
    now: Any,
    event: str,
    receipts_directory_exists: bool,
    reserved: set[Path],
) -> Path:
    for collision in range(1, 1_000_000):
        relative = Path("System/receipts") / receipts.receipt_filename(
            now, event, collision
        )
        if relative in reserved:
            continue
        if receipts_directory_exists and anchor.entry_exists(relative):
            continue
        reserved.add(relative)
        return relative
    raise EgressError("could not allocate a unique receipt filename")


def _validate_snapshot(
    anchor: Any,
    captured: Iterable[_CapturedText],
    people_tree: tuple[Path, ...],
) -> None:
    if not anchor.root_is_current():
        raise OSError("workspace root changed")
    for item in captured:
        if not anchor.matches_owned(item.owned):
            raise OSError("workspace source changed after inspection")
    current_tree = tuple(
        anchor.list_files("Memory/People", suffix=None, include_hidden=True)
    )
    if current_tree != people_tree:
        raise OSError("Memory/People changed after inspection")


def _publish(
    anchor: Any,
    artifacts: tuple[_Artifact, ...],
    *,
    create_receipts_directory: bool,
    captured: tuple[_CapturedText, ...],
    people_tree: tuple[Path, ...],
) -> None:
    owned_files: list[Any] = []
    owned_directory: Any | None = None
    try:
        _validate_snapshot(anchor, captured, people_tree)
        if create_receipts_directory:
            owned_directory = anchor.create_directory("System/receipts")
        for artifact in artifacts:
            artifact_owned_parent = (
                owned_directory
                if create_receipts_directory
                and artifact.relative.parent == Path("System/receipts")
                else None
            )
            owned_files.append(
                anchor.create_file(
                    artifact.relative,
                    artifact.content,
                    owned_parent=artifact_owned_parent,
                )
            )
        _validate_snapshot(anchor, captured, people_tree)
        if not all(anchor.matches_owned(item) for item in owned_files):
            raise OSError("published egress artifact changed before completion")
    except Exception as operation_error:
        cleanup_failed = False
        for owned in reversed(owned_files):
            try:
                anchor.unlink_owned(owned)
            except OSError:
                cleanup_failed = True
            finally:
                owned.close()
        if owned_directory is not None:
            try:
                anchor.remove_owned_directory(owned_directory)
            except OSError:
                cleanup_failed = True
            finally:
                owned_directory.close()
        if cleanup_failed:
            raise EgressError(
                "egress publication could not restore its prior state"
            ) from operation_error
        raise
    for owned in owned_files:
        owned.close()
    if owned_directory is not None:
        owned_directory.close()


def _validate_destination(destination: str | None) -> str | None:
    if destination is None:
        return None
    if not destination.strip() or "\n" in destination or "\r" in destination:
        raise EgressError("destination must be one line of plain language")
    if credentials._candidates(destination):
        raise EgressError("destination must not contain credential-floor content")
    return destination


def check_egress(
    workspace: str | Path,
    files: Sequence[str | Path],
    *,
    destination: str | None = None,
    decision: str | None = None,
    anchor_factory: Callable[[Path], Any] = WorkspaceAnchor,
) -> EgressResult:
    """Inspect outbound files and transactionally publish copies and receipts."""
    if decision is not None and decision not in DECISIONS:
        raise EgressError(f"decision must be one of {', '.join(DECISIONS)}")
    destination = _validate_destination(destination)
    root = _workspace_path(workspace)
    sources: tuple[_CapturedText, ...] = ()
    people_records: tuple[_CapturedText, ...] = ()
    try:
        try:
            anchor_context = anchor_factory(root)
        except (OSError, NotImplementedError, TypeError) as error:
            raise EgressError(
                "workspace path is not a containment-safe directory"
            ) from error
        with anchor_context as anchor:
            sources = _capture_sources(anchor, root, files)
            people_tree, people_records, people = _people_snapshot(anchor)
            scans = tuple(_scan(source, people) for source in sources)
            findings = tuple(
                sorted(
                    (item for scan in scans for item in scan.findings),
                    key=lambda item: (item.file, item.line, item.source, item.kind),
                )
            )
            offered, unavailable = _preflight_outputs(anchor, scans)
            outcome = _outcome(findings, unavailable, decision)
            publish_copies = outcome in {"use-redacted", "send-original"}
            published = offered if publish_copies else ()

            try:
                receipts_directory_exists = anchor.directory_exists(
                    "System/receipts"
                )
            except OSError as error:
                raise EgressError("System/receipts is not containment-safe") from error
            if not receipts_directory_exists:
                anchor.require_directory("System")

            egress_fields = _egress_receipt_fields(
                sources,
                findings,
                offered,
                published,
                unavailable,
                destination,
                decision,
                outcome,
            )
            now, egress_content = receipts.prepare_receipt("egress", egress_fields)
            credential_findings = tuple(
                item for item in findings if item.source == "credential"
            )
            redaction_content: bytes | None = None
            if credential_findings:
                _same_now, redaction_content = receipts.prepare_receipt(
                    "redaction",
                    _redaction_receipt_fields(findings, publish_copies),
                    now=now,
                )

            reserved = {source.relative for source in sources} | set(offered)
            redaction_relative: Path | None = None
            if redaction_content is not None:
                redaction_relative = _available_receipt_path(
                    anchor,
                    now,
                    "redaction",
                    receipts_directory_exists,
                    reserved,
                )
            egress_relative = _available_receipt_path(
                anchor,
                now,
                "egress",
                receipts_directory_exists,
                reserved,
            )

            copy_artifacts = tuple(
                _Artifact(
                    _redacted_relative(scan.source.relative),
                    scan.redacted.encode("utf-8"),
                )
                for scan in scans
                if publish_copies and scan.redacted is not None
            )
            receipt_artifacts: list[_Artifact] = []
            if redaction_relative is not None and redaction_content is not None:
                receipt_artifacts.append(
                    _Artifact(redaction_relative, redaction_content)
                )
            receipt_artifacts.append(_Artifact(egress_relative, egress_content))
            _publish(
                anchor,
                (*copy_artifacts, *receipt_artifacts),
                create_receipts_directory=not receipts_directory_exists,
                captured=(*sources, *people_records),
                people_tree=people_tree,
            )
            return EgressResult(
                findings=findings,
                redacted_offers=tuple(path.as_posix() for path in offered),
                redacted_copies=tuple(path.as_posix() for path in published),
                redaction_unavailable=unavailable,
                destination=destination,
                decision=decision,
                outcome=outcome,
                receipt=root / egress_relative,
                redaction_receipt=(
                    root / redaction_relative
                    if redaction_relative is not None
                    else None
                ),
            )
    except EgressError:
        raise
    except (OSError, UnicodeError, ValueError, records.yaml.YAMLError) as error:
        raise EgressError("egress check could not complete safely") from error
    finally:
        for item in (*sources, *people_records):
            item.close()
