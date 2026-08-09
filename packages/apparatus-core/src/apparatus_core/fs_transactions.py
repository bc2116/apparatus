"""Small platform primitives for containment-safe filesystem transactions."""

from __future__ import annotations

import ctypes
import os
import secrets
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
) -> int:
    kernel = _win_kernel()
    access = _GENERIC_READ
    if not directory or delete_access:
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

    def close(self) -> None:
        if self.handle >= 0:
            _win_close(self.handle)
            self.handle = -1
        if self.parent >= 0:
            _win_close(self.parent)
            self.parent = -1


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
        self.workspace = workspace
        self._root = _win_open(workspace, directory=True)
        self._root_identity = _win_identity(self._root)
        self._chain_handles: list[int] = []

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

    def _directory(self, relative: str | Path) -> tuple[Path, int]:
        current_path = self.workspace
        current = -1
        try:
            if not _same_windows_object(_win_identity(self._root), self._root_identity):
                raise OSError("workspace root changed")
            parts = _safe_parts(relative)
            for part in parts:
                following_path = current_path / part
                following = _win_open(following_path, directory=True)
                if current >= 0:
                    self._chain_handles.append(current)
                current = following
                current_path = following_path
            return current_path, current
        except Exception:
            _win_close(current)
            raise

    def _parent(self, relative: str | Path) -> tuple[Path, int, str]:
        parts = _safe_parts(relative)
        if len(parts) == 1:
            parent_path = self.workspace
            parent = _win_open(parent_path, directory=True)
            if not _same_windows_object(_win_identity(parent), self._root_identity):
                _win_close(parent)
                raise OSError("workspace root changed")
            return parent_path, parent, parts[0]
        parent_path, parent = self._directory(Path(*parts[:-1]))
        return parent_path, parent, parts[-1]

    def require_directory(self, relative: str | Path) -> None:
        _path, handle = self._directory(relative)
        _win_close(handle)

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
        parent_path, parent, name = self._parent(relative)
        try:
            content, identity, handle = self._read_locked(parent_path / name)
            _win_close(handle)
            return content, identity
        finally:
            _win_close(parent)

    def _parent_is_current(self, relative: Path, parent: int) -> bool:
        current = -1
        try:
            _path, current, _name = self._parent(relative)
            return _same_windows_object(_win_identity(current), _win_identity(parent))
        except OSError:
            return False
        finally:
            _win_close(current)

    def create_file(
        self, relative: str | Path, content: bytes, mode: int = 0o600
    ) -> WindowsOwnedFile:
        del mode
        parent_path, parent, name = self._parent(relative)
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
                Path(relative), parent, path, identity, content, verification
            )
            verification = -1
            if not self._parent_is_current(Path(relative), parent):
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

    def capture_file(self, relative: str | Path) -> WindowsOwnedFile:
        parent_path, parent, name = self._parent(relative)
        try:
            content, identity, handle = self._read_locked(parent_path / name)
            return WindowsOwnedFile(
                Path(relative), parent, parent_path / name, identity, content, handle
            )
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
        if not self._matches_owned(owned):
            raise OSError("owned workspace file changed before cleanup")
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

    def list_memory_records(self, relative: str | Path) -> list[Path]:
        root_relative = Path(relative)
        root_path, root_handle = self._directory(root_relative)
        found: list[Path] = []

        def inspect(path: Path, handle: int, current_relative: Path) -> None:
            before = _win_identity(handle)
            for entry in sorted(os.scandir(path), key=lambda item: item.name):
                if entry.name.startswith("."):
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
                    if entry.name.endswith(".md"):
                        found.append(child_relative)
                else:
                    raise OSError("Memory sweep found an unsupported file type")
            if _win_identity(handle) != before:
                raise OSError("Memory directory changed during discovery")

        try:
            inspect(root_path, root_handle, root_relative)
        finally:
            _win_close(root_handle)
        return found


def windows_publish_receipt(
    workspace: Path,
    event: str,
    content: bytes,
    filename: Any,
) -> Path:
    """Publish a receipt with retained Win32 directory and file handles."""
    del event
    if os.name != "nt":
        raise OSError("Win32 receipt publication is unavailable")
    root = _win_open(workspace, directory=True)
    root_identity = _win_identity(root)
    system = receipts = temporary = -1
    try:
        system_path = workspace / "System"
        _system_created = _win_create_directory(system_path)
        system = _win_open(system_path, directory=True)
        receipts_path = system_path / "receipts"
        _receipts_created = _win_create_directory(receipts_path)
        receipts = _win_open(receipts_path, directory=True)
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
            final = _win_open(
                final_path,
                directory=False,
                lock_name=False,
                share_existing_write=True,
            )
            try:
                if _win_identity(final) != temporary_identity:
                    raise OSError("receipt identity changed during publication")
            finally:
                _win_close(final)
            _win_delete_handle(temporary)
            _win_close(temporary)
            temporary = -1
            final = _win_open(final_path, directory=False)
            try:
                if _win_identity(final) != temporary_identity:
                    raise OSError("receipt identity changed after publication")
            finally:
                _win_close(final)
            return final_path
        raise OSError("could not allocate a unique receipt filename")
    finally:
        if temporary >= 0:
            try:
                _win_delete_handle(temporary)
            except OSError:
                pass
            _win_close(temporary)
        # Creation and the retained handle cannot be inseparably tied on every
        # supported Windows filesystem. Empty directories are safer to leave
        # behind than a concurrently substituted entry is to delete.
        _win_close(receipts)
        _win_close(system)
        _win_close(root)
