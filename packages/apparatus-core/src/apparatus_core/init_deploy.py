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
    child: WorkspaceAnchor


@dataclass
class _Removal:
    transaction: ReplacementTransaction
    target_removed: bool = False


def _removal_tombstone() -> bytes:
    return b"apparatus init removal\n" + secrets.token_bytes(32)


def _anchor_child(
    parent: WorkspaceAnchor,
    parent_path: Path,
    name: str,
) -> tuple[WorkspaceAnchor, OwnedDirectory | None, bool]:
    """Select one child through the parent anchor, then retain that exact child."""
    relative = Path(name)
    created: OwnedDirectory | None = None
    handoff = -1
    child: WorkspaceAnchor | None = None
    was_created = False
    try:
        try:
            created = parent.create_directory(relative)
            was_created = True
        except FileExistsError:
            # Existing and missing children converge on the same retained
            # first-object handoff below. There is deliberately no existence
            # probe whose result could go stale before object selection.
            pass
        handoff = parent.open_directory(
            relative,
            shares_delete=created is not None,
        )
        child = WorkspaceAnchor(
            parent_path / name,
            ancestor_shares_delete=parent.child_ancestor_shares_delete(),
            root_shares_delete=created is not None,
        )
        if not child.matches_root_handle(handoff):
            raise OSError("workspace directory changed during anchored handoff")
        parent.close_directory(handoff)
        handoff = -1
        if not parent.root_is_current() or not child.root_is_current():
            raise OSError("workspace directory changed during anchored handoff")
        return child, created, was_created
    except Exception as handoff_error:
        cleanup_error: Exception | None = None
        if handoff >= 0:
            try:
                parent.close_directory(handoff)
            except Exception as error:
                cleanup_error = error
        if child is not None:
            child.close()
        if created is not None:
            try:
                parent.remove_owned_directory(created)
            except Exception as error:
                cleanup_error = error
            created.close()
        if cleanup_error is not None:
            raise OSError(
                "workspace handoff cleanup was incomplete"
            ) from handoff_error
        raise


def _anchor_workspace(
    workspace: Path,
) -> tuple[
    WorkspaceAnchor,
    tuple[WorkspaceAnchor, ...],
    tuple[_CreatedDirectory, ...],
    bool,
]:
    """Anchor an existing root or create missing components with identity handoffs."""
    if workspace == Path(workspace.anchor):
        return WorkspaceAnchor(workspace), (), (), False

    # Always select the workspace's final component through its retained
    # parent. This gives existing and missing workspaces the same first-object
    # identity handoff and removes the former exists-then-anchor race.
    missing: list[str] = [workspace.name]
    current = workspace.parent
    while not current.exists():
        missing.append(current.name)
        current = current.parent
    if not current.is_dir():
        raise OSError("workspace ancestor is not a directory")

    parent = WorkspaceAnchor(current)
    ancestors: list[WorkspaceAnchor] = [parent]
    created_directories: list[_CreatedDirectory] = []
    current_path = current
    workspace_created = False
    try:
        for name in reversed(missing):
            child, created, was_created = _anchor_child(parent, current_path, name)
            ancestors.append(child)
            if created is not None:
                created_directories.append(_CreatedDirectory(parent, created, child))
            parent = child
            current_path /= name
            workspace_created = was_created
        return (
            parent,
            tuple(ancestors[:-1]),
            tuple(created_directories),
            workspace_created,
        )
    except Exception:
        cleanup_errors: list[Exception] = []
        for item in reversed(created_directories):
            item.child.close()
            try:
                item.anchor.remove_owned_directory(item.owned)
            except Exception as error:
                cleanup_errors.append(error)
            item.owned.close()
        for anchor in reversed(ancestors):
            anchor.close()
        if cleanup_errors:
            raise OSError(
                "workspace anchor cleanup was incomplete after handoff failure"
            )
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
    expected_contents: dict[str, bytes | None] | None = None,
) -> tuple[str, ...]:
    """Execute one pre-read init plan through retained directory identities."""
    _validate_plan(payload, overlay)
    expected_contents = dict(expected_contents or {})
    for relative, content in expected_contents.items():
        normalize_workspace_relative(relative)
        if content is not None and not isinstance(content, bytes):
            raise PayloadError("instruction preimage must be bytes or expected absence")
    if not isinstance(profile_content, bytes):
        raise PayloadError("profile content must be bytes")

    workspace_path = Path(os.path.abspath(os.fspath(workspace)))
    created_files: list[_CreatedFile] = []
    created_directories: list[_CreatedDirectory]
    transactions: list[ReplacementTransaction] = []
    removals: list[_Removal] = []
    changes: list[str] = []
    published: set[str] = set()

    root, root_ancestors, root_created, workspace_created = _anchor_workspace(
        workspace_path
    )
    created_directories = list(root_created)
    with ExitStack() as stack:
        for ancestor in root_ancestors:
            stack.callback(ancestor.close)
        stack.callback(root.close)
        anchors: dict[Path, WorkspaceAnchor] = {Path("."): root}
        try:
            if workspace_created:
                changes.append("created workspace")

            for relative in _all_directories(payload, overlay):
                parent_relative = relative.parent
                if parent_relative == Path("."):
                    parent_relative = Path(".")
                parent = anchors[parent_relative]
                parent_path = (
                    workspace_path
                    if parent_relative == Path(".")
                    else workspace_path / parent_relative
                )
                child, created, was_created = _anchor_child(
                    parent, parent_path, relative.name
                )
                anchors[relative] = child
                stack.callback(child.close)
                if created is not None:
                    created_directories.append(
                        _CreatedDirectory(parent, created, child)
                    )
                if was_created:
                    changes.append(f"created {relative.as_posix()}/")

            def parent_for(relative: Path) -> tuple[WorkspaceAnchor, str]:
                parent_relative = relative.parent
                if parent_relative == Path("."):
                    parent_relative = Path(".")
                return anchors[parent_relative], relative.name

            def require_preimage(relative: Path, actual: bytes | None) -> None:
                key = relative.as_posix()
                if key in expected_contents and actual != expected_contents[key]:
                    raise PayloadError(
                        "instruction changed after migration planning; rerun apparatus init"
                    )

            def check_preimage(relative: str) -> None:
                try:
                    actual = root.read_file(relative)[0]
                except FileNotFoundError:
                    actual = None
                require_preimage(Path(relative), actual)

            def create_missing(relative: Path, content: bytes, message: str) -> None:
                anchor, name = parent_for(relative)
                if anchor.entry_exists(name):
                    existing = anchor.capture_file(name)
                    try:
                        require_preimage(relative, existing.content)
                    finally:
                        existing.close()
                    return
                require_preimage(relative, None)
                owned = anchor.create_file(name, content)
                created_files.append(_CreatedFile(anchor, owned))
                published.add(relative.as_posix())
                changes.append(message)

            def publish(relative: Path, content: bytes, message: str) -> None:
                anchor, name = parent_for(relative)
                if not anchor.entry_exists(name):
                    require_preimage(relative, None)
                    owned = anchor.create_file(name, content)
                    created_files.append(_CreatedFile(anchor, owned))
                    published.add(relative.as_posix())
                    changes.append(message)
                    return
                existing = anchor.capture_file(name)
                try:
                    require_preimage(relative, existing.content)
                    if existing.content == content:
                        return
                    transaction = anchor.replace_if_unchanged(
                        name,
                        existing.identity,
                        existing.content,
                        content,
                    )
                    transactions.append(transaction)
                    published.add(relative.as_posix())
                    changes.append(message)
                finally:
                    existing.close()

            def remove(relative: Path, message: str) -> None:
                anchor, name = parent_for(relative)
                if not anchor.entry_exists(name):
                    require_preimage(relative, None)
                    return
                existing = anchor.capture_file(name)
                try:
                    require_preimage(relative, existing.content)
                    transaction = anchor.replace_if_unchanged(
                        name,
                        existing.identity,
                        existing.content,
                        _removal_tombstone(),
                    )
                    removals.append(_Removal(transaction))
                    published.add(relative.as_posix())
                    changes.append(message)
                finally:
                    existing.close()

            # Reject stale migration plans before any file publication. The
            # replacement repeats this preimage check at its transaction boundary.
            for relative in expected_contents:
                check_preimage(relative)

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

            def validate_final_state(*, removals_are_published: bool) -> None:
                for relative in expected_contents.keys() - published:
                    check_preimage(relative)
                all_anchors = (*root_ancestors, *anchors.values())
                if not all(anchor.root_is_current() for anchor in all_anchors):
                    raise OSError(
                        "workspace directory changed before init completion"
                    )
                if not all(
                    item.anchor.matches_owned(item.owned)
                    for item in created_files
                ):
                    raise OSError("workspace file changed before init completion")
                for transaction in transactions:
                    if transaction.finished:
                        if not transaction.anchor.matches_owned(transaction.target):
                            raise OSError(
                                "workspace replacement changed before init completion"
                            )
                    else:
                        transaction.validate_commit()
                for removal in removals:
                    transaction = removal.transaction
                    if removal.target_removed:
                        if transaction.anchor.entry_exists(
                            transaction.target.relative
                        ):
                            raise OSError(
                                "removed workspace file changed before init completion"
                            )
                    elif removals_are_published:
                        raise OSError(
                            "workspace removal was not finalized before init completion"
                        )
                    else:
                        transaction.validate_commit()

            # This is the reversible final gate. Every created object and
            # replacement/removal preimage is still retained at this point.
            validate_final_state(removals_are_published=False)
            for transaction in transactions:
                transaction.commit()
            for removal in removals:
                transaction = removal.transaction
                if not transaction.anchor.matches_owned(transaction.target):
                    raise OSError(
                        "workspace removal changed before init completion"
                    )
                transaction.anchor.unlink_owned(transaction.target)
                removal.target_removed = True
                transaction.discard_backup()
            # A committed replacement keeps its exact target proof. A removal
            # keeps its preimage bytes. That makes this post-settlement gate
            # reversible if a directory or file changed during finalization.
            validate_final_state(removals_are_published=True)
            return tuple(changes)
        except Exception as deployment_error:
            cleanup_errors: list[Exception] = []

            for removal in reversed(removals):
                transaction = removal.transaction
                try:
                    if removal.target_removed:
                        try:
                            restored = transaction.anchor.create_file(
                                transaction.target.relative,
                                transaction.backup.content,
                            )
                        except FileExistsError as error:
                            raise OSError(
                                "managed removal path changed before rollback"
                            ) from error
                        try:
                            if not transaction.anchor.matches_owned(restored):
                                raise OSError(
                                    "managed removal could not be rematerialized"
                                )
                        finally:
                            restored.close()
                        if not transaction.finished:
                            transaction.discard_backup()
                    elif transaction.finished:
                        transaction.anchor.restore_owned_if_unchanged(
                            transaction.target,
                            transaction.backup.content,
                        )
                    else:
                        transaction.rollback()
                except Exception as error:
                    cleanup_errors.append(error)
                finally:
                    # Win32 defers deletion while retained file and parent
                    # handles remain open. Release each settled proof before
                    # cleaning invocation-owned ancestor directories.
                    transaction.close()

            for transaction in reversed(transactions):
                try:
                    if transaction.finished:
                        transaction.anchor.restore_owned_if_unchanged(
                            transaction.target,
                            transaction.backup.content,
                        )
                    else:
                        transaction.rollback()
                except Exception as error:
                    cleanup_errors.append(error)
                finally:
                    transaction.close()

            for item in reversed(created_files):
                try:
                    item.anchor.unlink_owned_if_present(item.owned)
                except Exception as error:
                    cleanup_errors.append(error)
                finally:
                    item.owned.close()

            for item in reversed(created_directories):
                item.child.close()
                try:
                    item.anchor.remove_owned_directory(item.owned)
                except Exception as error:
                    cleanup_errors.append(error)
                finally:
                    # A child's retained parent handle can otherwise keep its
                    # parent's deletion pending on Windows until too late.
                    item.owned.close()

            if cleanup_errors:
                raise OSError(
                    "init deployment rollback was incomplete: "
                    f"{len(cleanup_errors)} exact cleanup operation(s) failed"
                ) from deployment_error
            raise
        finally:
            for transaction in transactions:
                transaction.close()
            for removal in removals:
                removal.transaction.close()
            for item in created_files:
                item.owned.close()
            for item in created_directories:
                item.owned.close()
