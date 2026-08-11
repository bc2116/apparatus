"""Starter-payload discovery and contained deployment helpers."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
import os
from pathlib import Path, PurePosixPath
from typing import Iterable


class PayloadError(ValueError):
    """A starter payload cannot safely be used for workspace deployment."""


def _embedded_starter_path(*parts: str) -> Path:
    """Resolve committed package data for ordinary filesystem installations."""
    try:
        resource = resources.files("apparatus_core").joinpath("starter", *parts)
        value = os.fspath(resource)
    except (ModuleNotFoundError, TypeError) as error:
        raise PayloadError(
            "embedded starter package data is unavailable as a filesystem resource"
        ) from error
    return _absolute_without_resolving(Path(value))


def shipped_payload() -> Path:
    """Return the payload committed inside the installed apparatus-core package."""
    return _embedded_starter_path("payload")


def shipped_profiles_manifest() -> Path:
    """Return the embedded profiles manifest paired with the shipped payload."""
    return _embedded_starter_path("profiles", "profiles.yaml")


def _absolute_without_resolving(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _path_components(path: Path) -> tuple[Path, ...]:
    absolute = _absolute_without_resolving(path)
    current = Path(absolute.anchor)
    components: list[Path] = []
    for part in absolute.parts[1:]:
        current /= part
        components.append(current)
    return tuple(components)


def canonical_source_directory(path: str | Path, description: str) -> Path:
    """Canonicalize external ancestors while rejecting a direct source link."""
    absolute = _absolute_without_resolving(Path(path))
    if absolute.is_symlink():
        raise PayloadError(f"{description} must not be a symbolic link")
    canonical = absolute.resolve(strict=False)
    if not canonical.is_dir():
        raise PayloadError(f"{description} is not a directory")
    return canonical


def canonical_source_file(path: str | Path, description: str) -> Path:
    """Canonicalize external ancestors while rejecting a final file link."""
    absolute = _absolute_without_resolving(Path(path))
    if absolute.is_symlink():
        raise PayloadError(f"{description} must not be a symbolic link")
    canonical = absolute.resolve(strict=False)
    if not canonical.is_file():
        raise PayloadError(f"{description} is not a file")
    return canonical


def resolve_payload(value: str | Path | None) -> Path:
    """Resolve an explicit payload or the installed package's embedded payload."""
    payload = Path(value) if value is not None else shipped_payload()
    try:
        return canonical_source_directory(payload, "payload source path")
    except PayloadError as error:
        if "not a directory" not in str(error):
            raise
        raise PayloadError(f"payload source was not found at {payload}")


def resolve_profiles_manifest(payload: str | Path) -> Path:
    """Prefer a custom payload's sibling manifest, then use the shipped one."""
    payload_path = canonical_source_directory(payload, "payload source path")
    bundle = payload_path.parent
    sibling = bundle
    for component in ("profiles", "profiles.yaml"):
        sibling /= component
        if sibling.is_symlink():
            relative = sibling.relative_to(bundle).as_posix()
            raise PayloadError(
                f"profiles manifest component {relative!r} must not be a symbolic link"
            )
    if sibling.is_file():
        return canonical_source_file(sibling, "profiles manifest path")
    shipped = shipped_profiles_manifest()
    if shipped.is_symlink():
        raise PayloadError("profiles manifest must not be a symbolic link")
    if not shipped.is_file():
        raise PayloadError(
            "profiles manifest was not found beside the payload or in embedded package data"
        )
    return canonical_source_file(shipped, "profiles manifest path")


def reject_source_entry_symlinks(payload: str | Path) -> None:
    """Reject symlinks anywhere in the payload tree without traversing them."""
    root = canonical_source_directory(payload, "payload source path")

    def inspection_failed(_error: OSError) -> None:
        raise PayloadError("payload source could not be inspected")

    for directory, directory_names, file_names in os.walk(
        root, topdown=True, followlinks=False, onerror=inspection_failed
    ):
        directory_names.sort()
        file_names.sort()
        parent = Path(directory)
        for name in (*directory_names, *file_names):
            entry = parent / name
            if entry.is_symlink():
                relative = entry.relative_to(root).as_posix()
                raise PayloadError(
                    f"payload source entry {relative!r} must not be a symbolic link"
                )


def reject_payload_workspace_overlap(payload: str | Path, workspace: str | Path) -> None:
    """Reject equality and either ancestor relationship after path resolution."""
    source = Path(payload).resolve()
    target = Path(workspace).resolve(strict=False)
    if source == target or source in target.parents or target in source.parents:
        raise PayloadError("payload source and workspace must not overlap")


@dataclass(frozen=True)
class PayloadFile:
    """One pre-read, non-managed payload file."""

    relative: Path
    content: bytes


@dataclass(frozen=True)
class PayloadPlan:
    """The validated payload operations safe to deploy."""

    directories: tuple[Path, ...]
    files: tuple[PayloadFile, ...]
    placeholders: tuple[Path, ...]


def _safe_source_bytes(path: Path, relative: Path) -> bytes:
    try:
        return path.read_bytes()
    except (OSError, UnicodeError) as error:
        raise PayloadError(
            f"payload source entry {relative.as_posix()!r} could not be read"
        ) from error


def plan_payload_deployment(
    payload: str | Path,
    managed_paths: Iterable[str],
    workspace: str | Path,
) -> PayloadPlan:
    """Read sources and fix exact generic target operations before mutation."""
    root = canonical_source_directory(payload, "payload source path")
    reject_source_entry_symlinks(root)
    managed = set(managed_paths) | {"System/profile.yaml"}
    directories: list[Path] = []
    files: list[PayloadFile] = []
    placeholders: list[Path] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root)
        relative_text = relative.as_posix()
        if path.is_dir():
            directories.append(relative)
        elif path.is_file():
            if relative.name == ".gitkeep":
                placeholders.append(relative)
            elif relative_text not in managed:
                files.append(PayloadFile(relative, _safe_source_bytes(path, relative)))
        else:
            raise PayloadError(f"payload source entry {relative_text!r} is not a regular file")
    plan = PayloadPlan(
        directories=tuple(directories),
        files=tuple(files),
        placeholders=tuple(placeholders),
    )
    preflight_payload_deployment(workspace, plan)
    return plan


def normalize_workspace_relative(value: str | Path) -> Path:
    """Return one normalized relative operation path or fail closed."""
    raw = str(value).replace("\\", "/")
    path = PurePosixPath(raw)
    if (
        path.is_absolute()
        or path.as_posix() != raw
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise PayloadError(f"workspace operation path {str(value)!r} is not normalized")
    return Path(*path.parts)


def _workspace_root_preflight(workspace: Path) -> Path:
    """Canonicalize external ancestors, then establish the workspace boundary."""
    absolute = _absolute_without_resolving(workspace)
    if absolute.is_symlink():
        raise PayloadError("workspace path '.' must not be a symbolic link")
    canonical = absolute.resolve(strict=False)
    if canonical.exists() and not canonical.is_dir():
        raise PayloadError("workspace path '.' must be a directory")
    return canonical


def _check_destination(workspace: Path, relative: Path, expected: str) -> None:
    current = workspace
    parts = relative.parts
    for index, part in enumerate(parts):
        current /= part
        display = Path(*parts[: index + 1]).as_posix()
        if current.is_symlink():
            raise PayloadError(f"workspace path {display!r} must not be a symbolic link")
        if index < len(parts) - 1:
            if current.exists() and not current.is_dir():
                raise PayloadError(f"workspace path {display!r} must be a directory")
            continue
        if current.exists() and expected == "directory" and not current.is_dir():
            raise PayloadError(f"workspace path {display!r} must be a directory")
        if current.exists() and expected == "file" and not current.is_file():
            raise PayloadError(f"workspace path {display!r} must be a file")


def _reject_tree_symlinks(path: Path, workspace: Path) -> None:
    if not path.exists():
        return

    def inspection_failed(_error: OSError) -> None:
        raise PayloadError("workspace snapshot store could not be inspected")

    for directory, directory_names, file_names in os.walk(
        path, topdown=True, followlinks=False, onerror=inspection_failed
    ):
        directory_names.sort()
        file_names.sort()
        parent = Path(directory)
        for name in (*directory_names, *file_names):
            entry = parent / name
            if entry.is_symlink():
                relative = entry.relative_to(workspace).as_posix()
                raise PayloadError(f"workspace path {relative!r} must not be a symbolic link")


def preflight_workspace_paths(
    workspace: str | Path,
    *,
    directories: Iterable[str | Path] = (),
    files: Iterable[str | Path] = (),
    inspect_git_store: bool = False,
) -> Path:
    """Validate every destination and ancestor before the first mutation."""
    root = _workspace_root_preflight(Path(workspace))
    expected: dict[Path, str] = {}
    for value, kind in (
        *((value, "directory") for value in directories),
        *((value, "file") for value in files),
    ):
        relative = normalize_workspace_relative(value)
        previous = expected.get(relative)
        if previous is not None and previous != kind:
            raise PayloadError(
                f"workspace path {relative.as_posix()!r} has conflicting operation types"
            )
        expected[relative] = kind
    for relative in expected:
        for parent in relative.parents:
            if parent == Path("."):
                break
            if expected.get(parent) == "file":
                raise PayloadError(
                    f"workspace path {parent.as_posix()!r} cannot be both a file and an ancestor"
                )
    for relative, kind in sorted(expected.items(), key=lambda item: item[0].as_posix()):
        _check_destination(root, relative, kind)
    if inspect_git_store:
        _reject_tree_symlinks(root / ".git", root)
    return root


def _normalized_payload_entries(
    plan: PayloadPlan,
) -> tuple[tuple[Path, ...], tuple[PayloadFile, ...], tuple[Path, ...]]:
    directories: list[Path] = []
    directory_set: set[Path] = set()
    for value in plan.directories:
        relative = normalize_workspace_relative(value)
        if relative in directory_set:
            raise PayloadError(f"payload plan repeats directory {relative.as_posix()!r}")
        directory_set.add(relative)
        directories.append(relative)

    files: list[PayloadFile] = []
    file_set: set[Path] = set()
    for entry in plan.files:
        if not isinstance(entry, PayloadFile) or not isinstance(entry.content, bytes):
            raise PayloadError("payload plan file content must be bytes")
        relative = normalize_workspace_relative(entry.relative)
        if relative in file_set:
            raise PayloadError(f"payload plan repeats file {relative.as_posix()!r}")
        file_set.add(relative)
        files.append(PayloadFile(relative, entry.content))

    placeholders: list[Path] = []
    placeholder_set: set[Path] = set()
    for value in plan.placeholders:
        relative = normalize_workspace_relative(value)
        if relative.name != ".gitkeep":
            raise PayloadError(
                f"payload placeholder path {relative.as_posix()!r} must end in .gitkeep"
            )
        if relative in placeholder_set:
            raise PayloadError(f"payload plan repeats placeholder {relative.as_posix()!r}")
        placeholder_set.add(relative)
        placeholders.append(relative)

    overlap = file_set.intersection(placeholder_set)
    if overlap:
        relative = min(overlap, key=lambda item: item.as_posix())
        raise PayloadError(
            f"payload plan cannot copy and remove {relative.as_posix()!r}"
        )
    return tuple(directories), tuple(files), tuple(placeholders)


def preflight_payload_deployment(workspace: str | Path, plan: PayloadPlan) -> Path:
    """Preflight generic deployment operations as a standalone safety boundary."""
    directories, files, placeholders = _normalized_payload_entries(plan)
    file_paths = (*placeholders, *(entry.relative for entry in files))
    return preflight_workspace_paths(
        workspace,
        directories=directories,
        # A payload-defined placeholder is the only .gitkeep init may remove.
        # Treat it as a file destination so a directory collision fails closed.
        files=file_paths,
    )


def deploy_missing_payload_files(
    payload: str | Path, workspace: str | Path, plan: PayloadPlan
) -> tuple[str, ...]:
    """Create required directories and copy only missing, non-managed files."""
    directories, files, placeholders = _normalized_payload_entries(plan)
    source_root = canonical_source_directory(payload, "payload source path")
    reject_source_entry_symlinks(source_root)
    for relative in directories:
        if not (source_root / relative).is_dir():
            raise PayloadError(
                f"payload plan directory {relative.as_posix()!r} is not in the payload"
            )
    for entry in files:
        source = source_root / entry.relative
        if (
            not source.is_file()
            or _safe_source_bytes(source, entry.relative) != entry.content
        ):
            raise PayloadError(
                f"payload plan file {entry.relative.as_posix()!r} no longer matches the payload"
            )
    for relative in placeholders:
        if not (source_root / relative).is_file():
            raise PayloadError(
                f"payload placeholder {relative.as_posix()!r} is not in the payload"
            )
    target_root = preflight_workspace_paths(
        workspace,
        directories=directories,
        files=(*placeholders, *(entry.relative for entry in files)),
    )
    changes: list[str] = []
    if not target_root.exists():
        target_root.mkdir(parents=True)
        changes.append("created workspace")
    for relative in directories:
        target = target_root / relative
        if not target.exists():
            target.mkdir(parents=True)
            changes.append(f"created {relative.as_posix()}/")
    for entry in files:
        target = target_root / entry.relative
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(entry.content)
        changes.append(f"restored {entry.relative.as_posix()}")
    for relative in placeholders:
        target = target_root / relative
        if target.is_file():
            target.unlink()
            changes.append(f"removed {relative.as_posix()}")
    return tuple(changes)
