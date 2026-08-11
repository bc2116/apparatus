"""The ``apparatus init`` command: safe starter-payload deployment."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from apparatus_core import records
from apparatus_core.detect import detect_sync_redirection
from apparatus_core.init_deploy import deploy_init_plan
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


def _read_existing_profile(workspace: Path, manifest: OverlayManifest) -> dict[str, Any] | None:
    profile = workspace / "System" / "profile.yaml"
    if not profile.exists():
        return None
    if not profile.is_file():
        raise ManifestError("existing System/profile.yaml is not a file")
    try:
        data = records.yaml.safe_load(profile.read_text(encoding="utf-8"))
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
        for key in ("key_people", "current_efforts", "source_locations"):
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


def _unavailable_snapshot_fields() -> dict[str, str]:
    return {
        "summary": "Snapshots are unavailable on this machine.",
        "body": "Outcome: unavailable.",
    }


def _warning(sync: dict[str, Any]) -> None:
    print("Warning: this workspace is inside a sync-redirected location.")
    print(f"Warning: {sync.get('reason', 'A sync-redirection risk was found.')}")


def run(
    args: argparse.Namespace,
    *,
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
        # A valid existing profile drives omitted selectors, but the profile
        # destination and its ancestors must be contained before it is read.
        preflight_workspace_paths(workspace, files=("System/profile.yaml",))
        existing = _read_existing_profile(workspace, manifest) if workspace.is_dir() else None
        profile = _profile_data(
            manifest,
            existing,
            getattr(args, "privacy_mode", None),
            getattr(args, "work_types", None),
        )
        profile_content = _profile_content(profile)
        profile_path = workspace / "System/profile.yaml"
        profile_write_required = (
            not profile_path.is_file()
            or profile_path.read_text(encoding="utf-8") != profile_content
        )
        payload_plan = plan_payload_deployment(payload, manifest.managed_paths, workspace)
        overlay_plan = plan_overlay(
            payload,
            workspace,
            manifest,
            privacy_mode=profile["privacy_mode"],
            work_types=profile["work_types"],
        )
    except (PayloadError, ManifestError) as error:
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
            *manifest.managed_paths,
            Path("System/profile.yaml"),
        )
        directory_targets = (*payload_plan.directories, Path("System/receipts"))
        if snapshots_available:
            directory_targets = (*directory_targets, Path(".git"))
        else:
            file_targets = (*file_targets, Path("System/machine-report.md"))
        preflight_workspace_paths(
            workspace,
            directories=directory_targets,
            files=file_targets,
            inspect_git_store=snapshots_available,
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
                profile_content.encode("utf-8"),
                profile_write_required=profile_write_required,
            )
        )
    except Exception:  # pragma: no cover - filesystem failures vary by host
        print("init: could not deploy workspace")
        return 2

    if bool(sync.get("at_risk")):
        _warning(sync)
    try:
        write(workspace, "init", _init_receipt_fields(tuple(changes), sync))
    except Exception:  # pragma: no cover - custom receipt backends vary by host
        print("init: could not write receipt")
        return 2

    if not snapshots_available:
        snapshot_receipt_written = True
        report_updated = True
        try:
            write(workspace, "snapshot", _unavailable_snapshot_fields())
        except Exception:
            snapshot_receipt_written = False
        try:
            report_updated = bool(update_report(workspace))
        except Exception:
            report_updated = False
        if not snapshot_receipt_written or not report_updated:
            print("init: could not record the unavailable snapshot state")
            return 2
        print("Snapshots are unavailable on this machine. Run apparatus doctor for details.")
        print("Workspace created.")
        return 0
    try:
        result = take(workspace, label="Workspace created")
    except SnapshotReceiptError:
        print("init: could not write the snapshot receipt")
        return 2
    except SnapshotError:
        print("init: could not save the initial snapshot")
        return 2
    except Exception:  # pragma: no cover - snapshot backends vary by host
        print("init: could not save the initial snapshot")
        return 2
    if result.snapshot is None:
        print("init: could not save the initial snapshot")
        return 2
    print("Workspace created.")
    return 0
