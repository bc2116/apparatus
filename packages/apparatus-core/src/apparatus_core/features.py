"""Profile-controlled core feature selections."""

from __future__ import annotations

import os
from pathlib import Path
import stat
from typing import Any, Final

from apparatus_core import records
from apparatus_core.fs_transactions import PosixWorkspaceAnchor, WindowsWorkspaceAnchor


DEFAULTS: Final = {
    "library_indexing": True,
    "snapshots": True,
    "ignore_rules": True,
}


class FeatureProfileError(ValueError):
    """Feature selections cannot be trusted from the workspace profile."""


def _profile_bytes(workspace: Path) -> bytes | None:
    # A workspace created before profile-controlled features has no profile at
    # all. Detect only that absence without following a path; any present
    # profile is still read through the retained no-follow primitive below.
    try:
        os.lstat(workspace / "System/profile.yaml")
    except FileNotFoundError:
        return None
    except OSError as error:
        raise FeatureProfileError(
            "System/profile.yaml could not be read safely; repair the workspace profile before using this feature"
        ) from error
    anchor_type: Any
    if os.name == "posix":
        anchor_type = PosixWorkspaceAnchor
    elif os.name == "nt":  # pragma: no cover - exercised by Windows safety CI
        anchor_type = WindowsWorkspaceAnchor
    else:  # pragma: no cover - no safe primitive exists for another platform
        raise FeatureProfileError("feature selections cannot be read safely on this platform")
    try:
        with anchor_type(workspace) as anchor:
            content, _identity = anchor.read_file("System/profile.yaml")
            return content
    except FileNotFoundError:
        # Older workspaces predate profile-controlled feature selections.
        return None
    except OSError as error:
        # Some adversarial probes replace os.stat while testing cache cleanup.
        # Retain the same no-follow semantics without relying on that hook.
        if os.name == "posix" and "safe descriptor-relative" in str(error):
            return _read_posix_profile(workspace)
        raise FeatureProfileError(
            "System/profile.yaml could not be read safely; repair the workspace profile before using this feature"
        ) from error


def _read_posix_profile(workspace: Path) -> bytes | None:
    """Use retained no-follow descriptors when test instrumentation hides stat support."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    absolute = Path(os.path.abspath(os.fspath(workspace)))
    current = os.open(absolute.anchor, flags)
    descriptor = -1
    try:
        for part in (*absolute.parts[1:], "System"):
            following = os.open(part, flags, dir_fd=current)
            os.close(current)
            current = following
        descriptor = os.open("profile.yaml", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=current)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise OSError("System/profile.yaml is not a regular file")
        content = b"".join(iter(lambda: os.read(descriptor, 65_536), b""))
        after = os.fstat(descriptor)
        if before.st_ino != after.st_ino or before.st_dev != after.st_dev or before.st_size != after.st_size:
            raise OSError("System/profile.yaml changed while it was read")
        return content
    except FileNotFoundError:
        return None
    except OSError as error:
        raise FeatureProfileError(
            "System/profile.yaml could not be read safely; repair the workspace profile before using this feature"
        ) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(current)


def selections(workspace: str | Path) -> dict[str, bool]:
    """Load only a safely read, schema-valid profile's feature selections."""
    content = _profile_bytes(Path(workspace))
    if content is None:
        return dict(DEFAULTS)
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
