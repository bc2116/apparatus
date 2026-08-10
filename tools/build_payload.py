#!/usr/bin/env python3
"""Build the deterministic universal Apparatus payload archive."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import io
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import sys
import tempfile
import unicodedata
import zipfile

from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.render import RenderError, is_reparse_path, render_workspace


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
IGNORED_FILE_NAMES = frozenset({".ds_store", "thumbs.db", "desktop.ini"})
_VERSION_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._+-]*[A-Za-z0-9])?")
_PROJECT_HEADER = re.compile(r"^\s*\[project\]\s*(?:#.*)?$")
_TABLE_HEADER = re.compile(r"^\s*\[")
_VERSION_LINE = re.compile(r'^\s*version\s*=\s*(["\'])([^"\']+)\1\s*(?:#.*)?$')
_WINDOWS_INVALID_CHARACTERS = frozenset('<>:"|?*')
_WINDOWS_RESERVED_BASENAMES = frozenset(
    (
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{number}" for number in range(1, 10)),
        *(f"lpt{number}" for number in range(1, 10)),
    )
)


class PayloadBuildError(RuntimeError):
    """The universal payload could not be built safely."""


def read_version(pyproject: Path) -> str:
    """Read the project version without adding a TOML dependency on Python 3.10."""
    try:
        lines = pyproject.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise PayloadBuildError("could not read the apparatus-core package metadata") from error

    in_project = False
    for line in lines:
        if _PROJECT_HEADER.match(line):
            in_project = True
            continue
        if in_project and _TABLE_HEADER.match(line):
            break
        if in_project:
            match = _VERSION_LINE.match(line)
            if match:
                return validate_version(match.group(2))
    raise PayloadBuildError("apparatus-core package metadata has no project version")


def validate_version(version: str) -> str:
    """Keep the override safe and portable as part of an archive filename."""
    if not _VERSION_PATTERN.fullmatch(version):
        raise PayloadBuildError(
            "version must contain only letters, numbers, dots, plus signs, hyphens, and underscores"
        )
    return version


def _portable_key(path: str) -> tuple[str, ...]:
    return tuple(
        unicodedata.normalize("NFC", component).casefold()
        for component in PurePosixPath(path).parts
    )


def reject_portable_collisions(paths: tuple[str, ...]) -> None:
    """Reject names that alias under supported case and Unicode semantics."""
    seen: dict[tuple[str, ...], str] = {}
    for path in paths:
        key = _portable_key(path)
        conflict = next(
            (
                original
                for other, original in seen.items()
                if key == other
                or key[: len(other)] == other
                or other[: len(key)] == key
            ),
            None,
        )
        if conflict is not None:
            raise PayloadBuildError(
                f"archive paths {conflict!r} and {path!r} conflict on a supported platform"
            )
        seen[key] = path


def _is_windows_reserved(component: str) -> bool:
    is_reserved = getattr(PureWindowsPath(component), "is_reserved", None)
    if callable(is_reserved) and is_reserved():
        return True
    return component.split(".", 1)[0].casefold() in _WINDOWS_RESERVED_BASENAMES


def validate_archive_path(path: str) -> str:
    """Return a normalized path that is safe on every supported platform."""
    pure = PurePosixPath(path)
    windows = PureWindowsPath(path)
    if (
        not path
        or "\\" in path
        or pure.is_absolute()
        or bool(windows.drive)
        or pure.as_posix() != path
        or any(component in {"", ".", ".."} for component in pure.parts)
    ):
        raise PayloadBuildError(f"archive path {path!r} is not normalized")
    for component in pure.parts:
        if (
            component.endswith((".", " "))
            or any(
                ord(character) < 32 or character in _WINDOWS_INVALID_CHARACTERS
                for character in component
            )
            or _is_windows_reserved(component)
        ):
            raise PayloadBuildError(f"archive path {path!r} is not portable")
    return path


def _is_ignored(name: str) -> bool:
    folded = name.casefold()
    return folded == "__pycache__" or folded in IGNORED_FILE_NAMES


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns


def _source_files(root: Path, archive_root: str) -> tuple[tuple[Path, str], ...]:
    """Enumerate source files through a retained, no-follow parent anchor."""
    if is_reparse_path(root):
        raise PayloadBuildError(f"starter {archive_root} tree must not be a symbolic link")
    if not root.is_dir():
        raise PayloadBuildError(f"starter {archive_root} tree is missing")
    try:
        root = root.parent.resolve(strict=True) / root.name
        with WorkspaceAnchor(root.parent) as anchor:
            return _anchored_source_files(anchor, root, archive_root)
    except OSError as error:
        raise PayloadBuildError(
            f"could not safely enumerate starter {archive_root} tree"
        ) from error


def _anchored_source_files(
    anchor: WorkspaceAnchor, root: Path, archive_root: str
) -> tuple[tuple[Path, str], ...]:
    anchored_root = Path(root.name)
    relative_files = anchor.list_files(anchored_root)
    files: list[tuple[Path, str]] = []
    for anchored_path in relative_files:
        relative = anchored_path.relative_to(anchored_root)
        if any(_is_ignored(part) for part in relative.parts):
            continue
        archive_path = validate_archive_path(f"{archive_root}/{relative.as_posix()}")
        files.append((root / relative, archive_path))
    files.sort(key=lambda item: item[1])
    reject_portable_collisions(tuple(archive_path for _source, archive_path in files))
    return tuple(files)


def _copy_tree(source: Path, destination: Path, archive_root: str) -> None:
    for archive_path, content in _capture_source_files(source, archive_root):
        relative = PurePosixPath(archive_path).relative_to(archive_root)
        target = destination.joinpath(*relative.parts)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        except OSError as error:
            raise PayloadBuildError(f"could not stage starter path {archive_path!r}") from error


def _capture_source_files(root: Path, archive_root: str) -> tuple[tuple[str, bytes], ...]:
    """Capture enumerated regular files through retained, no-follow ownership."""
    if is_reparse_path(root):
        raise PayloadBuildError(f"starter {archive_root} tree must not be a symbolic link")
    if not root.is_dir():
        raise PayloadBuildError(f"starter {archive_root} tree is missing")
    try:
        root = root.parent.resolve(strict=True) / root.name
        with WorkspaceAnchor(root.parent) as anchor:
            enumerated = _anchored_source_files(anchor, root, archive_root)
            captured: list[tuple[str, bytes]] = []
            for source, archive_path in enumerated:
                relative = source.relative_to(root)
                before = os.lstat(source)
                owned = anchor.capture_file(Path(root.name) / relative)
                try:
                    identity = owned.identity
                    after = os.lstat(source)
                    posix_identity_matches = not hasattr(identity, "device") or (
                        identity.device,
                        identity.inode,
                    ) == (before.st_dev, before.st_ino)
                    if (
                        not stat.S_ISREG(before.st_mode)
                        or is_reparse_path(source)
                        or _stat_identity(before) != _stat_identity(after)
                        or not posix_identity_matches
                        or len(owned.content) != before.st_size
                    ):
                        raise OSError("starter source changed while it was captured")
                    captured.append((archive_path, owned.content))
                finally:
                    owned.close()
            if not anchor.root_is_current():
                raise OSError("starter source tree changed while it was captured")
            return tuple(captured)
    except OSError as error:
        raise PayloadBuildError(f"could not safely capture starter {archive_root} tree") from error


def archive_timestamp(environ: Mapping[str, str] = os.environ) -> tuple[int, ...]:
    """Resolve the fixed ZIP timestamp in UTC at ZIP's two-second precision."""
    raw = environ.get("SOURCE_DATE_EPOCH")
    if raw is None:
        return DEFAULT_TIMESTAMP
    try:
        epoch = int(raw)
        value = datetime.fromtimestamp(epoch, timezone.utc).replace(tzinfo=None)
    except (OverflowError, OSError, ValueError) as error:
        raise PayloadBuildError("SOURCE_DATE_EPOCH must be an integer ZIP-range timestamp") from error
    if not datetime(1980, 1, 1) <= value <= datetime(2107, 12, 31, 23, 59, 58):
        raise PayloadBuildError("SOURCE_DATE_EPOCH is outside the ZIP timestamp range")
    value = value.replace(second=value.second - value.second % 2, microsecond=0)
    return value.timetuple()[:6]


def _manifest(version: str, files: tuple[tuple[str, bytes], ...]) -> bytes:
    lines = [f"version: {version}"]
    lines.extend(f"{hashlib.sha256(content).hexdigest()}  {path}" for path, content in files)
    return ("\n".join(lines) + "\n").encode("utf-8")


def _zip_info(path: str, timestamp: tuple[int, ...]) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=timestamp)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    return info


def _same_directory(requested: Path, canonical: Path) -> bool:
    try:
        return not is_reparse_path(requested) and os.path.samefile(requested, canonical)
    except OSError:
        return False


def _write_archive(
    output: Path,
    files: tuple[tuple[str, bytes], ...],
    version: str,
    timestamp: tuple[int, ...],
) -> None:
    entries = tuple(sorted(files, key=lambda item: item[0]))
    manifest = _manifest(version, entries)
    archive_entries = tuple(sorted((*entries, ("manifest.txt", manifest)), key=lambda item: item[0]))
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        publication_parent = output.parent.resolve(strict=True)
        if not _same_directory(output.parent, publication_parent):
            raise OSError("payload output directory is not a stable regular directory")
        serialized = io.BytesIO()
        with zipfile.ZipFile(serialized, "w") as archive:
            for path, content in archive_entries:
                archive.writestr(_zip_info(path, timestamp), content)
        content = serialized.getvalue()
        with WorkspaceAnchor(publication_parent) as anchor:
            try:
                current = anchor.capture_file(output.name)
            except FileNotFoundError:
                created = anchor.create_file(output.name, content, mode=0o644)
                try:
                    if not (
                        anchor.matches_owned(created)
                        and _same_directory(output.parent, publication_parent)
                    ):
                        try:
                            anchor.unlink_owned(created)
                        except OSError:
                            pass
                        raise OSError("payload archive changed during publication")
                finally:
                    created.close()
            else:
                try:
                    transaction = anchor.replace_if_unchanged(
                        output.name,
                        current.identity,
                        current.content,
                        content,
                    )
                    try:
                        transaction.validate_commit()
                        if not _same_directory(output.parent, publication_parent):
                            raise OSError("payload output directory changed during publication")
                        transaction.commit()
                    except Exception:
                        transaction.rollback()
                        raise
                    finally:
                        transaction.close()
                finally:
                    current.close()
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        raise PayloadBuildError(f"could not write payload archive to {output}") from error


def build_payload(
    output_directory: Path,
    *,
    version: str | None = None,
    repo_root: Path = REPO_ROOT,
    environ: Mapping[str, str] = os.environ,
) -> tuple[Path, tuple[str, ...]]:
    """Stage, render, and publish one universal payload archive."""
    selected_version = validate_version(version) if version is not None else read_version(
        repo_root / "packages" / "apparatus-core" / "pyproject.toml"
    )
    payload_source = repo_root / "starter" / "payload"
    profiles_source = repo_root / "starter" / "profiles"
    with tempfile.TemporaryDirectory(prefix="apparatus-payload-") as temporary_name:
        stage = Path(temporary_name)
        staged_payload = stage / "payload"
        staged_profiles = stage / "profiles"
        staged_payload.mkdir()
        staged_profiles.mkdir()
        _copy_tree(payload_source, staged_payload, "payload")
        _copy_tree(profiles_source, staged_profiles, "profiles")
        try:
            rendered = render_workspace(staged_payload)
        except RenderError as error:
            raise PayloadBuildError(f"could not render staged payload shims: {error}") from error

        drift = tuple(sorted(f"payload/{target}" for target in rendered.written))
        archive_files = _capture_source_files(
            staged_payload, "payload"
        ) + _capture_source_files(staged_profiles, "profiles")
        output = output_directory / f"apparatus-payload-{selected_version}.zip"
        _write_archive(output, archive_files, selected_version, archive_timestamp(environ))
    return output, drift


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="override the apparatus-core package version")
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "dist",
        help="output directory (default: repository dist/)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        output, drift = build_payload(args.out, version=args.version)
    except PayloadBuildError as error:
        print(f"build_payload: {error}", file=sys.stderr)
        return 2
    for path in drift:
        print(f"warning: committed shim differs from fresh render: {path}", file=sys.stderr)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
