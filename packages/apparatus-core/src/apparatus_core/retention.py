"""Small, file-backed task decisions and invocation-scoped retention policy."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from pathlib import Path
import re
from typing import Iterable, Mapping, Any
from uuid import UUID, uuid4

from apparatus_core import records
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.init_deploy import _anchor_child
from apparatus_core.payload import preflight_workspace_paths

TASK_DIRECTORY = "System/tasks"
TASK_SCHEMA = "apparatus/task@v0"


class TaskRetentionError(ValueError):
    """A task decision is missing, unsafe, or invalid."""


class RetentionSuppressed(TaskRetentionError):
    """A valid task suppresses automatic content retention."""


@dataclass(frozen=True)
class TaskContext:
    workspace: Path
    task_id: str | None
    save_memory: bool
    legacy: bool = False
    requested: frozenset[str] = frozenset()

    def require_identity(self) -> None:
        if not self.legacy and self.task_id is None:
            raise TaskRetentionError("Start a task, then pass --task ID to this operation.")

    def require_memory_write(self) -> None:
        self.require_identity()
        if not self.save_memory:
            raise RetentionSuppressed("This task does not save new Memory or setup answers.")

    def require_library_write(self) -> None:
        self.require_identity()
        if not self.save_memory and "library" not in self.requested:
            raise RetentionSuppressed("Automatic Library capture is off for this task.")

    def require_snapshot(self) -> None:
        self.require_identity()
        if not self.save_memory and "snapshot" not in self.requested:
            raise RetentionSuppressed("Automatic snapshots are off for this task.")


_current: ContextVar[TaskContext | None] = ContextVar("apparatus_task", default=None)


def _workspace(workspace: str | Path) -> Path:
    try:
        root = preflight_workspace_paths(Path(workspace))
        if not root.is_dir():
            raise OSError("missing workspace")
        return root
    except (OSError, ValueError) as error:
        raise TaskRetentionError("Task workspace must be an existing safe directory.") from error


def _task_id(value: str) -> str:
    try:
        parsed = UUID(value)
        if str(parsed) != value or parsed.version != 4:
            raise ValueError("not a canonical random UUID")
    except (ValueError, TypeError, AttributeError) as error:
        raise TaskRetentionError("Task ID must be the UUID returned by task start.") from error
    return value


def _task_bytes(task_id: str, save_memory: bool) -> bytes:
    return records.yaml.safe_dump({
        "schema": TASK_SCHEMA, "id": task_id,
        "memory": "save" if save_memory else "no-save",
    }, sort_keys=False).encode("utf-8")


def _decision(content: bytes, task_id: str) -> bool:
    try:
        if len(content) > 4096:
            raise ValueError("oversized control")
        text = content.decode("utf-8", errors="strict")
        node = records.yaml.compose(text)
        if not isinstance(node, records.yaml.MappingNode):
            raise ValueError("not a mapping")
        keys = [key.value for key, _ in node.value]
        if len(keys) != 3 or set(keys) != {"schema", "id", "memory"}:
            raise ValueError("unknown or duplicate control keys")
        data = records.yaml.safe_load(text)
        if (data["schema"] != TASK_SCHEMA or data["id"] != task_id
                or data["memory"] not in {"save", "no-save"}):
            raise ValueError("invalid control values")
        return data["memory"] == "save"
    except (ValueError, TypeError, UnicodeError, records.yaml.YAMLError) as error:
        raise TaskRetentionError("Task control is invalid; repair it without enabling retention.") from error


def context_for(workspace: str | Path, *, task_id: str | None = None,
                require_task: bool = False) -> TaskContext:
    root = _workspace(workspace)
    if task_id is not None:
        _task_id(task_id)
    current = _current.get()
    if current is not None and task_id is None and current.workspace != root:
        raise TaskRetentionError("Task context cannot be inherited by another workspace.")
    if current is not None and current.workspace == root and task_id in {None, current.task_id}:
        result = current
    else:
        try:
            with WorkspaceAnchor(root) as anchor:
                enabled = anchor.directory_exists(TASK_DIRECTORY)
                if task_id is not None:
                    identifier = _task_id(task_id)
                    content, _ = anchor.read_file(f"{TASK_DIRECTORY}/{identifier}.yaml")
                    result = TaskContext(root, identifier, _decision(content, identifier))
                else:
                    result = TaskContext(root, None, not enabled, legacy=not enabled)
        except OSError as error:
            raise TaskRetentionError("Task control is missing or unsafe; use a valid task ID.") from error
    if require_task:
        result.require_identity()
    return result


@contextmanager
def operation(workspace: str | Path, *, task_id: str | None = None,
              require_task: bool = False, requested: Iterable[str] = ()):
    context = context_for(workspace, task_id=task_id, require_task=require_task)
    permissions = frozenset(requested)
    if not permissions <= {"library", "snapshot"}:
        raise TaskRetentionError("Unknown task operation exception.")
    context = replace(context, requested=context.requested | permissions)
    token = _current.set(context)
    try:
        yield context
    finally:
        _current.reset(token)


def start_task(workspace: str | Path, *, save_memory: bool | None = None) -> TaskContext:
    root = _workspace(workspace)
    if save_memory is not None and not isinstance(save_memory, bool):
        raise TaskRetentionError("Task memory choice must be a boolean.")
    with WorkspaceAnchor(root) as anchor:
        try:
            raw, _ = anchor.read_file("System/profile.yaml")
            profile = records.yaml.safe_load(raw.decode("utf-8"))
            if not isinstance(profile, dict) or records.validate("profile", profile, "profile.yaml"):
                raise ValueError("invalid profile")
        except (OSError, ValueError, UnicodeError, records.yaml.YAMLError) as error:
            raise TaskRetentionError("Repair the workspace profile before starting a task.") from error
        decision = profile["privacy_mode"] != "private" if save_memory is None else save_memory
        identifier = str(uuid4())
        system, system_created, _ = _anchor_child(anchor, root, "System")
        tasks = created = owned = None
        succeeded = False
        try:
            tasks, created, _ = _anchor_child(system, root / "System", "tasks")
            owned = tasks.create_file(f"{identifier}.yaml", _task_bytes(identifier, decision))
            if not tasks.matches_owned(owned) or not system.root_is_current() or not anchor.root_is_current():
                raise OSError("task publication changed")
            succeeded = True
        except OSError as error:
            if tasks is not None and owned is not None:
                tasks.unlink_owned(owned)
            raise TaskRetentionError("Task could not be created safely; retry task start.") from error
        finally:
            if owned is not None:
                owned.close()
            if tasks is not None:
                tasks.close()
            if created is not None:
                if not succeeded:
                    system.remove_owned_directory(created)
                created.close()
            system.close()
            if system_created is not None:
                system_created.close()
        return TaskContext(root, identifier, decision)


def set_no_memory(workspace: str | Path, task_id: str) -> TaskContext:
    root = _workspace(workspace)
    identifier = _task_id(task_id)
    relative = f"{TASK_DIRECTORY}/{identifier}.yaml"
    try:
        with WorkspaceAnchor(root) as anchor:
            content, identity = anchor.read_file(relative)
            save = _decision(content, identifier)
            if save:
                transaction = anchor.replace_if_unchanged(relative, identity, content,
                                                           _task_bytes(identifier, False))
                try:
                    transaction.validate_commit()
                    transaction.commit()
                except Exception:
                    # Once no-save is published, cleanup failure must not
                    # reinstate a weaker saving decision.
                    transaction.discard_backup()
                    raise
                finally:
                    transaction.close()
            else:
                current, current_identity = anchor.read_file(relative)
                if current != content or current_identity != identity:
                    raise OSError("task changed")
        return TaskContext(root, identifier, False)
    except OSError as error:
        raise TaskRetentionError("Task changed or is unsafe; retry the no-memory instruction.") from error


def metadata_fields(workspace: str | Path, event: str, fields: Mapping[str, Any],
                    *, context: TaskContext | None = None) -> dict[str, Any]:
    """Shape no-save receipts before their bytes and ownership are bound."""
    context = context or context_for(workspace)
    if {"schema", "event", "timestamp"} & fields.keys():
        raise ValueError("receipt fields cannot override protected fields")
    if context.save_memory:
        return dict(fields)
    if event not in records.RECEIPT_EVENTS:
        raise ValueError("unknown receipt event")
    result: dict[str, Any] = {"summary": f"Apparatus {event} operation."}
    if context.task_id is not None:
        result["task_id"] = context.task_id
    for key in ("count", "total", "extracted", "indexed", "skipped", "failed", "matched",
                "examined", "changed", "files", "bytes", "sources"):
        value = fields.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            result[key] = value
    for key in ("snapshot_id", "commit", "commit_id", "tree", "archive_sha256"):
        value = fields.get(key)
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value):
            result[key] = value
    status = fields.get("status")
    if isinstance(status, str) and status in {
        "ok", "completed", "failed", "skipped", "unavailable", "no-op", "disabled",
        "restored", "exported", "matched", "no-match",
    }:
        result["status"] = status
    return result
