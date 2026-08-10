"""Deterministic inspection and redaction for workspace egress."""

from __future__ import annotations

import os
import stat
import tempfile
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apparatus_core import credentials, labeler, records
from apparatus_core.receipts import write_receipt

DECISIONS: tuple[str, ...] = ("use-redacted", "send-original")
CREDENTIAL_REFUSAL_CODE = "credential-original-forbidden"


class EgressError(ValueError):
    """An egress check could not be prepared without changing the workspace."""


@dataclass(frozen=True)
class Finding:
    """One sensitive-item match without retaining the matched value."""

    file: str
    source: str
    kind: str
    line: int


@dataclass(frozen=True)
class EgressResult:
    """The complete result of one egress check."""

    findings: tuple[Finding, ...]
    redacted_copies: tuple[str, ...]
    decision: str | None
    outcome: str
    receipt: Path
    redaction_receipt: Path | None

    @property
    def exit_code(self) -> int:
        if self.outcome in {"clean", "use-redacted", "send-original"}:
            return 0
        return 1


@dataclass(frozen=True)
class _OutboundFile:
    absolute: Path
    relative: Path
    text: str


@dataclass(frozen=True)
class _PeopleValue:
    kind: str
    value: str


def _is_reparse_path(path: Path) -> bool:
    try:
        status = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISLNK(status.st_mode) or bool(
        getattr(status, "st_file_attributes", 0) & 0x400
    )


def _workspace(value: str | Path) -> Path:
    requested = Path(value)
    if _is_reparse_path(requested):
        raise EgressError("workspace path must not be a symbolic link")
    if not requested.exists():
        raise EgressError("workspace path does not exist")
    if not requested.is_dir():
        raise EgressError("workspace path is not a directory")
    try:
        return requested.resolve(strict=True)
    except OSError as error:
        raise EgressError("workspace path could not be resolved") from error


def _relative_input(root: Path, value: str | Path) -> tuple[Path, Path]:
    supplied = Path(value)
    lexical = supplied if supplied.is_absolute() else root / supplied
    try:
        resolved = lexical.resolve(strict=True)
    except OSError as error:
        raise EgressError(f"file does not exist: {value}") from error
    try:
        relative = resolved.relative_to(root)
    except ValueError as error:
        raise EgressError(f"file is outside the workspace: {value}") from error
    if relative == Path("."):
        raise EgressError(f"file is not a regular file: {value}")

    current = root
    for part in relative.parts:
        current /= part
        if _is_reparse_path(current):
            raise EgressError(f"file path must not contain a symbolic link: {value}")
    if not resolved.is_file():
        raise EgressError(f"file is not a regular file: {value}")
    return resolved, relative


def _read_outbound_files(
    root: Path, values: Sequence[str | Path]
) -> tuple[_OutboundFile, ...]:
    if not values:
        raise EgressError("provide at least one file to check")
    prepared: list[_OutboundFile] = []
    seen: set[Path] = set()
    for value in values:
        absolute, relative = _relative_input(root, value)
        if relative in seen:
            continue
        seen.add(relative)
        try:
            text = absolute.read_bytes().decode("utf-8", errors="strict")
        except (OSError, UnicodeError) as error:
            raise EgressError(
                f"file must be readable strict UTF-8 text: {value}"
            ) from error
        prepared.append(_OutboundFile(absolute, relative, text))
    return tuple(prepared)


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _pattern_findings(file: _OutboundFile) -> list[Finding]:
    found: list[Finding] = []
    # PR-18 is intentionally coupled to the exact compiled pattern registries
    # landed in PR-12. Importing them avoids a second, drifting definition.
    for kind, pattern in labeler._PATTERNS:
        for match in pattern.finditer(file.text):
            found.append(
                Finding(
                    file.relative.as_posix(),
                    "label",
                    kind,
                    _line_number(file.text, match.start()),
                )
            )
    for candidate in credentials._candidates(file.text):
        found.append(
            Finding(
                file.relative.as_posix(),
                "credential",
                candidate.credential_class,
                _line_number(file.text, candidate.start),
            )
        )
    return found


def _people_values(root: Path) -> tuple[_PeopleValue, ...]:
    folder = root / "Memory" / "People"
    if not folder.is_dir():
        raise EgressError("workspace is missing Memory/People")
    values: set[tuple[str, str]] = set()
    for path in sorted(folder.rglob("*.md")):
        relative_parts = path.relative_to(folder).parts
        if path.name.startswith(".") or any(
            part.startswith(".") for part in relative_parts[:-1]
        ):
            continue
        current = folder
        for part in relative_parts:
            current /= part
            if _is_reparse_path(current):
                raise EgressError("Memory/People must not contain symbolic links")
        if not path.is_file():
            continue
        try:
            text = path.read_bytes().decode("utf-8", errors="strict")
            data, _body = records.parse_record(text)
        except (OSError, UnicodeError, ValueError, records.yaml.YAMLError) as error:
            raise EgressError(
                "Memory/People contains an unreadable or invalid record"
            ) from error
        problems = records.validate("person", data, filename=path.name)
        if problems:
            raise EgressError("Memory/People contains a record that does not match its schema")
        name = data["name"]
        if isinstance(name, str) and name:
            values.add(("person-name", name))
        for kind, pattern in labeler._PATTERNS:
            if kind != labeler.EMAIL:
                continue
            for match in pattern.finditer(text):
                values.add(("person-email", match.group(0)))
    return tuple(_PeopleValue(kind, value) for kind, value in sorted(values))


def _people_findings(
    file: _OutboundFile, people: Iterable[_PeopleValue]
) -> list[Finding]:
    found: list[Finding] = []
    for person in people:
        start = 0
        while True:
            offset = file.text.find(person.value, start)
            if offset < 0:
                break
            found.append(
                Finding(
                    file.relative.as_posix(),
                    "people",
                    person.kind,
                    _line_number(file.text, offset),
                )
            )
            start = offset + len(person.value)
    return found


def _replace_pattern(text: str, pattern: Any, placeholder: str) -> str:
    return pattern.sub(placeholder, text)


def _redacted_text(text: str, people: Iterable[_PeopleValue]) -> str:
    clean, _credential_findings = credentials.redact(text)
    for kind, pattern in labeler._PATTERNS:
        placeholder = f"[redacted-{kind.removeprefix('pii/')}]"
        clean = _replace_pattern(clean, pattern, placeholder)
    # Generic email redaction wins when the same value is also People-derived.
    # Longest-first prevents a shorter name from partially replacing a longer one.
    ordered = sorted(people, key=lambda item: (-len(item.value), item.kind, item.value))
    for person in ordered:
        placeholder = f"[redacted-{person.kind}]"
        clean = clean.replace(person.value, placeholder)
    return clean


def _redacted_relative(relative: Path) -> Path:
    return relative.with_name(f"{relative.stem}.redacted{relative.suffix}")


def _write_atomic(path: Path, content: bytes) -> None:
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise EgressError("redacted-copy destination is not a regular file")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".apparatus-egress-", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def _finding_counts(findings: Iterable[Finding]) -> dict[str, int]:
    counts = Counter(f"{finding.source}/{finding.kind}" for finding in findings)
    return {name: counts[name] for name in sorted(counts)}


def findings_summary(findings: Iterable[Finding]) -> str:
    """Render a stable value-free summary for conformance fixtures and receipts."""
    counts = _finding_counts(findings)
    if not counts:
        return "none\n"
    return "".join(f"{name}: {count}\n" for name, count in counts.items())


def _redaction_receipt_fields(findings: tuple[Finding, ...]) -> dict[str, Any]:
    credentials_only = tuple(
        finding for finding in findings if finding.source == "credential"
    )
    counts = Counter(finding.kind for finding in credentials_only)
    locations = [
        {"file": finding.file, "line": finding.line, "kind": finding.kind}
        for finding in credentials_only
    ]
    return {
        "summary": f"Credential floor replaced {len(credentials_only)} value(s).",
        "classes": sorted(counts),
        "counts": {name: counts[name] for name in sorted(counts)},
        "locations": locations,
        "body": "Credential classes and locations:\n"
        + "".join(
            f"- {item['file']}:{item['line']}: {item['kind']}\n"
            for item in locations
        ),
    }


def _egress_receipt_fields(
    files: tuple[_OutboundFile, ...],
    findings: tuple[Finding, ...],
    redacted_copies: tuple[str, ...],
    decision: str | None,
    outcome: str,
) -> dict[str, Any]:
    file_names = [item.relative.as_posix() for item in files]
    counts = _finding_counts(findings)
    details = "".join(
        f"- {finding.file}:{finding.line}: {finding.source}/{finding.kind}\n"
        for finding in findings
    ) or "- none\n"
    return {
        "summary": (
            f"Egress check found {len(findings)} sensitive item(s) "
            f"across {len(files)} file(s)."
        ),
        "files": file_names,
        "finding_counts": counts,
        "redacted_copies": list(redacted_copies),
        "decision": decision,
        "outcome": outcome,
        "body": (
            "Files checked:\n"
            + "".join(f"- {name}\n" for name in file_names)
            + "Destination: not provided to the check.\n"
            + "Findings:\n"
            + details
            + "Decision: "
            + (decision if decision is not None else "none")
            + "\nAnything left the workspace: no; this command only checks and records.\n"
        ),
    }


def _outcome(findings: tuple[Finding, ...], decision: str | None) -> str:
    if not findings:
        return "clean"
    if decision is None:
        return "decision-required"
    has_credentials = any(item.source == "credential" for item in findings)
    if decision == "send-original" and has_credentials:
        return "credential-original-refused"
    return decision


def check_egress(
    workspace: str | Path,
    files: Sequence[str | Path],
    *,
    decision: str | None = None,
    write: Callable[[str | Path, str, dict[str, Any]], Path] = write_receipt,
) -> EgressResult:
    """Inspect outbound files, write copies and receipts, and return the decision."""
    if decision is not None and decision not in DECISIONS:
        raise EgressError(f"decision must be one of {', '.join(DECISIONS)}")
    root = _workspace(workspace)
    outbound = _read_outbound_files(root, files)
    people = _people_values(root)
    findings = tuple(
        sorted(
            (
                finding
                for item in outbound
                for finding in (*_pattern_findings(item), *_people_findings(item, people))
            ),
            key=lambda item: (item.file, item.line, item.source, item.kind),
        )
    )

    copies: list[str] = []
    if findings:
        files_with_findings = {finding.file for finding in findings}
        for item in outbound:
            if item.relative.as_posix() not in files_with_findings:
                continue
            relative = _redacted_relative(item.relative)
            _write_atomic(root / relative, _redacted_text(item.text, people).encode("utf-8"))
            copies.append(relative.as_posix())

    redaction_receipt: Path | None = None
    if any(item.source == "credential" for item in findings):
        redaction_receipt = write(
            root, "redaction", _redaction_receipt_fields(findings)
        )
    outcome = _outcome(findings, decision)
    receipt = write(
        root,
        "egress",
        _egress_receipt_fields(outbound, findings, tuple(copies), decision, outcome),
    )
    return EgressResult(
        findings,
        tuple(copies),
        decision,
        outcome,
        receipt,
        redaction_receipt,
    )
