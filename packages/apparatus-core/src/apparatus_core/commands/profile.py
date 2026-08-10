"""Apply a configured setup profile without replacing user-authored records."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from apparatus_core import records
from apparatus_core.commands import memory
from apparatus_core.interview import goal_seeds, person_seeds
from apparatus_core.labeler import render_record
from apparatus_core.overlays import (
    ManifestError,
    apply_overlay_plan,
    canonical_work_types,
    load_manifest,
    plan_overlay,
)
from apparatus_core.payload import (
    PayloadError,
    preflight_workspace_paths,
    resolve_payload,
    resolve_profiles_manifest,
)
from apparatus_core.receipts import write_receipt


class ProfileCommandError(ValueError):
    """A profile could not be applied without risking workspace content."""


def register(subparsers: Any) -> None:
    """Register the profile verb through the shared entry-point path."""
    parser = subparsers.add_parser("profile", help="apply a configured setup profile")
    actions = parser.add_subparsers(dest="profile_action")
    apply = actions.add_parser("apply", help="apply profile selections and starter records")
    apply.add_argument("workspace", metavar="WORKSPACE", nargs="?", default=".")
    apply.add_argument("--payload", metavar="PATH", help="starter payload source")
    apply.set_defaults(func=run, profile_action="apply")


def _workspace(value: str) -> Path:
    requested = Path(value)
    if requested.is_symlink() or not requested.is_dir():
        raise ProfileCommandError(
            "workspace path must be an existing directory, not a symbolic link"
        )
    try:
        return preflight_workspace_paths(requested, files=("System/profile.yaml",))
    except PayloadError as error:
        raise ProfileCommandError(str(error)) from error


def _profile(workspace: Path) -> dict[str, Any]:
    path = workspace / "System/profile.yaml"
    if not path.is_file():
        raise ProfileCommandError("System/profile.yaml is missing")
    try:
        data = records.yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, records.yaml.YAMLError) as error:
        raise ProfileCommandError("System/profile.yaml must be valid UTF-8 YAML") from error
    if not isinstance(data, dict):
        raise ProfileCommandError("System/profile.yaml must be a YAML mapping")
    problems = records.validate("profile", data, filename="profile.yaml")
    if problems:
        raise ProfileCommandError("System/profile.yaml is invalid: " + "; ".join(problems))
    if data["status"] != "configured":
        raise ProfileCommandError(
            "System/profile.yaml status must be configured before apply"
        )
    return data


def _slug(value: str) -> str:
    return memory._slug(value)


def _goal_content(seed: Any) -> bytes:
    frontmatter = {
        "schema": records.SCHEMAS["goal"].schema_id,
        "title": seed.title,
        "owner": "me",
        "status": seed.status,
        "done-when": seed.done_when,
        "next-action": seed.next_action,
    }
    problems = records.validate(
        "goal", frontmatter, filename=f"{_slug(seed.title)}.md"
    )
    if problems:
        raise ProfileCommandError("generated goal does not match the goal schema")
    return render_record(frontmatter, "Seeded from the setup interview.").encode("utf-8")


def _receipt_fields(
    overlay_actions: tuple[str, ...], seeded: list[str], skipped: list[str]
) -> dict[str, str]:
    body = ["Overlay actions:"]
    if overlay_actions:
        body.extend(f"- {action}" for action in overlay_actions)
    else:
        body.append("- none")
    body.extend(("", "Records seeded:"))
    if seeded:
        body.extend(f"- {item}" for item in seeded)
    else:
        body.append("- none")
    body.extend(("", "Records skipped:"))
    if skipped:
        body.extend(f"- {item}" for item in skipped)
    else:
        body.append("- none")
    return {
        "summary": (
            f"Profile applied; {len(seeded)} record(s) seeded and {len(skipped)} skipped."
        ),
        "body": "\n".join(body) + "\n",
    }


def _seed_records(
    workspace: Path,
    profile: dict[str, Any],
    write: Callable[[str | Path, str, dict[str, Any]], Path],
) -> tuple[list[str], list[str]]:
    seeded: list[str] = []
    skipped: list[str] = []
    try:
        with memory._WorkspaceAnchor(workspace) as anchor:
            anchor.require_directory("Goals")
            anchor.require_directory("Memory/People")
            for seed in person_seeds(profile):
                relative = Path("Memory/People") / f"{_slug(seed.name)}.md"
                metadata = {"name": seed.name}
                if seed.role is not None:
                    metadata["role"] = seed.role
                if seed.organization is not None:
                    metadata["organization"] = seed.organization
                result = memory._new_record(
                    anchor,
                    kind="person",
                    metadata=metadata,
                    body="",
                    mode=profile["privacy_mode"],
                    write=write,
                    suffix_on_collision=False,
                )
                if result is None:
                    reason = (
                        "blocked by private mode"
                        if profile["privacy_mode"] == "private"
                        else "already exists"
                    )
                    skipped.append(f"{relative.as_posix()} ({reason})")
                else:
                    seeded.append(result[0].as_posix())
            for seed in goal_seeds(profile):
                relative = Path("Goals") / f"{_slug(seed.title)}.md"
                try:
                    owned = anchor.create_file(relative, _goal_content(seed))
                except FileExistsError:
                    skipped.append(f"{relative.as_posix()} (already exists)")
                    continue
                owned.close()
                seeded.append(relative.as_posix())
    except memory.MemoryCommandError as error:
        raise ProfileCommandError(str(error)) from error
    return seeded, skipped


def run(
    args: argparse.Namespace,
    *,
    write: Callable[[str | Path, str, dict[str, Any]], Path] = write_receipt,
) -> int:
    """Validate first, then apply overlays and seed only missing records."""
    if getattr(args, "profile_action", None) != "apply":
        print("profile: choose apply")
        return 2
    try:
        workspace = _workspace(args.workspace)
        profile = _profile(workspace)
        payload = resolve_payload(getattr(args, "payload", None))
        manifest = load_manifest(resolve_profiles_manifest(payload), payload)
        if profile["privacy_mode"] not in manifest.privacy_modes:
            raise ProfileCommandError(f"unknown privacy mode {profile['privacy_mode']!r}")
        canonical_work_types(manifest, profile["work_types"])
        overlay_plan = plan_overlay(
            payload,
            workspace,
            manifest,
            privacy_mode=profile["privacy_mode"],
            work_types=profile["work_types"],
        )
        # Derive every seed before mutating so malformed answer data has no effects.
        person_seeds(profile)
        goal_seeds(profile)
    except (PayloadError, ManifestError, ProfileCommandError) as error:
        print(f"profile: {error}")
        return 2
    except Exception:
        print("profile: could not prepare profile application")
        return 2

    try:
        overlay_actions = apply_overlay_plan(workspace, overlay_plan)
        seeded, skipped = _seed_records(workspace, profile, write)
        write(workspace, "profile-apply", _receipt_fields(overlay_actions, seeded, skipped))
    except (ManifestError, ProfileCommandError):
        print("profile: could not apply the profile safely")
        return 2
    except Exception:
        print("profile: could not apply the profile safely")
        return 2
    print(f"Profile applied: {len(seeded)} record(s) seeded, {len(skipped)} skipped.")
    return 0
