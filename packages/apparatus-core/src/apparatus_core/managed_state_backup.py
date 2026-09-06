"""Export declared managed state without traversing project files or root Git."""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
import os
import tempfile
from typing import Any, Callable

from apparatus_core import backup as publication
from apparatus_core.backup import BackupError, BackupResult, BackupUsageError
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.receipts import write_receipt
from apparatus_core.retention import TASK_DIRECTORY, _decision, _task_bytes, _task_id, operation
from apparatus_core.snapshots import SnapshotError, git_available
from apparatus_core.workspace_layout import LayoutError, MARKER, read_layout

SCOPE_NOTE = "MANAGED-BACKUP.md"


class _TaskProof:
    """Pin controls for validation, emitting only their closed metadata schema."""

    def __init__(self, root: Path, anchor: Any):
        self.anchor = anchor
        self.directory = None
        self.files: dict[str, bytes] = {}
        self.preimages: dict[Path, tuple[Any, Any]] = {}
        self.present = anchor.directory_exists(TASK_DIRECTORY)
        try:
            if self.present:
                self.directory = WorkspaceAnchor(root / TASK_DIRECTORY)
                for path in self._paths():
                    if path.parent != Path(TASK_DIRECTORY) or path.suffix != ".yaml":
                        raise BackupError("Task controls contain an unsupported entry.")
                    identifier = _task_id(path.stem)
                    content, identity = anchor.read_file(path)
                    self.files[path.as_posix()] = _task_bytes(identifier, _decision(content, identifier))
                    self.preimages[path] = (content, identity)
            self.validate()
        except Exception:
            self.close()
            raise

    def _paths(self) -> list[Path]:
        endpoint = self.directory._root if os.name == "posix" else self.directory.workspace
        return [Path(TASK_DIRECTORY) / name for name in os.listdir(endpoint)]

    def validate(self) -> None:
        if self.anchor.directory_exists(TASK_DIRECTORY) != self.present:
            raise BackupError("Task enrollment changed during backup export.")
        if not self.present:
            return
        if not self.directory.root_is_current():
            raise BackupError("Task controls changed during backup export.")
        if set(self._paths()) != set(self.preimages):
            raise BackupError("Task controls changed during backup export.")
        for path, preimage in self.preimages.items():
            if self.anchor.read_file(path) != preimage:
                raise BackupError("Task controls changed during backup export.")

    def close(self) -> None:
        publication._close_nonraising(self.directory)


class _ArchiveSource:
    """A closed in-memory inventory; this object cannot scan the source root."""

    def __init__(self, files: dict[str, bytes], tasks_present: bool):
        self.files = files
        self.tasks_present = tasks_present

    def write_entries(self, archive: Any, _transients: Any = ()) -> None:
        if self.tasks_present:
            archive.writestr(publication._zip_info(
                Path(TASK_DIRECTORY), directory=True, modified=0, executable=False,
            ), b"")
        for name, content in sorted(self.files.items()):
            archive.writestr(publication._zip_info(
                Path(name), directory=False, modified=0, executable=False,
            ), content)


def _archive_identity(owned: Any) -> tuple[Any, ...]:
    descriptor = owned.file_descriptor if hasattr(owned, "file_descriptor") else owned.handle
    return publication._stable_file_identity(os.fstat(descriptor))


def _checkpoint(source: Any, target: Any, root: Any, destination: Any,
                owned: Any, archive_identity: Any, proofs: tuple[Any, ...],
                receipt: Any = None, receipt_files: tuple[Any, ...] = ()) -> None:
    source.require_path_current()
    target.require_path_current()
    if not root.matches_root_handle(source.handle) or not destination.matches_root_handle(target.handle):
        raise BackupError("Backup directory identity changed.")
    target.require_outside(source, workspace_anchor=root, destination_anchor=destination, changed=True)
    for proof in proofs:
        proof.validate()
    if receipt is not None:
        receipt.validate()
    if receipt_files:
        publication._validate_backup_receipt_files(root, receipt_files)
    source.require_path_current()
    target.require_path_current()
    if not root.root_is_current() or not destination.root_is_current():
        raise BackupError("Backup directory identity changed.")
    owned.validate_name()
    if _archive_identity(owned) != archive_identity:
        raise BackupError("Backup archive changed during publication.")


def export_backup(workspace: str | Path, destination: str | Path, *,
                  available: Callable[[], bool] = git_available,
                  write: Callable[..., object] = write_receipt,
                  clock: Callable[[], datetime] | None = None,
                  task_id: str | None = None,
                  prepare: Callable[..., Any] | None = None) -> BackupResult:
    """Publish current managed state and reachable history with exact compensation."""
    from apparatus_core import managed_state_recovery as recovery

    root_path = publication._absolute(workspace)
    destination_path = publication._absolute(destination)
    timestamp = publication.utc_archive_timestamp(clock)
    source_type, target_type = publication._anchor_types()
    try:
        layout = read_layout(root_path)
        if layout is None:
            raise BackupUsageError("Managed backup requires a managed work-area marker.")
        with ExitStack() as stack:
            stack.enter_context(operation(root_path, task_id=task_id, require_task=True,
                                          requested=("snapshot",)))
            source = stack.enter_context(source_type(root_path))
            target = stack.enter_context(target_type(destination_path))
            anchor = stack.enter_context(WorkspaceAnchor(root_path))
            destination_anchor = stack.enter_context(WorkspaceAnchor(destination_path))
            target.require_outside(source, workspace_anchor=anchor, destination_anchor=destination_anchor)
            layout.validate(anchor)
            tasks = _TaskProof(root_path, anchor)
            stack.callback(tasks.close)
            capture = recovery.capture_state(root_path)
            stack.callback(publication._close_nonraising, capture)
            capture.validate()
            snapshots_available = available()
            if not snapshots_available and anchor.entry_exists("System/recovery"):
                raise BackupError("Git is unavailable; existing managed history cannot be validated.")
            transaction = owned = receipt = None
            receipt_files: tuple[Any, ...] = ()
            completed = False
            try:
                proofs: list[Any] = [capture, tasks]
                files = dict(capture.files)
                files[MARKER] = layout.canonical_bytes()
                files.update(tasks.files)
                snapshot_id = None
                if snapshots_available:
                    transaction = (prepare or recovery.prepare_snapshot)(
                        root_path, label="Before managed backup export", requested=True,
                    )
                    if transaction.result.snapshot is not None:
                        snapshot_id = transaction.result.snapshot.identifier
                    proofs.append(transaction)
                    staging = stack.enter_context(tempfile.TemporaryDirectory(
                        prefix="apparatus-managed-backup-", ignore_cleanup_errors=True,
                        dir=Path(tempfile.gettempdir()).resolve(strict=True),
                    ))
                    history = recovery.stage_reachable_history(root_path, Path(staging) / "store")
                    stack.callback(publication._close_nonraising, history)
                    proofs.append(history)
                    files.update({f"System/recovery/store/{name}": content
                                  for name, content in history.files.items()})
                files[SCOPE_NOTE] = (
                    "# Apparatus managed-state backup\n\n"
                    "Contains declared managed records and instructions, the work-area routing marker, "
                    "and export-time task restrictions.\n"
                    + ("Includes validated reachable managed snapshot history.\n" if snapshots_available else
                       "Snapshot history is unavailable because Git was unavailable; no existing store was omitted.\n")
                    + "Project files, project Git repositories, Library originals, caches and unknown files "
                    "are not included. Restore preserves later additions. Historical Memory may revive older "
                    "information. Task controls record export-time restrictions only.\n"
                ).encode("utf-8")
                for proof in proofs:
                    proof.validate()
                layout.validate(anchor)
                owned = target.allocate(timestamp)
                size = publication._write_archive(_ArchiveSource(files, tasks.present), owned)
                archive_identity = _archive_identity(owned)

                def checkpoint(live_receipt: Any = None, durable_receipt: bool = False) -> None:
                    layout.validate(anchor)
                    if not snapshots_available and anchor.entry_exists("System/recovery"):
                        raise BackupError("Managed history appeared during backup export.")
                    _checkpoint(source, target, anchor, destination_anchor, owned, archive_identity,
                                tuple(proofs), live_receipt, receipt_files if durable_receipt else ())

                checkpoint()
                result = BackupResult(destination_path / owned.name, snapshot_id, snapshots_available, size,
                                      scope="managed-state")
                fields = publication._receipt_fields(result, destination_path)
                fields["body"] = "Exported declared managed state; project and Library originals are excluded.\n"
                receipt = publication._write_owned_backup_receipt(write, root_path, fields)
                receipt_files = publication._capture_backup_receipt_files(root_path, anchor, receipt)
                receipt.commit()
                if transaction is not None:
                    transaction.settle()
                checkpoint(receipt)
                receipt.close()
                checkpoint(durable_receipt=True)
                if transaction is not None:
                    transaction.accept()
                publication._close_nonraising_many(receipt_files)
                try:
                    owned.finish()
                except Exception:
                    pass
                completed = True
                return result
            finally:
                if not completed:
                    errors = publication._cleanup_owned_receipt(receipt, anchor, receipt_files)
                    if owned is not None:
                        try:
                            owned.cleanup()
                        except Exception as error:
                            errors.append(error)
                    if transaction is not None:
                        try:
                            transaction.rollback()
                        except Exception as error:
                            errors.append(error)
                    if errors:
                        raise BackupError("Managed backup failed and exact cleanup could not be completed safely.") from errors[0]
                publication._close_nonraising(transaction)
    except BackupError:
        raise
    except LayoutError as error:
        raise BackupUsageError(str(error)) from error
    except (OSError, SnapshotError) as error:
        raise BackupError("Managed backup export could not be completed safely.") from error
