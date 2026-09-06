"""Draft safely; adopt only the exact workflow the user reviewed."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from apparatus_core import learned_skills as learned, skills
from apparatus_core.commands.memory import _receipt_fields, _write_owned_receipt
from apparatus_core.credentials import redact
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.init_deploy import _anchor_child
from apparatus_core.payload import PayloadError, preflight_workspace_paths
from apparatus_core.receipts import write_receipt
from apparatus_core.retention import RetentionSuppressed, TaskRetentionError, operation
from apparatus_core.workspace_layout import read_layout
from apparatus_core.snapshots import (
    SnapshotResult, SnapshotTransaction, _capture_snapshot_receipt_files,
    _close_nonraising, _snapshot_receipt_transient_paths,
)


def register(subparsers):
    parser = subparsers.add_parser("skill", help="draft and adopt a reviewed learned Skill")
    actions = parser.add_subparsers(dest="skill_action")
    for action in ("draft", "adopt"):
        command = actions.add_parser(action, help=f"{action} a learned Skill")
        command.add_argument("workspace", metavar="WORKSPACE")
        command.add_argument("name", metavar="NAME")
        if action == "draft":
            command.add_argument("--stdin", action="store_true", required=True)
        else:
            command.add_argument("--digest", required=True, metavar="SHA256")
        command.set_defaults(func=run)


def _optional(anchor, relative):
    try:
        return anchor.capture_file(relative, publication_compatible=True)
    except FileNotFoundError:
        return None


def _validate(anchor, reads, writes, parents):
    if not anchor.root_is_current() or any(not parent.root_is_current() for parent in parents.values()):
        raise OSError("Learned Skill parent changed during publication.")
    if any(not anchor.matches_owned(proof) for proof in reads):
        raise OSError("Learned Skill changed after review or planning.")
    if any(not parent.matches_owned(proof) for parent, proof in writes):
        raise OSError("Learned Skill publication changed before completion.")


def _publish(anchor, contents, reads, findings, write, *, new_native_leaf=None):
    parents = {"": anchor}
    directories = []
    writes = []
    receipt = None
    receipt_files = ()
    transaction = None
    native_parent = None
    try:
        # Select every destination parent through retained immediate handles.
        for relative in contents:
            current = anchor
            parts = Path(relative).parts
            for length, name in enumerate(parts[:-1], 1):
                key = "/".join(parts[:length])
                if key not in parents:
                    child, owned, _ = _anchor_child(current, anchor.workspace / Path(*parts[:length - 1]), name)
                    parents[key] = child
                    if owned is not None:
                        directories.append((current, owned, child))
                    if key == new_native_leaf:
                        if owned is None:
                            raise learned.LearnedSkillError("The native Skill directory already exists; preserve it and choose a new name.")
                        native_parent = (current, owned)
                current = parents[key]
            _validate(anchor, reads, writes, parents)
            if Path(relative).parent.as_posix() == new_native_leaf:
                # Bind the body to this invocation's exact newly-created leaf.
                parent, owned = native_parent
                proof = parent.create_file(Path(parts[-2]) / parts[-1], contents[relative], owned_parent=owned)
                writes.append((parent, proof))
            else:
                writes.append((current, current.create_file(parts[-1], contents[relative])))
        _validate(anchor, reads, writes, parents)
        if findings:
            receipt = _write_owned_receipt(write, anchor.workspace, "redaction", _receipt_fields(findings))
            transient = _snapshot_receipt_transient_paths(anchor.workspace, receipt)
            receipt_files = _capture_snapshot_receipt_files(anchor.workspace, anchor, receipt, transient)
            transaction = SnapshotTransaction(anchor.workspace, SnapshotResult(None), receipt=receipt,
                                              receipt_files=receipt_files, workspace_anchor=anchor)
            transaction.settle()
            _validate(anchor, reads, writes, parents)
            transaction.release()
            transaction.validate_durable()
        _validate(anchor, reads, writes, parents)
        if transaction is not None:
            transaction.validate_durable()
            transaction.accept()
    except Exception:
        compensation = transaction or SnapshotTransaction(anchor.workspace, SnapshotResult(None), receipt=receipt,
                                                           receipt_files=receipt_files, workspace_anchor=anchor)
        try:
            compensation.rollback()
        except Exception:
            pass  # A concurrent receipt belongs to its editor; retain the initiating failure.
        for parent, proof in reversed(writes):
            try:
                parent.unlink_owned_if_present(proof)
            except OSError:
                pass  # Preserve concurrent content rather than overwriting it.
            finally:
                _close_nonraising(proof)
        for parent, owned, child in reversed(directories):
            child.close()
            try:
                parent.remove_owned_directory(owned)
            except OSError:
                pass  # Never remove a directory that gained user contents.
        raise
    finally:
        _close_nonraising(receipt)
        for proof in receipt_files:
            _close_nonraising(proof)
        for _, proof in writes:
            _close_nonraising(proof)
        for _, owned, _ in directories:
            _close_nonraising(owned)
        for key, parent in reversed(tuple(parents.items())):
            if key:
                _close_nonraising(parent)


def run(args, *, input_stream=None, write=write_receipt):
    reads = []
    try:
        root = preflight_workspace_paths(args.workspace)
        with operation(root, task_id=getattr(args, "task", None)) as context:
            context.require_memory_write()
            if context.task_id is None:
                raise TaskRetentionError("Start a saving task and pass --task ID before capturing a learned Skill.")
            name = learned.require_name(args.name)
            layout = read_layout(root)
            if layout is None:
                raise learned.LearnedSkillError("Enroll this work area with apparatus init WORKSPACE --adopt before capturing learned Skills.")
            with WorkspaceAnchor(root) as anchor:
                layout.validate(anchor)
                enrollment = anchor.capture_file("System/workspace.yaml", publication_compatible=True)
                reads.append(enrollment)
                if enrollment.content != layout.content:
                    raise OSError("Work-area enrollment changed.")
                if args.skill_action == "draft":
                    text = (sys.stdin if input_stream is None else input_stream).read()
                    cleaned, findings = redact(text)
                    content = cleaned.encode("utf-8")
                    problems = skills.validate_skill(content, name)
                    if problems:
                        raise learned.LearnedSkillError(problems[0])
                    relative = learned.draft_path(name)
                    _publish(anchor, {relative: content}, reads, findings, write)
                elif args.skill_action == "adopt":
                    digest = getattr(args, "digest", None)
                    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                        raise learned.LearnedSkillError("Provide the SHA256 of the exact reviewed draft.")
                    proof = anchor.capture_file(learned.draft_path(name), publication_compatible=True)
                    reads.append(proof)
                    content = proof.content
                    if hashlib.sha256(content).hexdigest() != digest:
                        raise learned.LearnedSkillError("Draft changed since review; review the current draft before adoption.")
                    if skills.validate_skill(content, name):
                        raise learned.LearnedSkillError("Draft format is invalid; repair and review it before adoption.")
                    cleaned, findings = redact(content.decode("utf-8"))
                    if cleaned.encode("utf-8") != content or findings:
                        raise learned.LearnedSkillError("Draft needs credential redaction; create and review a safe draft before adoption.")
                    relative = learned.body_path(name)
                    marker = learned.marker_path(name)
                    body = _optional(anchor, relative)
                    if body is not None:
                        reads.append(body)
                    ownership = _optional(anchor, marker)
                    if ownership is not None:
                        reads.append(ownership)
                    if body is not None or ownership is not None:
                        if body is None or ownership is None or body.content != content:
                            raise learned.LearnedSkillError("Adoption destination is occupied or partial; preserve it and choose a new name.")
                        learned.parse_marker(marker, ownership.content)
                        _validate(anchor, reads, (), {})
                        print(json.dumps({"status": "unchanged", "path": relative, "sha256": digest}))
                        return 0
                    if anchor.directory_exists(Path(relative).parent):
                        raise learned.LearnedSkillError("The native Skill directory already exists; preserve it and choose a new name.")
                    _publish(anchor, {relative: content, marker: learned.marker_bytes(name)}, reads, (), write,
                             new_native_leaf=Path(relative).parent.as_posix())
                else:
                    raise learned.LearnedSkillError("Choose draft or adopt.")
                print(json.dumps({"status": "drafted" if args.skill_action == "draft" else "adopted",
                                  "path": relative, "sha256": hashlib.sha256(content).hexdigest()}))
        return 0
    except RetentionSuppressed:
        print("skill: this task does not save learned Skills or drafts.")
        return 1
    except (learned.LearnedSkillError, TaskRetentionError, PayloadError) as error:
        print(f"skill: {error}")
        return 2
    except Exception:
        print("skill: files changed, are occupied, or cannot be read or published safely; preserve them and retry after repair.")
        return 2
    finally:
        for proof in reads:
            _close_nonraising(proof)
