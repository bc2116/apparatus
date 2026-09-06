"""Isolated, manifest-checked recovery for explicitly enrolled work areas.

Git is only an object store. It never discovers or checks out a work-area or
project repository. Files are restored using the shared retained-root backend.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import zlib
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from apparatus_core import records, skills, learned_skills
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.init_deploy import _anchor_child
from apparatus_core.receipts import ReceiptPublication, prepare_receipt_invocation, write_receipt
from apparatus_core.retention import context_for, operation
from apparatus_core.snapshots import (
    GENERIC_EMAIL, Snapshot, SnapshotError, SnapshotReceiptError, SnapshotResult,
    SnapshotTransaction, UnknownSnapshotError, _capture_snapshot_receipt_files,
    _close_nonraising, _git_environment, _snapshot_receipt_transient_paths,
    _write_owned_snapshot_receipt, default_label,
)
from apparatus_core.workspace_layout import LayoutError, read_layout
from apparatus_core.library.sources import Catalog, REGISTRATION_ROOT, parse_registration, registration_path

STORE = "System/recovery/store"
REF = "refs/heads/managed"
MANIFEST = "recovery-manifest.json"
MANIFEST_SCHEMA = "apparatus/recovery-manifest@v0"
OWNER_SCHEMA = "apparatus/recovery-store@v0"
CONFIG = b"[core]\n\trepositoryformatversion = 0\n\tbare = true\n"
HEAD = b"ref: refs/heads/managed\n"
OPTIONAL_FILES = frozenset((
    "AGENTS.md", "CLAUDE.md", "Welcome.md", ".cursor/rules/apparatus.mdc",
    ".github/copilot-instructions.md", "System/profile.yaml", "System/ignore",
    "System/README.md", "System/guidance/model-guidance.md",
    "System/policy/standard.md", "System/policy/private.md",
)) | frozenset(skills.BUILTIN_PATHS)  # Current seven bodies; each remains optional in older trees.
RECORD_ROOTS = {
    "Goals": "goal", "Memory/People": "person", "Memory/Facts": "fact",
    "Memory/Decisions": "decision", "Decisions": "decision",
    "System/procedures": "procedure", "System/receipts": "receipt",
}
RECOVERY_EVENTS = frozenset(("snapshot", "restore", "backup-export"))
_OID = re.compile(r"[0-9a-f]{40}\Z")
_LOOSE = re.compile(r"objects/[0-9a-f]{2}/[0-9a-f]{38}\Z")


def _json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _closed_json(content: bytes) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate field")
            result[key] = value
        return result
    return json.loads(content.decode("utf-8"), object_pairs_hook=unique)


def _layout(workspace: str | Path) -> Any:
    try:
        layout = read_layout(workspace)
    except LayoutError as error:
        raise SnapshotError(str(error)) from error
    if layout is None:
        raise SnapshotError("Managed recovery requires explicit work-area enrollment.")
    return layout


def _validate_layout(layout: Any, anchor: Any) -> None:
    try:
        layout.validate(anchor)
    except (LayoutError, OSError) as error:
        raise SnapshotError("Managed recovery enrollment changed; repair it before recovery.") from error


def _path(value: str) -> PurePosixPath:
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or any(ord(c) < 32 for c in value)):
        raise SnapshotError("Recovery manifest contains an unsafe path.")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or any(p in {".", ".."} for p in path.parts):
        raise SnapshotError("Recovery manifest contains an unsafe path.")
    return path


def _kind(relative: str) -> str | None:
    path = _path(relative)
    if path.parent.as_posix() == REGISTRATION_ROOT and path.suffix == ".yaml":
        return "library_source"
    if relative in skills.BUILTIN_PATHS:
        return "skill"
    learned = learned_skills.path_kind(relative)
    if learned is not None:
        return learned[0]
    if relative in OPTIONAL_FILES:
        return "profile" if relative == "System/profile.yaml" else "text"
    for root, kind in RECORD_ROOTS.items():
        prefix = PurePosixPath(root)
        if prefix in path.parents and path.suffix == ".md":
            if any(part.startswith(".") for part in path.parts[len(prefix.parts):]):
                return None
            return kind
    return None


def _validate_file(relative: str, content: bytes) -> bool:
    """Return false only for intentionally excluded recovery receipts."""
    kind = _kind(relative)
    if kind is None:
        raise SnapshotError("Recovery coverage includes an undeclared path.")
    try:
        text = content.decode("utf-8", errors="strict")
        if kind == "learned-marker":
            learned_skills.parse_marker(relative, content)
            return True
        if kind == "learned-body":
            if skills.validate_skill(content, learned_skills.path_kind(relative)[1]):
                raise ValueError("invalid learned Skill")
            return True
        if kind == "library_source":
            parse_registration(content, relative)
            return True
        if kind == "text":
            return True
        if kind == "skill":
            if skills.validate_skill(text, skills.BUILTIN_PATHS[relative]):
                raise ValueError("invalid Skill")
            return True
        if kind == "profile":
            data, body = records.yaml.safe_load(text), None
        else:
            data, body = records.parse_record(text)
        if not isinstance(data, dict) or records.validate(kind, data, filename=PurePosixPath(relative).name, body=body):
            raise ValueError("invalid record")
        return kind != "receipt" or data.get("event") not in RECOVERY_EVENTS
    except (ValueError, TypeError, UnicodeError, records.yaml.YAMLError) as error:
        raise SnapshotError("Recovery coverage contains an invalid managed record or text file.") from error


def _read_compatible(anchor: Any, relative: str) -> tuple[bytes, Any]:
    """Read without DELETE access, alongside native readers and receipt proofs."""
    proof = anchor.capture_file(relative, publication_compatible=True)
    try:
        return proof.content, proof.identity
    finally:
        proof.close()


def _validate_library_registration_set(
    files: dict[str, bytes], workspace=None, *, transaction_compatible: bool = False,
    temporary_files: dict | None = None,
) -> None:
    """Validate a historical catalog or its union with preserved later entries."""
    selected = {}
    try:
        if workspace is not None:
            with Catalog(workspace, transaction_compatible=transaction_compatible,
                         temporary_files=temporary_files) as catalog:
                selected.update((registration_path(source.source_path), source) for source in catalog.sources)
                catalog.validate()
        for relative, content in files.items():
            if _kind(relative) == "library_source":
                selected[relative] = parse_registration(content, relative)
        seen = set()
        for source in selected.values():
            key = unicodedata.normalize("NFC", source.source_path).casefold()
            if key in seen:
                raise SnapshotError("Library source registrations have a portable path collision; resolve it before restore.")
            seen.add(key)
    except ValueError as error:
        raise SnapshotError("Library source catalog is invalid or has a portable path conflict; repair it before recovery.") from error


def _collect(anchor: Any) -> dict[str, bytes]:
    try:
        registered = learned_skills.registered_files(anchor)
    except (OSError, learned_skills.LearnedSkillError) as error:
        raise SnapshotError("Adopted Skill coverage is missing or invalid; repair the registered pair before recovery.") from error
    candidates = set(OPTIONAL_FILES) | set(registered)
    try:
        with Catalog(anchor.workspace) as catalog:
            candidates.update(registration_path(source.source_path) for source in catalog.sources)
            catalog.validate()
    except ValueError as error:
        raise SnapshotError("Library source catalog is invalid or changed; repair it before recovery.") from error
    for root in RECORD_ROOTS:
        if anchor.directory_exists(root):
            candidates.update(p.as_posix() for p in anchor.list_files(root, suffix=".md", include_hidden=False))
    result: dict[str, bytes] = {}
    folded: set[str] = set()
    for relative in sorted(candidates):
        try:
            content, _ = _read_compatible(anchor, relative)
        except FileNotFoundError:
            if relative in OPTIONAL_FILES:
                continue
            raise SnapshotError("Managed recovery coverage changed during capture.")
        if _validate_file(relative, content):
            if relative.casefold() in folded:
                raise SnapshotError("Managed recovery paths have a case collision.")
            folded.add(relative.casefold())
            result[relative] = content
    learned_skills.validate_pairs(result)
    return result


class Capture:
    def __init__(self, workspace: str | Path):
        self.layout = _layout(workspace)
        self.anchor = WorkspaceAnchor(self.layout.workspace)
        self.proofs: list[Any] = []
        try:
            _validate_layout(self.layout, self.anchor)
            self.files = _collect(self.anchor)
            for relative, content in self.files.items():
                proof = self.anchor.capture_file(relative, publication_compatible=True)
                self.proofs.append(proof)
                if proof.content != content:
                    raise SnapshotError("Managed recovery coverage changed during capture.")
            self.validate()
        except Exception:
            self.close()
            raise

    def validate(self) -> None:
        _validate_layout(self.layout, self.anchor)
        if any(not self.anchor.matches_owned(proof) for proof in self.proofs):
            raise SnapshotError("Managed recovery source changed during the operation.")
        if _collect(self.anchor) != self.files:
            raise SnapshotError("Managed recovery coverage changed during the operation.")
        _validate_layout(self.layout, self.anchor)

    def close(self) -> None:
        for proof in self.proofs:
            _close_nonraising(proof)
        _close_nonraising(self.anchor)

    def __enter__(self) -> Capture:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def capture_state(workspace: str | Path, *, run: Callable[..., Any] = subprocess.run) -> Capture:
    del run
    try:
        return Capture(workspace)
    except OSError as error:
        raise SnapshotError("Managed recovery sources could not be captured safely.") from error


def _exists(anchor: Any, relative: str) -> bool:
    try:
        return anchor.entry_exists(relative)
    except FileNotFoundError:
        return False


def _owner(identifier: str) -> bytes:
    return _json({"schema": OWNER_SCHEMA, "workspace_id": identifier})


def _inventory(anchor: Any) -> set[str]:
    """Check every store entry, including otherwise invisible empty directories."""
    files: set[str] = set()
    def visit(relative: str) -> None:
        handle = anchor.open_directory(relative) if relative else anchor._root
        try:
            names = os.listdir(handle if os.name == "posix" else anchor.workspace / relative)
            for name in names:
                child = f"{relative}/{name}" if relative else name
                directory = child in {"objects", "refs", "refs/heads"} or bool(re.fullmatch(r"objects/[0-9a-f]{2}", child))
                if directory:
                    visit(child)
                elif child in {"config", "HEAD", "apparatus-owner.json", REF} or _LOOSE.fullmatch(child):
                    # A retained read rejects links and special file endpoints.
                    if child == REF:
                        anchor.read_file(child)
                    else:
                        _read_compatible(anchor, child)
                    files.add(child)
                else:
                    raise SnapshotError("Managed recovery store contains unexpected content; repair it before recovery.")
        finally:
            if relative:
                anchor.close_directory(handle)
    visit("")
    return files


def _git(anchor: Any, arguments: list[str], *, run: Callable[..., Any], content: bytes | None = None) -> bytes:
    if not anchor.root_is_current():
        raise SnapshotError("Managed recovery store changed during the operation.")
    kwargs: dict[str, Any] = {}
    # macOS /dev/fd directory names cannot be traversed. A fixed exec launcher
    # enters the inherited directory with fchdir before replacing itself with
    # Git; it does not run a shell or discover any work-area repository.
    command = ["git", f"--git-dir={anchor.workspace}", *arguments]
    if os.name == "posix":
        launcher = "import os,sys; os.fchdir(int(sys.argv[1])); os.execvp('git', ['git', '--git-dir=.', *sys.argv[2:]])"
        command = [sys.executable, "-I", "-c", launcher, str(anchor._root), *arguments]
        kwargs["pass_fds"] = (anchor._root,)
    try:
        result = run(command, input=content, capture_output=True, check=False,
                     env=_git_environment(), **kwargs)
    except (OSError, subprocess.SubprocessError) as error:
        raise SnapshotError("Managed recovery Git operation failed.") from error
    if result.returncode != 0 or not anchor.root_is_current():
        raise SnapshotError("Managed recovery Git operation failed safely.")
    return result.stdout if isinstance(result.stdout, bytes) else result.stdout.encode("utf-8")


class Store:
    def __init__(self, workspace: str | Path, *, create: bool = False, run: Callable[..., Any] = subprocess.run):
        self.layout = _layout(workspace)
        self.root = WorkspaceAnchor(self.layout.workspace)
        self.anchor: Any | None = None
        self.pins: list[Any] = []
        self.ref_transaction: Any | None = None
        self.run = run
        try:
            if create:
                context_for(workspace).require_snapshot()
            _validate_layout(self.layout, self.root)
            if create and not self.root.directory_exists(STORE):
                _initialize_store(self.root, self.layout)
            if not self.root.directory_exists(STORE):
                # Existing recovery content without the owned store is not ours.
                if self.root.directory_exists("System/recovery"):
                    raise SnapshotError("Managed recovery store is incomplete; repair it before recovery.")
                _validate_layout(self.layout, self.root)
                return
            self.anchor = WorkspaceAnchor(self.layout.workspace / STORE)
            for path, expected in (("config", CONFIG), ("HEAD", HEAD), ("apparatus-owner.json", _owner(self.layout.workspace_id))):
                pin = self.anchor.capture_file(path, publication_compatible=True)
                self.pins.append(pin)
                if pin.content != expected:
                    raise SnapshotError("Managed recovery store ownership or configuration is invalid.")
            self.validate()
        except Exception as error:
            self.close()
            if isinstance(error, OSError):
                raise SnapshotError("Managed recovery store is incomplete or unsafe; repair it before recovery.") from error
            raise

    def validate(self) -> None:
        _validate_layout(self.layout, self.root)
        if self.anchor is None:
            if self.root.entry_exists("System/recovery"):
                raise SnapshotError("Managed recovery state appeared during the operation.")
            return
        if not self.anchor.root_is_current() or any(not self.anchor.matches_owned(p) for p in self.pins):
            raise SnapshotError("Managed recovery store changed during the operation.")
        try:
            files = _inventory(self.anchor)
        except OSError as error:
            raise SnapshotError("Managed recovery store is incomplete or unsafe; repair it before recovery.") from error
        if not {"config", "HEAD", "apparatus-owner.json"} <= files:
            raise SnapshotError("Managed recovery store is incomplete.")
        if REF in files:
            value = self.anchor.read_file(REF)[0]
            if not re.fullmatch(rb"[0-9a-f]{40}\n", value):
                raise SnapshotError("Managed recovery reference is invalid.")
        _validate_layout(self.layout, self.root)

    def head(self) -> str | None:
        self.validate()
        if self.anchor is None:
            return None
        try:
            return self.anchor.read_file(REF)[0].decode("ascii").strip()
        except FileNotFoundError:
            return None

    def close(self) -> None:
        for pin in self.pins:
            _close_nonraising(pin)
        _close_nonraising(self.ref_transaction)
        _close_nonraising(self.anchor)
        _close_nonraising(self.root)

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def _initialize_store(root: Any, layout: Any) -> None:
    """Create only a new owned store, never adopt a preexisting directory."""
    anchors: list[Any] = []
    directories: list[tuple[Any, Any, Any]] = []
    files: list[tuple[Any, Any]] = []

    def child(parent: Any, name: str, *, required_new: bool = True) -> Any:
        selected, owned, was_created = _anchor_child(parent, parent.workspace, name)
        anchors.append(selected)
        if owned is not None:
            directories.append((parent, owned, selected))
        if required_new and not was_created:
            raise SnapshotError("Existing recovery content is a collision, not an adoptable store.")
        return selected

    try:
        _validate_layout(layout, root)
        system = child(root, "System", required_new=False)
        recovery = child(system, "recovery")
        current = child(recovery, "store")
        child(current, "objects")
        refs = child(current, "refs")
        child(refs, "heads")
        for relative, content in (("config", CONFIG), ("HEAD", HEAD), ("apparatus-owner.json", _owner(layout.workspace_id))):
            files.append((current, current.create_file(relative, content)))
        _validate_layout(layout, root)
        if (any(not anchor.root_is_current() for anchor in anchors)
                or any(not anchor.matches_owned(owned) for anchor, owned in files)):
            raise SnapshotError("Managed recovery store changed during initialization.")
    except Exception as error:
        cleanup_errors: list[OSError] = []
        for parent, owned in reversed(files):
            try:
                parent.unlink_owned_if_present(owned)
            except OSError as cleanup_error:
                cleanup_errors.append(cleanup_error)
            finally:
                # Release deleted file handles before removing Windows parents.
                _close_nonraising(owned)
        for parent, owned, selected in reversed(directories):
            _close_nonraising(selected)
            try:
                parent.remove_owned_directory(owned)
            except FileNotFoundError:
                pass
            except OSError as cleanup_error:
                # Nonempty/substituted directories belong to concurrent work.
                cleanup_errors.append(cleanup_error)
            finally:
                _close_nonraising(owned)
        if cleanup_errors:
            raise SnapshotError(
                "Managed recovery initialization failed; changed or concurrent content was preserved. "
                "Repair the incomplete recovery state before retrying."
            ) from error
        raise
    finally:
        for anchor in reversed(anchors):
            _close_nonraising(anchor)
        for _, owned in files:
            _close_nonraising(owned)
        for _, owned, _ in directories:
            _close_nonraising(owned)


def _manifest(identifier: str, files: dict[str, bytes]) -> bytes:
    return _json({"schema": MANIFEST_SCHEMA, "workspace_id": identifier, "scope": "managed-state",
                  "files": [{"path": path, "sha256": hashlib.sha256(content).hexdigest()}
                            for path, content in sorted(files.items())]})


def _loose_bytes(kind: str, content: bytes) -> bytes:
    return f"{kind} {len(content)}\0".encode("ascii") + content


def _decode_loose(content: bytes) -> bytes:
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(content) + decoder.flush()
        if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError("incomplete or extra compressed content")
        return raw
    except (ValueError, zlib.error) as error:
        raise SnapshotError("Managed recovery object storage is invalid.") from error


def _publish_object(anchor: Any, kind: str, content: bytes) -> str:
    """Publish a standard loose Git object through retained parent handles."""
    raw = _loose_bytes(kind, content)
    oid = hashlib.sha1(raw).hexdigest()
    objects = fanout = None
    directories: list[Any] = []
    proof = None
    try:
        objects, owned, _ = _anchor_child(anchor, anchor.workspace, "objects")
        if owned:
            directories.append(owned)
        fanout, owned, _ = _anchor_child(objects, objects.workspace, oid[:2])
        if owned:
            directories.append(owned)
        try:
            proof = fanout.create_file(oid[2:], zlib.compress(raw))
        except FileExistsError:
            proof = fanout.capture_file(oid[2:], publication_compatible=True)
        if (_decode_loose(proof.content) != raw or not fanout.matches_owned(proof)
                or not objects.root_is_current() or not anchor.root_is_current()):
            raise SnapshotError("Managed object changed during publication.")
        return oid
    finally:
        _close_nonraising(proof)
        _close_nonraising(fanout)
        _close_nonraising(objects)
        for owned in directories:
            _close_nonraising(owned)


def _publish_reference(store: Store, history: History, commit: str) -> Any:
    """CAS only the retained preimage, obtaining ownership at publication."""
    history.validate()
    content = (commit + "\n").encode("ascii")
    if history.ref is None:
        return store.anchor.create_file(REF, content)
    # CAS reacquires and checks this exact preimage before publication. An
    # extra planning handle would keep its renamed backup open on Windows,
    # blocking compensation or leaving a delete-pending store entry behind.
    history.ref.close()
    transaction = store.anchor.replace_if_unchanged(
        REF, history.ref.identity, history.ref.content, content)
    store.ref_transaction = transaction
    try:
        transaction.validate_commit()
        transaction.discard_backup()
        return transaction.target
    except Exception:
        if transaction.finished:
            store.anchor.restore_owned_if_unchanged(transaction.target, history.ref.content)
        else:
            transaction.rollback()
        raise


def _object(store: Store, oid: str, kind: str, objects: dict[str, tuple[str, bytes]]) -> bytes:
    if not _OID.fullmatch(oid):
        raise SnapshotError("Managed snapshot contains an invalid object identifier.")
    if oid in objects:
        prior_kind, content = objects[oid]
        if prior_kind != kind:
            raise SnapshotError("Managed snapshot object kind is inconsistent.")
        return content
    store.validate()
    pin = store.anchor.capture_file(f"objects/{oid[:2]}/{oid[2:]}", publication_compatible=True)
    store.pins.append(pin)
    content = _git(store.anchor, ["cat-file", kind, oid], run=store.run)
    if not store.anchor.matches_owned(pin):
        raise SnapshotError("Managed snapshot object changed while being read.")
    if hashlib.sha1(f"{kind} {len(content)}\0".encode() + content).hexdigest() != oid:
        raise SnapshotError("Managed snapshot object integrity check failed.")
    if _decode_loose(pin.content) != _loose_bytes(kind, content):
        raise SnapshotError("Managed snapshot compressed object contains unexpected bytes.")
    objects[oid] = (kind, content)
    return content


def _tree_files(store: Store, oid: str, objects: dict[str, tuple[str, bytes]]) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    directories: set[str] = set()
    folded: set[str] = set()
    def walk(tree: str, prefix: str = "") -> None:
        raw = _object(store, tree, "tree", objects)
        position = 0
        while position < len(raw):
            end = raw.find(b"\0", position)
            if end < 0 or end + 21 > len(raw):
                raise SnapshotError("Managed snapshot tree is malformed.")
            try:
                mode, name_bytes = raw[position:end].split(b" ", 1)
                name = name_bytes.decode("utf-8")
            except (ValueError, UnicodeError) as error:
                raise SnapshotError("Managed snapshot tree is malformed.") from error
            if "/" in name or not name:
                raise SnapshotError("Managed snapshot tree contains an unsafe name.")
            relative = f"{prefix}/{name}" if prefix else name
            _path(relative)
            if relative.casefold() in folded:
                raise SnapshotError("Managed snapshot tree contains duplicate or colliding paths.")
            folded.add(relative.casefold())
            child = raw[end + 1:end + 21].hex()
            position = end + 21
            if mode == b"40000":
                directories.add(relative)
                walk(child, relative)
            elif mode == b"100644":
                files[relative] = _object(store, child, "blob", objects)
            else:
                raise SnapshotError("Managed snapshot contains an unsupported file mode.")
    walk(oid)
    expected_directories = {p.as_posix() for value in files for p in PurePosixPath(value).parents if p != PurePosixPath(".")}
    if directories != expected_directories:
        raise SnapshotError("Managed snapshot contains undeclared tree paths.")
    return files


def _validated_manifest(identifier: str, files: dict[str, bytes]) -> dict[str, bytes]:
    try:
        metadata = _closed_json(files[MANIFEST])
        if (not isinstance(metadata, dict) or set(metadata) != {"schema", "workspace_id", "scope", "files"}
                or metadata["schema"] != MANIFEST_SCHEMA or metadata["workspace_id"] != identifier
                or metadata["scope"] != "managed-state" or not isinstance(metadata["files"], list)):
            raise ValueError("invalid manifest")
        included: dict[str, bytes] = {}
        folded: set[str] = set()
        for entry in metadata["files"]:
            if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
                raise ValueError("invalid entry")
            relative = entry["path"]
            _path(relative)
            if relative.casefold() in folded or relative == MANIFEST:
                raise ValueError("duplicate path")
            folded.add(relative.casefold())
            content = files[relative]
            if entry["sha256"] != hashlib.sha256(content).hexdigest() or not _validate_file(relative, content):
                raise ValueError("invalid included file")
            included[relative] = content
        if set(files) != set(included) | {MANIFEST}:
            raise ValueError("extra tree path")
        learned_skills.validate_pairs(included)
        _validate_library_registration_set(included)
        return included
    except (KeyError, ValueError, TypeError, UnicodeError) as error:
        raise SnapshotError("Managed snapshot manifest or coverage is invalid.") from error


class History:
    """All reachable validated snapshots and immutable object/preimage proofs."""
    def __init__(self, store: Store):
        self.store = store
        self.head = store.head()
        self.ref = None
        self.pins: list[Any] = []
        self.objects: dict[str, tuple[str, bytes]] = {}
        self.snapshots: list[Snapshot] = []
        self.files: dict[str, dict[str, bytes]] = {}
        self.trees: dict[str, str] = {}
        try:
            if self.head:
                self.ref = store.anchor.capture_file(REF)
                if self.ref.content != (self.head + "\n").encode():
                    raise SnapshotError("Managed recovery reference changed.")
            current = self.head
            visited: set[str] = set()
            while current:
                if current in visited:
                    raise SnapshotError("Managed snapshot history is cyclic.")
                visited.add(current)
                raw = _object(store, current, "commit", self.objects)
                try:
                    headers, message = raw.split(b"\n\n", 1)
                    rows = headers.decode("utf-8").splitlines()
                    trees = [row[5:] for row in rows if row.startswith("tree ")]
                    parents = [row[7:] for row in rows if row.startswith("parent ")]
                    committers = [row[10:] for row in rows if row.startswith("committer ")]
                    authors = [row for row in rows if row.startswith("author ")]
                    if len(trees) != 1 or len(parents) > 1 or len(committers) != 1 or len(authors) != 1 or len(rows) != 3 + len(parents):
                        raise ValueError("invalid commit headers")
                    timestamp = datetime.fromtimestamp(int(committers[0].rsplit(" ", 2)[1]), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    label = message.decode("utf-8").strip()
                except (ValueError, UnicodeError, IndexError, OverflowError, OSError) as error:
                    raise SnapshotError("Managed snapshot commit is invalid.") from error
                self.files[current] = _validated_manifest(store.layout.workspace_id, _tree_files(store, trees[0], self.objects))
                self.trees[current] = trees[0]
                self.snapshots.append(Snapshot(current, timestamp, label, scope="managed-state"))
                current = parents[0] if parents else None
            # Pin compressed storage endpoints too: object replacement after a
            # successful Git read cannot escape the final validation checkpoint.
            for oid in self.objects:
                self.pins.append(store.anchor.capture_file(f"objects/{oid[:2]}/{oid[2:]}", publication_compatible=True))
            self.validate()
        except Exception as error:
            self.close()
            if isinstance(error, OSError):
                raise SnapshotError("Managed snapshot history is incomplete or unsafe; repair it before recovery.") from error
            raise

    def validate(self, *, reference: bool = True) -> None:
        self.store.validate()
        if reference:
            if self.ref is None:
                if self.store.head() is not None:
                    raise SnapshotError("Managed recovery reference changed.")
            elif not self.store.anchor.matches_owned(self.ref):
                raise SnapshotError("Managed recovery reference changed.")
        if any(not self.store.anchor.matches_owned(pin) for pin in self.pins):
            raise SnapshotError("Managed snapshot objects changed during the operation.")

    def close(self) -> None:
        for pin in self.pins:
            _close_nonraising(pin)
        _close_nonraising(self.ref)


def _write_tree(store: Store, files: dict[str, bytes]) -> str:
    tree: dict[str, Any] = {}
    for relative, content in files.items():
        parts = _path(relative).parts
        current = tree
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = content
    def write(node: dict[str, Any]) -> str:
        entries = []
        ordered = sorted(node.items(), key=lambda item: (item[0] + ("/" if isinstance(item[1], dict) else "")).encode("utf-8"))
        for name, value in ordered:
            if isinstance(value, dict):
                mode, oid = "40000", write(value)
            else:
                mode, oid = "100644", _publish_object(store.anchor, "blob", value)
            entries.append(f"{mode} {name}".encode("utf-8") + b"\0" + bytes.fromhex(oid))
        return _publish_object(store.anchor, "tree", b"".join(entries))
    store.validate()
    return write(tree)



class ManagedSnapshotTransaction:
    def __init__(self, capture: Capture, store: Store, history: History, inner: SnapshotTransaction):
        self.capture, self.store, self.history, self.inner = capture, store, history, inner
        self.result = inner.result
        self.closed = False
        self.settled = False

    def validate(self) -> None:
        if self.closed:
            raise SnapshotError("Managed snapshot transaction is closed.")
        self.capture.validate()
        self.history.validate(reference=self.result.no_changes)
        if self.settled:
            self.inner.validate_durable()
        else:
            self.inner.validate_receipt()

    def settle(self) -> None:
        self.validate()
        if not self.settled:
            self.inner.settle()
            self.inner.release()
            self.settled = True
        self.validate()

    def accept(self) -> SnapshotResult:
        self.inner.accept()
        self.closed = True
        self._close()
        return self.result

    def commit(self) -> SnapshotResult:
        self.settle()
        self.validate()
        return self.accept()

    def rollback(self) -> None:
        if self.closed:
            return
        try:
            self.inner.rollback()
        finally:
            self.closed = True
            self._close()

    def _close(self) -> None:
        _close_nonraising(self.history)
        _close_nonraising(self.store)
        _close_nonraising(self.capture)

    def close(self) -> None:
        if not self.closed:
            self.rollback()


def prepare_snapshot(workspace: str | Path, *, label: str | None = None, force: bool = False,
                     run: Callable[..., Any] = subprocess.run, write: Callable[..., Any] = write_receipt,
                     clock: Callable[..., Any] | None = None, task_id: str | None = None,
                     requested: bool = False) -> ManagedSnapshotTransaction:
    del force  # identical declared bytes never manufacture a new recovery event
    with operation(workspace, task_id=task_id, requested=("snapshot",) if requested else ()) as context:
        context.require_snapshot()
        capture = capture_state(workspace)
        store = history = inner = receipt = None
        receipt_files: tuple[Any, ...] = ()
        published_ref = None
        try:
            store = Store(workspace, create=True, run=run)
            history = History(store)
            capture.validate()
            history.validate()
            if history.head and capture.files == history.files[history.head]:
                inner = SnapshotTransaction(capture.layout.workspace, SnapshotResult(None, no_changes=True))
                result = ManagedSnapshotTransaction(capture, store, history, inner)
                result.validate()
                return result
            files = {**capture.files, MANIFEST: _manifest(capture.layout.workspace_id, capture.files)}
            tree = _write_tree(store, files)
            _validated_manifest(capture.layout.workspace_id, _tree_files(store, tree, {}))
            capture.validate()
            history.validate()
            safe_label = (label or default_label(clock)) if context.save_memory else "Requested managed-state snapshot"
            now = (clock or (lambda: datetime.now(timezone.utc)))().astimezone(timezone.utc)
            seconds = int(now.timestamp())
            headers = f"tree {tree}\n"
            if history.head:
                headers += f"parent {history.head}\n"
            identity = f"Apparatus <{GENERIC_EMAIL}> {seconds} +0000"
            raw_commit = (headers + f"author {identity}\ncommitter {identity}\n\n" + safe_label + "\n").encode("utf-8")
            commit = _publish_object(store.anchor, "commit", raw_commit)
            _object(store, commit, "commit", {})  # native Git validates the newly published object too
            receipt = _write_owned_snapshot_receipt(write, capture.layout.workspace, {
                "summary": "Managed-state snapshot saved.", "label": safe_label, "snapshot_id": commit,
                "body": "Saved declared managed state; project files and Library originals are outside recovery coverage.\n",
            })
            transients = _snapshot_receipt_transient_paths(capture.layout.workspace, receipt)
            receipt_files = _capture_snapshot_receipt_files(capture.layout.workspace, capture.anchor, receipt, transients)
            capture.validate()
            history.validate()
            previous_content = history.ref.content if history.ref else None
            published_ref = _publish_reference(store, history, commit)
            timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            inner = SnapshotTransaction(capture.layout.workspace, SnapshotResult(Snapshot(commit, timestamp, safe_label, scope="managed-state")),
                previous_head=history.head, prepared_head=commit,
                prepared_ref_file=published_ref, previous_ref_content=previous_content,
                receipt=receipt, receipt_files=receipt_files, workspace_anchor=capture.anchor,
                history_anchor=store.anchor, run=run)
            result = ManagedSnapshotTransaction(capture, store, history, inner)
            result.validate()
            return result
        except Exception:
            try:
                if inner:
                    try:
                        inner.rollback()
                    except Exception:
                        pass  # Preserve concurrent files; the initiating error still fails the save.
                else:
                    if published_ref is not None and store is not None and history is not None:
                        try:
                            if history.head:
                                store.anchor.restore_owned_if_unchanged(published_ref, (history.head + "\n").encode())
                            else:
                                store.anchor.unlink_owned_if_present(published_ref)
                        except OSError:
                            pass  # preserve a concurrent reference
                    if receipt is not None:
                        # Preparation can fail after receipt proofs are retained
                        # but before the snapshot transaction exists. Use its
                        # same exact-owned fallback when publication rollback
                        # cannot acquire DELETE access beside those proofs.
                        try:
                            SnapshotTransaction(
                                capture.layout.workspace, SnapshotResult(None),
                                receipt=receipt, receipt_files=receipt_files,
                                workspace_anchor=capture.anchor,
                            ).rollback()
                        except Exception:
                            pass  # Preserve concurrent receipts and the initiating error.
            finally:
                _close_nonraising(receipt)
                for proof in receipt_files:
                    _close_nonraising(proof)
                _close_nonraising(published_ref)
                _close_nonraising(history)
                _close_nonraising(store)
                capture.close()
            raise


def take_snapshot(workspace: str | Path, **kwargs: Any) -> SnapshotResult:
    transaction = prepare_snapshot(workspace, **kwargs)
    try:
        return transaction.commit()
    except Exception:
        transaction.rollback()
        raise
    finally:
        transaction.close()


def list_snapshots(workspace: str | Path, *, run: Callable[..., Any] = subprocess.run) -> list[Snapshot]:
    with Store(workspace, run=run) as store:
        history = History(store)
        try:
            history.validate()
            return list(history.snapshots)
        finally:
            history.close()


def _resolve(history: History, identifier: str) -> str:
    if not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{4,40}", identifier):
        raise UnknownSnapshotError("Choose a listed managed snapshot identifier.")
    matches = [entry.identifier for entry in history.snapshots if entry.identifier.startswith(identifier)]
    if len(matches) != 1:
        raise UnknownSnapshotError("Managed snapshot identifier is unknown or ambiguous.")
    return matches[0]


def resolve_snapshot_id(workspace: str | Path, identifier: str, *, run: Callable[..., Any] = subprocess.run) -> str:
    with Store(workspace, run=run) as store:
        history = History(store)
        try:
            result = _resolve(history, identifier)
            history.validate()
            return result
        finally:
            history.close()


class RestorePlan:
    def __init__(self, workspace: str | Path, identifier: str, run: Callable[..., Any]):
        self.store = Store(workspace, run=run)
        self.history = None
        self.preimages: dict[str, Any | None] = {}
        self.parents: dict[str, Any] = {}
        self.created_directories: list[tuple[Any, Any]] = []
        self.changes: list[Any] = []
        self.created_files: list[tuple[Any, Any]] = []
        self.receipt_transaction: SnapshotTransaction | None = None
        try:
            self.history = History(self.store)
            self.identifier = _resolve(self.history, identifier)
            self.files = self.history.files[self.identifier]
            for relative in self.files:
                try:
                    proof = self.store.root.capture_file(relative)
                except FileNotFoundError:
                    proof = None
                if proof is not None:
                    if not _validate_file(relative, proof.content):
                        proof.close()
                        raise SnapshotError("Restore target is not a declared managed record.")
                self.preimages[relative] = proof
            self.validate()
        except Exception:
            self.close()
            raise

    def validate(self) -> None:
        self.history.validate()
        _validate_library_registration_set(
            self.files, self.store.layout.workspace, transaction_compatible=True,
        )
        for relative, proof in self.preimages.items():
            if proof is None:
                if _exists(self.store.root, relative):
                    raise SnapshotError("Restore destination appeared during planning.")
            elif not self.store.root.matches_owned(proof):
                raise SnapshotError("Restore destination changed during planning.")
        _validate_layout(self.store.layout, self.store.root)

    def apply(self, *, write: Callable[..., Any] = write_receipt) -> None:
        self.validate()
        try:
            # All records and endpoint types were checked before directory or
            # file publication. Retain each created parent through final proof.
            self.parents[""] = self.store.root
            for relative in sorted(self.files):
                current, parent_path = self.store.root, self.store.layout.workspace
                parts = PurePosixPath(relative).parts
                for length, name in enumerate(parts[:-1], 1):
                    key = "/".join(parts[:length])
                    if key not in self.parents:
                        child, owned, _ = _anchor_child(current, parent_path, name)
                        self.parents[key] = child
                        if owned:
                            self.created_directories.append((current, owned))
                    current, parent_path = self.parents[key], parent_path / name
                proof, content = self.preimages[relative], self.files[relative]
                if proof is None:
                    self.created_files.append((current, current.create_file(parts[-1], content)))
                elif proof.content != content:
                    # Transfer protection to CAS before it creates a backup;
                    # unchanged destinations keep their planning proofs live.
                    proof.close()
                    self.changes.append(self.store.root.replace_if_unchanged(relative, proof.identity, proof.content, content))
            self._validate_published()
            self.receipt_transaction = _restore_receipt(self.store, self.identifier, write)
            self._validate_published()
            self.receipt_transaction.settle()
            self.receipt_transaction.release()
            self._validate_published()
            self.receipt_transaction.validate_durable()
            for change in self.changes:
                change.discard_backup()
            self._validate_published()
            self.receipt_transaction.validate_durable()
            self.receipt_transaction.accept()
        except Exception:
            errors: list[Exception] = []
            if self.receipt_transaction is not None:
                try:
                    self.receipt_transaction.rollback()
                except Exception as error:
                    errors.append(error)
            for change in reversed(self.changes):
                try:
                    if change.finished:
                        self.store.root.restore_owned_if_unchanged(change.target, self.preimages[change.target.relative.as_posix()].content)
                    else:
                        change.rollback()
                except Exception as error:
                    errors.append(error)
            for anchor, owned in reversed(self.created_files):
                try:
                    anchor.unlink_owned_if_present(owned)
                except Exception as error:
                    errors.append(error)
            for parent, owned in reversed(self.created_directories):
                try:
                    parent.remove_owned_directory(owned)
                except OSError:
                    pass  # preserve additions inside an invocation-created directory
            if errors:
                raise SnapshotError("Restore failed; concurrent changes were preserved and compensation was incomplete.") from errors[0]
            raise

    def _validate_published(self) -> None:
        self.history.validate()
        temporary = {}
        for change in self.changes:
            if not change.finished and _kind(change.target.relative.as_posix()) == "library_source":
                backup = change.backup
                name = backup.name if hasattr(backup, "name") else backup.path.name
                temporary[name] = (backup.content, backup.identity)
        _validate_library_registration_set(
            self.files, self.store.layout.workspace, transaction_compatible=True,
            temporary_files=temporary,
        )
        _validate_layout(self.store.layout, self.store.root)
        changed = {change.target.relative.as_posix() for change in self.changes}
        for change in self.changes:
            if not self.store.root.matches_owned(change.target):
                raise SnapshotError("Restored file changed before completion.")
            change.validate_commit()
        for anchor, owned in self.created_files:
            if not anchor.matches_owned(owned):
                raise SnapshotError("Restored file changed before completion.")
        for relative, proof in self.preimages.items():
            if proof is not None and relative not in changed and not self.store.root.matches_owned(proof):
                raise SnapshotError("Unchanged restore target changed before completion.")
        if any(not anchor.root_is_current() for anchor in self.parents.values()):
            raise SnapshotError("Restore parent changed before completion.")

    def close(self) -> None:
        for change in self.changes:
            _close_nonraising(change)
        for _, owned in self.created_files + self.created_directories:
            _close_nonraising(owned)
        for proof in self.preimages.values():
            _close_nonraising(proof)
        for key, anchor in self.parents.items():
            if key:
                _close_nonraising(anchor)
        _close_nonraising(self.history)
        _close_nonraising(self.store)


@contextmanager
def preflight_restore(workspace: str | Path, identifier: str, *, run: Callable[..., Any] = subprocess.run):
    plan = RestorePlan(workspace, identifier, run)
    try:
        yield plan
    finally:
        plan.close()


def restore_snapshot(workspace: str | Path, identifier: str, *, run: Callable[..., Any] = subprocess.run,
                     task_id: str | None = None, write: Callable[..., Any] = write_receipt) -> None:
    with operation(workspace, task_id=task_id):
        with preflight_restore(workspace, identifier, run=run) as plan:
            plan.apply(write=write)


def _restore_receipt(store: Store, identifier: str, write: Callable[..., Any]) -> SnapshotTransaction:
    fields = {"summary": "Declared managed state restored.", "snapshot_id": identifier,
              "body": "Restored saved managed files; later additions, project files, Library originals, and live task controls were preserved. Memory reflects the historical snapshot.\n"}
    invocation = prepare_receipt_invocation(store.layout.workspace, "restore", fields)
    receipt = None
    proofs: tuple[Any, ...] = ()
    try:
        receipt = write(store.layout.workspace, "restore", fields, invocation=invocation)
        if not isinstance(receipt, ReceiptPublication) or not receipt.is_bound_to(invocation):
            raise SnapshotReceiptError("Restore receipt writer did not return exact publication ownership.")
        receipt.claim(invocation)
        transient = _snapshot_receipt_transient_paths(store.layout.workspace, receipt)
        proofs = _capture_snapshot_receipt_files(store.layout.workspace, store.root, receipt, transient)
        return SnapshotTransaction(store.layout.workspace, SnapshotResult(None), receipt=receipt,
                                   receipt_files=proofs, workspace_anchor=store.root)
    except Exception as error:
        if isinstance(receipt, ReceiptPublication) and receipt.is_from_invocation(invocation):
            try:
                if receipt.claimed:
                    receipt.rollback()
            finally:
                _close_nonraising(receipt)
        for proof in proofs:
            _close_nonraising(proof)
        invocation.close()
        raise SnapshotReceiptError("Restore receipt could not be retained safely.") from error


class HistoryProof:
    def __init__(self, store: Store, history: History, destination: Path):
        self.store, self.history = store, history
        self.anchor = WorkspaceAnchor(destination)
        self.pins: list[Any] = []
        self.files: dict[str, bytes] = {}
        try:
            expected = {"config", "HEAD", "apparatus-owner.json"}
            expected.update(f"objects/{oid[:2]}/{oid[2:]}" for oid in history.objects)
            if history.head:
                expected.add(REF)
            if _inventory(self.anchor) != expected:
                raise SnapshotError("Staged history contains undeclared or unreachable objects.")
            for path in sorted(expected):
                pin = self.anchor.capture_file(path, publication_compatible=path != REF)
                self.pins.append(pin)
                self.files[path] = pin.content
                if _LOOSE.fullmatch(path):
                    oid = path.replace("objects/", "", 1).replace("/", "")
                    kind, content = history.objects[oid]
                    if _decode_loose(pin.content) != _loose_bytes(kind, content):
                        raise SnapshotError("Staged history object does not match reachable history.")
            self.validate()
        except Exception:
            self.close()
            raise

    def validate(self) -> None:
        self.history.validate()
        if _inventory(self.anchor) != set(self.files) or any(not self.anchor.matches_owned(pin) for pin in self.pins):
            raise SnapshotError("Staged managed history changed during export.")

    def close(self) -> None:
        for pin in self.pins:
            _close_nonraising(pin)
        _close_nonraising(self.anchor)
        _close_nonraising(self.history)
        _close_nonraising(self.store)

    def __enter__(self) -> HistoryProof:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def stage_reachable_history(workspace: str | Path, destination: str | Path, *,
                            run: Callable[..., Any] = subprocess.run) -> HistoryProof:
    store = Store(workspace, run=run)
    history = None
    try:
        history = History(store)
        destination = Path(destination)
        with WorkspaceAnchor(destination.parent) as parent:
            anchor, owned, created = _anchor_child(parent, destination.parent, destination.name)
            if not created:
                anchor.close()
                raise SnapshotError("Staged recovery store destination already exists.")
            try:
                for directory in ("objects", "refs", "refs/heads"):
                    anchor.create_directory(directory).close()
                for relative, content in (("config", CONFIG), ("HEAD", HEAD), ("apparatus-owner.json", _owner(store.layout.workspace_id))):
                    anchor.create_file(relative, content).close()
                for oid, (kind, content) in history.objects.items():
                    actual = _publish_object(anchor, kind, content)
                    if actual != oid:
                        raise SnapshotError("Staged recovery object changed during export.")
                if history.head:
                    anchor.create_file(REF, (history.head + "\n").encode()).close()
                history.validate()
                if not anchor.root_is_current() or not parent.root_is_current():
                    raise SnapshotError("Staged recovery store changed during export.")
            finally:
                anchor.close()
                _close_nonraising(owned)
        return HistoryProof(store, history, destination)
    except Exception:
        _close_nonraising(history)
        store.close()
        raise
