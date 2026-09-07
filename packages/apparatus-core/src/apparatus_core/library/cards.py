"""Small assistant-written cards bound to current selected-source evidence."""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
from pathlib import Path, PurePosixPath
import re

from apparatus_core import records
from apparatus_core.cache import library_cache_root
from apparatus_core.commands.memory import _redact_strings, _receipt_fields, _write_owned_receipt
from apparatus_core.features import enabled
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.ignore import load_ignore_rules
from apparatus_core.init_deploy import _anchor_child
from apparatus_core.library.index import IndexError, selected_evidence
from apparatus_core.library.sources import Catalog, Source, SourceError, SourceUnavailable, _names, _open_child
from apparatus_core.payload import preflight_workspace_paths
from apparatus_core.receipts import write_receipt
from apparatus_core.retention import TaskRetentionError, operation
from apparatus_core.snapshots import (SnapshotResult, SnapshotTransaction, _capture_snapshot_receipt_files,
                                     _snapshot_receipt_transient_paths, _close_nonraising)
from apparatus_core.workspace_layout import read_layout

ROOT = "System/library/cards"
SCHEMA = "apparatus/library-card@v0"
_FIELDS = {"schema", "source", "source_sha256", "text_sha256", "extractor_version", "summary", "topics"}
_HASH = re.compile(r"[0-9a-f]{64}\Z")


class CardError(ValueError):
    """A card cannot be trusted or published safely."""


def source_for(path):
    return Source(path, "library" if isinstance(path, str) and path.startswith("Library/") else "registered")


def card_path(source):
    return f"{ROOT}/{source.key}.yaml"


def _mapping(content):
    try:
        events = tuple(records.yaml.parse(content))
        if any(isinstance(event, records.yaml.AliasEvent) or getattr(event, "anchor", None) is not None for event in events):
            raise ValueError
        node = records.yaml.compose(content)
        if not isinstance(node, records.yaml.MappingNode):
            raise ValueError
        keys = [key.value for key, _ in node.value if isinstance(key, records.yaml.ScalarNode)
                and key.tag == "tag:yaml.org,2002:str"]
        if len(keys) != len(node.value) or len(keys) != len(set(keys)):
            raise ValueError
        return records.yaml.safe_load(content)
    except (ValueError, TypeError, UnicodeError, records.yaml.YAMLError) as error:
        raise CardError("Card must contain a closed mapping with unique plain keys and no aliases.") from error


def _validate(data):
    if not isinstance(data, dict) or set(data) != _FIELDS or data.get("schema") != SCHEMA:
        raise CardError("Card fields do not match apparatus/library-card@v0.")
    source = source_for(data["source"])
    if any(not isinstance(data[name], str) or not _HASH.fullmatch(data[name]) for name in ("source_sha256", "text_sha256")):
        raise CardError("Card provenance needs exact SHA-256 values.")
    if not isinstance(data["extractor_version"], str) or not 1 <= len(data["extractor_version"]) <= 128:
        raise CardError("Card extractor version is invalid.")
    if not isinstance(data["summary"], str) or not data["summary"].strip() or len(data["summary"]) > 1200:
        raise CardError("Card summary must contain 1 through 1200 characters.")
    topics = data["topics"]
    if (not isinstance(topics, list) or len(topics) > 8 or
            any(not isinstance(topic, str) or not topic.strip() or len(topic) > 64 for topic in topics) or
            len(topics) != len(set(topics))):
        raise CardError("Card needs at most eight distinct short topics.")
    return source


def parse_card(content: bytes, relative: str):
    data = _mapping(content)
    try:
        source = _validate(data)
    except SourceError as error:
        raise CardError("Card source path is invalid.") from error
    if relative != card_path(source):
        raise CardError("Card filename does not agree with its source.")
    return data


def card_files(anchor, *, excluded=None):
    """Read only direct managed card records, never discover source documents."""
    result = {}
    with ExitStack() as stack:
        parent = anchor
        for name in ROOT.split("/"):
            try:
                parent = stack.enter_context(_open_child(parent, name))
            except FileNotFoundError:
                return result
        names = _names(parent)
        proofs = []
        for name in sorted(names):
            relative = f"{ROOT}/{name}"
            if excluded is not None and (excluded(ROOT) or excluded(relative)):
                raise CardError("Ignore rules hide card records; card coverage is incomplete.")
            if not re.fullmatch(r"[0-9a-f]{64}\.yaml", name):
                raise CardError("Unknown entry in the card directory; preserve it and repair the card records.")
            proof = parent.capture_file(name, publication_compatible=True)
            stack.callback(proof.close)
            proofs.append(proof)
            parse_card(proof.content, relative)
            result[relative] = proof.content
        if _names(parent) != names or any(not parent.matches_owned(proof) for proof in proofs):
            raise CardError("Card records changed while being checked.")
    return result


def _exists(anchor, relative):
    try:
        return anchor.entry_exists(relative)
    except FileNotFoundError:
        return False


def _optional(anchor, relative):
    try:
        return anchor.capture_file(relative, publication_compatible=True)
    except FileNotFoundError:
        return None


def _status(data, evidence):
    if evidence.status != "extracted":
        return "stale" if evidence.status == "stale" else "unavailable"
    if data is None:
        return "absent"
    return "current" if all(data[name] == value for name, value in _provenance(evidence).items()) else "stale"


def _provenance(evidence):
    return {"source_sha256": evidence.source_sha256,
            "text_sha256": hashlib.sha256(evidence.text.encode("utf-8")).hexdigest(),
            "extractor_version": evidence.extractor_version}


def read_card(workspace, source_path, *, include_text=True):
    root = preflight_workspace_paths(workspace)
    source = source_for(source_path)
    unavailable = {"source": source.source_path, "card_status": "unavailable", "evidence_status": "unavailable"}
    result = dict(unavailable)
    rules = load_ignore_rules(root).require_valid()
    if rules.matches(source.source_path) or rules.matches(card_path(source)):
        return {**result, "reason": "ignored"}
    if not enabled(root, "library_indexing"):
        return {**result, "reason": "feature_off"}
    with Catalog(root) as catalog:
        if source.kind == "registered" and source not in catalog.sources:
            return {**result, "card_status": "unselected", "reason": "unselected"}
        try:
            cache = library_cache_root(root, create=False)
            with selected_evidence(cache, catalog, source, rules) as evidence, WorkspaceAnchor(root) as anchor:
                proof = _optional(anchor, card_path(source))
                try:
                    try:
                        data = parse_card(proof.content, card_path(source)) if proof else None
                    except CardError:
                        evidence.validate()
                        return {**result, "card_status": "invalid", "reason": "invalid_card"}
                    result.update(card_status=_status(data, evidence), evidence_status=evidence.status)
                    if evidence.status == "extracted":
                        result.update(_provenance(evidence))
                        result["coverage"] = "Available extracted text; extraction success does not establish complete page, image or table coverage."
                        if include_text:
                            result["text"] = evidence.text
                    if result["card_status"] == "current":
                        result.update(summary=data["summary"], topics=data["topics"])
                    evidence.validate()
                    if proof is not None and not anchor.matches_owned(proof):
                        raise CardError("Card changed during reading.")
                    if proof is None and _exists(anchor, card_path(source)):
                        raise CardError("Card appeared during reading.")
                    return result
                finally:
                    _close_nonraising(proof)
        except SourceUnavailable as error:
            return {**unavailable, "reason": error.reason}
        except (IndexError, OSError, ValueError, UnicodeError):
            return {**unavailable, "reason": "extraction_unavailable"}


def _publish(anchor, parent, name, content, existing, validate, findings, write):
    created = replacement = receipt = transaction = None
    receipt_files = ()
    try:
        validate()
        if existing is not None:
            if not parent.matches_owned(existing):
                raise CardError("Card changed before publication.")
            if existing.content != content:
                identity, original = existing.identity, existing.content
                existing.close()  # Hand exact identity/bytes to CAS before replacement.
                replacement = parent.replace_if_unchanged(name, identity, original, content)
        else:
            created = parent.create_file(name, content)

        def final():
            validate()
            proof = replacement.target if replacement is not None else (created or existing)
            if not parent.matches_owned(proof):
                raise CardError("Card publication changed before completion.")
            if replacement is not None:
                replacement.validate_commit()
            if transaction is not None:
                transaction.validate_durable()

        if findings:
            receipt = _write_owned_receipt(write, anchor.workspace, "redaction", _receipt_fields(findings))
            transient = _snapshot_receipt_transient_paths(anchor.workspace, receipt)
            receipt_files = _capture_snapshot_receipt_files(anchor.workspace, anchor, receipt, transient)
            transaction = SnapshotTransaction(anchor.workspace, SnapshotResult(None), receipt=receipt,
                                              receipt_files=receipt_files, workspace_anchor=anchor)
            transaction.settle()
            transaction.release()
        final()
        if replacement is not None:
            replacement.commit()
        final()
        if transaction is not None:
            transaction.accept()
        return created is not None or replacement is not None
    except Exception:
        compensation = transaction or SnapshotTransaction(anchor.workspace, SnapshotResult(None), receipt=receipt,
                                                           receipt_files=receipt_files, workspace_anchor=anchor)
        try:
            compensation.rollback()
        except Exception:
            pass
        try:
            if replacement is not None:
                if replacement.finished:
                    parent.restore_owned_if_unchanged(replacement.target, replacement.backup.content)
                else:
                    replacement.rollback()
            elif created is not None:
                parent.unlink_owned_if_present(created)
        except OSError:
            if replacement is not None:
                try:
                    replacement.discard_backup()
                except OSError:
                    pass
        raise
    finally:
        for proof in (existing, created, replacement, receipt, *receipt_files):
            _close_nonraising(proof)


def write_card(workspace, source_path, input_stream, *, task_id=None, write=write_receipt):
    root = preflight_workspace_paths(workspace)
    with operation(root, task_id=task_id) as context:
        context.require_memory_write()
        if context.task_id is None:
            raise TaskRetentionError("Start a saving task and pass --task ID before creating a Library card.")
        layout = read_layout(root)
        if layout is None:
            raise CardError("Enroll with apparatus init WORKSPACE --adopt before creating cards.")
        source = source_for(source_path)
        rules = load_ignore_rules(root).require_valid()
        if rules.matches(source.source_path) or rules.matches(card_path(source)):
            raise CardError("Ignore rules exclude this source or card.")
        if not enabled(root, "library_indexing"):
            raise CardError("Library indexing is off; no card was created.")
        candidate = _mapping(input_stream.read())
        if not isinstance(candidate, dict) or set(candidate) != _FIELDS - {"schema", "source"}:
            raise CardError("Supply summary/topics and the exact source/text hashes and extractor version from library card.")
        data = {"schema": SCHEMA, "source": source.source_path, **candidate}
        _validate(data)
        values = {"summary": data["summary"], **{str(i): topic for i, topic in enumerate(data["topics"])}}
        cleaned, findings = _redact_strings(values)
        data["summary"] = cleaned["summary"]
        data["topics"] = [cleaned[str(i)] for i in range(len(data["topics"]))]
        _validate(data)
        content = records.yaml.safe_dump(data, sort_keys=False, allow_unicode=True).encode("utf-8")
        parents, directories = [], []
        try:
            with WorkspaceAnchor(root) as anchor:
                parent = anchor
                for index, name in enumerate(ROOT.split("/")):
                    child, owned, _ = _anchor_child(parent, root / Path(*ROOT.split("/")[:index]), name)
                    parents.append(child)
                    if owned is not None:
                        directories.append((parent, owned, child))
                    parent = child
                with Catalog(root, transaction_compatible=True) as catalog:
                    selected = catalog.source(source.source_path)
                    cache = library_cache_root(root, create=False)
                    with selected_evidence(cache, catalog, selected, rules) as evidence:
                        if evidence.status != "extracted":
                            raise CardError("Current source extraction is unavailable or stale; refresh it before writing a card.")
                        if any(data[key] != value for key, value in _provenance(evidence).items()):
                            raise CardError("Card evidence changed; read the current extraction before writing a card.")
                        def validate():
                            layout.validate(anchor)
                            evidence.validate()
                            if any(not item.root_is_current() for item in parents):
                                raise CardError("Card parent changed during publication.")
                        name = Path(card_path(source)).name
                        existing = _optional(parent, name)
                        try:
                            if existing is not None:
                                parse_card(existing.content, card_path(source))
                            changed = _publish(anchor, parent, name, content, existing, validate, findings, write)
                        finally:
                            _close_nonraising(existing)
            return {"source": source.source_path, "card_status": "current", "status": "written" if changed else "unchanged"}
        except Exception:
            for parent, owned, child in reversed(directories):
                _close_nonraising(child)
                try:
                    parent.remove_owned_directory(owned)
                except OSError:
                    pass
                _close_nonraising(owned)
            raise
        finally:
            for _, owned, _ in directories:
                _close_nonraising(owned)
            for parent in reversed(parents):
                _close_nonraising(parent)
