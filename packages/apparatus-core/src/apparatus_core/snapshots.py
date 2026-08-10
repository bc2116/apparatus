"""Local snapshot and restore support backed by git when it is available."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from typing import Any

from apparatus_core.detect import detect_tool
from apparatus_core.receipts import write_receipt


GENERIC_EMAIL = "snapshots@apparatus.invalid"
_SNAPSHOT_ID = re.compile(r"^[0-9a-fA-F]{4,64}$")


class SnapshotError(RuntimeError):
    """A local snapshot operation could not be completed."""


class UnknownSnapshotError(SnapshotError):
    """The requested snapshot id is not available in this workspace."""


class SnapshotReceiptError(SnapshotError):
    """The workspace snapshot receipt could not be recorded."""


@dataclass(frozen=True)
class Snapshot:
    """A saved workspace state, presented without implementation vocabulary."""

    identifier: str
    timestamp: str
    label: str

    @property
    def short_id(self) -> str:
        return self.identifier[:12]


@dataclass(frozen=True)
class SnapshotResult:
    """The result of attempting to save a snapshot."""

    snapshot: Snapshot | None
    no_changes: bool = False


class SnapshotTransaction:
    """A prepared snapshot whose visible state can be accepted or rolled back."""

    def __init__(
        self,
        workspace: Path,
        result: SnapshotResult,
        *,
        previous_head: str | None = None,
        prepared_head: str | None = None,
        receipt: tuple[Path, tuple[int, int, int]] | None = None,
        run: Callable[..., Any] = subprocess.run,
    ) -> None:
        self.workspace = workspace
        self.result = result
        self.previous_head = previous_head
        self.prepared_head = prepared_head
        self.receipt = receipt
        self.run = run
        self.closed = False

    def commit(self) -> SnapshotResult:
        """Keep the prepared snapshot."""
        self.closed = True
        return self.result

    def rollback(self) -> None:
        """Remove only this transaction's visible snapshot and exact receipt."""
        if self.closed:
            return
        errors: list[Exception] = []
        if self.prepared_head is not None:
            arguments = ["update-ref"]
            if self.previous_head is None:
                arguments.extend(["-d", "HEAD", self.prepared_head])
            else:
                arguments.extend(["HEAD", self.previous_head, self.prepared_head])
            try:
                _require_success(_run_git(self.workspace, arguments, run=self.run))
            except Exception as error:  # preserve a concurrent ref instead of overwriting it
                errors.append(error)
        if self.receipt is not None:
            path, identity = self.receipt
            try:
                status = path.lstat()
                if (status.st_dev, status.st_ino, status.st_size) != identity:
                    raise SnapshotError("Snapshot receipt changed before rollback.")
                path.unlink()
            except FileNotFoundError:
                pass
            except Exception as error:
                errors.append(error)
        self.closed = True
        if errors:
            raise SnapshotError("The prepared snapshot could not be rolled back safely.") from errors[0]


def utc_timestamp(clock: Callable[[], datetime] | None = None) -> str:
    """Return the UTC timestamp used in the default human-readable label."""
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    return now.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_label(clock: Callable[[], datetime] | None = None) -> str:
    return f"Snapshot taken {utc_timestamp(clock)}"


def git_available(
    *,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., Any] = subprocess.run,
) -> bool:
    """Probe git through the shared, injectable PR-08 detector."""
    def controlled_run(arguments: list[str], **kwargs: Any) -> Any:
        kwargs["env"] = _git_environment()
        return run(arguments, **kwargs)

    return bool(detect_tool("git", which=which, run=controlled_run)["present"])


def _git_environment() -> dict[str, str]:
    """Make snapshot writes independent of personal/global git identity and signing."""
    environment = {
        name: value for name, value in os.environ.items() if not name.casefold().startswith("git_")
    }
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "Apparatus",
            "GIT_AUTHOR_EMAIL": GENERIC_EMAIL,
            "GIT_COMMITTER_NAME": "Apparatus",
            "GIT_COMMITTER_EMAIL": GENERIC_EMAIL,
        }
    )
    return environment


def _run_git(
    workspace: Path,
    arguments: list[str],
    *,
    run: Callable[..., Any] = subprocess.run,
) -> Any:
    """Run one git command with safe argv and captured output only."""
    try:
        return run(
            ["git", "-C", str(workspace), *arguments],
            capture_output=True,
            text=True,
            check=False,
            env=_git_environment(),
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise SnapshotError("Snapshots could not be completed on this machine.") from error


def _require_success(result: Any) -> str:
    if getattr(result, "returncode", 1) != 0:
        raise SnapshotError("Snapshots could not be completed for this workspace.")
    return str(getattr(result, "stdout", "") or "")


def _is_workspace_initialized(workspace: Path, *, run: Callable[..., Any]) -> bool:
    result = _run_git(workspace, ["rev-parse", "--show-toplevel"], run=run)
    if getattr(result, "returncode", 1) != 0:
        return False
    try:
        return Path(str(getattr(result, "stdout", "") or "").strip()).resolve() == workspace.resolve()
    except OSError:
        return False


def ensure_snapshot_store(workspace: str | Path, *, run: Callable[..., Any] = subprocess.run) -> Path:
    """Initialize the local implementation store and its generic identity when needed."""
    root = Path(workspace).resolve()
    if not _is_workspace_initialized(root, run=run):
        _require_success(_run_git(root, ["init"], run=run))
    _require_success(_run_git(root, ["config", "--local", "user.name", "Apparatus"], run=run))
    _require_success(_run_git(root, ["config", "--local", "user.email", GENERIC_EMAIL], run=run))
    _require_success(_run_git(root, ["config", "--local", "commit.gpgsign", "false"], run=run))
    return root


def _has_changes(workspace: Path, *, run: Callable[..., Any]) -> bool:
    return bool(_require_success(_run_git(workspace, ["status", "--porcelain"], run=run)).strip())


def _snapshot_from_head(workspace: Path, *, run: Callable[..., Any]) -> Snapshot:
    identifier = _require_success(_run_git(workspace, ["rev-parse", "HEAD"], run=run)).strip()
    entries = list_snapshots(workspace, run=run)
    for entry in entries:
        if entry.identifier == identifier:
            return entry
    raise SnapshotError("Snapshots could not be completed for this workspace.")


def _snapshot_receipt_fields(label: str) -> dict[str, str]:
    # The receipt is intentionally part of the saved state.  A content-addressed
    # id cannot name itself before the save exists, so its receipt says ``self``;
    # callers return the concrete id after saving.
    return {
        "summary": f"Snapshot saved: {label}.",
        "label": label,
        "snapshot_id": "self",
        "body": "This receipt is included in the snapshot it describes.\n",
    }


def take_snapshot(
    workspace: str | Path,
    *,
    label: str | None = None,
    force: bool = False,
    run: Callable[..., Any] = subprocess.run,
    write: Callable[[str | Path, str, dict[str, str]], object] = write_receipt,
    clock: Callable[[], datetime] | None = None,
) -> SnapshotResult:
    """Save workspace content, writing its receipt before the saved state exists."""
    root = ensure_snapshot_store(workspace, run=run)
    resolved_label = label or default_label(clock)
    if not force and not _has_changes(root, run=run):
        return SnapshotResult(snapshot=None, no_changes=True)
    try:
        write(root, "snapshot", _snapshot_receipt_fields(resolved_label))
    except (OSError, ValueError) as error:
        raise SnapshotReceiptError("Snapshot receipt could not be written.") from error
    _require_success(_run_git(root, ["add", "--all", "--force"], run=run))
    _require_success(_run_git(root, ["-c", "commit.gpgsign=false", "commit", "-m", resolved_label], run=run))
    return SnapshotResult(snapshot=_snapshot_from_head(root, run=run))


def _run_git_with_environment(
    workspace: Path,
    arguments: list[str],
    environment: dict[str, str],
    *,
    run: Callable[..., Any],
) -> Any:
    try:
        return run(
            ["git", "-C", str(workspace), *arguments],
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise SnapshotError("Snapshots could not be completed on this machine.") from error


def _captured_tree(
    workspace: Path,
    capture: Callable[[Path], None],
    *,
    run: Callable[..., Any],
) -> str:
    """Build a tree from caller-validated bytes without touching the caller's index."""
    store = workspace / ".git"
    if not store.is_dir():
        raise SnapshotError("Snapshots could not be completed for this workspace.")
    with tempfile.TemporaryDirectory(prefix="apparatus-snapshot-", dir=store) as temporary:
        transaction_root = Path(temporary)
        content = transaction_root / "content"
        content.mkdir()
        capture(content)
        environment = _git_environment()
        environment.update(
            {
                "GIT_DIR": str(store),
                "GIT_WORK_TREE": str(content),
                "GIT_INDEX_FILE": str(transaction_root / "index"),
            }
        )
        _require_success(
            _run_git_with_environment(workspace, ["read-tree", "--empty"], environment, run=run)
        )
        _require_success(
            _run_git_with_environment(
                workspace,
                ["add", "--all", "--force", "--", "."],
                environment,
                run=run,
            )
        )
        return _require_success(
            _run_git_with_environment(workspace, ["write-tree"], environment, run=run)
        ).strip()


def _current_head(workspace: Path, *, run: Callable[..., Any]) -> str | None:
    result = _run_git(workspace, ["rev-parse", "--verify", "HEAD"], run=run)
    if getattr(result, "returncode", 1) != 0:
        return None
    value = str(getattr(result, "stdout", "") or "").strip()
    return value or None


def _tree_for_head(workspace: Path, head: str | None, *, run: Callable[..., Any]) -> str | None:
    if head is None:
        return None
    return _require_success(_run_git(workspace, ["rev-parse", f"{head}^{{tree}}"], run=run)).strip()


def _owned_snapshot_receipt(workspace: Path, path: Path) -> tuple[Path, tuple[int, int, int]]:
    absolute = Path(os.path.abspath(path))
    try:
        relative = absolute.relative_to(workspace)
    except ValueError as error:
        raise SnapshotReceiptError("Snapshot receipt was not written inside the workspace.") from error
    if relative.parent != Path("System/receipts"):
        raise SnapshotReceiptError("Snapshot receipt was not written in the receipts folder.")
    status = absolute.lstat()
    if not stat.S_ISREG(status.st_mode):
        raise SnapshotReceiptError("Snapshot receipt is not a regular file.")
    return absolute, (status.st_dev, status.st_ino, status.st_size)


def prepare_snapshot(
    workspace: str | Path,
    *,
    label: str,
    capture: Callable[[Path], None],
    run: Callable[..., Any] = subprocess.run,
    write: Callable[[str | Path, str, dict[str, str]], Path] = write_receipt,
) -> SnapshotTransaction:
    """Prepare a rollback-capable snapshot from an independently captured tree.

    This path is for operations that must keep an external directory out of
    snapshot input. The normal PR-10 command continues to use ``take_snapshot``.
    """
    root = ensure_snapshot_store(workspace, run=run)
    previous_head = _current_head(root, run=run)
    initial_tree = _captured_tree(root, capture, run=run)
    if initial_tree == _tree_for_head(root, previous_head, run=run):
        return SnapshotTransaction(
            root,
            SnapshotResult(snapshot=None, no_changes=True),
            run=run,
        )

    receipt: tuple[Path, tuple[int, int, int]] | None = None
    prepared_head: str | None = None
    try:
        try:
            receipt_path = write(root, "snapshot", _snapshot_receipt_fields(label))
            receipt = _owned_snapshot_receipt(root, receipt_path)
        except (OSError, ValueError) as error:
            raise SnapshotReceiptError("Snapshot receipt could not be written.") from error
        tree = _captured_tree(root, capture, run=run)
        arguments = ["-c", "commit.gpgsign=false", "commit-tree", tree, "-m", label]
        if previous_head is not None:
            arguments.extend(["-p", previous_head])
        prepared_head = _require_success(_run_git(root, arguments, run=run)).strip()
        update = ["update-ref", "HEAD", prepared_head]
        if previous_head is not None:
            update.append(previous_head)
        _require_success(_run_git(root, update, run=run))
        result = SnapshotResult(snapshot=_snapshot_from_head(root, run=run))
        return SnapshotTransaction(
            root,
            result,
            previous_head=previous_head,
            prepared_head=prepared_head,
            receipt=receipt,
            run=run,
        )
    except Exception:
        transaction = SnapshotTransaction(
            root,
            SnapshotResult(snapshot=None),
            previous_head=previous_head,
            prepared_head=prepared_head,
            receipt=receipt,
            run=run,
        )
        transaction.rollback()
        raise


def list_snapshots(
    workspace: str | Path,
    *,
    run: Callable[..., Any] = subprocess.run,
) -> list[Snapshot]:
    """Return snapshots newest first; an uninitialized workspace has none."""
    root = Path(workspace).resolve()
    if not _is_workspace_initialized(root, run=run):
        return []
    result = _run_git(
        root,
        ["log", "--format=%H%x1f%cI%x1f%s", "HEAD"],
        run=run,
    )
    if getattr(result, "returncode", 1) != 0:
        return []
    snapshots: list[Snapshot] = []
    for line in str(getattr(result, "stdout", "") or "").splitlines():
        parts = line.split("\x1f", 2)
        if len(parts) == 3:
            try:
                timestamp = (
                    datetime.fromisoformat(parts[1].replace("Z", "+00:00"))
                    .astimezone(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z")
                )
            except ValueError:
                timestamp = parts[1]
            snapshots.append(Snapshot(parts[0], timestamp, parts[2]))
    return snapshots


def resolve_snapshot_id(
    workspace: str | Path,
    identifier: str,
    *,
    run: Callable[..., Any] = subprocess.run,
) -> str:
    """Resolve exactly one user-supplied snapshot id before any workspace mutation."""
    if not _SNAPSHOT_ID.fullmatch(identifier):
        raise UnknownSnapshotError("That snapshot id is not available.")
    root = Path(workspace).resolve()
    result = _run_git(
        root,
        ["rev-parse", "--verify", f"{identifier}^{{commit}}"],
        run=run,
    )
    if getattr(result, "returncode", 1) != 0:
        raise UnknownSnapshotError("That snapshot id is not available.")
    resolved = str(getattr(result, "stdout", "") or "").strip()
    if not _SNAPSHOT_ID.fullmatch(resolved):
        raise UnknownSnapshotError("That snapshot id is not available.")
    return resolved.lower()


def restore_snapshot(
    workspace: str | Path,
    identifier: str,
    *,
    run: Callable[..., Any] = subprocess.run,
) -> None:
    """Make workspace content exactly match a previously resolved snapshot."""
    root = Path(workspace).resolve()
    _require_success(_run_git(root, ["read-tree", "--reset", "-u", identifier], run=run))
    _require_success(_run_git(root, ["clean", "-ffdx"], run=run))


def mark_snapshots_unavailable(workspace: str | Path) -> bool:
    """Change only the existing report's snapshots field and matching body line."""
    report = Path(workspace) / "System" / "machine-report.md"
    if not report.is_file():
        return True
    try:
        text = report.read_text(encoding="utf-8")
    except OSError:
        return False
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return False
    close = next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), None)
    if close is None:
        return False
    replacement = 'snapshots: "unavailable"\n'
    frontmatter = lines[1:close]
    matching = [index for index, line in enumerate(frontmatter) if line.startswith("snapshots:")]
    if matching:
        frontmatter[matching[0]] = replacement
    else:
        frontmatter.append(replacement)
    body = lines[close + 1 :]
    body_matching = [index for index, line in enumerate(body) if line.startswith("Snapshots:")]
    if body_matching:
        body[body_matching[0]] = "Snapshots: unavailable.\n"
    else:
        body.append("Snapshots: unavailable.\n")
    try:
        report.write_text("".join([lines[0], *frontmatter, lines[close], *body]), encoding="utf-8")
    except OSError:
        return False
    return True
