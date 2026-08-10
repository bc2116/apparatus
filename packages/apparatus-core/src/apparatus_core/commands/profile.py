"""Credential-safe, auditable application of configured setup profiles."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from apparatus_core import records
from apparatus_core.commands import memory
from apparatus_core.credentials import RedactionFinding
from apparatus_core.interview import (
    GoalSeed,
    PersonSeed,
    goal_seeds,
    person_seeds,
    redact_answer_values,
)
from apparatus_core.labeler import render_record
from apparatus_core.overlays import (
    ManifestError,
    OverlayPlan,
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
from apparatus_core.receipts import (
    ReceiptInvocation,
    ReceiptPublication,
    prepare_receipt_invocation,
    write_receipt,
)


class ProfileCommandError(ValueError):
    """A profile could not be applied without risking workspace content."""


@dataclass(frozen=True)
class _SeedPlan:
    people: tuple[PersonSeed, ...]
    goals: tuple[GoalSeed, ...]
    seeded: tuple[str, ...]
    skipped: tuple[str, ...]


def register(subparsers: Any) -> None:
    """Register the profile verb through the shared entry-point path."""
    parser = subparsers.add_parser("profile", help="apply a configured setup profile")
    actions = parser.add_subparsers(dest="profile_action")
    apply = actions.add_parser("apply", help="apply profile selections and starter records")
    apply.add_argument("workspace", metavar="WORKSPACE", nargs="?", default=".")
    apply.add_argument("--payload", metavar="PATH", help="starter payload source")
    apply.add_argument(
        "--stdin",
        action="store_true",
        dest="candidate_stdin",
        help="read the configured profile YAML from standard input",
    )
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


def _profile_data(
    content: bytes,
) -> tuple[dict[str, Any], tuple[RedactionFinding, ...], bytes]:
    try:
        decoded = content.decode("utf-8", errors="strict")
        parsed = records.yaml.safe_load(decoded)
    except (UnicodeError, records.yaml.YAMLError) as error:
        raise ProfileCommandError(
            "System/profile.yaml must be valid UTF-8 YAML"
        ) from error
    if not isinstance(parsed, dict):
        raise ProfileCommandError("System/profile.yaml must be a YAML mapping")
    cleaned, findings = redact_answer_values(parsed)
    if not isinstance(cleaned, dict):  # pragma: no cover - mapping recursion is stable
        raise ProfileCommandError("System/profile.yaml must be a YAML mapping")
    problems = records.validate("profile", cleaned, filename="profile.yaml")
    if problems:
        raise ProfileCommandError("System/profile.yaml is invalid: " + "; ".join(problems))
    if cleaned["status"] != "configured":
        raise ProfileCommandError(
            "System/profile.yaml status must be configured before apply"
        )
    rendered = records.yaml.safe_dump(
        cleaned, sort_keys=False, allow_unicode=True
    ).encode("utf-8")
    return cleaned, findings, rendered


def _slug(value: str) -> str:
    return memory._slug(value)


def _goal_content(seed: GoalSeed) -> bytes:
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


def _exists(anchor: Any, relative: Path) -> bool:
    try:
        anchor.read_file(relative)
        return True
    except FileNotFoundError:
        return False
    except OSError as error:
        raise ProfileCommandError(
            f"workspace destination {relative.as_posix()!r} is not a safe file"
        ) from error


def _seed_plan(anchor: Any, profile: dict[str, Any]) -> _SeedPlan:
    people: list[PersonSeed] = []
    goals: list[GoalSeed] = []
    seeded: list[str] = []
    skipped: list[str] = []
    reserved: set[Path] = set()
    for seed in person_seeds(profile):
        relative = Path("Memory/People") / f"{_slug(seed.name)}.md"
        if relative in reserved or _exists(anchor, relative):
            skipped.append(f"{relative.as_posix()} (already exists)")
        elif profile["privacy_mode"] == "private":
            skipped.append(f"{relative.as_posix()} (blocked by private mode)")
        else:
            reserved.add(relative)
            people.append(seed)
            seeded.append(relative.as_posix())
    for seed in goal_seeds(profile):
        relative = Path("Goals") / f"{_slug(seed.title)}.md"
        if relative in reserved or _exists(anchor, relative):
            skipped.append(f"{relative.as_posix()} (already exists)")
        else:
            reserved.add(relative)
            goals.append(seed)
            seeded.append(relative.as_posix())
    return _SeedPlan(tuple(people), tuple(goals), tuple(seeded), tuple(skipped))


def _overlay_actions(plan: OverlayPlan) -> tuple[str, ...]:
    return (
        *(f"updated {write.relative}" for write in plan.writes),
        *(f"removed {relative}" for relative in plan.removals),
    )


def _receipt_fields(
    profile_updated: bool,
    overlay_actions: tuple[str, ...],
    seeded: tuple[str, ...],
    skipped: tuple[str, ...],
) -> dict[str, str]:
    body = [
        "Profile actions:",
        "- updated System/profile.yaml" if profile_updated else "- none",
    ]
    body.extend(("", "Overlay actions:"))
    body.extend(f"- {action}" for action in overlay_actions)
    if not overlay_actions:
        body.append("- none")
    body.extend(("", "Records seeded:"))
    body.extend(f"- {item}" for item in seeded)
    if not seeded:
        body.append("- none")
    body.extend(("", "Records skipped:"))
    body.extend(f"- {item}" for item in skipped)
    if not skipped:
        body.append("- none")
    return {
        "summary": (
            f"Profile applied; {len(seeded)} record(s) seeded and {len(skipped)} skipped."
        ),
        "body": "\n".join(body) + "\n",
    }


ReceiptPublisher = Callable[..., object]


def _accept_publication(
    value: object, invocation: ReceiptInvocation
) -> ReceiptPublication:
    if not isinstance(value, ReceiptPublication) or not value.is_bound_to(invocation):
        raise ProfileCommandError(
            "receipt writer did not return exact publication ownership"
        )
    try:
        value.claim(invocation)
    except OSError as error:
        try:
            value.rollback()
        except OSError:
            pass
        finally:
            value.close()
        raise ProfileCommandError(
            "receipt writer did not return exact publication ownership"
        ) from error
    return value


def _publish_owned(
    write: ReceiptPublisher,
    workspace: Path,
    event: str,
    fields: dict[str, Any],
) -> ReceiptPublication:
    invocation = prepare_receipt_invocation(workspace, event, fields)
    value = write(workspace, event, fields, invocation=invocation)
    return _accept_publication(value, invocation)


def _remove_receipts(owned: list[ReceiptPublication]) -> bool:
    ok = True
    for publication in reversed(owned):
        try:
            publication.rollback()
        except OSError:
            ok = False
        finally:
            publication.close()
    return ok


def _write_required_receipts(
    anchor: Any,
    findings: tuple[RedactionFinding, ...],
    fields: dict[str, str],
    write: ReceiptPublisher,
) -> list[ReceiptPublication]:
    owned: list[ReceiptPublication] = []
    try:
        if findings:
            owned.append(
                _publish_owned(
                    write,
                    anchor.workspace,
                    "redaction",
                    memory._receipt_fields(findings),
                )
            )
        owned.append(
            _publish_owned(
                write,
                anchor.workspace,
                "profile-apply",
                fields,
            )
        )
        return owned
    except Exception as error:
        if not _remove_receipts(owned):
            raise ProfileCommandError(
                "profile receipts could not restore their prior state"
            ) from error
        raise ProfileCommandError("could not write the required profile receipts") from error


def _restore_removals(anchor: Any, removed: list[tuple[Path, bytes]]) -> bool:
    restored: list[Any] = []
    try:
        for relative, content in reversed(removed):
            owned = anchor.create_file(relative, content)
            restored.append(owned)
        return True
    except (OSError, memory.MemoryCommandError):
        return False
    finally:
        for owned in restored:
            owned.close()


def _rollback(
    anchor: Any,
    removed: list[tuple[Path, bytes]],
    created: list[Any],
    replacements: list[Any],
    receipts: list[ReceiptPublication],
) -> bool:
    ok = _restore_removals(anchor, removed)
    for owned in reversed(created):
        try:
            anchor.unlink_owned(owned)
        except (OSError, memory.MemoryCommandError):
            ok = False
        finally:
            owned.close()
    for transaction in reversed(replacements):
        try:
            transaction.rollback()
        except (OSError, memory.MemoryCommandError):
            ok = False
        finally:
            transaction.close()
    if not _remove_receipts(receipts):
        ok = False
    return ok


def _commit(
    replacements: list[Any],
    created: list[Any],
    receipts: list[ReceiptPublication],
) -> None:
    cleanup_failed = False
    for transaction in replacements:
        try:
            transaction.commit()
        except (OSError, memory.MemoryCommandError):
            cleanup_failed = True
    if cleanup_failed:
        for transaction in replacements:
            try:
                transaction.discard_backup()
            except (OSError, memory.MemoryCommandError):
                cleanup_failed = True
    for transaction in replacements:
        transaction.close()
    for owned in created:
        owned.close()
    for receipt in receipts:
        receipt.close()
    if cleanup_failed:
        raise ProfileCommandError(
            "profile applied with receipts but protected backup cleanup failed"
        )


def _apply_changes(
    anchor: Any,
    original_profile: bytes,
    profile_identity: Any,
    rendered_profile: bytes,
    overlay_plan: OverlayPlan,
    seed_plan: _SeedPlan,
    receipts: list[ReceiptPublication],
    profile: dict[str, Any],
) -> None:
    replacements: list[Any] = []
    created: list[Any] = []
    removed: list[tuple[Path, bytes]] = []
    commit_phase = False

    def tracked_seed_receipt(
        _workspace: str | Path,
        _event: str,
        _fields: dict[str, Any],
        **_kwargs: object,
    ) -> object:
        raise ProfileCommandError("a profile seed bypassed credential sanitization")

    try:
        if rendered_profile != original_profile:
            replacements.append(
                anchor.replace_if_unchanged(
                    "System/profile.yaml",
                    profile_identity,
                    original_profile,
                    rendered_profile,
                )
            )
        for overlay_write in overlay_plan.writes:
            relative = Path(overlay_write.relative)
            try:
                current, identity = anchor.read_file(relative)
            except FileNotFoundError:
                created.append(anchor.create_file(relative, overlay_write.content))
            else:
                replacements.append(
                    anchor.replace_if_unchanged(
                        relative, identity, current, overlay_write.content
                    )
                )
        for seed in seed_plan.people:
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
                write=tracked_seed_receipt,
                suffix_on_collision=False,
                retain_ownership=True,
            )
            if result is None or len(result) != 4:
                raise ProfileCommandError("a planned People record could not be created")
            created.append(result[3])
            if result[1]:
                raise ProfileCommandError("a profile seed bypassed credential sanitization")
        for seed in seed_plan.goals:
            relative = Path("Goals") / f"{_slug(seed.title)}.md"
            created.append(anchor.create_file(relative, _goal_content(seed)))
        for transaction in replacements:
            transaction.validate_commit()
        for publication in receipts:
            publication.validate()
        for value in overlay_plan.removals:
            relative = Path(value)
            owned = anchor.capture_file(relative)
            content = owned.content
            anchor.unlink_owned(owned)
            owned.close()
            removed.append((relative, content))
        for publication in receipts:
            publication.commit()
        commit_phase = True
        _commit(replacements, created, receipts)
    except Exception as error:
        if commit_phase:
            for transaction in replacements:
                transaction.close()
            for owned in created:
                owned.close()
            for receipt in receipts:
                receipt.close()
            raise
        if not _rollback(anchor, removed, created, replacements, receipts):
            raise ProfileCommandError(
                "profile apply could not restore its prior state"
            ) from error
        raise


def run(
    args: argparse.Namespace,
    *,
    write: ReceiptPublisher = write_receipt,
    input_stream: TextIO | None = None,
) -> int:
    """Validate and receipt a complete apply before committing its mutations."""
    if getattr(args, "profile_action", None) != "apply":
        print("profile: choose apply")
        return 2
    try:
        workspace = _workspace(args.workspace)
        payload = resolve_payload(getattr(args, "payload", None))
        manifest = load_manifest(resolve_profiles_manifest(payload), payload)
        with memory._WorkspaceAnchor(workspace) as anchor:
            original_profile, profile_identity = anchor.read_file("System/profile.yaml")
            if getattr(args, "candidate_stdin", False):
                stream = sys.stdin if input_stream is None else input_stream
                candidate = stream.read().encode("utf-8")
            else:
                candidate = original_profile
            profile, findings, rendered_profile = _profile_data(candidate)
            if not getattr(args, "candidate_stdin", False) and not findings:
                rendered_profile = original_profile
            if profile["privacy_mode"] not in manifest.privacy_modes:
                raise ProfileCommandError("profile privacy_mode is not available")
            try:
                canonical_work_types(manifest, profile["work_types"])
            except ManifestError as error:
                raise ProfileCommandError(
                    "profile work_types includes an unknown work type"
                ) from error
            overlay_plan = plan_overlay(
                payload,
                workspace,
                manifest,
                privacy_mode=profile["privacy_mode"],
                work_types=profile["work_types"],
            )
            seeds = _seed_plan(anchor, profile)
            profile_updated = rendered_profile != original_profile
            receipt_fields = _receipt_fields(
                profile_updated,
                _overlay_actions(overlay_plan),
                seeds.seeded,
                seeds.skipped,
            )
            receipts = _write_required_receipts(
                anchor, findings, receipt_fields, write
            )
            _apply_changes(
                anchor,
                original_profile,
                profile_identity,
                rendered_profile,
                overlay_plan,
                seeds,
                receipts,
                profile,
            )
    except (PayloadError, ManifestError, ProfileCommandError) as error:
        print(f"profile: {error}")
        return 2
    except Exception:
        print("profile: could not apply the profile safely")
        return 2
    print(
        f"Profile applied: {len(seeds.seeded)} record(s) seeded, "
        f"{len(seeds.skipped)} skipped."
    )
    return 0
