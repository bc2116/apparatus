"""The ``apparatus memory`` commands for safe durable Memory writes."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import stat
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apparatus_core import records
from apparatus_core.memory import MemoryReadError, RECORD_ROOTS, recall as recall_memory, record_path, read_record
from apparatus_core.credentials import RedactionFinding, redact
from apparatus_core.fs_transactions import (
    OwnedFile as _OwnedFile,
    ReplacementTransaction as _ReplacementTransaction,
    WorkspaceAnchor as _WorkspaceAnchor,
    WorkspaceIdentity as _Identity,
)
from apparatus_core.labeler import (
    Label,
    find_labels,
    refresh_frontmatter_labels,
    render_record,
    split_record_exact,
)
from apparatus_core.retention import (
    RetentionSuppressed,
    TaskContext,
    TaskRetentionError,
    context_for,
    operation,
)
from apparatus_core.receipts import (
    ReceiptPublication,
    prepare_receipt_invocation,
    write_receipt,
)


class MemoryCommandError(ValueError):
    """A Memory operation could not be prepared safely."""


@dataclass(frozen=True)
class _SweepChange:
    relative: Path
    original: bytes
    identity: _Identity
    replacement: bytes
    findings: tuple[RedactionFinding, ...]


def register(subparsers: Any) -> None:
    """Register the Memory verb through the shared entry-point path."""
    parser = subparsers.add_parser("memory", help="manage durable Memory records")
    actions = parser.add_subparsers(dest="memory_action")

    fact = actions.add_parser("add-fact", help="save one fact in Memory")
    fact.add_argument("workspace", metavar="WORKSPACE")
    fact.add_argument("--title", required=True, metavar="TEXT")
    _body_arguments(fact)
    fact.set_defaults(func=run, memory_action="add-fact")

    person = actions.add_parser("add-person", help="save one People record in Memory")
    person.add_argument("workspace", metavar="WORKSPACE")
    person.add_argument("--name", required=True, metavar="TEXT")
    person.add_argument("--role", metavar="TEXT")
    _body_arguments(person)
    person.set_defaults(func=run, memory_action="add-person")

    sweep = actions.add_parser(
        "label", help="refresh labels in existing Memory records"
    )
    sweep.add_argument("workspace", metavar="WORKSPACE")
    sweep.set_defaults(func=run, memory_action="label")

    for action in ("correct", "outdated", "forget"):
        command = actions.add_parser(action, help=f"{action} one existing Memory record")
        command.add_argument("workspace", metavar="WORKSPACE")
        command.add_argument("record", metavar="RECORD")
        if action == "correct":
            command.add_argument("--from-file", required=True, metavar="PATH",
                                 help="complete replacement record; omitted metadata is removed")
        command.set_defaults(func=run, memory_action=action)
    recall = actions.add_parser("recall", help="find current Memory records")
    recall.add_argument("workspace", metavar="WORKSPACE")
    recall.add_argument("query", metavar="QUERY")
    recall.add_argument("--limit", type=int, default=5)
    recall.set_defaults(func=run, memory_action="recall")


def _body_arguments(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--body", metavar="TEXT")
    source.add_argument("--from-file", metavar="PATH")


def _workspace(value: str) -> Path:
    requested = Path(value)
    if _is_reparse_path(requested):
        raise MemoryCommandError("workspace path must not be a symbolic link")
    if not requested.exists():
        raise MemoryCommandError("workspace path does not exist")
    if not requested.is_dir():
        raise MemoryCommandError("workspace path is not a directory")
    try:
        return requested.resolve(strict=True)
    except OSError as error:
        raise MemoryCommandError("workspace path could not be resolved") from error


def _privacy_mode(anchor: _WorkspaceAnchor) -> str:
    try:
        content, _identity_value = anchor.read_file("System/profile.yaml")
        data = records.yaml.safe_load(content.decode("utf-8"))
    except (OSError, UnicodeError, records.yaml.YAMLError) as error:
        raise MemoryCommandError(
            "System/profile.yaml is not valid UTF-8 YAML"
        ) from error
    if not isinstance(data, dict):
        raise MemoryCommandError("System/profile.yaml must be a YAML mapping")
    problems = records.validate("profile", data, filename="profile.yaml")
    if problems:
        raise MemoryCommandError(
            "System/profile.yaml does not match the profile schema"
        )
    return str(data["privacy_mode"])


def _body(args: argparse.Namespace) -> str:
    inline = getattr(args, "body", None)
    source_value = getattr(args, "from_file", None)
    if (inline is None) == (source_value is None):
        raise MemoryCommandError("provide exactly one of --body or --from-file")
    if inline is not None:
        return str(inline)
    source = Path(str(source_value))
    if _is_reparse_path(source):
        raise MemoryCommandError("input file must not be a symbolic link")
    if not source.is_file():
        raise MemoryCommandError("input file is not a regular file")
    try:
        return source.read_bytes().decode("utf-8", errors="strict")
    except (OSError, UnicodeError) as error:
        raise MemoryCommandError(
            "input file must be readable strict UTF-8 text"
        ) from error


def _is_reparse_path(path: Path) -> bool:
    """Reject POSIX symlinks and Windows junction/reparse-point inputs."""
    try:
        status = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISLNK(status.st_mode) or bool(
        getattr(status, "st_file_attributes", 0) & 0x400
    )


def _merge_findings(
    findings: Iterable[RedactionFinding],
) -> tuple[RedactionFinding, ...]:
    counts: Counter[str] = Counter()
    for finding in findings:
        counts[finding.credential_class] += finding.count
    return tuple(RedactionFinding(name, counts[name]) for name in sorted(counts))


def _merge_labels(labels: Iterable[Label]) -> tuple[Label, ...]:
    counts: Counter[str] = Counter()
    for label in labels:
        counts[label.name] += label.count
    order = ("pii/email", "pii/phone", "pii/address", "pii/id")
    return tuple(Label(name, counts[name]) for name in order if counts[name])


def _redact_strings(
    values: dict[str, str],
) -> tuple[dict[str, str], tuple[RedactionFinding, ...]]:
    cleaned: dict[str, str] = {}
    findings: list[RedactionFinding] = []
    for name, value in values.items():
        clean, found = redact(value)
        cleaned[name] = clean
        findings.extend(found)
    return cleaned, _merge_findings(findings)


def _labels_for(values: Iterable[str]) -> tuple[Label, ...]:
    return _merge_labels(label for value in values for label in find_labels(value))


def _slug(value: str, *, limit: int = 80) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.casefold()).strip("-")
    slug = re.sub(r"-+", "-", slug) or "memory-record"
    return slug[:limit].rstrip("-") or "memory-record"


def _candidate_name(stem: str, collision: int) -> str:
    suffix = "" if collision == 1 else f"-{collision}"
    bounded_stem = stem[: 80 - len(suffix)].rstrip("-") or "memory-record"
    return f"{bounded_stem}{suffix}.md"


def _receipt_fields(findings: tuple[RedactionFinding, ...]) -> dict[str, Any]:
    counts = {finding.credential_class: finding.count for finding in findings}
    total = sum(counts.values())
    details = "\n".join(f"- {name}: {counts[name]}" for name in sorted(counts))
    return {
        "summary": f"Credential floor replaced {total} value(s).",
        "classes": sorted(counts),
        "counts": counts,
        "body": "Credential classes and counts:\n" + details + "\n",
    }


ReceiptWriter = Callable[..., object]


def _write_owned_receipt(
    write: ReceiptWriter,
    workspace: Path,
    event: str,
    fields: dict[str, Any],
) -> ReceiptPublication:
    invocation = prepare_receipt_invocation(workspace, event, fields)
    value: object | None = None
    try:
        value = write(workspace, event, fields, invocation=invocation)
        if not isinstance(value, ReceiptPublication) or not value.is_bound_to(
            invocation
        ):
            if isinstance(value, ReceiptPublication) and value.is_from_invocation(
                invocation
            ):
                value.close()
            raise MemoryCommandError(
                "receipt writer did not return exact publication ownership"
            )
        value.claim(invocation)
        return value
    except Exception as error:
        if isinstance(value, ReceiptPublication) and value.is_from_invocation(
            invocation
        ):
            try:
                if value.claimed:
                    value.rollback()
            finally:
                value.close()
        invocation.close()
        if isinstance(error, MemoryCommandError):
            raise
        raise MemoryCommandError(
            "receipt writer did not return exact publication ownership"
        ) from error


def _remove_owned_receipts(
    receipts: Iterable[ReceiptPublication],
) -> None:
    failed = False
    for receipt in reversed(tuple(receipts)):
        try:
            receipt.rollback()
        except OSError:
            failed = True
        finally:
            receipt.close()
    if failed:
        raise MemoryCommandError("owned receipts changed before cleanup")


def _new_record(
    anchor: _WorkspaceAnchor,
    *,
    kind: str,
    metadata: dict[str, str],
    body: str,
    mode: str,
    write: ReceiptWriter,
    suffix_on_collision: bool = True,
    retain_ownership: bool = False,
    task_context: TaskContext | None = None,
) -> (
    tuple[Path, tuple[RedactionFinding, ...], tuple[Label, ...]]
    | tuple[Path, tuple[RedactionFinding, ...], tuple[Label, ...], _OwnedFile]
    | None
):
    context = task_context if task_context is not None else context_for(anchor.workspace)
    if context.workspace != anchor.workspace:
        raise TaskRetentionError("Task context cannot be used in another workspace.")
    context.require_memory_write()
    if not context.legacy:
        mode = "standard"
    cleaned, findings = _redact_strings({**metadata, "body": body})
    cleaned_body = cleaned.pop("body")
    labels = _labels_for((*cleaned.values(), cleaned_body))

    structural_person = kind == "person"
    if mode == "private" and (labels or structural_person):
        if labels:
            names = ", ".join(label.name for label in labels)
            print(
                f"Private mode did not save this Memory record. Labels found: {names}."
            )
        else:
            print(
                "Private mode did not save this People record because it contains person data."
            )
        return None

    if kind == "fact":
        relative_folder = "Memory/Facts"
        filename_value = cleaned["title"]
        frontmatter: dict[str, Any] = {
            "schema": records.SCHEMAS["fact"].schema_id,
            "title": cleaned["title"],
        }
    else:
        relative_folder = "Memory/People"
        filename_value = cleaned["name"]
        frontmatter = {
            "schema": records.SCHEMAS["person"].schema_id,
            "name": cleaned["name"],
        }
        if "role" in cleaned:
            frontmatter["role"] = cleaned["role"]
        if "organization" in cleaned:
            frontmatter["organization"] = cleaned["organization"]
    frontmatter = refresh_frontmatter_labels(frontmatter, labels)
    anchor.require_directory(relative_folder)
    stem = _slug(filename_value)
    for collision in range(1, 1_000_000):
        name = _candidate_name(stem, collision)
        problems = records.validate(kind, frontmatter, filename=name)
        if problems:
            raise MemoryCommandError(
                "generated Memory record does not match its schema"
            )
        relative = Path(relative_folder) / name
        content = render_record(frontmatter, cleaned_body).encode("utf-8")
        try:
            owned_record = anchor.create_file(relative, content)
        except FileExistsError:
            if not suffix_on_collision:
                return None
            continue
        owned_receipt: ReceiptPublication | None = None
        try:
            if findings:
                owned_receipt = _write_owned_receipt(
                    write,
                    anchor.workspace,
                    "redaction",
                    _receipt_fields(findings),
                )
                owned_receipt.commit()
        except Exception as operation_error:
            cleanup_failed = False
            if owned_receipt is not None:
                try:
                    owned_receipt.rollback()
                except OSError:
                    cleanup_failed = True
                finally:
                    owned_receipt.close()
            try:
                anchor.unlink_owned(owned_record)
            except (OSError, MemoryCommandError):
                cleanup_failed = True
            finally:
                owned_record.close()
            if cleanup_failed:
                raise MemoryCommandError(
                    "Memory write could not restore its prior state"
                ) from operation_error
            raise
        if owned_receipt is not None:
            owned_receipt.close()
        if retain_ownership:
            return relative, findings, labels, owned_record
        owned_record.close()
        return relative, findings, labels
    raise MemoryCommandError("could not allocate a safe Memory filename")


def _redact_value(
    value: Any,
) -> tuple[Any, tuple[RedactionFinding, ...], tuple[str, ...]]:
    if isinstance(value, str):
        clean, findings = redact(value)
        return clean, tuple(findings), (clean,)
    if isinstance(value, bytes):
        try:
            decoded = value.decode("utf-8", errors="strict")
        except UnicodeError as error:
            raise MemoryCommandError(
                "Memory record contains binary data that cannot be scanned safely"
            ) from error
        clean, findings = redact(decoded)
        return clean.encode("utf-8"), tuple(findings), (clean,)
    if isinstance(value, list):
        cleaned: list[Any] = []
        findings: list[RedactionFinding] = []
        strings: list[str] = []
        for item in value:
            clean, found, durable = _redact_value(item)
            cleaned.append(clean)
            findings.extend(found)
            strings.extend(durable)
        return cleaned, _merge_findings(findings), tuple(strings)
    if isinstance(value, set):
        cleaned_set: set[Any] = set()
        findings = []
        strings = []
        for item in sorted(value, key=repr):
            clean, found, durable = _redact_value(item)
            try:
                duplicate = clean in cleaned_set
            except TypeError as error:
                raise MemoryCommandError(
                    "Memory record set contains an unsupported value"
                ) from error
            if duplicate:
                raise MemoryCommandError(
                    "credential redaction would duplicate a set value"
                )
            cleaned_set.add(clean)
            findings.extend(found)
            strings.extend(durable)
        return cleaned_set, _merge_findings(findings), tuple(strings)
    if isinstance(value, dict):
        cleaned_dict: dict[Any, Any] = {}
        findings = []
        strings = []
        for key, item in value.items():
            clean_key, key_findings, key_strings = _redact_value(key)
            clean, found, durable = _redact_value(item)
            if clean_key in cleaned_dict:
                raise MemoryCommandError(
                    "credential redaction would duplicate a mapping key"
                )
            cleaned_dict[clean_key] = clean
            findings.extend(key_findings)
            findings.extend(found)
            strings.extend(key_strings)
            strings.extend(durable)
        return cleaned_dict, _merge_findings(findings), tuple(strings)
    if value is None or isinstance(value, (bool, int, float, dt.date, dt.datetime)):
        return value, (), ()
    raise MemoryCommandError("Memory record contains an unsupported YAML value")


def _plan_sweep_record(
    relative: Path, anchor: _WorkspaceAnchor, kind: str
) -> _SweepChange:
    try:
        original, identity_value = anchor.read_file(relative)
        text = original.decode("utf-8", errors="strict")
        data, body = split_record_exact(text)
    except (OSError, UnicodeError, ValueError, records.yaml.YAMLError) as error:
        raise MemoryCommandError(
            "Memory sweep found an unreadable or invalid record"
        ) from error

    existing_problems = records.validate(kind, data, filename=relative.name, body=body)
    if existing_problems:
        raise MemoryCommandError(
            "Memory sweep found a record that does not match its schema"
        )

    cleaned_data: dict[Any, Any] = {}
    findings: list[RedactionFinding] = []
    durable_strings: list[str] = []
    for key, value in data.items():
        clean_key, key_findings, key_strings = _redact_value(key)
        if key == "schema":
            clean, found, strings = (
                value,
                (),
                (value,) if isinstance(value, str) else (),
            )
        else:
            clean, found, strings = _redact_value(value)
        if clean_key in cleaned_data:
            raise MemoryCommandError(
                "credential redaction would duplicate a frontmatter key"
            )
        cleaned_data[clean_key] = clean
        findings.extend(key_findings)
        findings.extend(found)
        durable_strings.extend(key_strings)
        durable_strings.extend(strings)
    cleaned_body, body_findings = redact(body)
    findings.extend(body_findings)
    durable_strings.append(cleaned_body)
    merged_findings = _merge_findings(findings)
    labels = _labels_for(durable_strings)
    refreshed = refresh_frontmatter_labels(cleaned_data, labels)
    problems = records.validate(kind, refreshed, filename=relative.name)
    if problems:
        raise MemoryCommandError("Memory sweep would produce an invalid record")
    replacement = render_record(refreshed, cleaned_body).encode("utf-8")
    if refreshed == data and cleaned_body == body:
        replacement = original
    return _SweepChange(
        relative, original, identity_value, replacement, merged_findings
    )


def _sweep(
    anchor: _WorkspaceAnchor,
    write: ReceiptWriter,
) -> tuple[int, int]:
    plans = [
        _plan_sweep_record(path, anchor, kind)
        for folder, kind in RECORD_ROOTS
        if kind != "decision" or anchor.directory_exists(folder)
        for path in anchor.list_memory_records(folder)
    ]
    return len(plans), _apply_changes(anchor, plans, write)


def _apply_changes(
    anchor: _WorkspaceAnchor, plans: list[_SweepChange], write: ReceiptWriter
) -> int:
    changed = [plan for plan in plans if plan.replacement != plan.original]
    unchanged = [plan for plan in plans if plan.replacement == plan.original]

    def validate_unchanged() -> None:
        for plan in unchanged:
            content, identity = anchor.read_file(plan.relative)
            if content != plan.original or identity != plan.identity:
                raise MemoryCommandError("Memory record changed before completion")

    applied: list[tuple[_SweepChange, _ReplacementTransaction]] = []
    owned_receipts: list[ReceiptPublication] = []
    commit_phase = False
    try:
        validate_unchanged()
        for plan in changed:
            transaction = anchor.replace_if_unchanged(
                plan.relative,
                plan.identity,
                plan.original,
                plan.replacement,
            )
            applied.append((plan, transaction))
            if plan.findings:
                owned_receipts.append(
                    _write_owned_receipt(
                        write,
                        anchor.workspace,
                        "redaction",
                        _receipt_fields(plan.findings),
                    )
                )
        # Validate every transaction before any backup is discarded. A later
        # validation failure can therefore still roll the complete sweep back.
        for _plan, transaction in applied:
            transaction.validate_commit()
        for receipt in owned_receipts:
            receipt.validate()
        # No-op plans need the same final preimage proof as replacements.
        validate_unchanged()
        for receipt in owned_receipts:
            receipt.commit()
        commit_phase = True
        for _plan, transaction in applied:
            transaction.commit()
    except Exception as operation_error:
        if commit_phase:
            # Every replacement and required receipt was durable before the
            # commit point. A backup-cleanup failure must not remove receipts
            # or partially roll records back. Destroy any still-owned raw
            # backups before closing handles and reporting it.
            backup_cleanup_failed = False
            for _plan, transaction in applied:
                try:
                    transaction.discard_backup()
                except (OSError, MemoryCommandError):
                    backup_cleanup_failed = True
                transaction.close()
            for receipt in owned_receipts:
                receipt.close()
            if backup_cleanup_failed:
                raise MemoryCommandError(
                    "Memory sweep could not remove its protected backup"
                ) from operation_error
            raise MemoryCommandError(
                "Memory sweep completed but cleanup could not finish safely"
            ) from operation_error
        rollback_failed = False
        try:
            _remove_owned_receipts(owned_receipts)
        except (OSError, MemoryCommandError):
            rollback_failed = True
        for _plan, transaction in reversed(applied):
            try:
                transaction.rollback()
            except (OSError, MemoryCommandError):
                rollback_failed = True
                # Preserve the concurrent target, but do not leave an owned
                # prior-content backup behind after a failed correction/forget.
                try:
                    transaction.discard_backup()
                except OSError:
                    pass
            finally:
                transaction.close()
        if rollback_failed:
            raise MemoryCommandError(
                "Memory sweep could not restore its prior state"
            ) from operation_error
        raise
    for _plan, transaction in applied:
        transaction.close()
    for receipt in owned_receipts:
        receipt.close()
    return len(changed)


def _lifecycle(anchor: _WorkspaceAnchor, args: argparse.Namespace,
               mode: str, write: ReceiptWriter) -> int:
    context = context_for(anchor.workspace)
    if args.memory_action == "correct":
        context.require_memory_write()
    if not context.legacy:
        mode = "standard"
    relative, kind = record_path(args.record)
    original, identity, data, body = read_record(anchor, relative, kind)
    action = args.memory_action
    findings: tuple[RedactionFinding, ...] = ()
    if action == "forget":
        replacement = render_record(
            {"schema": records.SCHEMAS[kind].schema_id, "status": "forgotten"}, ""
        ).encode("utf-8")
    else:
        if action == "outdated" and data.get("status") == "forgotten":
            raise MemoryCommandError("forgotten Memory cannot be marked outdated")
        if action == "correct":
            source = Path(os.path.abspath(args.from_file))
            # Retain the input's parent chain too: no symlink/reparse traversal.
            with _WorkspaceAnchor(source.parent) as input_anchor:
                raw, _input_identity = input_anchor.read_file(source.name)
            try:
                data, body = split_record_exact(raw.decode("utf-8", errors="strict"))
            except (UnicodeError, ValueError, records.yaml.YAMLError) as error:
                raise MemoryCommandError("replacement must be a valid UTF-8 Markdown record") from error
            if records.validate(kind, data, filename=relative.name, body=body):
                raise MemoryCommandError("replacement must match the existing Memory kind and schema")
            data["status"] = "current"
        else:
            data["status"] = "outdated"
        cleaned, found, strings = _redact_value(data)
        clean_body, body_findings = redact(body)
        findings = _merge_findings((*found, *body_findings))
        labels = _labels_for((*strings, clean_body))
        if action == "correct" and mode == "private" and (kind == "person" or labels):
            print("Private mode did not save this correction because it contains personal data.")
            return 1
        cleaned = refresh_frontmatter_labels(cleaned, labels)
        if records.validate(kind, cleaned, filename=relative.name, body=clean_body):
            raise MemoryCommandError("Memory change would produce an invalid record")
        replacement = render_record(cleaned, clean_body).encode("utf-8")
    _apply_changes(anchor, [_SweepChange(relative, original, identity, replacement, findings)], write)
    print("Memory record forgotten." if action == "forget" else "Memory record updated.")
    return 0


def _run_anchored(
    anchor: _WorkspaceAnchor,
    args: argparse.Namespace,
    write: ReceiptWriter,
) -> int:
    context = context_for(anchor.workspace)
    action = getattr(args, "memory_action", None)
    if action in {"add-fact", "add-person", "correct"}:
        context.require_memory_write()
    mode = _privacy_mode(anchor) if context.legacy else "standard"
    if action == "recall":
        print(json.dumps(recall_memory(anchor, args.query, limit=args.limit), ensure_ascii=False))
        return 0
    if action in {"correct", "outdated", "forget"}:
        return _lifecycle(anchor, args, mode, write)
    if action == "label":
        examined, changed = _sweep(anchor, write)
        print(
            f"Memory labels refreshed: {examined} record(s) checked, {changed} changed."
        )
        return 0
    body = _body(args)
    if action == "add-fact":
        title = str(args.title)
        if not title.strip():
            raise MemoryCommandError("--title must not be empty")
        result = _new_record(
            anchor,
            kind="fact",
            metadata={"title": title},
            body=body,
            mode=mode,
            write=write,
        )
    elif action == "add-person":
        name = str(args.name)
        if not name.strip():
            raise MemoryCommandError("--name must not be empty")
        metadata = {"name": name}
        role = getattr(args, "role", None)
        if role is not None:
            metadata["role"] = str(role)
        result = _new_record(
            anchor,
            kind="person",
            metadata=metadata,
            body=body,
            mode=mode,
            write=write,
        )
    else:
        raise MemoryCommandError("choose add-fact, add-person, or label")
    if result is None:
        return 1
    _target, findings, _labels = result
    print("Memory record saved.")
    if findings:
        total = sum(finding.count for finding in findings)
        classes = ", ".join(finding.credential_class for finding in findings)
        print(f"Credential floor replaced {total} value(s): {classes}.")
    return 0


def run(
    args: argparse.Namespace,
    *,
    write: ReceiptWriter = write_receipt,
    task_id: str | None = None,
) -> int:
    """Run one Memory subcommand with privacy-safe, calm output."""
    try:
        workspace = _workspace(args.workspace)
        with operation(workspace, task_id=task_id if task_id is not None else getattr(args, "task", None)):
            with _WorkspaceAnchor(workspace) as anchor:
                return _run_anchored(anchor, args, write)
    except RetentionSuppressed:
        print("Memory write skipped: this task does not save to Memory.")
        return 1
    except (MemoryCommandError, MemoryReadError, TaskRetentionError) as error:
        print(f"memory: {error}")
        return 2
    except Exception:  # noqa: BLE001 - CLI boundary sanitizes environment-specific failures
        print("memory: could not complete the Memory operation safely")
        return 2
