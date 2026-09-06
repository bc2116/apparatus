"""Profile-controlled core feature selections."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import stat
from typing import Callable, Final

from apparatus_core import fs_transactions, records
from apparatus_core.fs_transactions import WindowsWorkspaceAnchor
from apparatus_core.payload import PayloadError, preflight_workspace_paths


DEFAULTS: Final = {
    "library_indexing": True,
    "snapshots": True,
    "ignore_rules": True,
}


class FeatureProfileError(ValueError):
    """Feature selections cannot be trusted from the workspace profile."""


@dataclass(frozen=True)
class _ProfileRead:
    """One retained profile and the proof that its pathname is still current."""

    content: bytes
    current: Callable[[], bool]


def _profile_bytes(workspace: Path) -> bytes | None:
    """Read the profile bytes through the platform's safe retained primitive."""
    profile = _profile_read(workspace)
    return None if profile is None else profile.content


def _profile_read(workspace: Path) -> _ProfileRead | None:
    # Resolve only external ancestors (for example macOS /var). The final
    # workspace component remains a no-follow boundary. Reuse this canonical
    # path for the retained read and every post-parse currentness check.
    try:
        workspace = preflight_workspace_paths(workspace)
    except (OSError, PayloadError) as error:
        raise FeatureProfileError(
            "System/profile.yaml could not be read safely; repair the workspace profile before using this feature"
        ) from error
    if os.name == "posix":
        return _read_posix_profile(workspace)
    elif os.name == "nt":  # pragma: no cover - exercised by Windows safety CI
        return _read_windows_profile(workspace)
    else:  # pragma: no cover - no safe primitive exists for another platform
        raise FeatureProfileError("feature selections cannot be read safely on this platform")


def _read_windows_profile(workspace: Path) -> _ProfileRead | None:
    """Read a profile through retained Windows handles and prove its pathname is current."""
    try:
        with WindowsWorkspaceAnchor(workspace) as anchor:
            # The directory check keeps a present System from being treated
            # as absent; pre-profile workspaces still use compatibility
            # defaults when the whole profile path is missing.
            anchor.require_directory("System")
            try:
                owned = anchor.capture_file("System/profile.yaml")
            except FileNotFoundError:
                return None
            try:
                root_identity = anchor._root_identity
                system_identity = fs_transactions._win_identity(owned.parent)
                # ``capture_file`` retains the file and parent handles.  The
                # second proof makes the read fail closed if any current
                # workspace/System/profile.yaml pathname no longer names that
                # exact root, parent, identity, and content before a selection
                # can be used.
                if not anchor.matches_owned(owned):
                    raise OSError("System/profile.yaml changed while it was read")
                return _ProfileRead(
                    owned.content,
                    lambda: _windows_profile_is_current(
                        workspace,
                        root_identity,
                        system_identity,
                        owned.identity,
                        owned.content,
                    ),
                )
            finally:
                owned.close()
    except FileNotFoundError:
        # Feature selections were added after the standalone snapshot and
        # Library commands.  A workspace that has not been initialized yet
        # retains their all-enabled compatibility behavior.
        return None
    except OSError as error:
        raise FeatureProfileError(
            "System/profile.yaml could not be read safely; repair the workspace profile before using this feature"
        ) from error


def _windows_profile_is_current(
    workspace: Path,
    root_identity: fs_transactions.WindowsIdentity,
    system_identity: fs_transactions.WindowsIdentity,
    profile_identity: fs_transactions.WindowsIdentity,
    content: bytes,
) -> bool:
    """Recheck the original Windows root, System, and profile after parsing."""
    try:
        with WindowsWorkspaceAnchor(workspace) as anchor:
            if not fs_transactions._same_windows_object(
                anchor._root_identity, root_identity
            ):
                return False
            anchor.require_directory("System")
            owned = anchor.capture_file("System/profile.yaml")
            try:
                return (
                    fs_transactions._same_windows_object(
                        fs_transactions._win_identity(owned.parent), system_identity
                    )
                    and owned.identity == profile_identity
                    and owned.content == content
                    and anchor.matches_owned(owned)
                )
            finally:
                owned.close()
    except OSError:
        return False


def _posix_directory_flags() -> int:
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise OSError("safe descriptor-relative workspace operations are unavailable")
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _open_posix_workspace(workspace: Path) -> int:
    """Open the absolute workspace path without following any component."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    absolute = Path(os.path.abspath(os.fspath(workspace)))
    if not absolute.is_absolute() or not absolute.anchor:
        raise OSError("workspace path must be absolute")
    current = os.open(absolute.anchor, flags)
    try:
        for part in absolute.parts[1:]:
            following = os.open(part, flags, dir_fd=current)
            os.close(current)
            current = following
        return current
    except Exception:
        os.close(current)
        raise


def _read_posix_regular(parent: int, name: str) -> tuple[bytes, tuple[int, int, int, int]]:
    """Read one regular file without ever allowing a FIFO open to block."""
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0),
        dir_fd=parent,
    )
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise OSError("System/profile.yaml is not a regular file")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 65_536):
            chunks.append(chunk)
        after = os.fstat(descriptor)
        identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        if identity != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise OSError("System/profile.yaml changed while it was read")
        content = b"".join(chunks)
        if len(content) != after.st_size:
            raise OSError("System/profile.yaml changed while it was read")
        return content, identity
    finally:
        os.close(descriptor)


def _posix_profile_is_current(
    workspace: Path,
    root_identity: tuple[int, int],
    system_identity: tuple[int, int],
    profile_identity: tuple[int, int, int, int],
    content: bytes,
) -> bool:
    """Prove the retained profile still names current workspace/System/profile.yaml."""
    root = system = -1
    try:
        root = _open_posix_workspace(workspace)
        root_status = os.fstat(root)
        if (root_status.st_dev, root_status.st_ino) != root_identity:
            return False
        system = os.open("System", _posix_directory_flags(), dir_fd=root)
        system_status = os.fstat(system)
        if (system_status.st_dev, system_status.st_ino) != system_identity:
            return False
        current, current_identity = _read_posix_regular(system, "profile.yaml")
        return current_identity == profile_identity and current == content
    except OSError:
        return False
    finally:
        if system >= 0:
            os.close(system)
        if root >= 0:
            os.close(root)


def _read_posix_profile(workspace: Path) -> _ProfileRead | None:
    """Use retained no-follow descriptors and verify all current path components."""
    root = system = -1
    try:
        root = _open_posix_workspace(workspace)
        root_status = os.fstat(root)
        root_identity = (root_status.st_dev, root_status.st_ino)
        system = os.open("System", _posix_directory_flags(), dir_fd=root)
        system_status = os.fstat(system)
        system_identity = (system_status.st_dev, system_status.st_ino)
        try:
            content, profile_identity = _read_posix_regular(system, "profile.yaml")
        except FileNotFoundError:
            return None
        if not _posix_profile_is_current(
            workspace, root_identity, system_identity, profile_identity, content
        ):
            raise OSError("System/profile.yaml changed while it was read")
        return _ProfileRead(
            content,
            lambda: _posix_profile_is_current(
                workspace, root_identity, system_identity, profile_identity, content
            ),
        )
    except FileNotFoundError:
        # Pre-profile workspaces may have neither System nor profile.yaml.
        # A later pathname disappearance after a retained read is caught by
        # the currentness proof above and never reaches this compatibility
        # path.
        return None
    except OSError as error:
        raise FeatureProfileError(
            "System/profile.yaml could not be read safely; repair the workspace profile before using this feature"
        ) from error
    finally:
        if system >= 0:
            os.close(system)
        if root >= 0:
            os.close(root)


def selections(workspace: str | Path) -> dict[str, bool]:
    """Load only a safely read, schema-valid profile's feature selections."""
    profile = _profile_read(Path(workspace))
    if profile is None:
        return dict(DEFAULTS)
    content = profile.content
    try:
        data = records.yaml.safe_load(content.decode("utf-8"))
    except UnicodeError as error:
        raise FeatureProfileError(
            "System/profile.yaml must be valid UTF-8 YAML before using this feature"
        ) from error
    except records.yaml.YAMLError as error:
        raise FeatureProfileError(
            "System/profile.yaml must be valid YAML before using this feature"
        ) from error
    if not isinstance(data, dict):
        raise FeatureProfileError("System/profile.yaml must be a YAML mapping before using this feature")
    problems = records.validate("profile", data, filename="profile.yaml")
    if problems:
        raise FeatureProfileError(
            "System/profile.yaml is invalid; repair it before using this feature"
        )
    values = data.get("features")
    # Parsing is deliberately side-effect free. Before returning a choice,
    # prove that the exact profile retained above still names the current
    # workspace/System/profile.yaml through its current parent and root.
    if not profile.current():
        raise FeatureProfileError(
            "System/profile.yaml could not be read safely; repair the workspace profile before using this feature"
        )
    if values is None:
        return dict(DEFAULTS)
    # Schema validation above guarantees this mapping is complete and boolean.
    return {name: values[name] for name in DEFAULTS}


def enabled(workspace: str | Path, feature: str) -> bool:
    """Return one selection; defaults apply only to a valid omitted mapping."""
    if feature not in DEFAULTS:
        raise ValueError(f"unknown feature selection: {feature}")
    return selections(workspace)[feature]


def off_receipt_fields(feature: str, *, operation: str | None = None) -> dict[str, str]:
    """Render the durable, plain-language outcome for a disabled feature."""
    body = "Outcome: this feature is off; say the word and I'll enable it.\n"
    if operation is not None:
        body = f"Operation: {operation}.\n" + body
    return {
        "summary": f"{feature.replace('_', ' ').capitalize()} is off.",
        "body": body,
    }
