"""Small platform primitives for containment-safe filesystem transactions.

A check not repeated at the final success boundary is hope, not a guarantee;
success checkpoints reverify identity and containment through retained
descriptors or handles.
"""

from __future__ import annotations

import ctypes
import os
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_RENAME_EXCHANGE = 0x2
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_FILE_SHARE_DELETE = 0x00000004


def exchange_names(parent: int, first: str, second: str) -> None:
    """Atomically exchange two names in one retained POSIX directory."""
    if os.name != "posix":
        raise OSError("atomic name exchange is unavailable on this platform")
    library = ctypes.CDLL(None, use_errno=True)
    first_bytes = os.fsencode(first)
    second_bytes = os.fsencode(second)
    if hasattr(library, "renameatx_np"):
        function = library.renameatx_np
        function.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        result = function(parent, first_bytes, parent, second_bytes, _RENAME_EXCHANGE)
    elif hasattr(library, "renameat2"):
        function = library.renameat2
        function.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        result = function(parent, first_bytes, parent, second_bytes, _RENAME_EXCHANGE)
    else:
        raise OSError("atomic name exchange is unavailable on this POSIX system")
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


@dataclass(frozen=True)
class PosixIdentity:
    """Stable POSIX identity used by containment-safe workspace operations."""

    device: int
    inode: int
    size: int
    modified_ns: int


@dataclass
class PosixOwnedFile:
    """An exact invocation-owned file retained through its parent directory."""

    relative: Path
    parent: int
    name: str
    identity: PosixIdentity
    content: bytes

    def close(self) -> None:
        if self.parent >= 0:
            os.close(self.parent)
            self.parent = -1


@dataclass
class PosixOwnedDirectory:
    """An exact invocation-owned empty directory."""

    relative: Path
    parent: int
    name: str
    device: int
    inode: int

    def close(self) -> None:
        if self.parent >= 0:
            os.close(self.parent)
            self.parent = -1


@dataclass
class PosixReplacementTransaction:
    """One conditional replacement retaining its exact rollback copy."""

    anchor: PosixWorkspaceAnchor
    target: PosixOwnedFile
    backup: PosixOwnedFile
    finished: bool = False

    def rollback(self) -> None:
        if self.finished:
            return
        # Rollback is deliberately rooted in the retained parent descriptor.
        # Even when the visible workspace path was substituted, removing or
        # exchanging only the exact invocation-owned objects is still safe.
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
            raise OSError("workspace replacement changed before rollback")
        exchange_names(self.target.parent, self.target.name, self.backup.name)
        if not self.anchor._matches(
            self.target.parent,
            self.target.name,
            self.backup.identity,
            self.backup.content,
        ):
            raise OSError("workspace replacement rollback could not be verified")
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
        if self.finished:
            return
        if (
            not self.anchor.matches_owned(self.target)
            or not self.anchor.matches_owned(self.backup)
            or not self.anchor._parent_is_current(
                self.target.relative, self.target.parent
            )
        ):
            raise OSError("workspace replacement changed before completion")

    def close(self) -> None:
        self.target.close()
        self.backup.close()


def _posix_directory_flags() -> int:
    if (
        not hasattr(os, "O_DIRECTORY")
        or not hasattr(os, "O_NOFOLLOW")
        or os.open not in os.supports_dir_fd
        or os.stat not in os.supports_dir_fd
        or os.unlink not in os.supports_dir_fd
    ):
        raise OSError("safe descriptor-relative workspace operations are unavailable")
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _posix_identity(status_value: os.stat_result) -> PosixIdentity:
    return PosixIdentity(
        status_value.st_dev,
        status_value.st_ino,
        status_value.st_size,
        status_value.st_mtime_ns,
    )


def _open_posix_absolute_directory(path: Path) -> int:
    absolute = Path(os.path.abspath(os.fspath(path)))
    if not absolute.is_absolute() or not absolute.anchor:
        raise OSError("workspace path must be absolute")
    current = os.open(absolute.anchor, _posix_directory_flags())
    try:
        for part in absolute.parts[1:]:
            following = os.open(part, _posix_directory_flags(), dir_fd=current)
            os.close(current)
            current = following
        return current
    except Exception:
        os.close(current)
        raise


class PosixWorkspaceAnchor:
    """Workspace operations rooted at one no-follow POSIX descriptor chain."""

    def __init__(self, workspace: Path):
        self.workspace = Path(os.path.abspath(os.fspath(workspace)))
        self._root = _open_posix_absolute_directory(self.workspace)
        status_value = os.fstat(self._root)
        self._root_identity = (status_value.st_dev, status_value.st_ino)
        if not self.root_is_current():
            self.close()
            raise OSError("workspace root changed while it was anchored")

    def close(self) -> None:
        if self._root >= 0:
            os.close(self._root)
            self._root = -1

    def __enter__(self) -> PosixWorkspaceAnchor:  # noqa: PYI034
        return self

    def __exit__(self, _kind: object, _value: object, _traceback: object) -> None:
        self.close()

    def root_is_current(self) -> bool:
        current = -1
        try:
            current = _open_posix_absolute_directory(self.workspace)
            status_value = os.fstat(current)
            return (status_value.st_dev, status_value.st_ino) == self._root_identity
        except OSError:
            return False
        finally:
            if current >= 0:
                os.close(current)

    def matches_root_handle(self, root: int) -> bool:
        """Return whether ``root`` names this anchor's exact workspace object."""
        try:
            if self._root < 0 or root < 0:
                return False
            status_value = os.fstat(root)
            return (status_value.st_dev, status_value.st_ino) == self._root_identity
        except OSError:
            return False

    def contains_anchored_root(self, candidate: PosixWorkspaceAnchor) -> bool:
        """Return whether this root contains ``candidate`` by object identity."""
        if not self.root_is_current() or not candidate.root_is_current():
            raise OSError("anchored directory path changed")
        current = os.dup(candidate._root)
        try:
            while True:
                current_status = os.fstat(current)
                if (current_status.st_dev, current_status.st_ino) == (
                    self._root_identity
                ):
                    result = True
                    break
                parent = os.open("..", _posix_directory_flags(), dir_fd=current)
                parent_status = os.fstat(parent)
                if (parent_status.st_dev, parent_status.st_ino) == (
                    current_status.st_dev,
                    current_status.st_ino,
                ):
                    os.close(parent)
                    result = False
                    break
                os.close(current)
                current = parent
        finally:
            os.close(current)
        if not self.root_is_current() or not candidate.root_is_current():
            raise OSError("anchored directory path changed")
        return result

    @staticmethod
    def _parts(relative: str | Path) -> tuple[str, ...]:
        path = Path(relative)
        if (
            path.is_absolute()
            or not path.parts
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise OSError("workspace operation path is not safely relative")
        return path.parts

    def _parent(self, relative: str | Path) -> tuple[int, str]:
        parts = self._parts(relative)
        current = os.dup(self._root)
        try:
            for part in parts[:-1]:
                following = os.open(part, _posix_directory_flags(), dir_fd=current)
                os.close(current)
                current = following
            return current, parts[-1]
        except Exception:
            os.close(current)
            raise

    def open_directory(self, relative: str | Path) -> int:
        if not self.root_is_current():
            raise OSError("workspace root changed")
        parent, name = self._parent(relative)
        try:
            descriptor = os.open(name, _posix_directory_flags(), dir_fd=parent)
        finally:
            os.close(parent)
        if not self.root_is_current():
            os.close(descriptor)
            raise OSError("workspace root changed")
        return descriptor

    def require_directory(self, relative: str | Path) -> None:
        descriptor = self.open_directory(relative)
        os.close(descriptor)

    def directory_exists(self, relative: str | Path) -> bool:
        try:
            descriptor = self.open_directory(relative)
        except FileNotFoundError:
            return False
        else:
            os.close(descriptor)
            return True

    @staticmethod
    def _read_at(parent: int, name: str) -> tuple[bytes, PosixIdentity]:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise OSError("workspace file is not a regular file")
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 65_536)
                if not chunk:
                    break
                chunks.append(chunk)
            after = os.fstat(descriptor)
            if _posix_identity(before) != _posix_identity(after):
                raise OSError("workspace file changed while it was read")
            content = b"".join(chunks)
            if len(content) != after.st_size:
                raise OSError("workspace file changed while it was read")
            return content, _posix_identity(after)
        finally:
            os.close(descriptor)

    def read_file(self, relative: str | Path) -> tuple[bytes, PosixIdentity]:
        owned = self.capture_file(relative)
        try:
            return owned.content, owned.identity
        finally:
            owned.close()

    @staticmethod
    def _write_at(
        parent: int, name: str, content: bytes, mode: int
    ) -> PosixIdentity:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        descriptor = os.open(name, flags, mode, dir_fd=parent)
        opened_identity: PosixIdentity | None = None
        try:
            opened_identity = _posix_identity(os.fstat(descriptor))
            view = memoryview(content)
            written = 0
            while written < len(view):
                count = os.write(descriptor, view[written:])
                if count <= 0:
                    raise OSError("workspace content could not be written")
                written += count
            os.fsync(descriptor)
            return _posix_identity(os.fstat(descriptor))
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
        self,
        relative: str | Path,
        content: bytes,
        mode: int = 0o600,
        *,
        owned_parent: PosixOwnedDirectory | None = None,
    ) -> PosixOwnedFile:
        del owned_parent
        if not self.root_is_current():
            raise OSError("workspace root changed")
        parent, name = self._parent(relative)
        try:
            identity_value = self._write_at(parent, name, content, mode)
            owned = PosixOwnedFile(
                Path(relative), parent, name, identity_value, content
            )
            if not self._parent_is_current(owned.relative, parent):
                self._unlink_at_owned(parent, name, identity_value, content)
                raise OSError("workspace destination detached during creation")
            return owned
        except Exception:
            os.close(parent)
            raise

    def create_directory(self, relative: str | Path) -> PosixOwnedDirectory:
        if not self.root_is_current():
            raise OSError("workspace root changed")
        parent, name = self._parent(relative)
        try:
            os.mkdir(name, 0o700, dir_fd=parent)
            descriptor = os.open(name, _posix_directory_flags(), dir_fd=parent)
            try:
                status_value = os.fstat(descriptor)
            finally:
                os.close(descriptor)
            owned = PosixOwnedDirectory(
                Path(relative),
                parent,
                name,
                status_value.st_dev,
                status_value.st_ino,
            )
            if not self._parent_is_current(owned.relative, parent):
                self.remove_owned_directory(owned)
                raise OSError("workspace directory detached during creation")
            return owned
        except Exception:
            os.close(parent)
            raise

    def entry_exists(self, relative: str | Path) -> bool:
        if not self.root_is_current():
            raise OSError("workspace root changed")
        parent, name = self._parent(relative)
        try:
            try:
                os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                return False
            return True
        finally:
            os.close(parent)

    def _matches(
        self,
        parent: int,
        name: str,
        identity: PosixIdentity,
        content: bytes,
    ) -> bool:
        try:
            current_content, current_identity = self._read_at(parent, name)
        except OSError:
            return False
        return current_identity == identity and current_content == content

    def matches_owned(self, owned: PosixOwnedFile) -> bool:
        return (
            self.root_is_current()
            and self._parent_is_current(owned.relative, owned.parent)
            and self._matches(
                owned.parent, owned.name, owned.identity, owned.content
            )
        )

    def capture_file(self, relative: str | Path) -> PosixOwnedFile:
        if not self.root_is_current():
            raise OSError("workspace root changed")
        parent, name = self._parent(relative)
        try:
            content, identity_value = self._read_at(parent, name)
            owned = PosixOwnedFile(
                Path(relative), parent, name, identity_value, content
            )
            if not self._parent_is_current(owned.relative, parent):
                raise OSError("workspace source detached while it was read")
            return owned
        except Exception:
            os.close(parent)
            raise

    def unlink_owned(self, owned: PosixOwnedFile) -> None:
        # Cleanup uses the retained parent and exact identity/content. It must
        # remain available after a path substitution so a failed transaction
        # does not strand an invocation-owned artifact.
        self._unlink_at_owned(
            owned.parent, owned.name, owned.identity, owned.content
        )

    def _unlink_at_owned(
        self,
        parent: int,
        name: str,
        identity_value: PosixIdentity,
        content: bytes,
    ) -> None:
        if not self._matches(parent, name, identity_value, content):
            raise OSError("owned workspace file changed before cleanup")
        os.unlink(name, dir_fd=parent)

    def remove_owned_directory(self, owned: PosixOwnedDirectory) -> None:
        status_value = os.stat(
            owned.name, dir_fd=owned.parent, follow_symlinks=False
        )
        if (status_value.st_dev, status_value.st_ino) != (
            owned.device,
            owned.inode,
        ):
            raise OSError("owned workspace directory changed before cleanup")
        os.rmdir(owned.name, dir_fd=owned.parent)

    def _parent_is_current(self, relative: str | Path, parent: int) -> bool:
        current = -1
        try:
            if not self.root_is_current():
                return False
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
        expected_identity: PosixIdentity,
        expected_content: bytes,
        replacement: bytes,
    ) -> PosixReplacementTransaction:
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
        expected_identity: PosixIdentity,
        expected_content: bytes,
        replacement: bytes,
    ) -> PosixReplacementTransaction:
        temporary = f".apparatus-memory-{secrets.token_hex(16)}.tmp"
        temporary_created = False
        keep_parent = False
        replacement_identity: PosixIdentity | None = None
        try:
            if not self._parent_is_current(relative, parent):
                raise OSError("workspace destination detached before replacement")
            if not self._matches(parent, name, expected_identity, expected_content):
                raise OSError("workspace file changed after replacement planning")
            status_value = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISREG(status_value.st_mode):
                raise OSError("workspace file changed after replacement planning")
            mode = stat.S_IMODE(status_value.st_mode)
            replacement_identity = self._write_at(
                parent, temporary, replacement, mode
            )
            temporary_created = True
            if not self._matches(parent, name, expected_identity, expected_content):
                raise OSError("workspace file changed after replacement planning")
            if not self._parent_is_current(relative, parent):
                raise OSError("workspace destination detached before replacement")
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
                raise OSError("workspace file changed at conditional publication")
            target = PosixOwnedFile(
                relative, parent, name, replacement_identity, replacement
            )
            backup = PosixOwnedFile(
                relative,
                os.dup(parent),
                temporary,
                backup_identity,
                backup_content,
            )
            temporary_created = False
            keep_parent = True
            transaction = PosixReplacementTransaction(self, target, backup)
            if not self._parent_is_current(relative, parent):
                transaction.rollback()
                transaction.close()
                raise OSError("workspace destination detached after replacement")
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
                except OSError:
                    pass
            if temporary_created:
                try:
                    if replacement_identity is not None:
                        self._unlink_at_owned(
                            parent, temporary, replacement_identity, replacement
                        )
                except OSError:
                    pass
            if not keep_parent:
                os.close(parent)

    def list_files(
        self,
        relative: str | Path,
        *,
        suffix: str | None = None,
        include_hidden: bool = True,
    ) -> list[Path]:
        root_relative = Path(relative)
        descriptor = self.open_directory(root_relative)
        found: list[Path] = []

        def inspect(current: int, current_relative: Path) -> None:
            before = os.fstat(current)
            for name in sorted(os.listdir(current)):
                if not include_hidden and name.startswith("."):
                    continue
                status_value = os.stat(name, dir_fd=current, follow_symlinks=False)
                child_relative = current_relative / name
                if stat.S_ISLNK(status_value.st_mode):
                    raise OSError("workspace traversal found a symbolic link")
                if stat.S_ISDIR(status_value.st_mode):
                    child = os.open(name, _posix_directory_flags(), dir_fd=current)
                    try:
                        inspect(child, child_relative)
                    finally:
                        os.close(child)
                elif stat.S_ISREG(status_value.st_mode):
                    if suffix is None or name.endswith(suffix):
                        found.append(child_relative)
                else:
                    raise OSError("workspace traversal found an unsupported file type")
            after = os.fstat(current)
            if (before.st_dev, before.st_ino, before.st_mtime_ns) != (
                after.st_dev,
                after.st_ino,
                after.st_mtime_ns,
            ):
                raise OSError("workspace directory changed during traversal")

        try:
            inspect(descriptor, root_relative)
        finally:
            os.close(descriptor)
        if not self.root_is_current():
            raise OSError("workspace root changed during traversal")
        return found

    def list_memory_records(self, relative: str | Path) -> list[Path]:
        return self.list_files(relative, suffix=".md", include_hidden=False)


# Windows has no directory-fd API.  The backend below retains a no-reparse
# handle for every directory in an operation and denies FILE_SHARE_DELETE on
# those handles.  That makes the absolute child names stable while Win32's
# atomic ReplaceFile/CreateHardLink operations run; paths are never used after
# an unprotected containment check.
if os.name == "nt":  # pragma: no cover - exercised by the Windows CI job
    from ctypes import wintypes

    _INVALID_HANDLE = ctypes.c_void_p(-1).value
    _GENERIC_READ = 0x80000000
    _GENERIC_WRITE = 0x40000000
    _DELETE = 0x00010000
    _FILE_READ_ATTRIBUTES = 0x0080
    _CREATE_NEW = 1
    _OPEN_EXISTING = 3
    _FILE_ATTRIBUTE_DIRECTORY = 0x00000010
    _FILE_ATTRIBUTE_NORMAL = 0x00000080
    _FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _FILE_FLAG_WRITE_THROUGH = 0x80000000
    _FILE_DISPOSITION_INFO = 4

    class _FileTime(ctypes.Structure):
        _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

    class _ByHandleInformation(ctypes.Structure):
        _fields_ = [
            ("attributes", wintypes.DWORD),
            ("creation_time", _FileTime),
            ("access_time", _FileTime),
            ("write_time", _FileTime),
            ("volume_serial", wintypes.DWORD),
            ("size_high", wintypes.DWORD),
            ("size_low", wintypes.DWORD),
            ("links", wintypes.DWORD),
            ("index_high", wintypes.DWORD),
            ("index_low", wintypes.DWORD),
        ]

    class _FileDispositionInformation(ctypes.Structure):
        _fields_ = [("delete_file", wintypes.BOOL)]


@dataclass(frozen=True)
class WindowsIdentity:
    """Stable Win32 file identity used by the Memory transaction backend."""

    volume: int
    index: int
    size: int
    modified: int


def _win_kernel() -> Any:
    if os.name != "nt":
        raise OSError("Win32 filesystem operations are unavailable")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.GetFileInformationByHandle.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ByHandleInformation),
    ]
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.ReadFile.argtypes = [
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]
    kernel.ReadFile.restype = wintypes.BOOL
    kernel.WriteFile.argtypes = [
        wintypes.HANDLE,
        wintypes.LPCVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]
    kernel.WriteFile.restype = wintypes.BOOL
    kernel.FlushFileBuffers.argtypes = [wintypes.HANDLE]
    kernel.FlushFileBuffers.restype = wintypes.BOOL
    kernel.SetFileInformationByHandle.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    kernel.SetFileInformationByHandle.restype = wintypes.BOOL
    kernel.ReplaceFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.LPVOID,
    ]
    kernel.ReplaceFileW.restype = wintypes.BOOL
    kernel.CreateHardLinkW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPVOID,
    ]
    kernel.CreateHardLinkW.restype = wintypes.BOOL
    kernel.CreateDirectoryW.argtypes = [wintypes.LPCWSTR, wintypes.LPVOID]
    kernel.CreateDirectoryW.restype = wintypes.BOOL
    return kernel


def _win_error(message: str) -> OSError:
    code = ctypes.get_last_error()
    if code in {80, 183}:
        return FileExistsError(code, message, None, code)
    if code in {2, 3}:
        return FileNotFoundError(code, message, None, code)
    return OSError(code, message, None, code)


def _win_close(handle: int) -> None:
    if handle not in {0, -1, _INVALID_HANDLE}:
        _win_kernel().CloseHandle(handle)


def _win_open(
    path: Path,
    *,
    directory: bool,
    create: bool = False,
    lock_name: bool = True,
    delete_access: bool = False,
    share_existing_write: bool = False,
    retain_readable: bool = False,
) -> int:
    kernel = _win_kernel()
    access = _GENERIC_READ
    # Windows sharing is mutual: a handle holding DELETE access blocks every
    # ordinary reader that does not offer FILE_SHARE_DELETE. A retained
    # long-lived handle therefore opts out of DELETE access so the published
    # file stays readable at its path; deletion re-opens and re-verifies.
    if (not directory and not retain_readable) or delete_access:
        access |= _DELETE
    if create:
        access |= _GENERIC_WRITE
    sharing = _win_share_mode(
        directory=directory,
        lock_name=lock_name,
        share_existing_write=share_existing_write,
    )
    flags = _FILE_FLAG_OPEN_REPARSE_POINT
    if directory:
        flags |= _FILE_FLAG_BACKUP_SEMANTICS
    elif create:
        flags |= _FILE_ATTRIBUTE_NORMAL | _FILE_FLAG_WRITE_THROUGH
    handle = kernel.CreateFileW(
        str(path),
        access,
        sharing,
        None,
        _CREATE_NEW if create else _OPEN_EXISTING,
        flags,
        None,
    )
    if handle == _INVALID_HANDLE:
        raise _win_error("safe filesystem object could not be opened")
    try:
        information = _win_information(handle)
        is_directory = bool(information.attributes & _FILE_ATTRIBUTE_DIRECTORY)
        if bool(information.attributes & _FILE_ATTRIBUTE_REPARSE_POINT):
            raise OSError("filesystem reparse points are not allowed")
        if is_directory != directory:
            raise OSError("filesystem object has an unexpected type")
        return int(handle)
    except Exception:
        _win_close(int(handle))
        raise


def _win_information(handle: int) -> Any:
    information = _ByHandleInformation()
    if not _win_kernel().GetFileInformationByHandle(handle, ctypes.byref(information)):
        raise _win_error("filesystem identity could not be read")
    return information


def _win_identity(handle: int) -> WindowsIdentity:
    information = _win_information(handle)
    return WindowsIdentity(
        int(information.volume_serial),
        (int(information.index_high) << 32) | int(information.index_low),
        (int(information.size_high) << 32) | int(information.size_low),
        (int(information.write_time.high) << 32) | int(information.write_time.low),
    )


def _same_windows_object(first: WindowsIdentity, second: WindowsIdentity) -> bool:
    """Compare immutable Win32 object identity, not mutable file metadata."""
    return first.volume == second.volume and first.index == second.index


def _win_share_mode(
    *, directory: bool, lock_name: bool, share_existing_write: bool
) -> int:
    """Return the Win32 share mask used for one retained or alias handle."""
    sharing = _FILE_SHARE_READ
    if directory or share_existing_write:
        # Directories remain writable while their own names are locked. File
        # aliases opt in only while an invocation-owned writer already exists.
        sharing |= _FILE_SHARE_WRITE
    if not lock_name:
        sharing |= _FILE_SHARE_DELETE
    return sharing


def _win_read(handle: int) -> bytes:
    """Read an already-open Win32 file without reopening its pathname."""
    kernel = _win_kernel()
    chunks: list[bytes] = []
    while True:
        buffer = ctypes.create_string_buffer(1_048_576)
        read = wintypes.DWORD()
        if not kernel.ReadFile(
            handle,
            buffer,
            len(buffer),
            ctypes.byref(read),
            None,
        ):
            raise _win_error("filesystem content could not be read")
        if read.value == 0:
            return b"".join(chunks)
        chunks.append(buffer.raw[: read.value])


def _win_write(handle: int, content: bytes) -> None:
    kernel = _win_kernel()
    offset = 0
    while offset < len(content):
        chunk = content[offset : offset + 1_048_576]
        buffer = ctypes.create_string_buffer(chunk)
        written = wintypes.DWORD()
        if not kernel.WriteFile(
            handle, buffer, len(chunk), ctypes.byref(written), None
        ) or written.value != len(chunk):
            raise _win_error("filesystem content could not be written")
        offset += written.value
    if not kernel.FlushFileBuffers(handle):
        raise _win_error("filesystem content could not be flushed")


def _win_delete_handle(handle: int) -> None:
    disposition = _FileDispositionInformation(True)
    if not _win_kernel().SetFileInformationByHandle(
        handle,
        _FILE_DISPOSITION_INFO,
        ctypes.byref(disposition),
        ctypes.sizeof(disposition),
    ):
        raise _win_error("owned filesystem object could not be removed")


def _win_replace(target: Path, replacement: Path, backup: Path | None) -> None:
    # ReplaceFileW's write-through flag is unsupported. Each replacement is
    # already flushed through its writer before this atomic publication.
    if not _win_kernel().ReplaceFileW(
        str(target),
        str(replacement),
        None if backup is None else str(backup),
        0,
        None,
        None,
    ):
        raise _win_error("conditional filesystem replacement failed")


def _win_hardlink(link: Path, target: Path) -> None:
    if not _win_kernel().CreateHardLinkW(str(link), str(target), None):
        raise _win_error("exclusive receipt publication failed")


def _win_create_directory(path: Path) -> bool:
    if _win_kernel().CreateDirectoryW(str(path), None):
        return True
    code = ctypes.get_last_error()
    if code == 183:  # ERROR_ALREADY_EXISTS
        return False
    raise _win_error("safe receipt directory could not be created")


def _win_open_absolute_directory_chain(path: Path) -> tuple[int, list[int]]:
    absolute = Path(os.path.abspath(os.fspath(path)))
    if not absolute.is_absolute() or not absolute.anchor:
        raise OSError("workspace path must be absolute")
    current_path = Path(absolute.anchor)
    current = _win_open(current_path, directory=True)
    ancestors: list[int] = []
    try:
        for part in absolute.parts[1:]:
            following_path = current_path / part
            following = _win_open(following_path, directory=True)
            ancestors.append(current)
            current = following
            current_path = following_path
        return current, ancestors
    except Exception:
        _win_close(current)
        for handle in reversed(ancestors):
            _win_close(handle)
        raise


def _safe_parts(relative: str | Path) -> tuple[str, ...]:
    path = Path(relative)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise OSError("workspace operation path is not safely relative")
    return path.parts


@dataclass
class WindowsOwnedFile:
    relative: Path
    parent: int
    path: Path
    identity: WindowsIdentity
    content: bytes
    handle: int
    parent_shares_delete: bool = False

    def close(self) -> None:
        if self.handle >= 0:
            _win_close(self.handle)
            self.handle = -1
        if self.parent >= 0:
            _win_close(self.parent)
            self.parent = -1


@dataclass
class WindowsOwnedDirectory:
    relative: Path
    parent: int
    path: Path
    identity: WindowsIdentity
    handle: int

    def close(self) -> None:
        if self.handle >= 0:
            _win_close(self.handle)
            self.handle = -1
        if self.parent >= 0:
            _win_close(self.parent)
            self.parent = -1


@dataclass
class WindowsReceiptPublication:
    """Retained Win32 proof for one newly published receipt."""

    workspace: Path
    path: Path
    event: str
    content: bytes
    identity: WindowsIdentity
    root: int
    root_identity: WindowsIdentity
    system: int
    system_identity: WindowsIdentity
    receipts: int
    receipts_identity: WindowsIdentity
    handle: int

    def validate(self) -> None:
        if min(self.root, self.system, self.receipts, self.handle) < 0:
            raise OSError("receipt publication proof is no longer active")
        if (
            not _same_windows_object(_win_identity(self.root), self.root_identity)
            or not _same_windows_object(
                _win_identity(self.system), self.system_identity
            )
            or not _same_windows_object(
                _win_identity(self.receipts), self.receipts_identity
            )
            or _win_identity(self.handle) != self.identity
        ):
            raise OSError("receipt publication proof changed")
        current_root = _win_open(self.workspace, directory=True)
        try:
            if not _same_windows_object(
                _win_identity(current_root), self.root_identity
            ):
                raise OSError("receipt publication parent changed")
        finally:
            _win_close(current_root)

    def commit(self) -> None:
        self.validate()

    def rollback(self) -> None:
        self.validate()
        # The retained proof handle holds no DELETE access so the published
        # receipt stays readable by ordinary tools while the proof is live.
        # Deletion closes the pin, re-opens by name with DELETE access, and
        # re-verifies exact object identity before disposing.
        _win_close(self.handle)
        self.handle = -1
        reopened = _win_open(self.path, directory=False)
        try:
            if _win_identity(reopened) != self.identity:
                raise OSError("receipt publication changed before rollback")
            _win_delete_handle(reopened)
        finally:
            _win_close(reopened)

    def close(self) -> None:
        for name in ("handle", "receipts", "system", "root"):
            handle = getattr(self, name)
            if handle >= 0:
                _win_close(handle)
                setattr(self, name, -1)


@dataclass
class WindowsReplacementTransaction:
    anchor: WindowsWorkspaceAnchor
    target: WindowsOwnedFile
    backup: WindowsOwnedFile
    finished: bool = False

    def _release_file_locks(self) -> None:
        for owned in (self.target, self.backup):
            if owned.handle >= 0:
                _win_close(owned.handle)
                owned.handle = -1

    def rollback(self) -> None:
        if self.finished:
            return
        if not self.anchor._matches_owned(
            self.target
        ) or not self.anchor._matches_owned(self.backup):
            raise OSError("Memory replacement changed before rollback")
        self._release_file_locks()
        _win_replace(self.target.path, self.backup.path, None)
        if not self.anchor._matches_path(
            self.target.path, self.backup.identity, self.backup.content
        ):
            raise OSError("Memory replacement rollback could not be verified")
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
        if not self.anchor._matches_owned(self.backup):
            raise OSError("Memory replacement backup changed before cleanup")
        _win_delete_handle(self.backup.handle)
        _win_close(self.backup.handle)
        self.backup.handle = -1
        self.finished = True

    def validate_commit(self) -> None:
        """Prove this transaction can commit without destroying its backup."""
        if self.finished:
            return
        if (
            not self.anchor._matches_owned(self.target)
            or not self.anchor._matches_owned(self.backup)
            or not self.anchor._parent_is_current(
                self.target.relative, self.target.parent
            )
        ):
            raise OSError("Memory replacement changed before completion")

    def close(self) -> None:
        self.target.close()
        self.backup.close()


class WindowsWorkspaceAnchor:
    """Containment-safe Windows workspace backend using retained Win32 handles."""

    def __init__(self, workspace: Path):
        self.workspace = Path(os.path.abspath(os.fspath(workspace)))
        self._root, self._chain_handles = _win_open_absolute_directory_chain(
            self.workspace
        )
        self._root_identity = _win_identity(self._root)
        if not self.root_is_current():
            self.close()
            raise OSError("workspace root changed while it was anchored")

    def __enter__(self) -> WindowsWorkspaceAnchor:  # noqa: PYI034
        return self

    def __exit__(self, _kind: object, _value: object, _traceback: object) -> None:
        self.close()

    def close(self) -> None:
        for handle in reversed(self._chain_handles):
            _win_close(handle)
        self._chain_handles.clear()
        if self._root >= 0:
            _win_close(self._root)
            self._root = -1

    def root_is_current(self) -> bool:
        current = -1
        ancestors: list[int] = []
        try:
            current, ancestors = _win_open_absolute_directory_chain(self.workspace)
            return _same_windows_object(
                _win_identity(current), self._root_identity
            )
        except OSError:
            return False
        finally:
            _win_close(current)
            for handle in reversed(ancestors):
                _win_close(handle)

    def matches_root_handle(self, root: int) -> bool:
        """Return whether ``root`` names this anchor's exact workspace object."""
        try:
            return self._root >= 0 and root >= 0 and _same_windows_object(
                _win_identity(root), self._root_identity
            )
        except OSError:
            return False

    def contains_anchored_root(self, candidate: WindowsWorkspaceAnchor) -> bool:
        """Return whether this root contains ``candidate`` by object identity."""
        if not self.root_is_current() or not candidate.root_is_current():
            raise OSError("anchored directory path changed")
        if self._root < 0 or candidate._root < 0:
            raise OSError("anchored directory proof is no longer active")
        if not _same_windows_object(
            _win_identity(self._root), self._root_identity
        ) or not _same_windows_object(
            _win_identity(candidate._root), candidate._root_identity
        ):
            raise OSError("anchored directory identity changed")
        result = any(
            _same_windows_object(_win_identity(handle), self._root_identity)
            for handle in (candidate._root, *candidate._chain_handles)
        )
        if not self.root_is_current() or not candidate.root_is_current():
            raise OSError("anchored directory path changed")
        return result

    def _directory(
        self,
        relative: str | Path,
        *,
        final_shares_delete: bool = False,
    ) -> tuple[Path, int]:
        current_path = self.workspace
        current = -1
        try:
            if not self.root_is_current() or not _same_windows_object(
                _win_identity(self._root), self._root_identity
            ):
                raise OSError("workspace root changed")
            parts = _safe_parts(relative)
            for index, part in enumerate(parts):
                following_path = current_path / part
                # A newly invocation-owned directory retains a separate handle
                # that denies delete sharing. Its child-operation aliases must
                # share delete so they remain compatible with that owner's
                # DELETE access; the retained owner still locks the name.
                following = _win_open(
                    following_path,
                    directory=True,
                    lock_name=not (
                        final_shares_delete and index == len(parts) - 1
                    ),
                )
                if current >= 0:
                    self._chain_handles.append(current)
                current = following
                current_path = following_path
            return current_path, current
        except Exception:
            _win_close(current)
            raise

    def _parent(
        self,
        relative: str | Path,
        *,
        parent_shares_delete: bool = False,
    ) -> tuple[Path, int, str]:
        parts = _safe_parts(relative)
        if len(parts) == 1:
            parent_path = self.workspace
            parent = _win_open(parent_path, directory=True)
            if not _same_windows_object(_win_identity(parent), self._root_identity):
                _win_close(parent)
                raise OSError("workspace root changed")
            return parent_path, parent, parts[0]
        parent_path, parent = self._directory(
            Path(*parts[:-1]),
            final_shares_delete=parent_shares_delete,
        )
        return parent_path, parent, parts[-1]

    def require_directory(self, relative: str | Path) -> None:
        _path, handle = self._directory(relative)
        _win_close(handle)

    def directory_exists(self, relative: str | Path) -> bool:
        try:
            _path, handle = self._directory(relative)
        except FileNotFoundError:
            return False
        else:
            _win_close(handle)
            return True

    @staticmethod
    def _read_locked(path: Path) -> tuple[bytes, WindowsIdentity, int]:
        handle = _win_open(
            path,
            directory=False,
            lock_name=False,
        )
        try:
            before = _win_identity(handle)
            content = _win_read(handle)
            after = _win_identity(handle)
            if before != after or len(content) != after.size:
                raise OSError("workspace file changed while it was read")
            return content, after, handle
        except Exception:
            _win_close(handle)
            raise

    def read_file(self, relative: str | Path) -> tuple[bytes, WindowsIdentity]:
        owned = self.capture_file(relative)
        try:
            return owned.content, owned.identity
        finally:
            owned.close()

    def _parent_is_current(
        self,
        relative: Path,
        parent: int,
        *,
        parent_shares_delete: bool = False,
    ) -> bool:
        current = -1
        try:
            if not self.root_is_current():
                return False
            _path, current, _name = self._parent(
                relative,
                parent_shares_delete=parent_shares_delete,
            )
            return _same_windows_object(
                _win_identity(current), _win_identity(parent)
            )
        except OSError:
            return False
        finally:
            _win_close(current)

    def create_file(
        self,
        relative: str | Path,
        content: bytes,
        mode: int = 0o600,
        *,
        owned_parent: WindowsOwnedDirectory | None = None,
    ) -> WindowsOwnedFile:
        del mode
        if not self.root_is_current():
            raise OSError("workspace root changed")
        parent_shares_delete = owned_parent is not None
        if owned_parent is not None and (
            Path(relative).parent != owned_parent.relative
            or owned_parent.handle < 0
            or not _same_windows_object(
                _win_identity(owned_parent.handle), owned_parent.identity
            )
            or not self._parent_is_current(
                owned_parent.relative, owned_parent.parent
            )
        ):
            raise OSError("invocation-owned parent directory changed")
        parent_path, parent, name = self._parent(
            relative,
            parent_shares_delete=parent_shares_delete,
        )
        path = parent_path / name
        handle = verification = -1
        identity: WindowsIdentity | None = None
        current: bytes | None = None
        owned: WindowsOwnedFile | None = None
        try:
            handle = _win_open(path, directory=False, create=True, lock_name=False)
            _win_write(handle, content)
            identity = _win_identity(handle)
            _win_close(handle)
            handle = -1
            current, current_identity, verification = self._read_locked(path)
            if current_identity != identity or current != content:
                raise OSError("Memory record changed during creation")
            owned = WindowsOwnedFile(
                Path(relative),
                parent,
                path,
                identity,
                content,
                verification,
                parent_shares_delete,
            )
            verification = -1
            if not self._parent_is_current(
                Path(relative),
                parent,
                parent_shares_delete=parent_shares_delete,
            ):
                self.unlink_owned(owned)
                raise OSError("Memory destination detached during creation")
            return owned
        except Exception:
            if handle >= 0:
                try:
                    _win_delete_handle(handle)
                except OSError:
                    pass
                _win_close(handle)
            elif verification >= 0:
                try:
                    if (
                        identity is not None
                        and current == content
                        and _win_identity(verification) == identity
                    ):
                        _win_delete_handle(verification)
                except OSError:
                    pass
                _win_close(verification)
            elif identity is not None:
                cleanup = -1
                try:
                    current, current_identity, cleanup = self._read_locked(path)
                    if current_identity == identity and current == content:
                        _win_delete_handle(cleanup)
                except OSError:
                    pass
                finally:
                    _win_close(cleanup)
            if owned is not None:
                owned.close()
                parent = -1
            _win_close(parent)
            raise

    def create_directory(self, relative: str | Path) -> WindowsOwnedDirectory:
        if not self.root_is_current():
            raise OSError("workspace root changed")
        parent_path, parent, name = self._parent(relative)
        path = parent_path / name
        handle = -1
        try:
            if not _win_create_directory(path):
                raise FileExistsError("workspace directory already exists")
            handle = _win_open(path, directory=True, delete_access=True)
            owned = WindowsOwnedDirectory(
                Path(relative), parent, path, _win_identity(handle), handle
            )
            handle = -1
            if not self._parent_is_current(Path(relative), parent):
                self.remove_owned_directory(owned)
                owned.close()
                parent = -1
                raise OSError("workspace directory detached during creation")
            return owned
        except Exception:
            if handle >= 0:
                try:
                    _win_delete_handle(handle)
                except OSError:
                    pass
                _win_close(handle)
            _win_close(parent)
            raise

    def entry_exists(self, relative: str | Path) -> bool:
        if not self.root_is_current():
            raise OSError("workspace root changed")
        parent_path, parent, name = self._parent(relative)
        handle = -1
        path = parent_path / name
        try:
            try:
                handle = _win_open(path, directory=False, lock_name=False)
            except FileNotFoundError:
                try:
                    handle = _win_open(path, directory=True)
                except FileNotFoundError:
                    return False
            return True
        except OSError as error:
            # Reparse points and unexpected object types still occupy the
            # name and therefore collide with an exclusive egress output.
            try:
                os.lstat(path)
            except OSError:
                raise error
            return True
        finally:
            _win_close(handle)
            _win_close(parent)

    def capture_file(self, relative: str | Path) -> WindowsOwnedFile:
        if not self.root_is_current():
            raise OSError("workspace root changed")
        parent_path, parent, name = self._parent(relative)
        try:
            content, identity, handle = self._read_locked(parent_path / name)
            owned = WindowsOwnedFile(
                Path(relative), parent, parent_path / name, identity, content, handle
            )
            if not self._parent_is_current(Path(relative), parent):
                owned.close()
                parent = -1
                raise OSError("workspace source detached while it was read")
            return owned
        except Exception:
            _win_close(parent)
            raise

    @staticmethod
    def _matches_path(
        path: Path,
        identity: WindowsIdentity,
        content: bytes,
    ) -> bool:
        try:
            current, current_identity, handle = WindowsWorkspaceAnchor._read_locked(
                path
            )
            _win_close(handle)
        except OSError:
            return False
        return current_identity == identity and current == content

    def _matches_owned(self, owned: WindowsOwnedFile) -> bool:
        return (
            owned.handle >= 0
            and _win_identity(owned.handle) == owned.identity
            and self._matches_path(owned.path, owned.identity, owned.content)
        )

    def unlink_owned(self, owned: WindowsOwnedFile) -> None:
        # The retained handle identifies and write-locks the exact object. It
        # is safe to delete that object even if its visible path was swapped.
        if owned.handle < 0 or _win_identity(owned.handle) != owned.identity:
            raise OSError("owned workspace file changed before cleanup")
        _win_delete_handle(owned.handle)
        _win_close(owned.handle)
        owned.handle = -1

    def matches_owned(self, owned: WindowsOwnedFile) -> bool:
        return (
            self.root_is_current()
            and self._parent_is_current(
                owned.relative,
                owned.parent,
                parent_shares_delete=owned.parent_shares_delete,
            )
            and self._matches_owned(owned)
        )

    def remove_owned_directory(self, owned: WindowsOwnedDirectory) -> None:
        if (
            owned.handle < 0
            or not _same_windows_object(
                _win_identity(owned.handle), owned.identity
            )
        ):
            raise OSError("owned workspace directory changed before cleanup")
        _win_delete_handle(owned.handle)
        _win_close(owned.handle)
        owned.handle = -1

    def _discard_created_file(
        self,
        path: Path,
        handle: int,
        identity: WindowsIdentity | None,
        content: bytes,
    ) -> None:
        """Delete only the invocation-owned temporary object, if still exact."""
        if handle >= 0:
            try:
                _win_delete_handle(handle)
            except OSError:
                pass
            finally:
                _win_close(handle)
            return
        if identity is None:
            return
        verification = -1
        try:
            current, current_identity, verification = self._read_locked(path)
            if current_identity == identity and current == content:
                _win_delete_handle(verification)
        except OSError:
            pass
        finally:
            _win_close(verification)

    def _restore_exact_backup(
        self,
        target_path: Path,
        target_identity: WindowsIdentity,
        target_content: bytes,
        backup_path: Path,
        backup_identity: WindowsIdentity,
        backup_content: bytes,
    ) -> bool:
        """Restore only when both published target and backup remain exact."""
        if not self._matches_path(
            target_path, target_identity, target_content
        ) or not self._matches_path(backup_path, backup_identity, backup_content):
            return False
        _win_replace(target_path, backup_path, None)
        return True

    def replace_if_unchanged(
        self,
        relative: str | Path,
        expected_identity: WindowsIdentity,
        expected_content: bytes,
        replacement: bytes,
    ) -> WindowsReplacementTransaction:
        relative_path = Path(relative)
        parent_path, parent, name = self._parent(relative_path)
        target_path = parent_path / name
        temporary_path = parent_path / f".apparatus-memory-{secrets.token_hex(16)}.tmp"
        backup_path = parent_path / f".apparatus-memory-{secrets.token_hex(16)}.bak"
        original_handle = replacement_handle = published_handle = -1
        replacement_identity: WindowsIdentity | None = None
        backup_parent = -1
        target_owned: WindowsOwnedFile | None = None
        backup_owned: WindowsOwnedFile | None = None
        replaced = False
        try:
            original, original_identity, original_handle = self._read_locked(
                target_path
            )
            if original_identity != expected_identity or original != expected_content:
                raise OSError("Memory record changed after sweep planning")
            replacement_handle = _win_open(
                temporary_path,
                directory=False,
                create=True,
                lock_name=False,
            )
            _win_write(replacement_handle, replacement)
            replacement_identity = _win_identity(replacement_handle)
            # ReplaceFileW opens its replacement name with no sharing. Capture
            # the exact file first, then release this invocation-owned writer.
            _win_close(replacement_handle)
            replacement_handle = -1
            if not self._parent_is_current(relative_path, parent):
                raise OSError("Memory destination detached before replacement")
            _win_replace(target_path, temporary_path, backup_path)
            replaced = True
            # Deny subsequent writers while this retained handle verifies and
            # owns the exact object that ReplaceFileW published at the target.
            published, published_identity, published_handle = self._read_locked(
                target_path
            )
            if (
                published_identity != replacement_identity
                or published != replacement
                or _win_identity(original_handle) != expected_identity
                or not self._matches_path(
                    backup_path, expected_identity, expected_content
                )
            ):
                raise OSError("Memory record changed at conditional publication")
            target_owned = WindowsOwnedFile(
                relative_path,
                parent,
                target_path,
                replacement_identity,
                replacement,
                published_handle,
            )
            published_handle = -1
            backup_parent = _win_open(parent_path, directory=True)
            backup_owned = WindowsOwnedFile(
                relative_path,
                backup_parent,
                backup_path,
                expected_identity,
                expected_content,
                original_handle,
            )
            original_handle = -1
            backup_parent = -1
            transaction = WindowsReplacementTransaction(
                self, target_owned, backup_owned
            )
            if not self._parent_is_current(relative_path, parent):
                transaction.rollback()
                transaction.close()
                replaced = False
                parent = -1
                raise OSError("Memory destination detached after replacement")
            return transaction
        except Exception:
            _win_close(original_handle)
            _win_close(published_handle)
            _win_close(backup_parent)
            for owned in (target_owned, backup_owned):
                if owned is not None and owned.handle >= 0:
                    _win_close(owned.handle)
                    owned.handle = -1
            if replaced:
                _win_close(replacement_handle)
                try:
                    if replacement_identity is not None:
                        self._restore_exact_backup(
                            target_path,
                            replacement_identity,
                            replacement,
                            backup_path,
                            expected_identity,
                            expected_content,
                        )
                except OSError:
                    pass
            else:
                self._discard_created_file(
                    temporary_path,
                    replacement_handle,
                    replacement_identity,
                    replacement,
                )
            if target_owned is not None:
                target_owned.close()
                parent = -1
            if backup_owned is not None:
                backup_owned.close()
            _win_close(parent)
            raise

    def list_files(
        self,
        relative: str | Path,
        *,
        suffix: str | None = None,
        include_hidden: bool = True,
    ) -> list[Path]:
        root_relative = Path(relative)
        root_path, root_handle = self._directory(root_relative)
        found: list[Path] = []

        def inspect(path: Path, handle: int, current_relative: Path) -> None:
            before = _win_identity(handle)
            for entry in sorted(os.scandir(path), key=lambda item: item.name):
                if not include_hidden and entry.name.startswith("."):
                    continue
                child_relative = current_relative / entry.name
                if entry.is_symlink():
                    raise OSError("Memory sweep found a symbolic link")
                if entry.is_dir(follow_symlinks=False):
                    child = _win_open(Path(entry.path), directory=True)
                    try:
                        inspect(Path(entry.path), child, child_relative)
                    finally:
                        _win_close(child)
                elif entry.is_file(follow_symlinks=False):
                    if suffix is None or entry.name.endswith(suffix):
                        found.append(child_relative)
                else:
                    raise OSError("Memory sweep found an unsupported file type")
            if _win_identity(handle) != before:
                raise OSError("Memory directory changed during discovery")

        try:
            inspect(root_path, root_handle, root_relative)
        finally:
            _win_close(root_handle)
        if not self.root_is_current():
            raise OSError("workspace root changed during traversal")
        return found

    def list_memory_records(self, relative: str | Path) -> list[Path]:
        return self.list_files(relative, suffix=".md", include_hidden=False)


if os.name == "nt":  # pragma: no cover - selected by native Windows CI
    WorkspaceAnchor = WindowsWorkspaceAnchor
    WorkspaceIdentity = WindowsIdentity
    OwnedFile = WindowsOwnedFile
    OwnedDirectory = WindowsOwnedDirectory
    ReplacementTransaction = WindowsReplacementTransaction
else:
    WorkspaceAnchor = PosixWorkspaceAnchor
    WorkspaceIdentity = PosixIdentity
    OwnedFile = PosixOwnedFile
    OwnedDirectory = PosixOwnedDirectory
    ReplacementTransaction = PosixReplacementTransaction


def windows_publish_receipt(
    workspace: Path,
    event: str,
    content: bytes,
    filename: Any,
) -> WindowsReceiptPublication:
    """Publish a receipt with retained Win32 directory and file handles."""
    if os.name != "nt":
        raise OSError("Win32 receipt publication is unavailable")
    root = _win_open(workspace, directory=True)
    root_identity = _win_identity(root)
    system = receipts = temporary = final = -1
    try:
        system_path = workspace / "System"
        _system_created = _win_create_directory(system_path)
        system = _win_open(system_path, directory=True)
        system_identity = _win_identity(system)
        receipts_path = system_path / "receipts"
        _receipts_created = _win_create_directory(receipts_path)
        receipts = _win_open(receipts_path, directory=True)
        receipts_identity = _win_identity(receipts)
        current_root = _win_open(workspace, directory=True)
        try:
            if not _same_windows_object(_win_identity(current_root), root_identity):
                raise OSError("receipt destination changed during publication")
        finally:
            _win_close(current_root)
        temporary_path = (
            receipts_path / f".apparatus-receipt-{secrets.token_hex(16)}.tmp"
        )
        temporary = _win_open(
            temporary_path, directory=False, create=True, lock_name=False
        )
        _win_write(temporary, content)
        temporary_identity = _win_identity(temporary)
        for collision in range(1, 1_000_000):
            name = filename(collision)
            final_path = receipts_path / name
            try:
                _win_hardlink(final_path, temporary_path)
            except OSError as error:
                if getattr(error, "winerror", error.errno) in {80, 183}:
                    continue
                raise
            verification = _win_open(
                final_path,
                directory=False,
                lock_name=False,
                share_existing_write=True,
            )
            try:
                if _win_identity(verification) != temporary_identity:
                    raise OSError("receipt identity changed during publication")
            finally:
                _win_close(verification)
            _win_delete_handle(temporary)
            _win_close(temporary)
            temporary = -1
            final = _win_open(final_path, directory=False, retain_readable=True)
            if _win_identity(final) != temporary_identity:
                raise OSError("receipt identity changed after publication")
            publication = WindowsReceiptPublication(
                workspace,
                final_path,
                event,
                content,
                temporary_identity,
                root,
                root_identity,
                system,
                system_identity,
                receipts,
                receipts_identity,
                final,
            )
            root = system = receipts = final = -1
            publication.validate()
            return publication
        raise OSError("could not allocate a unique receipt filename")
    finally:
        if temporary >= 0:
            try:
                _win_delete_handle(temporary)
            except OSError:
                pass
            _win_close(temporary)
        _win_close(final)
        # Creation and the retained handle cannot be inseparably tied on every
        # supported Windows filesystem. Empty directories are safer to leave
        # behind than a concurrently substituted entry is to delete.
        _win_close(receipts)
        _win_close(system)
        _win_close(root)
