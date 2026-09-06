"""The ``apparatus init`` command: safe starter-payload deployment."""

from __future__ import annotations

import argparse
import os
from contextlib import ExitStack
from dataclasses import replace
from collections.abc import Callable
from pathlib import Path
from typing import Any

from apparatus_core import records
from apparatus_core.detect import detect_sync_redirection
from apparatus_core.init_deploy import deploy_init_plan
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.retention import RetentionSuppressed, TaskRetentionError, operation
from apparatus_core.workspace_layout import (
    LayoutError, MARKER, RECOVERY_DIRECTORY, _root_identity, new_layout_bytes, read_layout,
)
from apparatus_core.instruction_updates import instruction_updates
from apparatus_core.overlays import (
    ManifestError,
    OverlayManifest,
    canonical_work_types,
    load_manifest,
    plan_overlay,
)
from apparatus_core.payload import (
    PayloadError,
    plan_payload_deployment,
    preflight_workspace_paths,
    reject_payload_workspace_overlap,
    resolve_payload,
    resolve_profiles_manifest,
)
from apparatus_core.project_binding import (
    BindingError, read_project_binding, require_unbound_root, resolve_project_context,
)
from apparatus_core.receipts import write_receipt
from apparatus_core.snapshots import (
    SnapshotError,
    SnapshotReceiptError,
    git_available,
    mark_snapshots_unavailable,
    take_snapshot,
)


def register(subparsers: Any) -> None:
    """Register init through the shared command entry-point path."""
    parser = subparsers.add_parser("init", help="create or repair a workspace")
    parser.add_argument("workspace", metavar="WORKSPACE")
    parser.add_argument("--adopt", action="store_true", help="enroll an existing unmarked folder without moving its files")
    parser.add_argument("--privacy-mode", choices=records.PRIVACY_MODES)
    parser.add_argument("--work-types", metavar="LIST", help="comma-separated work types")
    parser.add_argument("--payload", metavar="PATH", help="starter payload source")
    parser.set_defaults(func=run)


def _parse_work_types(value: str) -> tuple[str, ...]:
    parts = tuple(part.strip() for part in value.split(","))
    if not parts or any(not part for part in parts):
        raise ManifestError("--work-types must be a comma-separated list with no empty names")
    if len(set(parts)) != len(parts):
        raise ManifestError("--work-types must not repeat a work type")
    return parts


def _read_existing_profile(workspace: Path, manifest: OverlayManifest, content: bytes | None = None) -> dict[str, Any] | None:
    profile = workspace / "System" / "profile.yaml"
    if not profile.exists():
        return None
    if not profile.is_file():
        raise ManifestError("existing System/profile.yaml is not a file")
    try:
        data = records.yaml.safe_load(content.decode("utf-8") if content is not None else profile.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, records.yaml.YAMLError) as error:
        raise ManifestError("existing System/profile.yaml could not be read") from error
    if not isinstance(data, dict):
        raise ManifestError("existing System/profile.yaml must be a YAML mapping")
    problems = records.validate("profile", data, filename="profile.yaml")
    if problems:
        raise ManifestError("existing System/profile.yaml is invalid: " + "; ".join(problems))
    if data["privacy_mode"] not in manifest.privacy_modes:
        raise ManifestError(
            "existing System/profile.yaml names unknown privacy mode "
            f"{data['privacy_mode']!r}"
        )
    canonical_work_types(manifest, data["work_types"])
    return data


def _profile_data(
    manifest: OverlayManifest,
    existing: dict[str, Any] | None,
    privacy_mode: str | None,
    work_types: str | None,
) -> dict[str, Any]:
    mode = privacy_mode if privacy_mode is not None else (
        existing["privacy_mode"] if existing is not None else manifest.default_privacy_mode
    )
    if mode not in manifest.privacy_modes:
        raise ManifestError(f"unknown privacy mode {mode!r}")
    requested_types = (
        _parse_work_types(work_types)
        if work_types is not None
        else (existing["work_types"] if existing is not None else manifest.default_work_types)
    )
    normalized_types = canonical_work_types(manifest, requested_types)
    profile = {
        "schema": records.SCHEMAS["profile"].schema_id,
        "status": existing["status"] if existing is not None else "unconfigured",
        "privacy_mode": mode,
        "work_types": list(normalized_types),
        "review_day": existing["review_day"] if existing is not None else None,
        "spend": existing.get("spend", "balanced") if existing is not None else "balanced",
    }
    if existing is not None:
        for key in ("features", "key_people", "current_efforts", "source_locations"):
            if key in existing:
                profile[key] = existing[key]
    problems = records.validate("profile", profile, filename="profile.yaml")
    if problems:
        raise ManifestError("generated System/profile.yaml is invalid: " + "; ".join(problems))
    return profile


def _profile_content(profile: dict[str, Any]) -> str:
    return records.yaml.safe_dump(profile, sort_keys=False, allow_unicode=True)


def _init_receipt_fields(changes: tuple[str, ...], sync: dict[str, Any]) -> dict[str, str]:
    lines = ["Changes:"]
    lines.extend(f"- {change}" for change in sorted(changes))
    if len(lines) == 1:
        lines.append("- none")
    note = str(sync.get("reason", "No sync-redirection result was available."))
    lines.extend(("", f"Sync redirection: {note}"))
    return {
        "summary": f"Workspace initialized with {len(changes)} change(s).",
        "body": "\n".join(lines) + "\n",
    }


def _warning(sync: dict[str, Any]) -> None:
    print("Warning: this workspace is inside a sync-redirected location.")
    print(f"Warning: {sync.get('reason', 'A sync-redirection risk was found.')}")


def _run(
    args: argparse.Namespace,
    *,
    stack: ExitStack,
    available: Callable[[], bool] = git_available,
    detect: Callable[..., dict[str, Any]] = detect_sync_redirection,
    write: Callable[[str | Path, str, dict[str, str]], object] = write_receipt,
    take: Callable[..., Any] = take_snapshot,
    update_report: Callable[[str | Path], bool] = mark_snapshots_unavailable,
) -> int:
    """Validate first, then deploy without replacing un-managed user content."""
    requested_workspace = Path(args.workspace)
    if requested_workspace.is_symlink():
        print("init: workspace path '.' must not be a symbolic link")
        return 2
    if requested_workspace.exists() and not requested_workspace.is_dir():
        print("init: workspace path is not a directory")
        return 2
    try:
        payload = resolve_payload(getattr(args, "payload", None))
        workspace = preflight_workspace_paths(requested_workspace)
        reject_payload_workspace_overlap(payload, workspace)
        manifest = load_manifest(resolve_profiles_manifest(payload), payload)
        # Reject control collisions before reading or deploying content. No
        # repository discovery or .git inspection participates in enrollment.
        preflight_workspace_paths(workspace, files=("System/profile.yaml", MARKER))
        existing_root = stack.enter_context(WorkspaceAnchor(workspace)) if workspace.is_dir() else None
        layout = read_layout(workspace) if existing_root else None
        if existing_root and read_project_binding(workspace) is not None:
            with resolve_project_context(workspace) as selected:
                selected.validate()
                raise PayloadError(f"this is a bound project; run apparatus init on its work area: {selected.workspace}")
        was_empty = existing_root is not None and not os.listdir(
            existing_root._root if os.name == "posix" else workspace)
        if existing_root and layout is None and not was_empty and not getattr(args, "adopt", False):
            raise PayloadError("existing unmarked folder requires --adopt; its files and repositories will stay in place")
        task_id = getattr(args, "task", None)
        context = stack.enter_context(operation(workspace, task_id=task_id)) if existing_root else None
        if task_id is not None and existing_root is None:
            raise TaskRetentionError("A fresh work area has no task controls; initialize it before starting a task.")
        profile_proof = None
        if existing_root is not None:
            try:
                profile_proof = existing_root.capture_file(
                    "System/profile.yaml", publication_compatible=True)
                stack.callback(profile_proof.close)
            except FileNotFoundError:
                pass
        previous_profile = profile_proof.content if profile_proof else None
        existing = _read_existing_profile(workspace, manifest, previous_profile) if existing_root else None
        selectors = (getattr(args, "privacy_mode", None), getattr(args, "work_types", None))
        if existing is not None and selectors == (None, None):
            profile = existing
            profile_content = previous_profile
            profile_write_required = False
        else:
            profile = _profile_data(manifest, existing, *selectors)
            profile_content = _profile_content(profile).encode("utf-8")
            profile_write_required = previous_profile != profile_content
            if selectors != (None, None) and profile_write_required and context is not None:
                context.require_memory_write()
        enrollment_content = None if layout is not None else new_layout_bytes()

        def validate_enrollment(anchor: WorkspaceAnchor, published: bool) -> None:
            nonlocal profile_proof
            if existing_root is not None and _root_identity(anchor) != _root_identity(existing_root):
                raise PayloadError("work-area directory changed after planning; rerun apparatus init")
            require_unbound_root(anchor)
            if layout is not None:
                layout.validate(anchor)
            elif not published:
                # New marker bytes are checked by deploy_init_plan's retained
                # created-file proof at every final gate, without reopening a
                # newly created System directory with incompatible handles.
                try:
                    present = anchor.entry_exists(MARKER) or anchor.entry_exists(RECOVERY_DIRECTORY)
                except FileNotFoundError:
                    present = False
                if present:
                    raise LayoutError("Work-area enrollment or recovery appeared after planning; rerun init.")
                if was_empty and not getattr(args, "adopt", False) and os.listdir(
                    anchor._root if os.name == "posix" else workspace):
                    raise PayloadError("folder is no longer empty; rerun with --adopt to enroll it")
            if profile_proof is not None and (not published or not profile_write_required):
                if not anchor.matches_owned(profile_proof):
                    raise PayloadError("profile changed after planning; rerun apparatus init")
                if profile_write_required and not published:
                    # Hand the validated preimage to deployment's byte check and
                    # CAS transaction before it acquires replacement ownership.
                    profile_proof.close()
                    profile_proof = None

        payload_plan = plan_payload_deployment(payload, manifest.managed_paths, workspace)
        overlay_plan = plan_overlay(
            payload,
            workspace,
            manifest,
            privacy_mode=profile["privacy_mode"],
            work_types=profile["work_types"],
        )
        overlay_plan, instruction_preimages = instruction_updates(
            workspace, payload, overlay_plan
        )
        instruction_preimages["System/profile.yaml"] = previous_profile
        if layout is not None:
            instruction_preimages[MARKER] = layout.content
        overlay_paths = {item.relative for item in overlay_plan.writes}
        # Retain parents of preserved compatibility pointers too. Fresh native
        # payloads no longer contain their legacy directory, and an unchanged
        # pointer still needs final preimage checks through its immediate parent.
        preimage_parents = {parent for relative, content in instruction_preimages.items()
                            if content is not None for parent in Path(relative).parents
                            if parent != Path(".")}
        payload_plan = replace(payload_plan, files=tuple(
            entry for entry in payload_plan.files if entry.relative.as_posix() not in overlay_paths),
            directories=tuple(sorted(set(payload_plan.directories) | preimage_parents,
                                     key=lambda path: path.as_posix())))
        payload_paths = (*payload_plan.directories, *payload_plan.placeholders,
                         *(entry.relative for entry in payload_plan.files))
        if any(path.parts[0].casefold() in {".git", ".apparatus"}
               or path.as_posix().casefold() == MARKER.casefold()
               or tuple(part.casefold() for part in path.parts[:2]) in {
                   ("system", "recovery"), ("system", "tasks")}
               for path in payload_paths):
            raise PayloadError("starter payload must not contain repository, binding, task, or enrollment controls")
    except RetentionSuppressed as error:
        print(f"init: {error}")
        return 1
    except (PayloadError, ManifestError, LayoutError, TaskRetentionError, BindingError) as error:
        print(f"init: {error}")
        return 2
    except Exception:  # pragma: no cover - filesystem failures vary by host
        print("init: could not prepare workspace deployment")
        return 2

    try:
        sync = detect(workspace)
        snapshots_available = available()
        if (
            not isinstance(sync, dict)
            or not isinstance(sync.get("at_risk"), bool)
            or not isinstance(sync.get("reason"), str)
            or not isinstance(snapshots_available, bool)
        ):
            raise ValueError("invalid capability result")
    except Exception:  # pragma: no cover - collaborator failures vary by host
        print("init: could not inspect workspace capabilities")
        return 2

    try:
        file_targets = (
            *(entry.relative for entry in payload_plan.files),
            *payload_plan.placeholders,
            *(item.relative for item in overlay_plan.writes), *overlay_plan.removals,
            *manifest.managed_paths,
            Path("System/profile.yaml"), Path(MARKER),
        )
        directory_targets = (*payload_plan.directories, Path("System/receipts"))
        if not snapshots_available:
            file_targets = (*file_targets, Path("System/machine-report.md"))
        preflight_workspace_paths(
            workspace,
            directories=directory_targets,
            files=file_targets,
            inspect_git_store=False,
        )
    except PayloadError as error:
        print(f"init: {error}")
        return 2
    except Exception:  # pragma: no cover - filesystem failures vary by host
        print("init: could not prepare workspace deployment")
        return 2

    try:
        changes = list(
            deploy_init_plan(
                workspace,
                payload_plan,
                overlay_plan,
                profile_content,
                profile_write_required=profile_write_required,
                expected_contents=instruction_preimages,
                enrollment_content=enrollment_content,
                validate_enrollment=validate_enrollment,
            )
        )
    except (PayloadError, LayoutError, BindingError) as error:
        print(f"init: could not deploy workspace: {error}")
        return 2
    except Exception:  # pragma: no cover - filesystem failures vary by host
        print("init: could not deploy workspace")
        return 2

    if context is None:
        context = stack.enter_context(operation(workspace))
    if bool(sync.get("at_risk")):
        _warning(sync)
    if changes:
        try:
            write(workspace, "init", _init_receipt_fields(tuple(changes), sync))
        except Exception:
            print("init: work-area deployment completed, but its receipt could not be written")
            return 2
    state = "Workspace created." if enrollment_content is not None else (
        "Work area repaired." if changes else "Work area is already up to date.")
    if not context.save_memory:
        print(state)
        if context.task_id is None:
            print("Automatic managed snapshot skipped: pass --task ID to select this operation's task.")
        else:
            print("Automatic managed snapshot skipped: this task does not save to Memory.")
        return 0
    if not snapshots_available:
        try:
            report_updated = bool(update_report(workspace))
        except Exception:
            report_updated = False
        if not report_updated:
            print("init: work-area deployment completed, but the unavailable snapshot state could not be recorded")
            return 2
        print("Snapshots are unavailable on this machine. Managed recovery excludes project files and Library originals; run apparatus doctor for details.")
        print(state)
        return 0
    try:
        result = take(workspace, label="Workspace created" if enrollment_content is not None else "Work area repaired")
    except (SnapshotReceiptError, SnapshotError):
        print("init: work-area deployment completed, but its managed snapshot failed; enrollment remains installed. Run apparatus snapshot to retry.")
        return 2
    except Exception:
        print("init: work-area deployment completed, but its managed snapshot could not be saved")
        return 2
    if result.snapshot is None and not getattr(result, "no_changes", False):
        print("init: work-area deployment completed, but its managed snapshot could not be saved")
        return 2
    print(state)
    if getattr(result, "no_changes", False):
        print("Managed snapshot unchanged; no new snapshot was needed.")
    return 0


def run(args: argparse.Namespace, **kwargs: Any) -> int:
    """Keep the explicit destination and selected task context for the command."""
    if getattr(args, "_project_context", None) is not None:
        print("init: this invocation selected a bound project; run apparatus init on its work area")
        return 2
    with ExitStack() as stack:
        try:
            return _run(args, stack=stack, **kwargs)
        except (PayloadError, ManifestError, LayoutError, TaskRetentionError, BindingError) as error:
            print(f"init: {error}")
            return 2
