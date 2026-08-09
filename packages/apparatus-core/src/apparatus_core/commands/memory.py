"""The ``apparatus memory`` commands for safe durable Memory writes."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import secrets
import stat
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apparatus_core import records
from apparatus_core.credentials import RedactionFinding, redact
from apparatus_core.fs_transactions import WindowsWorkspaceAnchor, exchange_names
from apparatus_core.labeler import (
    Label,
    find_labels,
    refresh_frontmatter_labels,
    render_record,
    split_record_exact,
)
from apparatus_core.receipts import write_receipt


class MemoryCommandError(ValueError):
    """A Memory operation could not be prepared safely."""


@dataclass(frozen=True)
class _SweepChange:
    relative: Path
    original: bytes
    identity: _Identity
    replacement: bytes
    findings: tuple[RedactionFinding, ...]


@dataclass(frozen=True)
class _Identity:
    device: int
    inode: int
    size: int
    modified_ns: int


@dataclass
class _OwnedFile:
    relative: Path
    parent: int
    name: str
    identity: _Identity
    content: bytes

    def close(self) -> None:
        if self.parent >= 0:
            os.close(self.parent)
            self.parent = -1


@dataclass
class _ReplacementTransaction:
    anchor: _WorkspaceAnchor
    target: _OwnedFile
    backup: _OwnedFile
    finished: bool = False

    def rollback(self) -> None:
        if self.finished:
            return
        if not self.anchor._matches(
            self.target.parent,
            self.target.name,
            self.target.identity,
            self.target.content,
        ) or not self.anchor._matches(
            self.backup.parent,
            self.backup.name,
            self.backup.identity,
            self.backup.content,
        ):
            raise MemoryCommandError("Memory replacement changed before rollback")
        exchange_names(self.target.parent, self.target.name, self.backup.name)
        if not self.anchor._matches(
            self.target.parent,
            self.target.name,
            self.backup.identity,
            self.backup.content,
        ):
            raise MemoryCommandError(
                "Memory replacement rollback could not be verified"
            )
        self.anchor._unlink_at_owned(
            self.backup.parent,
            self.backup.name,
            self.target.identity,
            self.target.content,
        )
        self.finished = True

    def commit(self) -> None:
        if self.finished:
            return
        self.validate_commit()
        self.discard_backup()

    def discard_backup(self) -> None:
        """Remove this transaction's exact-owned pre-floor backup."""
        if self.finished:
            return
        self.anchor._unlink_at_owned(
            self.backup.parent,
            self.backup.name,
            self.backup.identity,
            self.backup.content,
        )
        self.finished = True

    def validate_commit(self) -> None:
        """Prove this transaction can commit without discarding rollback state."""
        if self.finished:
            return
        if not self.anchor._matches(
            self.target.parent,
            self.target.name,
            self.target.identity,
            self.target.content,
        ) or not self.anchor._matches(
            self.backup.parent,
            self.backup.name,
            self.backup.identity,
            self.backup.content,
        ):
            raise MemoryCommandError("Memory replacement changed before completion")
        if not self.anchor._parent_is_current(self.target.relative, self.target.parent):
            raise MemoryCommandError("Memory destination detached before completion")

    def close(self) -> None:
        self.target.close()
        self.backup.close()


def _directory_flags() -> int:
    if (
        not hasattr(os, "O_DIRECTORY")
        or not hasattr(os, "O_NOFOLLOW")
        or os.open not in os.supports_dir_fd
        or os.stat not in os.supports_dir_fd
        or os.unlink not in os.supports_dir_fd
    ):
        raise OSError("safe descriptor-relative workspace operations are unavailable")
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _identity(status: os.stat_result) -> _Identity:
    return _Identity(status.st_dev, status.st_ino, status.st_size, status.st_mtime_ns)


class _WorkspaceAnchor:
    """Workspace operations rooted at one no-follow directory descriptor."""

    def __init__(self, workspace: Path):
        try:
            self._root = os.open(workspace, _directory_flags())
        except (OSError, NotImplementedError, TypeError) as error:
            raise MemoryCommandError(
                "workspace containment could not be anchored"
            ) from error
        self.workspace = workspace

    def close(self) -> None:
        if self._root >= 0:
            os.close(self._root)
            self._root = -1

    def __enter__(self) -> _WorkspaceAnchor:  # noqa: PYI034
        return self

    def __exit__(self, _kind: object, _value: object, _traceback: object) -> None:
        self.close()

    @staticmethod
    def _parts(relative: str | Path) -> tuple[str, ...]:
        path = Path(relative)
        if (
            path.is_absolute()
            or not path.parts
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise MemoryCommandError("workspace operation path is not safely relative")
        return path.parts

    def _parent(self, relative: str | Path) -> tuple[int, str]:
        parts = self._parts(relative)
        current = os.dup(self._root)
        try:
            for part in parts[:-1]:
                following = os.open(part, _directory_flags(), dir_fd=current)
                os.close(current)
                current = following
            return current, parts[-1]
        except Exception:
            os.close(current)
            raise

    def open_directory(self, relative: str | Path) -> int:
        parent, name = self._parent(relative)
        try:
            return os.open(name, _directory_flags(), dir_fd=parent)
        finally:
            os.close(parent)

    def require_directory(self, relative: str | Path) -> None:
        descriptor = self.open_directory(relative)
        os.close(descriptor)

    @staticmethod
    def _read_at(parent: int, name: str) -> tuple[bytes, _Identity]:
        descriptor = os.open(
            name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent
        )
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise MemoryCommandError("workspace file is not a regular file")
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 65_536)
                if not chunk:
                    break
                chunks.append(chunk)
            after = os.fstat(descriptor)
            if _identity(before) != _identity(after):
                raise MemoryCommandError("workspace file changed while it was read")
            content = b"".join(chunks)
            if len(content) != after.st_size:
                raise MemoryCommandError("workspace file changed while it was read")
            return content, _identity(after)
        finally:
            os.close(descriptor)

    def read_file(self, relative: str | Path) -> tuple[bytes, _Identity]:
        parent, name = self._parent(relative)
        try:
            return self._read_at(parent, name)
        finally:
            os.close(parent)

    @staticmethod
    def _write_at(parent: int, name: str, content: bytes, mode: int) -> _Identity:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(name, flags, mode, dir_fd=parent)
        opened_identity: _Identity | None = None
        try:
            opened_identity = _identity(os.fstat(descriptor))
            view = memoryview(content)
            written = 0
            while written < len(view):
                count = os.write(descriptor, view[written:])
                if count <= 0:
                    raise OSError("workspace content could not be written")
                written += count
            os.fsync(descriptor)
            return _identity(os.fstat(descriptor))
        except Exception:
            try:
                if opened_identity is not None:
                    current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                    if (current.st_dev, current.st_ino) == (
                        opened_identity.device,
                        opened_identity.inode,
                    ):
                        os.unlink(name, dir_fd=parent)
            except OSError:
                pass
            raise
        finally:
            os.close(descriptor)

    def create_file(
        self, relative: str | Path, content: bytes, mode: int = 0o600
    ) -> _OwnedFile:
        parent, name = self._parent(relative)
        try:
            identity_value = self._write_at(parent, name, content, mode)
            owned = _OwnedFile(Path(relative), parent, name, identity_value, content)
            if not self._parent_is_current(owned.relative, parent):
                self._unlink_at_owned(parent, name, identity_value, content)
                raise MemoryCommandError("Memory destination detached during creation")
            return owned
        except Exception:
            os.close(parent)
            raise

    def _matches(
        self, parent: int, name: str, identity: _Identity, content: bytes
    ) -> bool:
        try:
            current_content, current_identity = self._read_at(parent, name)
        except (FileNotFoundError, OSError, MemoryCommandError):
            return False
        return current_identity == identity and current_content == content

    def capture_file(self, relative: str | Path) -> _OwnedFile:
        parent, name = self._parent(relative)
        try:
            content, identity_value = self._read_at(parent, name)
            return _OwnedFile(Path(relative), parent, name, identity_value, content)
        except Exception:
            os.close(parent)
            raise

    def unlink_owned(self, owned: _OwnedFile) -> None:
        self._unlink_at_owned(owned.parent, owned.name, owned.identity, owned.content)

    def _unlink_at_owned(
        self,
        parent: int,
        name: str,
        identity_value: _Identity,
        content: bytes,
    ) -> None:
        if not self._matches(parent, name, identity_value, content):
            raise MemoryCommandError("owned workspace file changed before cleanup")
        os.unlink(name, dir_fd=parent)

    def _parent_is_current(self, relative: str | Path, parent: int) -> bool:
        current = -1
        try:
            current, _name = self._parent(relative)
            current_status = os.fstat(current)
            retained_status = os.fstat(parent)
            return (current_status.st_dev, current_status.st_ino) == (
                retained_status.st_dev,
                retained_status.st_ino,
            )
        except OSError:
            return False
        finally:
            if current >= 0:
                os.close(current)

    def replace_if_unchanged(
        self,
        relative: str | Path,
        expected_identity: _Identity,
        expected_content: bytes,
        replacement: bytes,
    ) -> _ReplacementTransaction:
        parent, name = self._parent(relative)
        return self._replace_at(
            Path(relative),
            parent,
            name,
            expected_identity,
            expected_content,
            replacement,
        )

    def _replace_at(
        self,
        relative: Path,
        parent: int,
        name: str,
        expected_identity: _Identity,
        expected_content: bytes,
        replacement: bytes,
    ) -> _ReplacementTransaction:
        temporary = f".apparatus-memory-{secrets.token_hex(16)}.tmp"
        temporary_created = False
        keep_parent = False
        replacement_identity: _Identity | None = None
        try:
            if not self._parent_is_current(relative, parent):
                raise MemoryCommandError(
                    "Memory destination detached before replacement"
                )
            if not self._matches(parent, name, expected_identity, expected_content):
                raise MemoryCommandError("Memory record changed after sweep planning")
            status = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISREG(status.st_mode):
                raise MemoryCommandError("Memory record changed after sweep planning")
            mode = stat.S_IMODE(status.st_mode)
            replacement_identity = self._write_at(parent, temporary, replacement, mode)
            temporary_created = True
            if not self._matches(parent, name, expected_identity, expected_content):
                raise MemoryCommandError("Memory record changed after sweep planning")
            if not self._parent_is_current(relative, parent):
                raise MemoryCommandError(
                    "Memory destination detached before replacement"
                )
            exchange_names(parent, temporary, name)
            new_content, new_identity = self._read_at(parent, name)
            backup_content, backup_identity = self._read_at(parent, temporary)
            if (
                new_identity != replacement_identity
                or new_content != replacement
                or backup_identity != expected_identity
                or backup_content != expected_content
                or not self._parent_is_current(relative, parent)
            ):
                if new_identity == replacement_identity and new_content == replacement:
                    exchange_names(parent, temporary, name)
                raise MemoryCommandError(
                    "Memory record changed at conditional publication"
                )
            target = _OwnedFile(
                relative, parent, name, replacement_identity, replacement
            )
            backup = _OwnedFile(
                relative, os.dup(parent), temporary, backup_identity, backup_content
            )
            temporary_created = False
            keep_parent = True
            transaction = _ReplacementTransaction(self, target, backup)
            if not self._parent_is_current(relative, parent):
                transaction.rollback()
                transaction.close()
                raise MemoryCommandError(
                    "Memory destination detached after replacement"
                )
            return transaction
        finally:
            if temporary_created:
                try:
                    current_content, current_identity = self._read_at(parent, name)
                    backup_content, backup_identity = self._read_at(parent, temporary)
                    if (
                        replacement_identity is not None
                        and current_identity == replacement_identity
                        and current_content == replacement
                        and backup_identity == expected_identity
                        and backup_content == expected_content
                    ):
                        exchange_names(parent, temporary, name)
                except (OSError, MemoryCommandError):
                    pass
            if temporary_created:
                try:
                    if replacement_identity is not None:
                        self._unlink_at_owned(
                            parent, temporary, replacement_identity, replacement
                        )
                except (OSError, MemoryCommandError):
                    pass
            if not keep_parent:
                os.close(parent)

    def list_memory_records(self, relative: str | Path) -> list[Path]:
        root_relative = Path(relative)
        descriptor = self.open_directory(root_relative)
        found: list[Path] = []

        def inspect(current: int, current_relative: Path) -> None:
            for name in sorted(os.listdir(current)):
                if name.startswith("."):
                    continue
                status = os.stat(name, dir_fd=current, follow_symlinks=False)
                child_relative = current_relative / name
                if stat.S_ISLNK(status.st_mode):
                    raise MemoryCommandError("Memory sweep found a symbolic link")
                if stat.S_ISDIR(status.st_mode):
                    child = os.open(name, _directory_flags(), dir_fd=current)
                    try:
                        inspect(child, child_relative)
                    finally:
                        os.close(child)
                elif stat.S_ISREG(status.st_mode):
                    if name.endswith(".md"):
                        found.append(child_relative)
                else:
                    raise MemoryCommandError(
                        "Memory sweep found an unsupported file type"
                    )

        try:
            inspect(descriptor, root_relative)
        finally:
            os.close(descriptor)
        return found


if os.name == "nt":  # pragma: no cover - exercised by the Windows CI job
    _WorkspaceAnchor = WindowsWorkspaceAnchor  # type: ignore[misc,assignment]


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


def _capture_receipt(anchor: _WorkspaceAnchor, path: Path) -> _OwnedFile:
    try:
        relative = Path(path).relative_to(anchor.workspace)
    except ValueError as error:
        raise MemoryCommandError("receipt writer returned an unowned path") from error
    if relative.parent != Path("System/receipts"):
        raise MemoryCommandError("receipt writer returned an unowned path")
    return anchor.capture_file(relative)


def _remove_owned_receipts(
    anchor: _WorkspaceAnchor, receipts: Iterable[_OwnedFile]
) -> None:
    failed = False
    for receipt in reversed(tuple(receipts)):
        try:
            anchor.unlink_owned(receipt)
        except (OSError, MemoryCommandError):
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
    write: Callable[[str | Path, str, dict[str, Any]], Path],
) -> tuple[Path, tuple[RedactionFinding, ...], tuple[Label, ...]] | None:
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
            continue
        owned_receipt: _OwnedFile | None = None
        try:
            if findings:
                receipt_path = write(
                    anchor.workspace, "redaction", _receipt_fields(findings)
                )
                owned_receipt = _capture_receipt(anchor, receipt_path)
        except Exception as operation_error:
            cleanup_failed = False
            if owned_receipt is not None:
                try:
                    anchor.unlink_owned(owned_receipt)
                except (OSError, MemoryCommandError):
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

    existing_problems = records.validate(kind, data, filename=relative.name)
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
    write: Callable[[str | Path, str, dict[str, Any]], Path],
) -> tuple[int, int]:
    people = anchor.list_memory_records("Memory/People")
    facts = anchor.list_memory_records("Memory/Facts")
    plans = [
        *(_plan_sweep_record(path, anchor, "person") for path in people),
        *(_plan_sweep_record(path, anchor, "fact") for path in facts),
    ]
    changed = [plan for plan in plans if plan.replacement != plan.original]
    applied: list[tuple[_SweepChange, _ReplacementTransaction]] = []
    owned_receipts: list[_OwnedFile] = []
    commit_phase = False
    try:
        for plan in changed:
            transaction = anchor.replace_if_unchanged(
                plan.relative,
                plan.identity,
                plan.original,
                plan.replacement,
            )
            applied.append((plan, transaction))
            if plan.findings:
                receipt_path = write(
                    anchor.workspace, "redaction", _receipt_fields(plan.findings)
                )
                owned_receipts.append(_capture_receipt(anchor, receipt_path))
        # Validate every transaction before any backup is discarded. A later
        # validation failure can therefore still roll the complete sweep back.
        for _plan, transaction in applied:
            transaction.validate_commit()
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
            _remove_owned_receipts(anchor, owned_receipts)
        except (OSError, MemoryCommandError):
            rollback_failed = True
        for _plan, transaction in reversed(applied):
            try:
                transaction.rollback()
            except (OSError, MemoryCommandError):
                rollback_failed = True
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
    return len(plans), len(changed)


def _run_anchored(
    anchor: _WorkspaceAnchor,
    args: argparse.Namespace,
    write: Callable[[str | Path, str, dict[str, Any]], Path],
) -> int:
    mode = _privacy_mode(anchor)
    action = getattr(args, "memory_action", None)
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
    write: Callable[[str | Path, str, dict[str, Any]], Path] = write_receipt,
) -> int:
    """Run one Memory subcommand with privacy-safe, calm output."""
    try:
        workspace = _workspace(args.workspace)
        with _WorkspaceAnchor(workspace) as anchor:
            return _run_anchored(anchor, args, write)
    except MemoryCommandError as error:
        print(f"memory: {error}")
        return 2
    except Exception:  # noqa: BLE001 - CLI boundary sanitizes environment-specific failures
        print("memory: could not complete the Memory operation safely")
        return 2
