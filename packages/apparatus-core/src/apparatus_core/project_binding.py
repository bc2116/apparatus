"""Explicit, portable project links to one work area; no discovery registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from contextlib import nullcontext
import os
from pathlib import Path
from typing import Any
from uuid import UUID

from apparatus_core import records
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.init_deploy import _anchor_child
from apparatus_core.payload import preflight_workspace_paths
from apparatus_core.workspace_layout import LayoutError, _root_identity, read_layout

CONTROL_DIRECTORY = ".apparatus"
CONTROL = ".apparatus/workspace.yaml"
SCHEMA = "apparatus/project@v0"
MANAGED_ROOTS = {"goals", "memory", "system", "library", "decisions", "deliverables"}
CONTROL_COMPONENTS = {".git", ".apparatus", ".agents", ".claude", ".cursor", ".github"}
BLOCK_START = b"<!-- Apparatus project link: v1 -->"
BLOCK_END = b"<!-- /Apparatus project link -->"
BLOCK = b"\n".join((
    BLOCK_START,
    b"Read .apparatus/workspace.yaml to find this project's work area.",
    b"Resolve its relative workspace path and verify its workspace_id against",
    b"System/workspace.yaml there before reading that work area's AGENTS.md.",
    b"Use that area's Memory, goals and Library; keep this project's instructions",
    b"and finished files here. A missing or invalid link needs repair, not an",
    b"ancestor search. Apparatus commands accept this project as WORKSPACE.",
    BLOCK_END,
))


class BindingError(ValueError):
    """A project link cannot be selected or changed safely."""


def _root(value: str | Path) -> Path:
    try:
        root = preflight_workspace_paths(Path(value))
        if not root.is_dir():
            raise OSError("missing directory")
        return root
    except (OSError, ValueError) as error:
        raise BindingError("Choose an existing project or work-area directory without links.") from error


def _read_optional(anchor: Any, path: str) -> tuple[bytes, Any] | None:
    try:
        return anchor.read_file(path)
    except FileNotFoundError:
        return None


def _names(anchor: Any) -> set[str]:
    endpoint = anchor._root if os.name == "posix" else anchor.workspace
    result = set(os.listdir(endpoint))
    if not anchor.root_is_current():
        raise BindingError("Project control directory changed; retry the operation.")
    return result


def _control_names(project: Any) -> set[str] | None:
    if not project.directory_exists(CONTROL_DIRECTORY):
        return None
    handle = project.open_directory(CONTROL_DIRECTORY)
    try:
        with WorkspaceAnchor(project.workspace / CONTROL_DIRECTORY) as child:
            if not child.matches_root_handle(handle):
                raise BindingError("Project control directory changed; retry the operation.")
            return _names(child)
    finally:
        project.close_directory(handle)


def _parse(content: bytes) -> tuple[str, str]:
    try:
        if len(content) > 4096:
            raise ValueError("oversized control")
        text = content.decode("utf-8", errors="strict")
        node = records.yaml.compose(text)
        if not isinstance(node, records.yaml.MappingNode):
            raise ValueError("not a mapping")
        keys = [key.value for key, _ in node.value]
        if len(keys) != 3 or set(keys) != {"schema", "workspace", "workspace_id"}:
            raise ValueError("unknown or duplicate fields")
        data = records.yaml.safe_load(text)
        identifier, relative = data["workspace_id"], data["workspace"]
        parsed = UUID(identifier)
        # A work area must be an ancestor of the explicit project. Therefore the
        # entire portable path is a bounded sequence of parent components.
        parts = relative.split("/")
        if (data["schema"] != SCHEMA or str(parsed) != identifier or parsed.version != 4
                or not 1 <= len(parts) <= 64 or any(part != ".." for part in parts)):
            raise ValueError("invalid relative link")
        return relative, identifier
    except (ValueError, TypeError, AttributeError, UnicodeError, records.yaml.YAMLError) as error:
        raise BindingError("Repair the closed metadata in .apparatus/workspace.yaml before continuing.") from error


def _bytes(relative: str, identifier: str) -> bytes:
    return records.yaml.safe_dump({"schema": SCHEMA, "workspace": relative,
                                   "workspace_id": identifier}, sort_keys=False).encode("utf-8")


def _relative(project: Path, workspace: Path) -> str:
    try:
        parts = project.relative_to(workspace).parts
        if (not parts or parts[0].casefold() in MANAGED_ROOTS or len(parts) > 64
                or any(part.casefold() in CONTROL_COMPONENTS for part in parts)):
            raise ValueError("not a project directory")
        return "/".join(".." for _ in parts)
    except ValueError as error:
        raise BindingError("Choose a project inside the work area, outside managed and Git or app control folders.") from error


@dataclass(frozen=True)
class ProjectBinding:
    project: Path
    relative_workspace: str
    workspace_id: str
    content: bytes = field(repr=False)
    _identity: Any = field(repr=False)
    _root: Any = field(repr=False)

    def validate(self, anchor: Any) -> None:
        if (anchor.workspace != self.project or not anchor.root_is_current()
                or _root_identity(anchor) != self._root
                or anchor.read_file(CONTROL) != (self.content, self._identity)
                or _control_names(anchor) != {"workspace.yaml"}):
            raise BindingError("Project link changed; retry with the intended work area.")


def read_project_binding(project: str | Path) -> ProjectBinding | None:
    """Read only this root's control, including evidence of a lost link."""
    try:
        root = _root(project)
        with WorkspaceAnchor(root) as anchor:
            value = _read_optional(anchor, CONTROL)
            if value is None:
                try:
                    canon = _read_optional(anchor, "AGENTS.md")
                except OSError as error:
                    raise BindingError("Project AGENTS.md is unsafe; repair it before checking its work-area link.") from error
                if (_control_names(anchor) is not None
                        or (canon and (b"<!-- Apparatus project link" in canon[0] or BLOCK_END in canon[0]))):
                    raise BindingError("Project link is missing; repair .apparatus/workspace.yaml.")
                return None
            relative, identifier = _parse(value[0])
            result = ProjectBinding(root, relative, identifier, value[0], value[1], _root_identity(anchor))
            result.validate(anchor)
            return result
    except (OSError, LayoutError) as error:
        raise BindingError("Project link is unsafe or changed; repair it before continuing.") from error


def require_unbound_root(anchor: Any) -> None:
    """Recheck enrollment through its already-retained root, without reopening it."""
    try:
        if anchor.entry_exists(CONTROL_DIRECTORY):
            raise BindingError("A project link occupies this root; initialize its work area instead.")
        canon = _read_optional(anchor, "AGENTS.md")
        if canon and (b"<!-- Apparatus project link" in canon[0] or BLOCK_END in canon[0]):
            raise BindingError("This root contains a project link; initialize its work area instead.")
        if not anchor.root_is_current():
            raise BindingError("The requested work-area root changed; retry enrollment.")
    except OSError as error:
        raise BindingError("Work-area instructions or project controls are unsafe; repair them before enrollment.") from error


class ResolvedContext:
    def __init__(self, binding: ProjectBinding):
        self.project = binding.project
        self.workspace = binding.project
        for _ in binding.relative_workspace.split("/"):
            self.workspace = self.workspace.parent
        self.workspace_id = binding.workspace_id
        self.binding = binding
        self.project_anchor = self.workspace_anchor = None
        try:
            self.layout = read_layout(self.workspace)
            if self.layout is None or self.layout.workspace_id != self.workspace_id:
                raise BindingError("Project work-area identity does not match; use project bind --replace to relink it.")
            if _relative(self.project, self.workspace) != binding.relative_workspace:
                raise BindingError("Project link no longer names its intended work area.")
            self.project_anchor = WorkspaceAnchor(self.project)
            self.workspace_anchor = WorkspaceAnchor(self.workspace)
            self.validate()
        except Exception as error:
            self.close()
            if isinstance(error, (OSError, LayoutError)):
                raise BindingError("Project work area is unavailable; restore it or use project bind --replace.") from error
            raise

    def validate(self) -> None:
        try:
            self.binding.validate(self.project_anchor)
            self.layout.validate(self.workspace_anchor)
        except (OSError, LayoutError) as error:
            raise BindingError("Project context changed; retry with the intended work area.") from error

    def close(self) -> None:
        for anchor in (self.workspace_anchor, self.project_anchor):
            if anchor is not None:
                anchor.close()

    def __enter__(self):
        self.validate()
        return self

    def __exit__(self, *_):
        self.close()


def resolve_project_context(project: str | Path) -> ResolvedContext:
    binding = read_project_binding(project)
    if binding is None:
        raise BindingError("This project has no work-area link; run project bind PROJECT --workspace WORKAREA.")
    return ResolvedContext(binding)


def _pointer_content(content: bytes | None) -> bytes:
    original = content or b""
    try:
        original.decode("utf-8", errors="strict")
    except UnicodeError as error:
        raise BindingError("Project AGENTS.md must be UTF-8; preserve and repair it before binding.") from error
    if b"<!-- Apparatus project link" in original or BLOCK_END in original:
        if (original.count(b"<!-- Apparatus project link") != 1
                or original.count(BLOCK_START) != 1 or original.count(BLOCK_END) != 1):
            raise BindingError("Project instruction link is edited or duplicated; reconcile it before binding.")
        start, end = original.index(BLOCK_START), original.index(BLOCK_END) + len(BLOCK_END)
        if original[start:end] not in (BLOCK, BLOCK.replace(b"\n", b"\r\n")):
            raise BindingError("Project instruction link is customized; preserve and reconcile it before binding.")
        return original
    newline = b"\r\n" if b"\r\n" in original else b"\n"
    separator = b"" if not original else (newline if original.endswith(newline) else newline * 2)
    return original + separator + BLOCK.replace(b"\n", newline) + newline


def check_project_pointer(project: str | Path, *, context: ResolvedContext | None = None) -> None:
    try:
        with (nullcontext(context) if context is not None else resolve_project_context(project)) as context:
            context.validate()
            if _root(project) != context.project:
                raise BindingError("Project context does not match the requested project.")
            value = _read_optional(context.project_anchor, "AGENTS.md")
            if value is None or _pointer_content(value[0]) != value[0]:
                raise BindingError("Project instruction link is missing; run project bind with its work area to repair it.")
            context.validate()
    except OSError as error:
        raise BindingError("Project instruction link is unsafe or changed; repair it before continuing.") from error


@dataclass(frozen=True)
class BindingResult:
    project: Path
    workspace: Path
    changed: bool


def bind_project(project: str | Path, workspace: str | Path, *, replace: bool = False,
                 context: ResolvedContext | None = None) -> BindingResult:
    """Publish only a control and pointer, compensating both until final acceptance."""
    project_path, workspace_path = _root(project), _root(workspace)
    if context is not None:
        context.validate()
        if (context.project, context.workspace) != (project_path, workspace_path):
            raise BindingError("Project context does not match the requested destinations.")
    relative = _relative(project_path, workspace_path)
    try:
        layout = read_layout(workspace_path)
        if layout is None:
            raise BindingError("Enroll the work area with init --adopt before binding a project.")
        old_binding = read_project_binding(project_path)
        if old_binding and (old_binding.relative_workspace, old_binding.workspace_id) != (relative, layout.workspace_id) and not replace:
            raise BindingError("This project already names another work area; use project bind --replace to change it.")
        desired_binding = (_bytes(relative, layout.workspace_id) if old_binding is None or
                           (old_binding.relative_workspace, old_binding.workspace_id) != (relative, layout.workspace_id)
                           else old_binding.content)
        with WorkspaceAnchor(project_path) as root, WorkspaceAnchor(workspace_path) as area:
            layout.validate(area)
            if old_binding:
                old_binding.validate(root)
            control_before = _read_optional(root, CONTROL)
            if control_before != (None if old_binding is None else (old_binding.content, old_binding._identity)):
                raise BindingError("Project link changed during planning; retry.")
            pointer_before = _read_optional(root, "AGENTS.md")
            pointer = _pointer_content(None if pointer_before is None else pointer_before[0])
            if control_before and control_before[0] == desired_binding and pointer_before and pointer_before[0] == pointer:
                if context is not None:
                    context.validate()
                layout.validate(area)
                old_binding.validate(root)
                if _read_optional(root, "AGENTS.md") != pointer_before:
                    raise BindingError("Project instructions changed during planning; retry.")
                return BindingResult(project_path, workspace_path, False)
            control_anchor = owned_directory = None
            created: list[tuple[Any, Any]] = []
            replacements: list[Any] = []
            unchanged: list[tuple[Any, str, Any]] = []
            completed = False
            try:
                control_anchor, owned_directory, _ = _anchor_child(root, project_path, CONTROL_DIRECTORY)
                expected_names = {"workspace.yaml"} if control_before else set()
                if _names(control_anchor) != expected_names:
                    raise BindingError("Project control directory contains unrelated content; preserve it before binding.")

                def publish(anchor, name, before, content):
                    if _read_optional(anchor, name) != before:
                        raise BindingError("Project instructions or link changed during planning; retry.")
                    if before is None:
                        created.append((anchor, anchor.create_file(name, content)))
                    elif before[0] != content:
                        replacements.append(anchor.replace_if_unchanged(name, before[1], before[0], content))
                    else:
                        unchanged.append((anchor, name, before))

                layout.validate(area)
                if context is not None:
                    context.validate()
                publish(control_anchor, "workspace.yaml", control_before, desired_binding)
                publish(root, "AGENTS.md", pointer_before, pointer)

                def validate():
                    if context is not None:
                        context.validate()
                    layout.validate(area)
                    if not root.root_is_current() or not control_anchor.root_is_current():
                        raise BindingError("Project directory changed during binding.")
                    names = {"workspace.yaml"}
                    for transaction in replacements:
                        if not transaction.finished:
                            transaction.validate_commit()
                            if transaction.anchor is control_anchor:
                                # Both proofs keep relative as the original target;
                                # the retained backup name is platform-specific.
                                backup = transaction.backup
                                names.add(backup.name if hasattr(backup, "name") else backup.path.name)
                        elif not transaction.anchor.matches_owned(transaction.target):
                            raise BindingError("Project link changed before completion.")
                    if _names(control_anchor) != names:
                        raise BindingError("Project control directory changed during binding.")
                    if any(not anchor.matches_owned(owned) for anchor, owned in created):
                        raise BindingError("Project link changed before completion.")
                    if any(_read_optional(anchor, name) != before for anchor, name, before in unchanged):
                        raise BindingError("Project instructions changed before completion.")

                validate()
                for transaction in replacements:
                    transaction.commit()
                validate()
                completed = True
                return BindingResult(project_path, workspace_path, True)
            finally:
                errors = []
                if not completed:
                    for transaction in reversed(replacements):
                        try:
                            if transaction.finished:
                                transaction.anchor.restore_owned_if_unchanged(transaction.target, transaction.backup.content)
                            else:
                                transaction.rollback()
                        except Exception as error:
                            errors.append(error)
                        finally:
                            transaction.close()
                    for anchor, owned in reversed(created):
                        try:
                            anchor.unlink_owned_if_present(owned)
                        except Exception as error:
                            errors.append(error)
                        finally:
                            owned.close()
                    if owned_directory is not None:
                        control_anchor.close()
                        try:
                            root.remove_owned_directory(owned_directory)
                        except Exception as error:
                            errors.append(error)
                for transaction in replacements:
                    transaction.close()
                for _, owned in created:
                    owned.close()
                if control_anchor is not None:
                    control_anchor.close()
                if owned_directory is not None:
                    owned_directory.close()
                if errors:
                    raise BindingError("Project binding failed; concurrent content was preserved and cleanup needs repair.") from errors[0]
    except (OSError, LayoutError) as error:
        raise BindingError("Project binding could not finish safely; repair the link before retrying.") from error
