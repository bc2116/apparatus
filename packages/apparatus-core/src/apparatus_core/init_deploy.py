"""Retained-root execution for an already prepared ``apparatus init`` plan."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
import os
from pathlib import Path
import secrets

from apparatus_core.fs_transactions import (
    OwnedDirectory,
    OwnedFile,
    ReplacementTransaction,
    WorkspaceAnchor,
)
from apparatus_core.overlays import ManifestError, OverlayPlan, OverlayWrite
from apparatus_core.payload import (
    PayloadError,
    PayloadFile,
    PayloadPlan,
    normalize_workspace_relative,
)


@dataclass
class _CreatedFile:
    anchor: WorkspaceAnchor
    owned: OwnedFile


@dataclass
class _CreatedDirectory:
    anchor: WorkspaceAnchor
    owned: OwnedDirectory


def _marker_name() -> str:
    return f".apparatus-init-{secrets.token_hex(16)}.tmp"


def _anchor_child(
    parent: WorkspaceAnchor,
    parent_path: Path,
    name: str,
) -> tuple[WorkspaceAnchor, OwnedDirectory | None, bool]:
    """Select one child through the parent anchor, then retain that exact child."""
    relative = Path(name)
    created: OwnedDirectory | None = None
    marker: OwnedFile | None = None
    child: WorkspaceAnchor | None = None
    was_created = False
    try:
        if not parent.entry_exists(relative):
            created = parent.create_directory(relative)
            was_created = True
        marker_relative = relative / _marker_name()
        marker = parent.create_file(
            marker_relative,
            secrets.token_bytes(32),
            owned_parent=created,
        )
        if os.name == "nt" and created is not None:
            # The creation handle requests DELETE access. The marker's retained
            # parent handle is the identity bridge and shares delete, so the
            # creation-only handle can close before the child anchor locks the
            # directory name against native Windows replacement.
            created.close()
            created = None
        child = WorkspaceAnchor(parent_path / name)
        if not child.matches_root_handle(marker.parent):
            raise OSError("workspace directory changed during anchored handoff")
        parent.unlink_owned(marker)
        marker.close()
        marker = None
        if not parent.root_is_current() or not child.root_is_current():
            raise OSError("workspace directory changed during anchored handoff")
        return child, created, was_created
    except Exception:
        if marker is not None:
            try:
                parent.unlink_owned_if_present(marker)
            except OSError:
                pass
            marker.close()
        if child is not None:
            child.close()
        if created is not None:
            try:
                parent.remove_owned_directory(created)
            except OSError:
                pass
            created.close()
        raise


def _anchor_workspace(
    workspace: Path,
) -> tuple[WorkspaceAnchor, tuple[WorkspaceAnchor, ...]]:
    """Anchor an existing root or create missing components with identity handoffs."""
    if workspace.exists():
        return WorkspaceAnchor(workspace), ()

    missing: list[str] = []
    current = workspace
    while not current.exists():
        missing.append(current.name)
        current = current.parent
    if not current.is_dir():
        raise OSError("workspace ancestor is not a directory")

    parent = WorkspaceAnchor(current)
    ancestors: list[WorkspaceAnchor] = [parent]
    current_path = current
    try:
        for name in reversed(missing):
            child, created, _was_created = _anchor_child(parent, current_path, name)
            if created is not None:
                created.close()
            ancestors.append(child)
            parent = child
            current_path /= name
        return parent, tuple(ancestors[:-1])
    except Exception:
        for anchor in reversed(ancestors):
            anchor.close()
        raise


def _all_directories(
    payload: PayloadPlan,
    overlay: OverlayPlan,
) -> tuple[Path, ...]:
    directories: set[Path] = {
        normalize_workspace_relative(value) for value in payload.directories
    }
    file_paths = [
        *(entry.relative for entry in payload.files),
        *payload.placeholders,
        *(write.relative for write in overlay.writes),
        *overlay.removals,
        Path("System/profile.yaml"),
    ]
    for value in file_paths:
        relative = normalize_workspace_relative(value)
        for parent in relative.parents:
            if parent == Path("."):
                break
            directories.add(parent)
    return tuple(sorted(directories, key=lambda path: (len(path.parts), path.as_posix())))


def _validate_plan(payload: PayloadPlan, overlay: OverlayPlan) -> None:
    if not isinstance(payload, PayloadPlan) or not isinstance(overlay, OverlayPlan):
        raise PayloadError("init deployment plan is invalid")
    for entry in payload.files:
        if not isinstance(entry, PayloadFile) or not isinstance(entry.content, bytes):
            raise PayloadError("payload plan file content must be bytes")
        normalize_workspace_relative(entry.relative)
    for value in (*payload.directories, *payload.placeholders):
        normalize_workspace_relative(value)
    for write in overlay.writes:
        if not isinstance(write, OverlayWrite) or not isinstance(write.content, bytes):
            raise ManifestError("overlay plan write content must be bytes")
        normalize_workspace_relative(write.relative)
    for value in overlay.removals:
        normalize_workspace_relative(value)


def deploy_init_plan(
    workspace: str | Path,
    payload: PayloadPlan,
    overlay: OverlayPlan,
    profile_content: bytes,
    *,
    profile_write_required: bool,
) -> tuple[str, ...]:
    """Execute one pre-read init plan through retained directory identities."""
    _validate_plan(payload, overlay)
    if not isinstance(profile_content, bytes):
        raise PayloadError("profile content must be bytes")

    workspace_path = Path(os.path.abspath(os.fspath(workspace)))
    workspace_existed = workspace_path.exists()
    created_files: list[_CreatedFile] = []
    created_directories: list[_CreatedDirectory] = []
    transactions: list[ReplacementTransaction] = []
    changes: list[str] = []

    root, root_ancestors = _anchor_workspace(workspace_path)
    with ExitStack() as stack:
        for ancestor in root_ancestors:
            stack.callback(ancestor.close)
        stack.callback(root.close)
        anchors: dict[Path, WorkspaceAnchor] = {Path("."): root}
        try:
            if not workspace_existed:
                changes.append("created workspace")

            for relative in _all_directories(payload, overlay):
                parent_relative = relative.parent
                if parent_relative == Path("."):
                    parent_relative = Path(".")
                parent = anchors[parent_relative]
                parent_path = workspace_path if parent_relative == Path(".") else workspace_path / parent_relative
                child, created, was_created = _anchor_child(
                    parent, parent_path, relative.name
                )
                anchors[relative] = child
                stack.callback(child.close)
                if created is not None:
                    created_directories.append(_CreatedDirectory(parent, created))
                if was_created:
                    changes.append(f"created {relative.as_posix()}/")

            def parent_for(relative: Path) -> tuple[WorkspaceAnchor, str]:
                parent_relative = relative.parent
                if parent_relative == Path("."):
                    parent_relative = Path(".")
                return anchors[parent_relative], relative.name

            def create_missing(relative: Path, content: bytes, message: str) -> None:
                anchor, name = parent_for(relative)
                if anchor.entry_exists(name):
                    existing = anchor.capture_file(name)
                    existing.close()
                    return
                owned = anchor.create_file(name, content)
                created_files.append(_CreatedFile(anchor, owned))
                changes.append(message)

            def publish(relative: Path, content: bytes, message: str) -> None:
                anchor, name = parent_for(relative)
                if not anchor.entry_exists(name):
                    owned = anchor.create_file(name, content)
                    created_files.append(_CreatedFile(anchor, owned))
                    changes.append(message)
                    return
                existing = anchor.capture_file(name)
                try:
                    if existing.content == content:
                        return
                    transaction = anchor.replace_if_unchanged(
                        name,
                        existing.identity,
                        existing.content,
                        content,
                    )
                    transactions.append(transaction)
                    changes.append(message)
                finally:
                    existing.close()

            def remove(relative: Path, message: str) -> None:
                anchor, name = parent_for(relative)
                if not anchor.entry_exists(name):
                    return
                existing = anchor.capture_file(name)
                try:
                    anchor.unlink_owned(existing)
                    changes.append(message)
                finally:
                    existing.close()

            for entry in payload.files:
                relative = normalize_workspace_relative(entry.relative)
                create_missing(
                    relative,
                    entry.content,
                    f"restored {relative.as_posix()}",
                )
            for write in overlay.writes:
                relative = normalize_workspace_relative(write.relative)
                publish(relative, write.content, f"updated {relative.as_posix()}")
            if profile_write_required:
                relative = Path("System/profile.yaml")
                publish(relative, profile_content, "updated System/profile.yaml")
            for value in payload.placeholders:
                relative = normalize_workspace_relative(value)
                remove(relative, f"removed {relative.as_posix()}")
            for value in overlay.removals:
                relative = normalize_workspace_relative(value)
                remove(relative, f"removed {relative.as_posix()}")

            if not all(anchor.root_is_current() for anchor in anchors.values()):
                raise OSError("workspace directory changed before init completion")
            if not all(item.anchor.matches_owned(item.owned) for item in created_files):
                raise OSError("workspace file changed before init completion")
            for transaction in transactions:
                transaction.validate_commit()
            for transaction in transactions:
                transaction.commit()
            if not root.root_is_current():
                raise OSError("workspace root changed before init completion")
            return tuple(changes)
        except Exception:
            for transaction in reversed(transactions):
                try:
                    transaction.rollback()
                except OSError:
                    pass
            for item in reversed(created_files):
                try:
                    item.anchor.unlink_owned_if_present(item.owned)
                except OSError:
                    pass
            for item in reversed(created_directories):
                try:
                    item.anchor.remove_owned_directory(item.owned)
                except OSError:
                    pass
            raise
        finally:
            for transaction in transactions:
                transaction.close()
            for item in created_files:
                item.owned.close()
            for item in created_directories:
                item.owned.close()
