"""Shared writer for human-legible, collision-safe workspace receipts."""

from __future__ import annotations

import os
import secrets
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apparatus_core import records
from apparatus_core.fs_transactions import windows_publish_receipt


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _timestamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _filename(now: datetime, event: str, collision: int) -> str:
    stem = now.astimezone(timezone.utc).strftime("%Y-%m-%d-%H%M%S") + f"-{event}"
    suffix = "" if collision == 1 else f"-{collision}"
    return f"{stem}{suffix}.md"


def receipt_filename(now: datetime, event: str, collision: int = 1) -> str:
    """Return the canonical receipt filename for a prepared UTC instant."""
    if event not in records.RECEIPT_EVENTS:
        raise ValueError(f"unknown receipt event: {event!r}")
    if collision < 1:
        raise ValueError("receipt collision number must be positive")
    return _filename(now, event, collision)


def _render(event: str, timestamp: str, fields: Mapping[str, Any]) -> str:
    protected = {"schema", "event", "timestamp"}
    attempted_overrides = protected.intersection(fields)
    if attempted_overrides:
        names = ", ".join(sorted(attempted_overrides))
        raise ValueError(f"receipt fields cannot override protected fields: {names}")
    summary = fields.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("receipt fields must include a non-empty summary")
    frontmatter: dict[str, Any] = {
        "schema": records.SCHEMAS["receipt"].schema_id,
        "event": event,
        "timestamp": timestamp,
        "summary": summary,
    }
    frontmatter.update(
        (name, value)
        for name, value in fields.items()
        if name not in {"summary", "body"}
    )
    problems = records.validate("receipt", frontmatter)
    if problems:
        raise ValueError("invalid receipt fields: " + "; ".join(problems))
    body = fields.get("body", "")
    if not isinstance(body, str):
        raise ValueError("receipt body must be text")  # noqa: TRY004
    return (
        "---\n"
        + records.yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
        + "---\n"
        + body.rstrip()
        + "\n"
    )


def prepare_receipt(
    event: str,
    fields: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> tuple[datetime, bytes]:
    """Render one receipt for transaction-aware callers without publishing it."""
    if event not in records.RECEIPT_EVENTS:
        raise ValueError(f"unknown receipt event: {event!r}")
    instant = _utcnow() if now is None else now.astimezone(timezone.utc).replace(
        microsecond=0
    )
    return instant, _render(event, _timestamp(instant), fields).encode("utf-8")


def _directory_flags() -> int:
    required = (os.open, os.mkdir, os.link, os.unlink)
    if (
        not hasattr(os, "O_DIRECTORY")
        or not hasattr(os, "O_NOFOLLOW")
        or any(function not in os.supports_dir_fd for function in required)
    ):
        raise OSError("safe descriptor-relative receipt operations are unavailable")
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _open_directory(parent: int, name: str, *, create: bool) -> tuple[int, bool]:
    try:
        return os.open(name, _directory_flags(), dir_fd=parent), False
    except FileNotFoundError:
        if not create:
            raise
    created = False
    try:
        os.mkdir(name, 0o700, dir_fd=parent)
        created = True
    except FileExistsError:
        pass
    return os.open(name, _directory_flags(), dir_fd=parent), created


def _write_complete(descriptor: int, content: bytes) -> None:
    view = memoryview(content)
    written = 0
    while written < len(view):
        count = os.write(descriptor, view[written:])
        if count <= 0:
            raise OSError("receipt content could not be written")
        written += count
    os.fsync(descriptor)


def _link_at(parent: int, source: str, target: str) -> None:
    os.link(
        source,
        target,
        src_dir_fd=parent,
        dst_dir_fd=parent,
        follow_symlinks=False,
    )


def _identity_at(parent: int, name: str) -> tuple[int, int, int]:
    status = os.stat(name, dir_fd=parent, follow_symlinks=False)
    return status.st_dev, status.st_ino, status.st_size


def _unlink_if_owned(parent: int, name: str, identity: tuple[int, int, int]) -> bool:
    try:
        if _identity_at(parent, name)[:2] != identity[:2]:
            return False
        os.unlink(name, dir_fd=parent)
        return True
    except FileNotFoundError:
        return False


def _published_is_owned(
    root: int,
    system: int,
    receipts: int,
    name: str,
    identity: tuple[int, int, int],
) -> bool:
    try:
        return (
            _directory_is_current(root, system, receipts)
            and _identity_at(receipts, name) == identity
        )
    except OSError:
        return False


def _directory_is_current(root: int, system: int, receipts: int) -> bool:
    current_system = current_receipts = -1
    try:
        current_system, _created = _open_directory(root, "System", create=False)
        if (os.fstat(current_system).st_dev, os.fstat(current_system).st_ino) != (
            os.fstat(system).st_dev,
            os.fstat(system).st_ino,
        ):
            return False
        current_receipts, _created = _open_directory(
            current_system, "receipts", create=False
        )
        return (
            os.fstat(current_receipts).st_dev,
            os.fstat(current_receipts).st_ino,
        ) == (
            os.fstat(receipts).st_dev,
            os.fstat(receipts).st_ino,
        )
    except OSError:
        return False
    finally:
        for descriptor in (current_receipts, current_system):
            if descriptor >= 0:
                os.close(descriptor)


def _publish_receipt(
    workspace: Path, event: str, now: datetime, content: bytes
) -> Path:
    if os.name == "nt":  # pragma: no cover - exercised by the Windows CI job
        return windows_publish_receipt(
            workspace,
            event,
            content,
            lambda collision: _filename(now, event, collision),
        )
    root = os.open(workspace, _directory_flags())
    system = receipts = -1
    temporary_name = f".apparatus-receipt-{secrets.token_hex(16)}.tmp"
    temporary_created = False
    temporary_identity: tuple[int, int, int] | None = None
    try:
        system, _system_created = _open_directory(root, "System", create=True)
        receipts, _receipts_created = _open_directory(system, "receipts", create=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        temporary = os.open(temporary_name, flags, 0o600, dir_fd=receipts)
        temporary_created = True
        temporary_status = os.fstat(temporary)
        temporary_identity = (
            temporary_status.st_dev,
            temporary_status.st_ino,
            temporary_status.st_size,
        )
        try:
            _write_complete(temporary, content)
            temporary_status = os.fstat(temporary)
            temporary_identity = (
                temporary_status.st_dev,
                temporary_status.st_ino,
                temporary_status.st_size,
            )
        finally:
            os.close(temporary)
        if not _directory_is_current(root, system, receipts):
            raise OSError("receipt destination changed during publication")
        for collision in range(1, 1_000_000):
            name = _filename(now, event, collision)
            try:
                _link_at(receipts, temporary_name, name)
            except FileExistsError:
                continue
            if temporary_identity is None or not _published_is_owned(
                root, system, receipts, name, temporary_identity
            ):
                if temporary_identity is not None:
                    _unlink_if_owned(receipts, name, temporary_identity)
                raise OSError("receipt destination changed during publication")
            try:
                if not _unlink_if_owned(receipts, temporary_name, temporary_identity):
                    raise OSError("receipt temporary changed during publication")
                temporary_created = False
            except OSError:
                # Both names are invocation-owned. Remove the published name
                # before reporting failure so no partial success is visible.
                try:
                    _unlink_if_owned(receipts, name, temporary_identity)
                finally:
                    if _unlink_if_owned(receipts, temporary_name, temporary_identity):
                        temporary_created = False
                raise
            if not _published_is_owned(
                root, system, receipts, name, temporary_identity
            ):
                raise OSError("receipt identity changed after publication")
            return workspace / "System" / "receipts" / name
        raise OSError("could not allocate a unique receipt filename")
    finally:
        if temporary_created and receipts >= 0 and temporary_identity is not None:
            _unlink_if_owned(receipts, temporary_name, temporary_identity)
        # Directory creation cannot be inseparably tied to the retained handle
        # on every supported platform. Leave empty directories after failure
        # rather than risk deleting a concurrently substituted entry.
        for descriptor in (receipts, system, root):
            if descriptor >= 0:
                os.close(descriptor)


def write_receipt(workspace: str | Path, event: str, fields: Mapping[str, Any]) -> Path:
    """Atomically publish one unique receipt and return its workspace path."""
    now, content = prepare_receipt(event, fields)
    workspace_path = Path(os.path.abspath(os.fspath(workspace)))
    try:
        if workspace_path.is_symlink() or not workspace_path.is_dir():
            raise OSError("workspace is not a safe directory")
        return _publish_receipt(workspace_path, event, now, content)
    except (NotImplementedError, TypeError) as error:
        raise OSError("safe receipt publication is unavailable") from error
