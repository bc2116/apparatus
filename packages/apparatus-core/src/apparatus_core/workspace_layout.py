"""Explicit work-area enrollment; absence never guesses past residual state."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from apparatus_core import records
from apparatus_core.fs_transactions import WorkspaceAnchor, WindowsIdentity
from apparatus_core.payload import PayloadError, preflight_workspace_paths


MARKER = "System/workspace.yaml"
RECOVERY_DIRECTORY = "System/recovery"
LAYOUT_SCHEMA = "apparatus/workspace@v0"


class LayoutError(ValueError):
    """Work-area routing is missing, invalid, or no longer current."""


def new_layout_bytes() -> bytes:
    """Create canonical enrollment bytes; the caller owns their transaction."""
    return records.yaml.safe_dump({
        "schema": LAYOUT_SCHEMA, "id": str(uuid4()),
        "layout": "sibling-projects", "recovery": "managed-state",
    }, sort_keys=False).encode("utf-8")


def _root_identity(anchor: Any) -> tuple[int, int]:
    value = anchor._root_identity
    if isinstance(value, WindowsIdentity):
        return value.volume, value.index
    return value


@dataclass(frozen=True)
class ManagedLayout:
    workspace: Path
    workspace_id: str
    content: bytes = field(repr=False)
    _identity: Any = field(repr=False)
    _root: tuple[int, int] = field(repr=False)

    def canonical_bytes(self) -> bytes:
        """Serialize control fields without retaining comments or other prose."""
        return records.yaml.safe_dump({
            "schema": LAYOUT_SCHEMA, "id": self.workspace_id,
            "layout": "sibling-projects", "recovery": "managed-state",
        }, sort_keys=False).encode("utf-8")

    def validate(self, anchor: Any) -> None:
        """Require the same root object and exact enrollment preimage."""
        try:
            if (anchor.workspace != self.workspace or not anchor.root_is_current()
                    or _root_identity(anchor) != self._root):
                raise OSError("workspace changed")
            content, identity = anchor.read_file(MARKER)
            if content != self.content or identity != self._identity:
                raise OSError("enrollment changed")
        except OSError as error:
            raise LayoutError("Work-area enrollment changed; repair it before recovery.") from error


def _parse(content: bytes) -> str:
    try:
        if len(content) > 4096:
            raise ValueError("oversized enrollment")
        text = content.decode("utf-8", errors="strict")
        node = records.yaml.compose(text)
        if not isinstance(node, records.yaml.MappingNode):
            raise ValueError("not a mapping")
        keys = [key.value for key, _ in node.value]
        if len(keys) != 4 or set(keys) != {"schema", "id", "layout", "recovery"}:
            raise ValueError("unknown or duplicate fields")
        data = records.yaml.safe_load(text)
        identifier = data["id"]
        parsed = UUID(identifier)
        if (str(parsed) != identifier or parsed.version != 4
                or data["schema"] != LAYOUT_SCHEMA
                or data["layout"] != "sibling-projects"
                or data["recovery"] != "managed-state"):
            raise ValueError("unsupported enrollment")
        return identifier
    except (ValueError, TypeError, AttributeError, UnicodeError, records.yaml.YAMLError) as error:
        raise LayoutError("Work-area enrollment is invalid; repair System/workspace.yaml.") from error


def read_layout(workspace: str | Path) -> ManagedLayout | None:
    """Read the explicit root only. A clean absence preserves the legacy route."""
    try:
        root = preflight_workspace_paths(Path(workspace))
        with WorkspaceAnchor(root) as anchor:
            try:
                content, identity = anchor.read_file(MARKER)
            except FileNotFoundError:
                if anchor.directory_exists(RECOVERY_DIRECTORY):
                    raise LayoutError(
                        "Managed recovery exists without work-area enrollment; "
                        "repair System/workspace.yaml before recovery."
                    )
                return None
            layout = ManagedLayout(root, _parse(content), content, identity, _root_identity(anchor))
            layout.validate(anchor)
            return layout
    except (OSError, PayloadError) as error:
        raise LayoutError("Work-area enrollment or recovery storage is missing or unsafe.") from error
