"""Shared writer for human-legible, collision-safe workspace receipts."""

from __future__ import annotations

import os
import secrets
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from apparatus_core import records
from apparatus_core.fs_transactions import (
    WorkspaceAnchor,
    exchange_names,
    windows_publish_receipt,
)


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


_INVOCATION_SEAL = object()


class ReceiptInvocation:
    """Opaque one-use intent for one exact rendered receipt publication."""

    __slots__ = (
        "_workspace",
        "_event",
        "_instant",
        "_content",
        "_content_digest",
        "_anchor",
        "_lock",
        "_state",
        "_publication_token",
        "_claimed",
    )

    def __init__(
        self,
        workspace: Path,
        event: str,
        instant: datetime,
        content: bytes,
        seal: object,
    ):
        if seal is not _INVOCATION_SEAL:
            raise TypeError(
                "receipt invocations are created by prepare_receipt_invocation"
            )
        anchor = WorkspaceAnchor(workspace)
        self._workspace = workspace
        self._event = event
        self._instant = instant
        self._content = content
        self._content_digest = sha256(content).digest()
        self._anchor = anchor
        self._lock = threading.Lock()
        self._state = "prepared"
        self._publication_token: object | None = None
        self._claimed = False

    def _consume(
        self,
        workspace: Path,
        event: str,
        fields: Mapping[str, Any],
        seal: object,
    ) -> tuple[bytes, object]:
        if seal is not _INVOCATION_SEAL:
            raise TypeError("receipt invocation cannot be consumed here")
        with self._lock:
            if self._state != "prepared":
                raise OSError("receipt invocation freshness was already consumed")
            try:
                _instant, rendered = prepare_receipt(
                    event, fields, now=self._instant
                )
            except Exception:
                self._state = "closed"
                self._anchor.close()
                raise
            if (
                workspace != self._workspace
                or event != self._event
                or sha256(rendered).digest() != self._content_digest
                or rendered != self._content
                or not self._anchor.root_is_current()
            ):
                self._state = "closed"
                self._anchor.close()
                raise OSError(
                    "receipt invocation does not match the requested receipt"
                )
            token = object()
            self._publication_token = token
            self._state = "consumed"
            return self._content, token

    def _claim(self, token: object, seal: object) -> None:
        if seal is not _INVOCATION_SEAL:
            raise TypeError("receipt invocation cannot be claimed here")
        with self._lock:
            if self._state != "consumed" or token is not self._publication_token:
                raise OSError("receipt invocation was not published here")
            if self._claimed:
                raise OSError("receipt invocation was already claimed")
            self._claimed = True

    def _matches_publication(self, handle: Any, token: object) -> bool:
        with self._lock:
            return (
                self._state == "consumed"
                and token is self._publication_token
                and self._anchor.matches_root_handle(handle.root)
                and handle.workspace == self._workspace
                and handle.event == self._event
                and sha256(handle.content).digest() == self._content_digest
                and handle.content == self._content
            )

    def _close(self, token: object | None = None) -> None:
        anchor_to_close = None
        with self._lock:
            if self._state == "closed":
                return
            if token is not None and token is not self._publication_token:
                return
            self._state = "closed"
            anchor_to_close = self._anchor
        anchor_to_close.close()

    def close(self) -> None:
        """Release an unused invocation's retained workspace anchor."""
        self._close()


def prepare_receipt_invocation(
    workspace: str | Path,
    event: str,
    fields: Mapping[str, Any],
) -> ReceiptInvocation:
    """Prepare one fresh intent bound to exact rendered receipt bytes."""
    instant, content = prepare_receipt(event, fields)
    workspace_path = Path(os.path.abspath(os.fspath(workspace)))
    return ReceiptInvocation(
        workspace_path,
        event,
        instant,
        content,
        _INVOCATION_SEAL,
    )


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


def _read_descriptor(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    offset = 0
    while True:
        chunk = os.pread(descriptor, 1_048_576, offset)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        offset += len(chunk)


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


@dataclass
class _PosixReceiptPublication:
    workspace: Path
    path: Path
    event: str
    content: bytes
    identity: tuple[int, int, int]
    root: int
    system: int
    receipts: int
    descriptor: int
    name: str
    ownership_name: str
    prior_names: frozenset[str]
    ownership_link: bool = True

    def _descriptor_is_exact(self) -> bool:
        before = os.fstat(self.descriptor)
        current = _read_descriptor(self.descriptor)
        after = os.fstat(self.descriptor)
        return (
            (before.st_dev, before.st_ino, before.st_size) == self.identity
            and (after.st_dev, after.st_ino, after.st_size) == self.identity
            and current == self.content
        )

    def _name_is_exact(self, name: str) -> bool:
        try:
            return _identity_at(self.receipts, name) == self.identity
        except OSError:
            return False

    def validate(self) -> None:
        if min(self.root, self.system, self.receipts, self.descriptor) < 0:
            raise OSError("receipt publication proof is no longer active")
        if (
            not _directory_is_current(self.root, self.system, self.receipts)
            or not self._descriptor_is_exact()
            or not self._name_is_exact(self.name)
            or (self.ownership_link and not self._name_is_exact(self.ownership_name))
        ):
            raise OSError("receipt publication proof changed")

    def commit(self) -> None:
        self.validate()
        if self.ownership_link:
            if not _unlink_if_owned(
                self.receipts, self.ownership_name, self.identity
            ):
                raise OSError("receipt ownership link changed before commit")
            self.ownership_link = False
        if not self._name_is_exact(self.name) or not self._descriptor_is_exact():
            raise OSError("receipt publication changed during commit")

    def rollback(self) -> None:
        if min(self.root, self.system, self.receipts, self.descriptor) < 0:
            raise OSError("receipt publication proof is no longer active")
        if not _directory_is_current(self.root, self.system, self.receipts):
            raise OSError("receipt publication parent changed")
        if not self._descriptor_is_exact():
            raise OSError("receipt publication changed before rollback")
        prior_aliases = [
            candidate
            for candidate in os.listdir(self.receipts)
            if candidate in self.prior_names and self._name_is_exact(candidate)
        ]
        if prior_aliases:
            if len(prior_aliases) != 1 or self._name_is_exact(self.name):
                raise OSError("receipt prior-name substitution is ambiguous")
            displaced_name = prior_aliases[0]
            exchange_names(self.receipts, self.name, displaced_name)
            if not self._name_is_exact(self.name) or self._name_is_exact(
                displaced_name
            ):
                exchange_names(self.receipts, self.name, displaced_name)
                raise OSError("receipt prior-name substitution changed")
        # Every pathname for this inode was created after ``prior_names`` was
        # captured unless a prior name was displaced; that case was restored
        # above. Delete only exact aliases at new names, then use the open
        # descriptor's link count to prove no late alias survived the scan.
        for candidate in os.listdir(self.receipts):
            if candidate in self.prior_names and self._name_is_exact(candidate):
                raise OSError("receipt prior-name substitution changed")
            if self._name_is_exact(candidate):
                if not _unlink_if_owned(self.receipts, candidate, self.identity):
                    raise OSError("receipt alias changed during rollback")
        if os.fstat(self.descriptor).st_nlink != 0:
            raise OSError("receipt aliases changed during rollback")
        self.ownership_link = False

    def close(self) -> None:
        for name in ("descriptor", "receipts", "system", "root"):
            descriptor = getattr(self, name)
            if descriptor >= 0:
                os.close(descriptor)
                setattr(self, name, -1)


_PUBLICATION_SEAL = object()


class ReceiptPublication:
    """Opaque, live proof that one exact receipt was newly published."""

    __slots__ = (
        "_handle",
        "_invocation",
        "_token",
        "_active",
        "_claimed",
        "_settlement",
        "_lock",
    )

    def __init__(
        self,
        handle: Any,
        invocation: ReceiptInvocation,
        token: object,
        seal: object,
    ):
        if seal is not _PUBLICATION_SEAL:
            raise TypeError("receipt publications are created by write_receipt")
        self._handle = handle
        self._invocation = invocation
        self._token = token
        self._active = True
        self._claimed = False
        self._settlement: str | None = None
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._handle.path

    @property
    def claimed(self) -> bool:
        with self._lock:
            return self._claimed

    @property
    def content_digest(self) -> str:
        return self._invocation._content_digest.hex()

    def is_bound_to(self, invocation: ReceiptInvocation) -> bool:
        """Return whether this proof came from the exact prepared invocation."""
        with self._lock:
            return self._active and self._invocation is invocation and (
                invocation._matches_publication(self._handle, self._token)
            )

    def is_from_invocation(self, invocation: ReceiptInvocation) -> bool:
        """Return whether this proof was created for ``invocation``."""
        with self._lock:
            return self._invocation is invocation

    def claim(self, invocation: ReceiptInvocation) -> None:
        with self._lock:
            if not self._active:
                raise OSError("receipt publication proof is no longer active")
            if self._claimed:
                raise OSError("receipt publication proof was already claimed")
            if self._invocation is not invocation or not invocation._matches_publication(
                self._handle, self._token
            ):
                raise OSError("receipt publication belongs to another invocation")
            self._handle.validate()
            invocation._claim(self._token, _INVOCATION_SEAL)
            self._claimed = True

    def validate(self) -> None:
        with self._lock:
            if not self._active:
                raise OSError("receipt publication proof is no longer active")
            self._handle.validate()

    def commit(self) -> None:
        with self._lock:
            if not self._active:
                raise OSError("receipt publication proof is no longer active")
            if not self._claimed:
                raise OSError("receipt publication proof was not claimed")
            if self._settlement is not None:
                raise OSError("receipt publication was already settled")
            self._handle.commit()
            self._settlement = "committed"

    def rollback(self) -> None:
        with self._lock:
            if not self._active:
                raise OSError("receipt publication proof is no longer active")
            if not self._claimed:
                raise OSError("receipt publication proof was not claimed")
            if self._settlement == "rolled-back":
                raise OSError("receipt publication was already settled")
            self._handle.rollback()
            self._settlement = "rolled-back"

    def _discard_unclaimed(self) -> None:
        """Remove this writer's exact publication during sealed setup failure."""
        with self._lock:
            if (
                not self._active
                or self._claimed
                or self._settlement == "discarded"
            ):
                return
            self._handle.rollback()
            self._settlement = "discarded"

    def close(self) -> None:
        with self._lock:
            if not self._active:
                return
            try:
                if self._settlement is None:
                    self._handle.rollback()
            finally:
                try:
                    self._handle.close()
                finally:
                    self._invocation._close(self._token)
                    self._active = False


def _publish_receipt_handle(
    workspace: Path, event: str, now: datetime, content: bytes
) -> Any:
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
    publication_descriptor = -1
    try:
        system, _system_created = _open_directory(root, "System", create=True)
        receipts, _receipts_created = _open_directory(system, "receipts", create=True)
        prior_names = frozenset(os.listdir(receipts))
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
            if not _published_is_owned(
                root, system, receipts, name, temporary_identity
            ):
                raise OSError("receipt identity changed after publication")
            publication_descriptor = os.open(
                name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=receipts
            )
            handle = _PosixReceiptPublication(
                workspace,
                workspace / "System" / "receipts" / name,
                event,
                content,
                temporary_identity,
                root,
                system,
                receipts,
                publication_descriptor,
                name,
                temporary_name,
                prior_names,
            )
            handle.validate()
            publication_descriptor = -1
            temporary_created = False
            root = system = receipts = -1
            return handle
        raise OSError("could not allocate a unique receipt filename")
    finally:
        if publication_descriptor >= 0:
            os.close(publication_descriptor)
        if temporary_created and receipts >= 0 and temporary_identity is not None:
            _unlink_if_owned(receipts, temporary_name, temporary_identity)
        # Directory creation cannot be inseparably tied to the retained handle
        # on every supported platform. Leave empty directories after failure
        # rather than risk deleting a concurrently substituted entry.
        for descriptor in (receipts, system, root):
            if descriptor >= 0:
                os.close(descriptor)


def write_receipt(
    workspace: str | Path,
    event: str,
    fields: Mapping[str, Any],
    *,
    invocation: ReceiptInvocation | None = None,
) -> ReceiptPublication:
    """Publish one receipt and return its invocation-bound ownership proof.

    Ordinary callers receive an already committed proof and retain the familiar
    durable-write behavior. Transactional callers prepare and pass an explicit
    invocation; their proof stays live until they commit or roll it back.
    """
    workspace_path = Path(os.path.abspath(os.fspath(workspace)))
    retained = invocation is not None
    prepared = invocation or prepare_receipt_invocation(
        workspace_path, event, fields
    )
    token: object | None = None
    publication: ReceiptPublication | None = None
    try:
        content, token = prepared._consume(
            workspace_path,
            event,
            fields,
            _INVOCATION_SEAL,
        )
        if workspace_path.is_symlink() or not workspace_path.is_dir():
            raise OSError("workspace is not a safe directory")
        publication = ReceiptPublication(
            _publish_receipt_handle(
                workspace_path,
                event,
                prepared._instant,
                content,
            ),
            prepared,
            token,
            _PUBLICATION_SEAL,
        )
        if not publication.is_bound_to(prepared):
            publication._discard_unclaimed()
            raise OSError("receipt workspace changed during publication")
        if retained:
            return publication
        try:
            publication.claim(prepared)
            publication.commit()
            return publication
        except Exception:
            try:
                publication.rollback()
            except OSError:
                pass
            raise
        finally:
            publication.close()
    except (NotImplementedError, TypeError) as error:
        if publication is not None:
            try:
                publication._discard_unclaimed()
            except OSError:
                pass
            publication.close()
        elif token is not None:
            prepared._close(token)
        raise OSError("safe receipt publication is unavailable") from error
    except Exception:
        if publication is not None:
            try:
                publication._discard_unclaimed()
            except OSError:
                pass
            publication.close()
        elif token is not None:
            prepared._close(token)
        raise
