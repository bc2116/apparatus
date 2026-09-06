"""Validated, data-driven profile overlays for deployed workspaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from apparatus_core import records, skills
from apparatus_core.payload import (
    PayloadError,
    canonical_source_directory,
    canonical_source_file,
    normalize_workspace_relative,
    preflight_workspace_paths,
)


class ManifestError(ValueError):
    """The profile overlay manifest is not safe to apply."""


@dataclass(frozen=True)
class OverlayManifest:
    """A closed, validated projection of ``profiles.yaml``."""

    privacy_modes: dict[str, str]
    work_types: dict[str, tuple[str, ...]]
    default_privacy_mode: str
    default_work_types: tuple[str, ...]

    @property
    def managed_policy_paths(self) -> tuple[str, ...]:
        return tuple(self.privacy_modes.values())

    @property
    def managed_workflow_paths(self) -> tuple[str, ...]:
        return _unique(path for paths in self.work_types.values() for path in paths)

    @property
    def managed_procedure_paths(self) -> tuple[str, ...]:
        """Compatibility name for callers using legacy procedure manifests."""
        return self.managed_workflow_paths

    @property
    def managed_paths(self) -> tuple[str, ...]:
        return _unique((*self.managed_policy_paths, *self.managed_workflow_paths))


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"profiles.yaml: {name} must be a mapping")
    return value


def _closed_keys(value: Mapping[str, Any], allowed: set[str], name: str) -> None:
    unexpected = sorted(set(value) - allowed)
    missing = sorted(allowed - set(value))
    if unexpected:
        raise ManifestError(f"profiles.yaml: {name} has unexpected key {unexpected[0]!r}")
    if missing:
        raise ManifestError(f"profiles.yaml: {name} is missing key {missing[0]!r}")


def _payload_path(
    value: object,
    payload: Path,
    entry: str,
    required_parent: tuple[str, str],
) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestError(f"profiles.yaml: {entry} must be a non-empty path")
    pure = PurePosixPath(value)
    if (
        "\\" in value
        or pure.is_absolute()
        or any(part in {"", ".", ".."} for part in pure.parts)
        or pure.as_posix() != value
    ):
        raise ManifestError(f"profiles.yaml: {entry} must be a normalized payload-relative path")
    if pure.parts[:2] != required_parent or len(pure.parts) < 3:
        parent = PurePosixPath(*required_parent).as_posix() + "/"
        raise ManifestError(f"profiles.yaml: {entry} must stay under {parent!r}")
    current = payload
    for index, part in enumerate(pure.parts):
        current /= part
        if current.is_symlink():
            offending = PurePosixPath(*pure.parts[: index + 1]).as_posix()
            raise ManifestError(
                f"profiles.yaml: {entry} contains symbolic link {offending!r}"
            )
    candidate = current
    if not candidate.is_file():
        raise ManifestError(f"profiles.yaml: {entry} names missing payload file {value!r}")
    return value


def _name(value: object, entry: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"profiles.yaml: {entry} must be a non-empty name")
    return value


def _workflow_path(value: object, payload: Path, entry: str) -> str:
    if isinstance(value, str) and value in skills.BUILTIN_PATHS:
        relative = _payload_path(value, payload, entry, (".agents", "skills"))
        problems = skills.validate_skill(
            _managed_source_bytes(payload / relative, entry), skills.BUILTIN_PATHS[relative]
        )
        if problems:
            raise ManifestError(f"profiles.yaml: {entry}: {problems[0]}")
        return relative
    return _payload_path(value, payload, entry, ("System", "procedures"))


def _validate_native_payload(payload: Path) -> None:
    """A native built-in source is a complete set, with no recursive ownership."""
    if any((payload / relative).parent.exists() or (payload / relative).parent.is_symlink()
           for relative in skills.BUILTIN_PATHS):
        for relative in skills.BUILTIN_PATHS:
            _workflow_path(relative, payload, relative)


def load_manifest(path: str | Path, payload: str | Path) -> OverlayManifest:
    """Load and completely validate the closed manifest before deployment."""
    manifest_path = Path(path)
    payload_path = Path(payload)
    try:
        manifest_path = canonical_source_file(manifest_path, "profiles manifest")
        payload_path = canonical_source_directory(payload_path, "payload source path")
    except PayloadError as error:
        raise ManifestError(str(error)) from error
    try:
        data = records.yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, records.yaml.YAMLError) as error:
        raise ManifestError("could not read profiles manifest profiles.yaml") from error
    root = _mapping(data, "root")
    _closed_keys(root, {"privacy_modes", "work_types", "default"}, "root")

    modes = _mapping(root["privacy_modes"], "privacy_modes")
    if not modes:
        raise ManifestError("profiles.yaml: privacy_modes must not be empty")
    privacy_modes: dict[str, str] = {}
    for mode, policy in modes.items():
        privacy_modes[_name(mode, "privacy_modes key")] = _payload_path(
            policy,
            payload_path,
            f"privacy_modes.{mode}",
            ("System", "policy"),
        )

    work_type_data = _mapping(root["work_types"], "work_types")
    if not work_type_data:
        raise ManifestError("profiles.yaml: work_types must not be empty")
    work_types: dict[str, tuple[str, ...]] = {}
    for work_type, procedures in work_type_data.items():
        name = _name(work_type, "work_types key")
        if not isinstance(procedures, list) or not procedures:
            raise ManifestError(f"profiles.yaml: work_types.{name} must be a non-empty list")
        work_types[name] = tuple(
            _workflow_path(
                procedure,
                payload_path,
                f"work_types.{name}[{index}]",
            )
            for index, procedure in enumerate(procedures)
        )
        if len(set(work_types[name])) != len(work_types[name]):
            raise ManifestError(f"profiles.yaml: work_types.{name} repeats a workflow path")

    _validate_native_payload(payload_path)

    default = _mapping(root["default"], "default")
    _closed_keys(default, {"privacy_mode", "work_types"}, "default")
    default_mode = _name(default["privacy_mode"], "default.privacy_mode")
    if default_mode not in privacy_modes:
        raise ManifestError(
            f"profiles.yaml: default.privacy_mode names unknown mode {default_mode!r}"
        )
    default_types_data = default["work_types"]
    if not isinstance(default_types_data, list):
        raise ManifestError("profiles.yaml: default.work_types must be a list")
    default_types = tuple(
        _name(item, f"default.work_types[{index}]")
        for index, item in enumerate(default_types_data)
    )
    unknown = next((item for item in default_types if item not in work_types), None)
    if unknown is not None:
        raise ManifestError(
            f"profiles.yaml: default.work_types names unknown work type {unknown!r}"
        )
    if len(set(default_types)) != len(default_types):
        raise ManifestError("profiles.yaml: default.work_types repeats a work type")
    return OverlayManifest(privacy_modes, work_types, default_mode, default_types)


def canonical_work_types(manifest: OverlayManifest, work_types: Iterable[str]) -> tuple[str, ...]:
    """Validate and normalize work types in their manifest-defined order."""
    requested = tuple(work_types)
    unknown = next((item for item in requested if item not in manifest.work_types), None)
    if unknown is not None:
        raise ManifestError(f"unknown work type {unknown!r}")
    requested_set = set(requested)
    return tuple(name for name in manifest.work_types if name in requested_set)


def selected_workflow_paths(
    manifest: OverlayManifest, work_types: Iterable[str]
) -> tuple[str, ...]:
    """Resolve managed workflows without mode-specific program branches.

    An empty selection intentionally means no filtering: keep every manifest-
    managed starter workflow. This preserves a hand-copied, unconfigured
    payload while making new-workspace defaults explicit.
    """
    selected = canonical_work_types(manifest, work_types)
    source_types = selected or tuple(manifest.work_types)
    return _unique(path for work_type in source_types for path in manifest.work_types[work_type])


selected_procedure_paths = selected_workflow_paths


@dataclass(frozen=True)
class OverlayWrite:
    """One pre-read managed file write."""

    relative: str
    content: bytes


@dataclass(frozen=True)
class OverlayPlan:
    """All managed writes and removals for one profile selection."""

    writes: tuple[OverlayWrite, ...]
    removals: tuple[str, ...]


def _managed_source_bytes(source: Path, entry: str) -> bytes:
    if source.is_symlink():
        raise ManifestError(f"profiles.yaml: {entry} contains a symbolic link")
    try:
        return source.read_bytes()
    except OSError as error:
        raise ManifestError(f"profiles.yaml: {entry} could not be read") from error


def plan_overlay(
    payload: str | Path,
    workspace: str | Path,
    manifest: OverlayManifest,
    *,
    privacy_mode: str,
    work_types: Iterable[str],
) -> OverlayPlan:
    """Validate every managed source and target before overlay mutation."""
    if privacy_mode not in manifest.privacy_modes:
        raise ManifestError(f"unknown privacy mode {privacy_mode!r}")
    try:
        source_root = canonical_source_directory(payload, "payload source path")
    except PayloadError as error:
        raise ManifestError(str(error)) from error
    _validate_native_payload(source_root)
    desired = set(selected_workflow_paths(manifest, work_types))
    candidate_writes: list[OverlayWrite] = []
    for mode, relative in manifest.privacy_modes.items():
        _payload_path(
            relative,
            source_root,
            f"privacy_modes.{mode}",
            ("System", "policy"),
        )
        candidate_writes.append(
            OverlayWrite(
                relative,
                _managed_source_bytes(source_root / relative, f"privacy_modes.{mode}"),
            )
        )
    for work_type, procedures in manifest.work_types.items():
        for index, relative in enumerate(procedures):
            _workflow_path(
                relative,
                source_root,
                f"work_types.{work_type}[{index}]",
            )
    for work_type, procedures in manifest.work_types.items():
        for index, relative in enumerate(procedures):
            if relative in desired and relative not in {
                entry.relative for entry in candidate_writes
            }:
                candidate_writes.append(
                    OverlayWrite(
                        relative,
                        _managed_source_bytes(
                            source_root / relative, f"work_types.{work_type}[{index}]"
                        ),
                    )
                )
    try:
        root = preflight_workspace_paths(workspace, files=manifest.managed_paths)
    except PayloadError as error:
        raise ManifestError(str(error)) from error
    writes: list[OverlayWrite] = []
    for write in candidate_writes:
        target = root / write.relative
        if target.is_file():
            try:
                current = target.read_bytes()
                if current == write.content:
                    continue
                if write.relative in skills.BUILTIN_PATHS:
                    problems = skills.validate_skill(current, skills.BUILTIN_PATHS[write.relative])
                    if problems:
                        raise ManifestError(f"workspace Skill {write.relative!r}: {problems[0]}")
                    continue  # A valid customized canonical body belongs to the user.
            except OSError as error:
                raise ManifestError(
                    f"workspace path {write.relative!r} could not be read"
                ) from error
        writes.append(write)
    removals: list[str] = []
    for relative in manifest.managed_workflow_paths:
        target = root / relative
        if relative in desired or not target.is_file():
            continue
        if relative in skills.BUILTIN_PATHS:
            try:
                current = target.read_bytes()
            except OSError as error:
                raise ManifestError(f"workspace path {relative!r} could not be read") from error
            problems = skills.validate_skill(current, skills.BUILTIN_PATHS[relative])
            if problems:
                raise ManifestError(f"workspace Skill {relative!r}: {problems[0]}")
            if current != _managed_source_bytes(source_root / relative, relative):
                continue
        removals.append(relative)
    return OverlayPlan(tuple(writes), tuple(removals))


def _write_managed(content: bytes, target: Path, relative: str, changes: list[str]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    changes.append(f"updated {relative}")


def apply_overlay(
    payload: str | Path,
    workspace: str | Path,
    manifest: OverlayManifest,
    *,
    privacy_mode: str,
    work_types: Iterable[str],
) -> tuple[str, ...]:
    """Apply only manifest-managed policy and workflow file operations."""
    plan = plan_overlay(
        payload,
        workspace,
        manifest,
        privacy_mode=privacy_mode,
        work_types=work_types,
    )
    return apply_overlay_plan(workspace, plan)


def apply_overlay_plan(workspace: str | Path, plan: OverlayPlan) -> tuple[str, ...]:
    """Revalidate and apply a possibly stale or externally constructed plan."""
    writes: list[OverlayWrite] = []
    write_paths: set[Path] = set()
    for write in plan.writes:
        if not isinstance(write, OverlayWrite) or not isinstance(write.content, bytes):
            raise ManifestError("overlay plan write content must be bytes")
        try:
            relative = normalize_workspace_relative(write.relative)
        except PayloadError as error:
            raise ManifestError(str(error)) from error
        if relative.as_posix() not in skills.BUILTIN_PATHS and (relative.parts[:2] not in {
            ("System", "policy"),
            ("System", "procedures"),
        } or len(relative.parts) < 3):
            raise ManifestError(
                f"overlay operation path {relative.as_posix()!r} is outside managed folders"
            )
        if relative.as_posix() in skills.BUILTIN_PATHS:
            problems = skills.validate_skill(write.content, skills.BUILTIN_PATHS[relative.as_posix()])
            if problems:
                raise ManifestError(f"overlay Skill {relative.as_posix()!r}: {problems[0]}")
        if relative in write_paths:
            raise ManifestError(f"overlay plan repeats write {relative.as_posix()!r}")
        write_paths.add(relative)
        writes.append(OverlayWrite(relative.as_posix(), write.content))

    removals: list[Path] = []
    removal_paths: set[Path] = set()
    for value in plan.removals:
        try:
            relative = normalize_workspace_relative(value)
        except PayloadError as error:
            raise ManifestError(str(error)) from error
        if relative.as_posix() not in skills.BUILTIN_PATHS and (
            relative.parts[:2] != ("System", "procedures") or len(relative.parts) < 3
        ):
            raise ManifestError(
                f"overlay removal path {relative.as_posix()!r} is outside System/procedures/ or built-in Skills"
            )
        if relative in removal_paths:
            raise ManifestError(f"overlay plan repeats removal {relative.as_posix()!r}")
        removal_paths.add(relative)
        removals.append(relative)

    overlap = write_paths.intersection(removal_paths)
    if overlap:
        relative = min(overlap, key=lambda item: item.as_posix())
        raise ManifestError(
            f"overlay plan cannot write and remove {relative.as_posix()!r}"
        )
    try:
        root = preflight_workspace_paths(
            workspace,
            files=(*write_paths, *removal_paths),
        )
    except PayloadError as error:
        raise ManifestError(str(error)) from error

    changes: list[str] = []
    for write in writes:
        _write_managed(write.content, root / write.relative, write.relative, changes)
    for relative in removals:
        target = root / relative
        if target.is_file():
            target.unlink()
            changes.append(f"removed {relative.as_posix()}")
    return tuple(changes)
