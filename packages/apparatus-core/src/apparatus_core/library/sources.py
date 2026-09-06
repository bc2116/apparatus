"""Selected original files, with retained catalog and source preimages.

This module selects paths and publishes small registration records. Extraction,
cache state, receipts, and recovery orchestration belong to their existing owners.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat
import unicodedata

import yaml

from apparatus_core.credentials import redact
from apparatus_core.features import enabled
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.ignore import load_ignore_rules
from apparatus_core.init_deploy import _anchor_child
from apparatus_core.payload import preflight_workspace_paths
from apparatus_core.retention import operation

SCHEMA = "apparatus/library-source@v0"
REGISTRATION_ROOT = "System/library/sources"
_RECORD_NAME = re.compile(r"[0-9a-f]{64}\.yaml\Z")
_CONTROL = {".git", ".apparatus", ".agents", ".claude", ".cursor", ".github"}
_STATE = {"system", "memory", "goals", "decisions"}
_RESERVED = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?\Z", re.I)


class SourceError(ValueError):
    """The selected-source catalog needs an explicit repair."""


class SourceUnavailable(SourceError):
    """A bounded reason, without disclosing an operating-system exception."""

    def __init__(self, reason: str):
        self.reason = reason
        messages = {
            "missing": "Selected source is missing; add its new path explicitly if it moved.",
            "unavailable": "Selected source is unavailable or changed; retry when it is readable.",
            "unsafe": "Selected source must be a regular file under safe work-area directories.",
            "ignored": "Selected source is excluded by ignore rules; review System/ignore before retrying.",
        }
        super().__init__(messages[reason])


def _portable_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def normalize_source(value: str) -> str:
    """Validate an already-normalized, portable work-area-relative file path."""
    if not isinstance(value, str) or not value or value != unicodedata.normalize("NFC", value):
        raise SourceError("Source path must use normalized portable relative spelling.")
    parts = value.split("/")
    if any(
        part in ("", ".", "..") or part.endswith((".", " "))
        or any(unicodedata.category(char).startswith("C") or char in '\\:<>"|?*' for char in part)
        or _RESERVED.fullmatch(part)
        for part in parts
    ):
        raise SourceError("Source path must use normalized portable relative spelling.")
    if parts[0].casefold() in _STATE or any(part.casefold() in _CONTROL for part in parts):
        raise SourceError("Internal state and app control paths cannot be Library sources.")
    if parts[0].casefold() == "library" and (parts[0] != "Library" or len(parts) < 2):
        raise SourceError("Library sources must name a file using the exact Library directory spelling.")
    if redact(value)[1]:
        raise SourceError("Credential-bearing source paths cannot be registered.")
    return value


def _implicit_library_path(value: str) -> str:
    """Preserve safe existing Library spelling; do not migrate its filenames."""
    if not isinstance(value, str) or not value.startswith("Library/"):
        raise SourceError("Implicit sources must name a file inside Library.")
    parts = value.split("/")
    if any(part in ("", ".", "..") or "\\" in part
           or any(unicodedata.category(char).startswith("C") for char in part)
           for part in parts):
        raise SourceError("Library source must use a safe relative file path.")
    if any(part.casefold() in _CONTROL for part in parts):
        raise SourceError("App control paths cannot be Library sources.")
    if os.name == "nt" and any(
        part.endswith((".", " ")) or _RESERVED.fullmatch(part)
        or any(char in ':<>"|?*' for char in part) for part in parts
    ):
        raise SourceError("Library source must use a safe native file path.")
    if redact(value)[1]:
        raise SourceError("Credential-bearing source paths cannot be selected.")
    return value


def _selected_path(value: str) -> str:
    if isinstance(value, str) and value.startswith("Library/"):
        return _implicit_library_path(value)
    return normalize_source(value)


def source_key(source_path: str) -> str:
    return hashlib.sha256(normalize_source(source_path).encode("utf-8")).hexdigest()


def registration_path(source_path: str) -> str:
    return f"{REGISTRATION_ROOT}/{source_key(source_path)}.yaml"


@dataclass(frozen=True)
class Source:
    source_path: str
    kind: str = "registered"

    def __post_init__(self):
        _selected_path(self.source_path)
        expected = "library" if self.source_path.startswith("Library/") else "registered"
        if self.kind != expected:
            raise SourceError("Source kind does not agree with its path.")

    @property
    def key(self) -> str:
        return hashlib.sha256(self.source_path.encode("utf-8")).hexdigest()

    @property
    def cache_relative(self) -> str:
        if self.kind == "library":
            return "extractions/" + self.source_path[len("Library/"):]
        return "references/" + self.key


def parse_registration(content: bytes, relative_record_path: str | Path) -> Source:
    """Validate a closed record independently of live source availability."""
    try:
        if len(content) > 8192:
            raise ValueError
        text = content.decode("utf-8")
        if any(isinstance(token, (yaml.AliasToken, yaml.AnchorToken)) for token in yaml.scan(text)):
            raise ValueError
        node = yaml.compose(text, Loader=yaml.SafeLoader)
        if not isinstance(node, yaml.MappingNode) or node.tag != "tag:yaml.org,2002:map" or len(node.value) != 2:
            raise ValueError
        values = {}
        for key, value in node.value:
            if not all(isinstance(item, yaml.ScalarNode) and item.tag == "tag:yaml.org,2002:str" for item in (key, value)):
                raise ValueError
            if key.value in values:
                raise ValueError
            values[key.value] = value.value
        if set(values) != {"schema", "source"} or values["schema"] != SCHEMA:
            raise ValueError
        source = Source(values["source"])
        if Path(relative_record_path).as_posix() != registration_path(source.source_path):
            raise ValueError
        return source
    except (ValueError, UnicodeError, yaml.YAMLError):
        raise SourceError("Invalid Library source registration; repair the catalog before retrying.") from None


def _record_bytes(source: Source) -> bytes:
    return yaml.safe_dump({"schema": SCHEMA, "source": source.source_path}, sort_keys=False, allow_unicode=True).encode("utf-8")


def _names(anchor) -> set[str]:
    if not anchor.root_is_current():
        raise OSError("source parent changed")
    names = set(os.listdir(anchor._root if os.name == "posix" else anchor.workspace))
    if not anchor.root_is_current():
        raise OSError("source parent changed")
    return names


def _exact_name(anchor, name: str) -> None:
    matches = {entry for entry in _names(anchor) if _portable_key(entry) == _portable_key(name)}
    if not matches:
        raise FileNotFoundError
    if matches != {name}:
        raise SourceUnavailable("unsafe")


def _open_child(parent, name: str, *, shares_delete: bool = False):
    _status(parent, name, directory=True)
    handle = parent.open_directory(name, shares_delete=shares_delete)
    child = None
    try:
        child = WorkspaceAnchor(
            parent.workspace / name,
            ancestor_shares_delete=parent.child_ancestor_shares_delete(),
            root_shares_delete=shares_delete,
        )
        if not child.matches_root_handle(handle) or not parent.root_is_current() or not child.root_is_current():
            raise OSError("source parent changed")
        return child
    except BaseException:
        if child is not None:
            child.close()
        raise
    finally:
        parent.close_directory(handle)


def _status(anchor, name: str, *, directory=False):
    _exact_name(anchor, name)
    if os.name == "posix":
        result = os.stat(name, dir_fd=anchor._root, follow_symlinks=False)
    else:
        result = os.lstat(anchor.workspace / name)
    if not anchor.root_is_current():
        raise OSError("source parent changed")
    regular = stat.S_ISDIR(result.st_mode) if directory else stat.S_ISREG(result.st_mode)
    if not regular or getattr(result, "st_file_attributes", 0) & 0x400:
        raise SourceUnavailable("unsafe")
    return result


class SourceRead:
    """One exact source read. Keep open and validate before accepting results."""

    def __init__(self, catalog, source: Source, rules=None):
        self.catalog = catalog
        self.source = source
        self._parents = []
        self._proof = None
        try:
            catalog.validate()
            if rules is not None and rules.require_valid().matches(source.source_path):
                raise SourceUnavailable("ignored")
            parent = catalog._root
            for name in source.source_path.split("/")[:-1]:
                parent = _open_child(parent, name)
                self._parents.append(parent)
            name = source.source_path.split("/")[-1]
            _status(parent, name)
            self._anchor = parent
            self._proof = parent.capture_file(name, publication_compatible=True)
            self.content = self._proof.content
            self.sha256 = hashlib.sha256(self.content).hexdigest()
            self.size_bytes = len(self.content)
            self.validate()
        except BaseException as error:
            self.close()
            if isinstance(error, FileNotFoundError):
                raise SourceUnavailable("missing") from None
            if isinstance(error, OSError):
                raise SourceUnavailable("unavailable") from None
            raise

    def validate(self):
        self.catalog.validate()
        if self._proof is None or any(not parent.root_is_current() for parent in self._parents):
            raise SourceUnavailable("unavailable")
        try:
            for parent, name in zip([self.catalog._root, *self._parents], self.source.source_path.split("/")):
                _exact_name(parent, name)
            if not self._anchor.matches_owned(self._proof):
                raise OSError
        except OSError:
            raise SourceUnavailable("unavailable") from None

    def close(self):
        if self._proof is not None:
            self._proof.close()
            self._proof = None
        for parent in reversed(self._parents):
            parent.close()
        self._parents.clear()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class Catalog:
    """Read-only catalog inventory retained through its final validation."""

    def __init__(self, workspace: str | Path, *, transaction_compatible: bool = False,
                 temporary_files: dict | None = None):
        # Restore and card publication retain DELETE-capable owned parents
        # and publication proofs. Their validation aliases must share DELETE access with those exact
        # objects and any created parents. Ordinary catalog reads keep their
        # existing readable, name-locked proofs. Both modes revalidate all
        # parent identities, record bytes and names at the final boundary.
        self._anchors = []
        self._records = {}
        self._temporary = {}
        expected_temporary = dict(temporary_files or {})
        self._created = []
        self._missing = None
        self._leaf = None
        try:
            if expected_temporary and not transaction_compatible:
                raise SourceError("Temporary catalog files require retained restore transactions.")
            self._root = WorkspaceAnchor(preflight_workspace_paths(workspace))
            self._anchors.append(self._root)
            parent = self._root
            parts = REGISTRATION_ROOT.split("/")
            for index, name in enumerate(parts):
                try:
                    child = _open_child(parent, name, shares_delete=transaction_compatible)
                except FileNotFoundError:
                    self._missing = (parent, index)
                    break
                self._anchors.append(child)
                parent = child
            else:
                self._leaf = parent
                seen = set()
                for name in sorted(_names(parent)):
                    if not _RECORD_NAME.fullmatch(name) and name not in expected_temporary:
                        raise SourceError("Unknown entry in Library source catalog; repair it before retrying.")
                    _status(parent, name)
                    proof = parent.capture_file(name, publication_compatible=not transaction_compatible)
                    try:
                        if name in expected_temporary:
                            if (_RECORD_NAME.fullmatch(name)
                                    or (proof.content, proof.identity) != expected_temporary[name]):
                                raise SourceError("Retained catalog backup changed during restore.")
                            self._temporary[name] = proof
                            continue
                        source = parse_registration(proof.content, f"{REGISTRATION_ROOT}/{name}")
                        folded = _portable_key(source.source_path)
                        if folded in seen:
                            raise SourceError("Portable source paths collide; repair the Library catalog.")
                        seen.add(folded)
                        self._records[name] = (source, proof)
                    except BaseException:
                        proof.close()
                        raise
            if set(expected_temporary) != set(self._temporary):
                raise SourceError("Retained catalog backup is missing during restore.")
            self.validate()
        except BaseException as error:
            self.close()
            if isinstance(error, OSError):
                raise SourceError("Library source catalog is unavailable or unsafe; repair it before retrying.") from None
            raise

    @property
    def sources(self) -> tuple[Source, ...]:
        return tuple(sorted((record[0] for record in self._records.values()), key=lambda source: source.source_path))

    def validate(self):
        try:
            if not self._anchors or any(not anchor.root_is_current() for anchor in self._anchors):
                raise OSError
            if self._missing is not None:
                parent, index = self._missing
                name = REGISTRATION_ROOT.split("/")[index]
                if any(_portable_key(entry) == _portable_key(name) for entry in _names(parent)):
                    raise OSError
            if self._leaf is not None:
                if _names(self._leaf) != set(self._records) | set(self._temporary):
                    raise OSError
                if any(not self._leaf.matches_owned(proof) for _, proof in self._records.values()):
                    raise OSError
                if any(not self._leaf.matches_owned(proof) for proof in self._temporary.values()):
                    raise OSError
        except OSError:
            raise SourceError("Library source catalog changed during the operation; retry.") from None

    def source(self, source_path: str) -> Source:
        path = _selected_path(source_path)
        if path.startswith("Library/"):
            return Source(path, "library")
        for source in self.sources:
            if source.source_path == path:
                return source
        raise SourceError("Source is not selected; register its exact relative path first.")

    def read(self, source: Source, rules=None) -> SourceRead:
        if self.source(source.source_path) != source:
            raise SourceError("Source does not match the selected catalog.")
        return SourceRead(self, source, rules)

    def _ensure_directory(self):
        self.validate()
        if self._missing is None:
            return
        parent, index = self._missing
        for name in REGISTRATION_ROOT.split("/")[index:]:
            # The absent preimage must still be absent. A competing creator is
            # never adopted as invocation-owned state.
            if parent.entry_exists(name):
                raise SourceError("Library catalog appeared during registration; retry.")
            child, owned, created = _anchor_child(parent, parent.workspace, name)
            if not created:
                child.close()
                raise SourceError("Library catalog appeared during registration; retry.")
            self._created.append((parent, owned, child))
            self._anchors.append(child)
            parent = child
        self._missing = None
        self._leaf = parent
        self.validate()

    def _cleanup_directories(self):
        for parent, owned, child in reversed(self._created):
            child.close()
            try:
                parent.remove_owned_directory(owned)
            except OSError:
                pass  # A concurrent addition belongs to its writer.
            finally:
                owned.close()

    def close(self):
        for _, proof in self._records.values():
            proof.close()
        for proof in self._temporary.values():
            proof.close()
        for anchor in reversed(self._anchors):
            anchor.close()
        self._anchors.clear()
        for _, owned, _ in self._created:
            owned.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


@dataclass(frozen=True)
class RegistrationResult:
    source: Source
    changed: bool
    implicit: bool = False


@dataclass(frozen=True)
class SourceStatus:
    source: Source
    status: str

    @property
    def source_path(self) -> str:
        return self.source.source_path


def register_source(workspace, source_path: str, *, task_id=None, requested=False) -> RegistrationResult:
    with operation(workspace, task_id=task_id, requested=("library",) if requested else ()) as context:
        context.require_library_write()
        workspace = context.workspace
        if not enabled(workspace, "library_indexing"):
            raise SourceError("Library indexing is disabled; registration did not change it.")
        path = _selected_path(source_path)
        source = Source(path, "library" if path.startswith("Library/") else "registered")
        rules = load_ignore_rules(workspace).require_valid()
        with Catalog(workspace) as catalog:
            for existing in catalog.sources:
                if _portable_key(existing.source_path) == _portable_key(path) and existing != source:
                    raise SourceError("Portable source paths collide; use the exact existing path.")
            # A new selected path is read explicitly, without pretending it is
            # already a catalog member. No sibling file content is read.
            with SourceRead(catalog, source, rules) as reader:
                if source.kind == "library" or source in catalog.sources:
                    reader.validate()
                    return RegistrationResult(source, False, source.kind == "library")
                proof = None
                name = source.key + ".yaml"
                try:
                    catalog._ensure_directory()
                    reader.validate()
                    content = _record_bytes(source)
                    parse_registration(content, registration_path(path))
                    proof = catalog._leaf.create_file(name, content)
                    catalog._records[name] = (source, proof)
                    reader.validate()
                    return RegistrationResult(source, True)
                except BaseException:
                    if proof is not None:
                        try:
                            catalog._leaf.unlink_owned_if_present(proof)
                        except OSError:
                            pass
                        finally:
                            proof.close()
                    catalog._cleanup_directories()
                    raise


def unregister_source(workspace, source_path: str, *, task_id=None, requested=False) -> RegistrationResult:
    with operation(workspace, task_id=task_id, requested=("library",) if requested else ()) as context:
        context.require_library_write()
        workspace = context.workspace
        path = _selected_path(source_path)
        source = Source(path, "library" if path.startswith("Library/") else "registered")
        with Catalog(workspace) as catalog:
            name = source.key + ".yaml"
            if source.kind == "library" or name not in catalog._records:
                catalog.validate()
                return RegistrationResult(source, False, source.kind == "library")
            _, proof = catalog._records[name]
            removed = False
            try:
                catalog.validate()
                removed = catalog._leaf.unlink_owned_if_present(proof)
                if not removed:
                    raise SourceError("Library source registration changed before removal; retry.")
                del catalog._records[name]
                catalog.validate()
                return RegistrationResult(source, True)
            except BaseException:
                if removed:
                    try:
                        restored = catalog._leaf.create_file(name, proof.content)
                        restored.close()
                    except OSError:
                        pass  # Never overwrite a concurrent catalog writer.
                raise
            finally:
                proof.close()


def list_sources(workspace, *, rules=None) -> tuple[SourceStatus, ...]:
    workspace = preflight_workspace_paths(workspace)
    rules = (load_ignore_rules(workspace) if rules is None else rules).require_valid()
    with Catalog(workspace) as catalog:
        results = []
        for source in catalog.sources:
            if rules.matches(source.source_path):
                results.append(SourceStatus(source, "ignored"))
                continue
            parents = []
            try:
                parent = catalog._root
                for name in source.source_path.split("/")[:-1]:
                    parent = _open_child(parent, name)
                    parents.append(parent)
                _status(parent, source.source_path.split("/")[-1])
                if any(not parent.root_is_current() for parent in parents):
                    raise OSError
                status_value = "available"
            except FileNotFoundError:
                status_value = "missing"
            except SourceUnavailable as error:
                status_value = error.reason
            except OSError:
                status_value = "unavailable"
            finally:
                for parent in reversed(parents):
                    parent.close()
            results.append(SourceStatus(source, status_value))
        catalog.validate()
        return tuple(results)
