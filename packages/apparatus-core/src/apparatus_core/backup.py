"""One-way snapshot export support for workspace backups."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import os
import re
import stat
import zipfile
from typing import Any, BinaryIO

from apparatus_core.receipts import (
    ReceiptInvocation,
    ReceiptPublication,
    prepare_receipt_invocation,
    write_receipt,
)
from apparatus_core.snapshots import (
    SnapshotError,
    SnapshotTransientPath,
    SnapshotTransaction,
    git_available,
    prepare_snapshot,
)


_CHUNK_SIZE = 1024 * 1024
_MAX_COLLISIONS = 1_000_000
_RECEIPT_OWNERSHIP_NAME = re.compile(r"^\.apparatus-receipt-[0-9a-f]+\.tmp$")


class BackupError(RuntimeError):
    """A backup archive could not be written."""


class BackupUsageError(BackupError):
    """A workspace or destination argument is not safe to use."""


@dataclass(frozen=True)
class BackupResult:
    """Details of one completed one-way backup export."""

    archive: Path
    snapshot_id: str | None
    snapshots_available: bool
    size: int


def utc_archive_timestamp(clock: Callable[[], datetime] | None = None) -> str:
    """Return the UTC timestamp used in a backup archive filename."""
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    return now.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%d-%H%M%S")


def _absolute(path: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _zip_datetime(timestamp: float) -> tuple[int, int, int, int, int, int]:
    value = datetime.fromtimestamp(timestamp, timezone.utc).replace(microsecond=0)
    if value.year < 1980:
        value = datetime(1980, 1, 1, tzinfo=timezone.utc)
    elif value.year > 2107:
        value = datetime(2107, 12, 31, 23, 59, 58, tzinfo=timezone.utc)
    return value.year, value.month, value.day, value.hour, value.minute, value.second


def _zip_info(
    relative: Path, *, directory: bool, modified: float, executable: bool
) -> zipfile.ZipInfo:
    name = relative.as_posix() + ("/" if directory else "")
    info = zipfile.ZipInfo(name, _zip_datetime(modified))
    info.create_system = 3
    permissions = 0o755 if directory or executable else 0o644
    kind = stat.S_IFDIR if directory else stat.S_IFREG
    info.external_attr = ((kind | permissions) & 0xFFFF) << 16
    if directory:
        info.external_attr |= 0x10
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def _write_chunks(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    chunks: Iterator[bytes],
) -> None:
    with archive.open(info, mode="w", force_zip64=True) as member:
        for chunk in chunks:
            member.write(chunk)


def _identity(value: os.stat_result) -> tuple[int, int, int]:
    return value.st_dev, value.st_ino, stat.S_IFMT(value.st_mode)


def _stable_file_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, stat.S_IFMT(value.st_mode)


def _stable_directory_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_mtime_ns, stat.S_IFMT(value.st_mode)


def _consume_posix_transient(
    relative: Path,
    value: os.stat_result,
    remaining: set[SnapshotTransientPath],
) -> bool:
    match = next((item for item in remaining if item.relative == relative), None)
    if match is None:
        return False
    if not stat.S_ISREG(value.st_mode) or (value.st_dev, value.st_ino) != (
        match.device,
        match.inode,
    ):
        raise BackupError("Snapshot receipt ownership changed during backup export.")
    remaining.remove(match)
    return True


def _require_no_transients(remaining: set[SnapshotTransientPath]) -> None:
    if remaining:
        raise BackupError("Snapshot receipt ownership changed during backup export.")


def _config_uses_external_history(content: bytes) -> bool:
    """Recognize local configuration that can make history non-self-contained."""
    section = ""
    for raw_line in content.decode("utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and "]" in line:
            section = "".join(line[1 : line.index("]")].casefold().split())
            if section.startswith("include"):
                return True
            continue
        pieces = line.split("=", 1)
        key = "".join(pieces[0].casefold().split())
        value = pieces[1].strip().casefold() if len(pieces) == 2 else "true"
        if section == "core" and key == "worktree":
            return True
        if section == "core" and key == "bare" and value not in {"false", "no", "off", "0"}:
            return True
        if section == "extensions" and key in {"partialclone", "worktreeconfig"}:
            return True
        if section.startswith("remote") and key in {"promisor", "partialclonefilter"}:
            return True
        if "alternate" in key or section.startswith("odb"):
            return True
    return False


def _external_history_marker(relative: Path) -> bool:
    parts = tuple(part.casefold() for part in relative.parts)
    if not parts:
        return False
    if parts in {("commondir",), ("gitdir",), ("config.worktree",)}:
        return True
    if parts[0] in {"modules", "worktrees"}:
        return True
    if len(parts) >= 3 and parts[-3:] in {
        ("objects", "info", "alternates"),
        ("objects", "info", "http-alternates"),
    }:
        return True
    return "objects" in parts and parts[-1].endswith(".promisor")


def _posix_directory_flags() -> int:
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise OSError("safe directory handles are unavailable")
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _posix_file_flags() -> int:
    if not hasattr(os, "O_NOFOLLOW"):
        raise OSError("safe file handles are unavailable")
    return os.O_RDONLY | os.O_NOFOLLOW


class _PosixWorkspaceAnchor:
    def __init__(self, workspace: Path):
        self.path = workspace
        self.handle = -1
        self.root_identity: tuple[int, int, int] | None = None
        self.root_device = -1
        self.forbidden_identities: set[tuple[int, int, int]] = set()

    def __enter__(self) -> _PosixWorkspaceAnchor:
        try:
            self.handle = os.open(self.path, _posix_directory_flags())
            status = os.fstat(self.handle)
            if not stat.S_ISDIR(status.st_mode):
                raise OSError("workspace is not a directory")
            self.root_identity = _identity(status)
            self.root_device = status.st_dev
            self.require_path_current()
            return self
        except Exception:
            self.close()
            raise BackupUsageError("workspace path is not a safe directory") from None

    def __exit__(self, _kind: object, _value: object, _traceback: object) -> None:
        self.close()

    def close(self) -> None:
        if self.handle >= 0:
            os.close(self.handle)
            self.handle = -1

    def require_path_current(self) -> None:
        if self.root_identity is None:
            raise OSError("workspace anchor is not open")
        current = os.stat(self.path, follow_symlinks=False)
        if _identity(current) != self.root_identity or not stat.S_ISDIR(current.st_mode):
            raise BackupError("Workspace path changed during backup export.")

    def snapshot_storage(self) -> str:
        try:
            value = os.stat(".git", dir_fd=self.handle, follow_symlinks=False)
        except FileNotFoundError:
            return "missing"
        if stat.S_ISDIR(value.st_mode):
            return "standalone"
        if stat.S_ISREG(value.st_mode):
            return "external"
        return "unsafe"

    def validate_snapshot_history(self) -> None:
        """Reject external or nested history without opening external objects."""
        self._scan_for_history(self.handle, Path())

    def _scan_for_history(self, parent: int, relative: Path) -> None:
        try:
            names = os.listdir(parent)
        except OSError as error:
            raise BackupError("Workspace contents could not be read safely.") from error
        for name in names:
            child_relative = relative / name
            try:
                before = os.stat(name, dir_fd=parent, follow_symlinks=False)
                self._same_filesystem(before)
                if not stat.S_ISDIR(before.st_mode):
                    if name.casefold() == ".git":
                        raise BackupError(
                            "This workspace uses external snapshot storage and cannot be "
                            "backed up safely."
                        )
                    continue
                child = os.open(name, _posix_directory_flags(), dir_fd=parent)
                try:
                    opened = os.fstat(child)
                    if _identity(opened) != _identity(before):
                        raise BackupError("Workspace content changed during backup export.")
                    if name.casefold() == ".git":
                        if relative.parts:
                            raise BackupError(
                                "This workspace contains nested snapshot storage and cannot be "
                                "backed up safely."
                            )
                        self._validate_git_store(child, Path())
                    else:
                        self._scan_for_history(child, child_relative)
                finally:
                    os.close(child)
            except BackupError:
                raise
            except OSError as error:
                raise BackupError("Workspace contents could not be read safely.") from error

    def _validate_git_store(self, parent: int, relative: Path) -> None:
        try:
            names = os.listdir(parent)
        except OSError as error:
            raise BackupError("Workspace snapshot storage could not be inspected safely.") from error
        for name in names:
            child_relative = relative / name
            try:
                before = os.stat(name, dir_fd=parent, follow_symlinks=False)
                self._same_filesystem(before)
                if _external_history_marker(child_relative):
                    raise BackupError(
                        "This workspace uses external snapshot history and cannot be backed up "
                        "safely."
                    )
                if stat.S_ISDIR(before.st_mode):
                    child = os.open(name, _posix_directory_flags(), dir_fd=parent)
                    try:
                        opened = os.fstat(child)
                        if _identity(opened) != _identity(before):
                            raise BackupError("Workspace content changed during backup export.")
                        self._validate_git_store(child, child_relative)
                    finally:
                        os.close(child)
                elif stat.S_ISREG(before.st_mode):
                    if child_relative == Path("config"):
                        child = os.open(name, _posix_file_flags(), dir_fd=parent)
                        try:
                            opened = os.fstat(child)
                            if _identity(opened) != _identity(before) or opened.st_size > 1024 * 1024:
                                raise BackupError(
                                    "Workspace snapshot storage could not be inspected safely."
                                )
                            content = b"".join(self._file_chunks(child))
                            if _config_uses_external_history(content):
                                raise BackupError(
                                    "This workspace uses external snapshot history and cannot be "
                                    "backed up safely."
                                )
                        finally:
                            os.close(child)
                else:
                    raise BackupError("Workspace snapshot storage is not safe to archive.")
            except BackupError:
                raise
            except OSError as error:
                raise BackupError("Workspace snapshot storage could not be inspected safely.") from error

    def forbid(self, *identities: tuple[int, int, int]) -> None:
        self.forbidden_identities.update(identities)

    def cleanup_snapshot_transients(
        self,
        transient_paths: tuple[SnapshotTransientPath, ...],
    ) -> None:
        """Remove only exact POSIX ownership aliases retained by this export."""
        if not transient_paths:
            return
        expected = {(item.device, item.inode) for item in transient_paths}
        system = receipts = -1
        try:
            self.require_path_current()
            system = os.open("System", _posix_directory_flags(), dir_fd=self.handle)
            receipts = os.open("receipts", _posix_directory_flags(), dir_fd=system)
            for name in os.listdir(receipts):
                if not _RECEIPT_OWNERSHIP_NAME.fullmatch(name):
                    continue
                value = os.stat(name, dir_fd=receipts, follow_symlinks=False)
                if (value.st_dev, value.st_ino) in expected:
                    os.unlink(name, dir_fd=receipts)
            for name in os.listdir(receipts):
                if not _RECEIPT_OWNERSHIP_NAME.fullmatch(name):
                    continue
                value = os.stat(name, dir_fd=receipts, follow_symlinks=False)
                if (value.st_dev, value.st_ino) in expected:
                    raise BackupError(
                        "Snapshot receipt ownership could not be removed safely."
                    )
            self.require_path_current()
        except BackupError:
            raise
        except OSError as error:
            raise BackupError(
                "Snapshot receipt ownership could not be removed safely."
            ) from error
        finally:
            for descriptor in (receipts, system):
                if descriptor >= 0:
                    os.close(descriptor)

    def copy_snapshot_content(
        self,
        destination: Path,
        transient_paths: tuple[SnapshotTransientPath, ...] = (),
    ) -> None:
        """Copy identity-checked workspace bytes, excluding implementation history."""
        self.require_path_current()
        before = os.fstat(self.handle)
        remaining = set(transient_paths)
        self._copy_directory(self.handle, Path(), destination, remaining)
        _require_no_transients(remaining)
        if _stable_directory_identity(os.fstat(self.handle)) != _stable_directory_identity(before):
            raise BackupError("Workspace content changed during backup export.")
        self.require_path_current()

    def _copy_directory(
        self,
        parent: int,
        relative: Path,
        destination: Path,
        remaining: set[SnapshotTransientPath],
    ) -> None:
        try:
            names = sorted(os.listdir(parent))
        except OSError as error:
            raise BackupError("Workspace contents could not be read safely.") from error
        for name in names:
            if not relative.parts and name.casefold() == ".git":
                continue
            child_relative = relative / name
            target = destination / name
            try:
                before = os.stat(name, dir_fd=parent, follow_symlinks=False)
                self._same_filesystem(before)
                if stat.S_ISDIR(before.st_mode):
                    child = os.open(name, _posix_directory_flags(), dir_fd=parent)
                    try:
                        opened = os.fstat(child)
                        if _identity(opened) != _identity(before):
                            raise BackupError("Workspace content changed during backup export.")
                        target.mkdir()
                        self._copy_directory(child, child_relative, target, remaining)
                        if _stable_directory_identity(os.fstat(child)) != _stable_directory_identity(
                            opened
                        ):
                            raise BackupError("Workspace content changed during backup export.")
                    finally:
                        os.close(child)
                elif stat.S_ISREG(before.st_mode):
                    child = os.open(name, _posix_file_flags(), dir_fd=parent)
                    try:
                        opened = os.fstat(child)
                        if _identity(opened) != _identity(before):
                            raise BackupError("Workspace content changed during backup export.")
                        transient = _consume_posix_transient(
                            child_relative,
                            opened,
                            remaining,
                        )
                        if not transient:
                            with target.open("xb") as output:
                                for chunk in self._file_chunks(child):
                                    output.write(chunk)
                            target.chmod(0o755 if opened.st_mode & 0o111 else 0o644)
                        current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                        if _stable_file_identity(os.fstat(child)) != _stable_file_identity(opened):
                            raise BackupError("Workspace content changed during backup export.")
                        if _identity(current) != _identity(opened):
                            raise BackupError("Workspace content changed during backup export.")
                    finally:
                        os.close(child)
                else:
                    raise BackupError("Workspace contains an unsupported filesystem entry.")
            except BackupError:
                raise
            except OSError as error:
                raise BackupError("Workspace contents could not be read safely.") from error

    def write_entries(
        self,
        archive: zipfile.ZipFile,
        transient_paths: tuple[SnapshotTransientPath, ...] = (),
    ) -> None:
        self.require_path_current()
        before = os.fstat(self.handle)
        remaining = set(transient_paths)
        self._write_directory(archive, self.handle, Path(), remaining)
        _require_no_transients(remaining)
        if _stable_directory_identity(os.fstat(self.handle)) != _stable_directory_identity(before):
            raise BackupError("Workspace content changed during backup export.")
        self.require_path_current()

    def _same_filesystem(self, value: os.stat_result) -> None:
        if value.st_dev != self.root_device:
            raise BackupError("Workspace contains content outside its safe filesystem boundary.")
        if _identity(value) in self.forbidden_identities:
            raise BackupError("Destination moved into the workspace during backup export.")

    def _write_directory(
        self,
        archive: zipfile.ZipFile,
        parent: int,
        relative: Path,
        remaining: set[SnapshotTransientPath],
    ) -> None:
        try:
            names = sorted(os.listdir(parent))
        except OSError as error:
            raise BackupError("Workspace contents could not be read safely.") from error
        for name in names:
            child_relative = relative / name
            try:
                before = os.stat(name, dir_fd=parent, follow_symlinks=False)
                self._same_filesystem(before)
                if stat.S_ISDIR(before.st_mode):
                    child = os.open(name, _posix_directory_flags(), dir_fd=parent)
                    try:
                        opened = os.fstat(child)
                        if _identity(opened) != _identity(before):
                            raise BackupError("Workspace content changed during backup export.")
                        archive.writestr(
                            _zip_info(
                                child_relative,
                                directory=True,
                                modified=opened.st_mtime,
                                executable=True,
                            ),
                            b"",
                        )
                        self._write_directory(archive, child, child_relative, remaining)
                        after = os.fstat(child)
                        current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                        if (
                            _stable_directory_identity(after)
                            != _stable_directory_identity(opened)
                            or _identity(current) != _identity(opened)
                        ):
                            raise BackupError("Workspace content changed during backup export.")
                    finally:
                        os.close(child)
                elif stat.S_ISREG(before.st_mode):
                    if not relative.parts and name.casefold() == ".git":
                        raise BackupError(
                            "This workspace uses external snapshot storage and cannot be "
                            "backed up safely."
                        )
                    child = os.open(name, _posix_file_flags(), dir_fd=parent)
                    try:
                        opened = os.fstat(child)
                        if _identity(opened) != _identity(before):
                            raise BackupError("Workspace content changed during backup export.")
                        transient = _consume_posix_transient(
                            child_relative,
                            opened,
                            remaining,
                        )
                        if not transient:
                            _write_chunks(
                                archive,
                                _zip_info(
                                    child_relative,
                                    directory=False,
                                    modified=opened.st_mtime,
                                    executable=bool(opened.st_mode & 0o111),
                                ),
                                self._file_chunks(child),
                            )
                        after = os.fstat(child)
                        current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                        if (
                            _stable_file_identity(after) != _stable_file_identity(opened)
                            or _identity(current) != _identity(opened)
                        ):
                            raise BackupError("Workspace content changed during backup export.")
                    finally:
                        os.close(child)
                else:
                    raise BackupError("Workspace contains an unsupported filesystem entry.")
            except BackupError:
                raise
            except OSError as error:
                raise BackupError("Workspace contents could not be read safely.") from error

    @staticmethod
    def _file_chunks(handle: int) -> Iterator[bytes]:
        while True:
            chunk = os.read(handle, _CHUNK_SIZE)
            if not chunk:
                return
            yield chunk


class _PosixOwnedArchive:
    def __init__(self, destination: _PosixDestinationAnchor, name: str, handle: int):
        self.destination = destination
        self.name = name
        self.handle = handle
        self.identity = _identity(os.fstat(handle))

    def writer(self) -> BinaryIO:
        return os.fdopen(self.handle, "wb", closefd=False)

    def size(self) -> int:
        return os.fstat(self.handle).st_size

    def validate_name(self) -> None:
        if self.handle < 0:
            raise BackupError("Backup archive ownership is no longer retained.")
        try:
            retained = os.fstat(self.handle)
            current = os.stat(
                self.name,
                dir_fd=self.destination.handle,
                follow_symlinks=False,
            )
        except OSError as error:
            raise BackupError("Backup archive path changed during export.") from error
        if _identity(retained) != self.identity or _identity(current) != self.identity:
            raise BackupError("Backup archive path changed during export.")

    def finish(self) -> None:
        if self.handle >= 0:
            self.validate_name()
            os.close(self.handle)
            self.handle = -1

    def cleanup(self) -> None:
        if self.handle < 0:
            return
        cleanup_error: BackupError | None = None
        try:
            current = os.stat(self.name, dir_fd=self.destination.handle, follow_symlinks=False)
            if _identity(current) == self.identity:
                os.unlink(self.name, dir_fd=self.destination.handle)
        except FileNotFoundError:
            pass
        finally:
            retained = os.fstat(self.handle)
            os.close(self.handle)
            self.handle = -1
            if retained.st_nlink != 0:
                cleanup_error = BackupError(
                    "Owned backup archive changed path and could not be removed safely."
                )
        if cleanup_error is not None:
            raise cleanup_error


class _PosixDestinationAnchor:
    def __init__(self, destination: Path):
        self.path = destination
        self.handle = -1
        self.identity: tuple[int, int, int] | None = None

    def __enter__(self) -> _PosixDestinationAnchor:
        try:
            self.handle = os.open(self.path, _posix_directory_flags())
            status = os.fstat(self.handle)
            if not stat.S_ISDIR(status.st_mode):
                raise OSError("destination is not a directory")
            self.identity = _identity(status)
            self.require_path_current()
            return self
        except Exception:
            self.close()
            raise BackupUsageError(
                "destination path does not exist or is not a safe directory"
            ) from None

    def __exit__(self, _kind: object, _value: object, _traceback: object) -> None:
        self.close()

    def close(self) -> None:
        if self.handle >= 0:
            os.close(self.handle)
            self.handle = -1

    def require_path_current(self) -> None:
        if self.identity is None:
            raise OSError("destination anchor is not open")
        current = os.stat(self.path, follow_symlinks=False)
        if _identity(current) != self.identity or not stat.S_ISDIR(current.st_mode):
            raise BackupError("Destination path changed during backup export.")

    def require_outside(self, workspace: _PosixWorkspaceAnchor) -> None:
        current = os.dup(self.handle)
        try:
            while True:
                current_status = os.fstat(current)
                if _identity(current_status) == workspace.root_identity:
                    raise BackupUsageError("destination must be outside the workspace")
                parent = os.open("..", _posix_directory_flags(), dir_fd=current)
                parent_status = os.fstat(parent)
                if _identity(parent_status) == _identity(current_status):
                    os.close(parent)
                    return
                os.close(current)
                current = parent
        finally:
            os.close(current)

    def allocate(self, timestamp: str) -> _PosixOwnedArchive:
        stem = f"apparatus-backup-{timestamp}"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        for collision in range(1, _MAX_COLLISIONS):
            suffix = "" if collision == 1 else f"-{collision}"
            name = f"{stem}{suffix}.zip"
            try:
                handle = os.open(name, flags, 0o600, dir_fd=self.handle)
                return _PosixOwnedArchive(self, name, handle)
            except FileExistsError:
                continue
        raise BackupError("Could not choose a backup archive name.")

    def object_identity(self) -> tuple[int, int, int]:
        if self.identity is None:
            raise OSError("destination anchor is not open")
        return self.identity


if os.name == "nt":  # pragma: no cover - exercised by the Windows CI job
    import ctypes
    import msvcrt
    from ctypes import wintypes

    from apparatus_core import fs_transactions as _windows_fs

    _WINDOWS_EPOCH = 116444736000000000
    _FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400

    def _windows_final_path(handle: int) -> str:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetFinalPathNameByHandleW.argtypes = [
            wintypes.HANDLE,
            wintypes.LPWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        kernel.GetFinalPathNameByHandleW.restype = wintypes.DWORD
        length = kernel.GetFinalPathNameByHandleW(handle, None, 0, 0)
        if not length:
            raise OSError("filesystem path could not be anchored")
        buffer = ctypes.create_unicode_buffer(length + 1)
        written = kernel.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if not written or written >= len(buffer):
            raise OSError("filesystem path could not be anchored")
        return os.path.normcase(buffer.value.rstrip("\\/"))

    def _windows_modified(identity: Any) -> float:
        return max(0.0, (identity.modified - _WINDOWS_EPOCH) / 10_000_000)

    def _windows_chunks(handle: int) -> Iterator[bytes]:
        kernel = _windows_fs._win_kernel()
        while True:
            buffer = ctypes.create_string_buffer(_CHUNK_SIZE)
            read = wintypes.DWORD()
            if not kernel.ReadFile(handle, buffer, len(buffer), ctypes.byref(read), None):
                raise OSError("workspace file could not be read")
            if read.value == 0:
                return
            yield buffer.raw[: read.value]


class _WindowsWorkspaceAnchor:
    def __init__(self, workspace: Path):
        self.path = workspace
        self.handle = -1
        self.identity: Any = None
        self.final_path = ""
        self.forbidden_identities: set[tuple[int, int]] = set()

    def __enter__(self) -> _WindowsWorkspaceAnchor:
        if os.name != "nt":
            raise OSError("Windows filesystem handles are unavailable")
        try:
            self.handle = _windows_fs._win_open(self.path, directory=True)
            self.identity = _windows_fs._win_identity(self.handle)
            self.final_path = _windows_final_path(self.handle)
            self.require_path_current()
            return self
        except Exception:
            self.close()
            raise BackupUsageError("workspace path is not a safe directory") from None

    def __exit__(self, _kind: object, _value: object, _traceback: object) -> None:
        self.close()

    def close(self) -> None:
        if self.handle >= 0:
            _windows_fs._win_close(self.handle)
            self.handle = -1

    def require_path_current(self) -> None:
        if _windows_final_path(self.handle) != self.final_path:
            raise BackupError("Workspace path changed during backup export.")

    def snapshot_storage(self) -> str:
        path = self.path / ".git"
        try:
            value = path.lstat()
        except FileNotFoundError:
            return "missing"
        if getattr(value, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT:
            return "unsafe"
        if stat.S_ISDIR(value.st_mode):
            return "standalone"
        if stat.S_ISREG(value.st_mode):
            return "external"
        return "unsafe"

    def validate_snapshot_history(self) -> None:
        self._scan_for_history(self.path, Path())

    def _scan_for_history(self, parent_path: Path, relative: Path) -> None:
        try:
            names = os.listdir(parent_path)
        except OSError as error:
            raise BackupError("Workspace contents could not be read safely.") from error
        for name in names:
            path = parent_path / name
            child_relative = relative / name
            handle = -1
            try:
                value = path.lstat()
                if getattr(value, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT:
                    raise BackupError("Workspace contains an unsupported filesystem entry.")
                if name.casefold() == ".git" and not stat.S_ISDIR(value.st_mode):
                    raise BackupError(
                        "This workspace uses external snapshot storage and cannot be backed up "
                        "safely."
                    )
                if not stat.S_ISDIR(value.st_mode):
                    continue
                handle = _windows_fs._win_open(path, directory=True)
                identity = _windows_fs._win_identity(handle)
                if (identity.volume, identity.index) in self.forbidden_identities:
                    raise BackupError("Destination moved into the workspace during backup export.")
                if name.casefold() == ".git":
                    if relative.parts:
                        raise BackupError(
                            "This workspace contains nested snapshot storage and cannot be backed "
                            "up safely."
                        )
                    self._validate_git_store(path, Path())
                else:
                    self._scan_for_history(path, child_relative)
            except BackupError:
                raise
            except OSError as error:
                raise BackupError("Workspace contents could not be read safely.") from error
            finally:
                _windows_fs._win_close(handle)

    def _validate_git_store(self, parent_path: Path, relative: Path) -> None:
        try:
            names = os.listdir(parent_path)
        except OSError as error:
            raise BackupError("Workspace snapshot storage could not be inspected safely.") from error
        for name in names:
            path = parent_path / name
            child_relative = relative / name
            handle = -1
            try:
                value = path.lstat()
                if getattr(value, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT:
                    raise BackupError("Workspace snapshot storage is not safe to archive.")
                if _external_history_marker(child_relative):
                    raise BackupError(
                        "This workspace uses external snapshot history and cannot be backed up "
                        "safely."
                    )
                directory = stat.S_ISDIR(value.st_mode)
                if not directory and not stat.S_ISREG(value.st_mode):
                    raise BackupError("Workspace snapshot storage is not safe to archive.")
                handle = _windows_fs._win_open(path, directory=directory)
                identity = _windows_fs._win_identity(handle)
                if (identity.volume, identity.index) in self.forbidden_identities:
                    raise BackupError("Destination moved into the workspace during backup export.")
                if directory:
                    self._validate_git_store(path, child_relative)
                elif child_relative == Path("config"):
                    if identity.size > 1024 * 1024:
                        raise BackupError(
                            "Workspace snapshot storage could not be inspected safely."
                        )
                    if _config_uses_external_history(b"".join(_windows_chunks(handle))):
                        raise BackupError(
                            "This workspace uses external snapshot history and cannot be backed "
                            "up safely."
                        )
            except BackupError:
                raise
            except OSError as error:
                raise BackupError("Workspace snapshot storage could not be inspected safely.") from error
            finally:
                _windows_fs._win_close(handle)

    def forbid(self, *identities: tuple[int, int]) -> None:
        self.forbidden_identities.update(identities)

    def cleanup_snapshot_transients(
        self,
        transient_paths: tuple[SnapshotTransientPath, ...],
    ) -> None:
        _require_no_transients(set(transient_paths))

    def copy_snapshot_content(
        self,
        destination: Path,
        transient_paths: tuple[SnapshotTransientPath, ...] = (),
    ) -> None:
        _require_no_transients(set(transient_paths))
        self.require_path_current()
        before = _windows_fs._win_identity(self.handle)
        self._copy_directory(self.path, Path(), destination)
        if _windows_fs._win_identity(self.handle) != before:
            raise BackupError("Workspace content changed during backup export.")
        self.require_path_current()

    def _copy_directory(self, parent_path: Path, relative: Path, destination: Path) -> None:
        try:
            names = sorted(os.listdir(parent_path))
        except OSError as error:
            raise BackupError("Workspace contents could not be read safely.") from error
        for name in names:
            if not relative.parts and name.casefold() == ".git":
                continue
            path = parent_path / name
            target = destination / name
            handle = -1
            try:
                value = path.lstat()
                if getattr(value, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT:
                    raise BackupError("Workspace contains an unsupported filesystem entry.")
                directory = stat.S_ISDIR(value.st_mode)
                if not directory and not stat.S_ISREG(value.st_mode):
                    raise BackupError("Workspace contains an unsupported filesystem entry.")
                handle = _windows_fs._win_open(
                    path,
                    directory=directory,
                    retain_readable=not directory,
                )
                identity = _windows_fs._win_identity(handle)
                if (identity.volume, identity.index) in self.forbidden_identities:
                    raise BackupError("Destination moved into the workspace during backup export.")
                if directory:
                    target.mkdir()
                    self._copy_directory(path, relative / name, target)
                    if _windows_fs._win_identity(handle) != identity:
                        raise BackupError("Workspace content changed during backup export.")
                else:
                    with target.open("xb") as output:
                        for chunk in _windows_chunks(handle):
                            output.write(chunk)
                    if _windows_fs._win_identity(handle) != identity:
                        raise BackupError("Workspace content changed during backup export.")
            except BackupError:
                raise
            except OSError as error:
                raise BackupError("Workspace contents could not be read safely.") from error
            finally:
                _windows_fs._win_close(handle)

    def write_entries(
        self,
        archive: zipfile.ZipFile,
        transient_paths: tuple[SnapshotTransientPath, ...] = (),
    ) -> None:
        _require_no_transients(set(transient_paths))
        self.require_path_current()
        before = _windows_fs._win_identity(self.handle)
        self._write_directory(archive, self.path, self.handle, Path())
        if _windows_fs._win_identity(self.handle) != before:
            raise BackupError("Workspace content changed during backup export.")
        self.require_path_current()

    def _write_directory(
        self, archive: zipfile.ZipFile, parent_path: Path, parent: int, relative: Path
    ) -> None:
        del parent
        try:
            names = sorted(os.listdir(parent_path))
        except OSError as error:
            raise BackupError("Workspace contents could not be read safely.") from error
        for name in names:
            path = parent_path / name
            child_relative = relative / name
            handle = -1
            try:
                value = path.lstat()
                if getattr(value, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT:
                    raise BackupError("Workspace contains an unsupported filesystem entry.")
                directory = stat.S_ISDIR(value.st_mode)
                if not directory and not stat.S_ISREG(value.st_mode):
                    raise BackupError("Workspace contains an unsupported filesystem entry.")
                if not directory and not relative.parts and name.casefold() == ".git":
                    raise BackupError(
                        "This workspace uses external snapshot storage and cannot be "
                        "backed up safely."
                    )
                handle = _windows_fs._win_open(
                    path,
                    directory=directory,
                    retain_readable=not directory,
                )
                identity = _windows_fs._win_identity(handle)
                if (identity.volume, identity.index) in self.forbidden_identities:
                    raise BackupError("Destination moved into the workspace during backup export.")
                if directory:
                    archive.writestr(
                        _zip_info(
                            child_relative,
                            directory=True,
                            modified=_windows_modified(identity),
                            executable=True,
                        ),
                        b"",
                    )
                    self._write_directory(archive, path, handle, child_relative)
                    if _windows_fs._win_identity(handle) != identity:
                        raise BackupError("Workspace content changed during backup export.")
                else:
                    _write_chunks(
                        archive,
                        _zip_info(
                            child_relative,
                            directory=False,
                            modified=_windows_modified(identity),
                            executable=False,
                        ),
                        _windows_chunks(handle),
                    )
                    if _windows_fs._win_identity(handle) != identity:
                        raise BackupError("Workspace content changed during backup export.")
            except BackupError:
                raise
            except OSError as error:
                raise BackupError("Workspace contents could not be read safely.") from error
            finally:
                _windows_fs._win_close(handle)


class _WindowsOwnedArchive:
    def __init__(self, destination: _WindowsDestinationAnchor, name: str, handle: int):
        self.destination = destination
        self.name = name
        self.windows_handle = handle
        identity = _windows_fs._win_identity(handle)
        self.identity = (identity.volume, identity.index)
        try:
            self.file_descriptor = msvcrt.open_osfhandle(handle, os.O_BINARY | os.O_WRONLY)
        except Exception:
            _windows_fs._win_delete_handle(handle)
            _windows_fs._win_close(handle)
            raise

    def writer(self) -> BinaryIO:
        return os.fdopen(self.file_descriptor, "wb", closefd=False)

    def size(self) -> int:
        return os.fstat(self.file_descriptor).st_size

    def validate_name(self) -> None:
        if self.file_descriptor < 0:
            raise BackupError("Backup archive ownership is no longer retained.")
        identity = _windows_fs._win_identity(self.windows_handle)
        if (identity.volume, identity.index) != self.identity:
            raise BackupError("Backup archive path changed during export.")

    def finish(self) -> None:
        if self.file_descriptor >= 0:
            self.validate_name()
            os.close(self.file_descriptor)
            self.file_descriptor = -1
            self.windows_handle = -1

    def cleanup(self) -> None:
        if self.file_descriptor < 0:
            return
        try:
            _windows_fs._win_delete_handle(self.windows_handle)
        finally:
            self.finish()


class _WindowsDestinationAnchor:
    def __init__(self, destination: Path):
        self.path = destination
        self.handle = -1
        self.final_path = ""
        self.identity: tuple[int, int] | None = None

    def __enter__(self) -> _WindowsDestinationAnchor:
        if os.name != "nt":
            raise OSError("Windows filesystem handles are unavailable")
        try:
            self.handle = _windows_fs._win_open(self.path, directory=True)
            identity = _windows_fs._win_identity(self.handle)
            self.identity = (identity.volume, identity.index)
            self.final_path = _windows_final_path(self.handle)
            self.require_path_current()
            return self
        except Exception:
            self.close()
            raise BackupUsageError(
                "destination path does not exist or is not a safe directory"
            ) from None

    def __exit__(self, _kind: object, _value: object, _traceback: object) -> None:
        self.close()

    def close(self) -> None:
        if self.handle >= 0:
            _windows_fs._win_close(self.handle)
            self.handle = -1

    def require_path_current(self) -> None:
        if _windows_final_path(self.handle) != self.final_path:
            raise BackupError("Destination path changed during backup export.")

    def require_outside(self, workspace: _WindowsWorkspaceAnchor) -> None:
        try:
            common = os.path.commonpath([workspace.final_path, self.final_path])
        except ValueError:
            return
        if os.path.normcase(common) == workspace.final_path:
            raise BackupUsageError("destination must be outside the workspace")

    def allocate(self, timestamp: str) -> _WindowsOwnedArchive:
        stem = f"apparatus-backup-{timestamp}"
        for collision in range(1, _MAX_COLLISIONS):
            suffix = "" if collision == 1 else f"-{collision}"
            name = f"{stem}{suffix}.zip"
            try:
                handle = _windows_fs._win_open(
                    self.path / name,
                    directory=False,
                    create=True,
                    lock_name=True,
                )
                return _WindowsOwnedArchive(self, name, handle)
            except FileExistsError:
                continue
        raise BackupError("Could not choose a backup archive name.")

    def object_identity(self) -> tuple[int, int]:
        if self.identity is None:
            raise OSError("destination anchor is not open")
        return self.identity


def _anchor_types() -> tuple[type[Any], type[Any]]:
    if os.name == "nt":
        return _WindowsWorkspaceAnchor, _WindowsDestinationAnchor
    if os.name == "posix":
        return _PosixWorkspaceAnchor, _PosixDestinationAnchor
    raise BackupUsageError("safe backup export is unavailable on this machine")


def _write_archive(
    source: Any,
    owned: Any,
    transient_paths: tuple[SnapshotTransientPath, ...] = (),
) -> int:
    try:
        with owned.writer() as archive_file:
            with zipfile.ZipFile(
                archive_file,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                strict_timestamps=True,
            ) as archive:
                source.write_entries(archive, transient_paths)
            archive_file.flush()
        os.fsync(
            owned.file_descriptor if hasattr(owned, "file_descriptor") else owned.handle
        )
        return owned.size()
    except BackupError:
        raise
    except (OSError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
        raise BackupError("Could not write the backup archive.") from error


def _receipt_fields(result: BackupResult, destination: Path) -> dict[str, str | int]:
    fields: dict[str, str | int] = {
        "summary": f"Backup exported: {result.archive.name}.",
        "archive_filename": result.archive.name,
        "destination": str(destination),
        "archive_size": result.size,
        "body": "This receipt was written after the backup archive landed.\n",
    }
    if result.snapshot_id is not None:
        fields["snapshot_id"] = result.snapshot_id
    return fields


def _write_owned_backup_receipt(
    write: Callable[..., object],
    workspace: Path,
    fields: dict[str, str | int],
) -> ReceiptPublication:
    invocation: ReceiptInvocation = prepare_receipt_invocation(
        workspace,
        "backup-export",
        fields,
    )
    value: object | None = None
    try:
        value = write(
            workspace,
            "backup-export",
            fields,
            invocation=invocation,
        )
        if not isinstance(value, ReceiptPublication) or not value.is_bound_to(
            invocation
        ):
            if isinstance(value, ReceiptPublication) and value.is_from_invocation(
                invocation
            ):
                value.close()
            raise BackupError(
                "Backup receipt writer did not return exact publication ownership."
            )
        value.claim(invocation)
        return value
    except Exception:
        invocation.close()
        raise


def export_backup(
    workspace: str | Path,
    destination: str | Path,
    *,
    available: Callable[[], bool] = git_available,
    take: Callable[..., SnapshotTransaction] = prepare_snapshot,
    write: Callable[..., object] = write_receipt,
    clock: Callable[[], datetime] | None = None,
) -> BackupResult:
    """Export one anchored workspace archive without reading destination content."""
    root = _absolute(workspace)
    destination_path = _absolute(destination)
    timestamp = utc_archive_timestamp(clock)
    workspace_anchor_type, destination_anchor_type = _anchor_types()
    try:
        with workspace_anchor_type(root) as source, destination_anchor_type(
            destination_path
        ) as target:
            target.require_outside(source)
            source.forbid(target.object_identity())
            storage = source.snapshot_storage()
            if storage == "external":
                raise BackupError(
                    "This workspace uses external snapshot storage and cannot be backed up safely."
                )
            if storage == "unsafe":
                raise BackupError("Workspace snapshot storage is not safe to archive.")
            source.validate_snapshot_history()
            snapshots_available = available()
            snapshot_id: str | None = None
            transaction: SnapshotTransaction | None = None
            owned: Any = None
            success_receipt: ReceiptPublication | None = None
            completed = False
            try:
                if snapshots_available:
                    source.require_path_current()
                    try:
                        transaction = take(
                            root,
                            label=f"Before backup export {timestamp}",
                            capture=source.copy_snapshot_content,
                        )
                    except BackupError:
                        raise
                    except (OSError, ValueError, SnapshotError) as error:
                        raise BackupError("Could not save the pre-export snapshot.") from error
                    source.require_path_current()
                    snapshot = transaction.result
                    if snapshot.snapshot is not None:
                        snapshot_id = snapshot.snapshot.identifier
                    if source.snapshot_storage() != "standalone":
                        raise BackupError("Workspace snapshot storage is not safe to archive.")
                    source.validate_snapshot_history()
                    transaction.validate_receipt()
                source.require_path_current()
                target.require_path_current()
                owned = target.allocate(timestamp)
                source.forbid(owned.identity)
                target.require_path_current()
                target.require_outside(source)
                transient_paths = (
                    transaction.transient_paths if transaction is not None else ()
                )
                size = _write_archive(source, owned, transient_paths)
                owned.validate_name()
                if transaction is not None:
                    transaction.validate_receipt()
                source.require_path_current()
                target.require_path_current()
                target.require_outside(source)
                result = BackupResult(
                    archive=destination_path / owned.name,
                    snapshot_id=snapshot_id,
                    snapshots_available=snapshots_available,
                    size=size,
                )
                try:
                    success_receipt = _write_owned_backup_receipt(
                        write,
                        root,
                        _receipt_fields(result, destination_path),
                    )
                except BackupError:
                    raise
                except (OSError, TypeError, ValueError) as error:
                    raise BackupError(
                        "Backup archive was written, but its receipt could not be recorded."
                    ) from error
                success_receipt.commit()
                if transaction is not None:
                    transaction.settle()
                owned.finish()
                if transaction is not None:
                    transaction.commit()
                success_receipt.close()
                completed = True
                return result
            finally:
                if not completed:
                    cleanup_errors: list[Exception] = []
                    if success_receipt is not None:
                        try:
                            success_receipt.rollback()
                        except Exception as error:
                            cleanup_errors.append(error)
                        try:
                            success_receipt.close()
                        except Exception as error:
                            cleanup_errors.append(error)
                    if owned is not None:
                        try:
                            owned.cleanup()
                        except Exception as error:
                            cleanup_errors.append(error)
                    if transaction is not None:
                        try:
                            transaction.rollback()
                        except Exception as error:
                            cleanup_errors.append(error)
                        try:
                            source.cleanup_snapshot_transients(
                                transaction.transient_paths
                            )
                        except Exception as error:
                            cleanup_errors.append(error)
                    if cleanup_errors:
                        raise BackupError(
                            "Backup export failed and exact cleanup could not be completed "
                            "safely."
                        ) from cleanup_errors[0]
    except BackupError:
        raise
    except OSError as error:
        raise BackupError("Backup export could not be completed safely.") from error
