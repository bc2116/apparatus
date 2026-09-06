from __future__ import annotations

import argparse
import json
import errno
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from apparatus_core import managed_state_recovery as recovery
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.labeler import render_record
from apparatus_core.retention import RetentionSuppressed, set_no_memory, start_task
from apparatus_core.snapshots import SnapshotError, SnapshotReceiptError


def workspace(path: Path) -> Path:
    (path / "System/receipts").mkdir(parents=True)
    (path / "Memory/Facts").mkdir(parents=True)
    (path / "System/workspace.yaml").write_text(
        f"schema: apparatus/workspace@v0\nid: {uuid4()}\n"
        "layout: sibling-projects\nrecovery: managed-state\n", encoding="utf-8")
    (path / "System/profile.yaml").write_text(
        "schema: apparatus/profile@v0\nstatus: configured\nprivacy_mode: standard\n"
        "work_types: []\nreview_day: null\n", encoding="utf-8")
    (path / "AGENTS.md").write_text("Synthetic managed canon.\n", encoding="utf-8")
    fact(path, "Original synthetic context.")
    return path


def fact(root: Path, body: str, name: str = "sample.md") -> Path:
    path = root / "Memory/Facts" / name
    path.write_text(render_record({"schema": "apparatus/fact@v0", "title": "Synthetic fact"}, body), encoding="utf-8")
    return path


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            check=True, env=recovery._git_environment())
    return result.stdout


def dirty_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q")
    (root / "tracked.txt").write_text("original\n")
    git(root, "add", "tracked.txt")
    git(root, "-c", "commit.gpgsign=false", "commit", "-qm", "Synthetic baseline")
    (root / "tracked.txt").write_text("staged\n")
    git(root, "add", "tracked.txt")
    (root / "tracked.txt").write_text("unstaged\n")
    (root / "untracked.txt").write_text("untracked sentinel\n")


def repository_proof(root: Path) -> tuple[bytes, ...]:
    return (git(root, "rev-parse", "HEAD"), (root / ".git/index").read_bytes(),
            (root / ".git/config").read_bytes(), (root / "tracked.txt").read_bytes(),
            (root / "untracked.txt").read_bytes())


def receipts(root: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in (root / "System/receipts").glob("*.md")}


def test_isolated_snapshot_scope_and_unchanged_save(tmp_path):
    root = workspace(tmp_path / "area")
    projects = [root, root / "project-a", root / "project-b"]
    for project in projects:
        dirty_repo(project)
    (root / "Library").mkdir()
    (root / "Library/original.txt").write_text("Library original sentinel")
    (root / "System/unknown.txt").write_text("Unknown managed-looking sentinel")
    before = [repository_proof(project) for project in projects]
    first = recovery.take_snapshot(root)
    assert first.snapshot is not None
    saved_receipts = receipts(root)
    second = recovery.take_snapshot(root, force=True)
    assert second.no_changes and second.snapshot is None
    assert receipts(root) == saved_receipts
    assert [repository_proof(project) for project in projects] == before
    with recovery.Store(root) as store:
        history = recovery.History(store)
        try:
            assert set(history.files[first.snapshot.identifier]) == {
                "AGENTS.md", "System/profile.yaml", "Memory/Facts/sample.md"}
            assert len(history.snapshots) == 1
        finally:
            history.close()
    assert recovery.resolve_snapshot_id(root, first.snapshot.short_id) == first.snapshot.identifier


def test_no_save_guard_precedes_store_creation_and_requested_exception(tmp_path):
    root = workspace(tmp_path / "area")
    task = start_task(root, save_memory=False)
    with pytest.raises(RetentionSuppressed):
        recovery.take_snapshot(root, task_id=task.task_id)
    assert not (root / "System/recovery").exists()
    assert not (root / ".git").exists()
    result = recovery.take_snapshot(root, task_id=task.task_id, requested=True, label="private task phrase")
    assert result.snapshot is not None
    assert result.snapshot.label == "Requested managed-state snapshot"
    assert b"private task phrase" not in b"".join(receipts(root).values())
    with pytest.raises(RetentionSuppressed):
        recovery.take_snapshot(root, task_id=task.task_id)


def test_native_git_reads_store_and_objects_while_exact_proofs_remain_live(tmp_path):
    root = workspace(tmp_path / "area")
    observed = []
    def native_run(command, **options):
        result = subprocess.run(command, **options)
        observed.append((result.returncode, result.stdout, result.stderr))
        assert result.returncode == 0, observed[-1]
        return result
    with recovery.Store(root, create=True, run=native_run) as store:
        assert recovery._git(store.anchor, ["rev-parse", "--is-bare-repository"], run=native_run) == b"true\n"
        content = b"Synthetic native reader compatibility.\n"
        oid = recovery._publish_object(store.anchor, "blob", content)
        assert recovery._object(store, oid, "blob", {}) == content
        # All config/HEAD/object pins remain live while a second native reader
        # opens those same endpoints. Releasing proofs would hide the Win32 bug.
        assert recovery._git(store.anchor, ["cat-file", "blob", oid], run=native_run) == content
        store.validate()
    assert len(observed) == 3


def test_capture_revalidates_with_retained_recovery_receipt_proof(tmp_path):
    root = workspace(tmp_path / "area")
    with recovery.capture_state(root) as capture:
        invocation = recovery.prepare_receipt_invocation(root, "backup-export", {
            "summary": "Synthetic export evidence.", "body": "Synthetic coverage only.\n"})
        receipt = recovery.write_receipt(root, "backup-export", {
            "summary": "Synthetic export evidence.", "body": "Synthetic coverage only.\n"},
            invocation=invocation)
        receipt.claim(invocation)
        proof = capture.anchor.capture_file(receipt.path.relative_to(root), publication_compatible=True)
        try:
            capture.validate()
            with recovery.capture_state(root) as second:
                assert second.files == capture.files
                second.validate()
            receipt.validate()
            assert capture.anchor.matches_owned(proof)
        finally:
            proof.close()
            receipt.rollback()
            receipt.close()
    assert not receipts(root)


def test_saving_task_cli_restore_releases_preflight_before_snapshot_and_replans(tmp_path, monkeypatch):
    from apparatus_core import snapshots
    from apparatus_core.commands import restore

    root = workspace(tmp_path / "area")
    task = start_task(root, save_memory=True)
    control = root / f"System/tasks/{task.task_id}.yaml"
    task_bytes = control.read_bytes()
    first = recovery.take_snapshot(root, task_id=task.task_id).snapshot
    original = (root / "Memory/Facts/sample.md").read_bytes()
    current = fact(root, "Newer synthetic context.").read_bytes()
    active = set()
    initialize, close, apply = recovery.RestorePlan.__init__, recovery.RestorePlan.close, recovery.RestorePlan.apply
    def tracked_init(plan, *values, **options):
        initialize(plan, *values, **options)
        active.add(id(plan))
    def tracked_close(plan):
        try:
            close(plan)
        finally:
            active.discard(id(plan))
    restored = []
    def tracked_apply(plan, **options):
        assert active == {id(plan)}
        assert plan.preimages["Memory/Facts/sample.md"].content == current
        restored.append(plan.identifier)
        return apply(plan, **options)
    saved = []
    def take(workspace, **options):
        assert not active, "temporary restore preflight still holds destination handles"
        result = snapshots.take_snapshot(workspace, **options)
        saved.append(result.snapshot.identifier)
        return result
    monkeypatch.setattr(recovery.RestorePlan, "__init__", tracked_init)
    monkeypatch.setattr(recovery.RestorePlan, "close", tracked_close)
    monkeypatch.setattr(recovery.RestorePlan, "apply", tracked_apply)
    arguments = argparse.Namespace(workspace=str(root), task=task.task_id,
                                   snapshot_id=first.identifier, list=False)
    assert restore.run(arguments, take=take) == 0
    assert len(saved) == 1 and restored == [first.identifier] and not active
    assert (root / "Memory/Facts/sample.md").read_bytes() == original
    assert control.read_bytes() == task_bytes
    with recovery.Store(root) as store:
        history = recovery.History(store)
        try:
            assert history.files[saved[0]]["Memory/Facts/sample.md"] == current
        finally:
            history.close()
    assert len(list((root / "System/receipts").glob("*-restore*.md"))) == 1


def test_restore_preserves_additions_projects_and_live_task_controls(tmp_path):
    root = workspace(tmp_path / "area")
    first = recovery.take_snapshot(root).snapshot
    original = (root / "Memory/Facts/sample.md").read_bytes()
    task = start_task(root)
    set_no_memory(root, task.task_id)
    controls = (root / f"System/tasks/{task.task_id}.yaml").read_bytes()
    fact(root, "New synthetic context.")
    added = fact(root, "Keep later addition.", "later.md")
    project = root / "project-a"
    dirty_repo(project)
    before = repository_proof(project)
    recovery.restore_snapshot(root, first.identifier, task_id=task.task_id)
    assert (root / "Memory/Facts/sample.md").read_bytes() == original
    assert b"Keep later addition" in added.read_bytes()
    assert (root / f"System/tasks/{task.task_id}.yaml").read_bytes() == controls
    assert repository_proof(project) == before


@pytest.mark.parametrize("relative, content", [
    ("Memory/Facts/sample.md", b"unrelated malformed document"),
    ("System/profile.yaml", b"schema: wrong\n"),
    ("AGENTS.md", b"\xff"),
])
def test_invalid_expected_source_fails_before_store(tmp_path, relative, content):
    root = workspace(tmp_path / "area")
    (root / relative).write_bytes(content)
    with pytest.raises(SnapshotError, match="coverage"):
        recovery.take_snapshot(root)
    assert not (root / "System/recovery").exists()
    assert not receipts(root)


@pytest.mark.parametrize("path", ["config", "apparatus-owner.json", "objects/info/alternates", "sentinel.txt", "refs/heads/other"])
def test_unknown_or_redirected_store_rejected(tmp_path, path):
    root = workspace(tmp_path / "area")
    recovery.take_snapshot(root)
    target = root / recovery.STORE / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"synthetic invalid store content")
    before = receipts(root)
    with pytest.raises((SnapshotError, OSError)):
        recovery.take_snapshot(root)
    assert receipts(root) == before


def test_lost_marker_never_lists_legacy_history(tmp_path):
    root = workspace(tmp_path / "area")
    dirty_repo(root)
    recovery.take_snapshot(root)
    (root / "System/workspace.yaml").unlink()
    before = repository_proof(root)
    with pytest.raises(SnapshotError):
        recovery.list_snapshots(root)
    assert repository_proof(root) == before


def test_receipt_failure_leaves_no_reference_or_receipt(tmp_path):
    root = workspace(tmp_path / "area")
    dirty_repo(root)
    before = repository_proof(root)
    def fail(*args, **kwargs):
        raise OSError("synthetic receipt failure")
    with pytest.raises(SnapshotReceiptError):
        recovery.take_snapshot(root, write=fail)
    assert not (root / recovery.STORE / recovery.REF).exists()
    assert not receipts(root)
    assert repository_proof(root) == before


def test_transient_store_initialization_failure_allows_ordinary_retry(tmp_path, monkeypatch):
    root = workspace(tmp_path / "area")
    dirty_repo(root)
    before = repository_proof(root)
    original = WorkspaceAnchor.create_file
    failures = []
    def fail_head_once(anchor, relative, content):
        if anchor.workspace == root / recovery.STORE and str(relative) == "HEAD" and not failures:
            failures.append("HEAD")
            raise OSError("synthetic transient initialization failure")
        return original(anchor, relative, content)
    monkeypatch.setattr(WorkspaceAnchor, "create_file", fail_head_once)
    with pytest.raises(SnapshotError):
        recovery.take_snapshot(root)
    assert failures == ["HEAD"]
    assert not (root / "System/recovery").exists()
    assert not receipts(root)
    assert repository_proof(root) == before
    result = recovery.take_snapshot(root)
    assert result.snapshot is not None
    assert recovery.list_snapshots(root) == [result.snapshot]
    assert repository_proof(root) == before


def test_initialization_compensation_preserves_concurrent_addition(tmp_path, monkeypatch):
    root = workspace(tmp_path / "area")
    original = WorkspaceAnchor.create_file
    sentinel = root / recovery.STORE / "concurrent.txt"
    def add_then_fail(anchor, relative, content):
        if anchor.workspace == root / recovery.STORE and str(relative) == "HEAD":
            sentinel.write_bytes(b"concurrent content must survive")
            raise OSError("synthetic initialization failure after concurrent addition")
        return original(anchor, relative, content)
    monkeypatch.setattr(WorkspaceAnchor, "create_file", add_then_fail)
    with pytest.raises(SnapshotError, match="concurrent content was preserved"):
        recovery.take_snapshot(root)
    assert sentinel.read_bytes() == b"concurrent content must survive"
    assert {path.name for path in sentinel.parent.iterdir()} == {"concurrent.txt"}
    assert not receipts(root)
    with pytest.raises(SnapshotError):
        recovery.take_snapshot(root)
    assert sentinel.read_bytes() == b"concurrent content must survive"


def test_late_snapshot_failure_compensates_owned_reference_and_receipt(tmp_path, monkeypatch):
    root = workspace(tmp_path / "area")
    initial = recovery.take_snapshot(root).snapshot
    fact(root, "Changed context.")
    before = receipts(root)
    def fail(self):
        raise OSError("synthetic last checkpoint failure")
    monkeypatch.setattr(recovery.ManagedSnapshotTransaction, "settle", fail)
    with pytest.raises(OSError):
        recovery.take_snapshot(root)
    assert receipts(root) == before
    assert [entry.identifier for entry in recovery.list_snapshots(root)] == [initial.identifier]


def test_concurrent_reference_is_preserved_after_failed_save(tmp_path, monkeypatch):
    root = workspace(tmp_path / "area")
    first = recovery.take_snapshot(root).snapshot
    fact(root, "Next context.")
    before = receipts(root)
    witness = []
    def fail(transaction):
        # A competing atomic replacement, using the same cross-platform CAS
        # backend, is possible even while the old inode has retained readers.
        with WorkspaceAnchor(root / recovery.STORE) as anchor:
            old = anchor.capture_file(recovery.REF)
            try:
                replacement = anchor.replace_if_unchanged(recovery.REF, old.identity, old.content,
                                                         (first.identifier + "\n").encode())
                try:
                    replacement.commit()
                    witness.append(replacement.target.identity)
                finally:
                    replacement.close()
            finally:
                old.close()
        transaction.validate()  # must reject the competing inode itself
    monkeypatch.setattr(recovery.ManagedSnapshotTransaction, "settle", fail)
    with pytest.raises(SnapshotError):
        recovery.take_snapshot(root)
    assert len(witness) == 1
    with WorkspaceAnchor(root / recovery.STORE) as anchor:
        content, identity = anchor.read_file(recovery.REF)
    assert identity == witness[0]
    assert content == (first.identifier + "\n").encode()
    assert receipts(root) == before


def test_late_object_directory_substitution_cannot_write_outside_store(tmp_path, monkeypatch):
    root = workspace(tmp_path / "area")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sentinel.txt").write_bytes(b"unchanged outside sentinel")
    original = recovery._anchor_child
    attempts = []
    def swap(parent, parent_path, name):
        result = original(parent, parent_path, name)
        if (name == "objects" and not attempts
                and (parent_path / "apparatus-owner.json").is_file()):
            try:
                (parent_path / name).rename(parent_path / "objects-held")
            except PermissionError as error:
                attempts.append(("blocked", error.errno))
                assert os.name == "nt" and error.errno == errno.EACCES
                # The retained native directory prevented the competing rename.
                result[0].close()
                raise OSError("observed native directory rename denial")
            attempts.append(("replaced", None))
            (parent_path / name).symlink_to(outside, target_is_directory=True)
        return result
    monkeypatch.setattr(recovery, "_anchor_child", swap)
    with pytest.raises((SnapshotError, OSError)):
        recovery.take_snapshot(root)
    assert attempts, "the late nested-directory fault was exercised"
    assert {p.name: p.read_bytes() for p in outside.iterdir()} == {"sentinel.txt": b"unchanged outside sentinel"}
    assert not (root / recovery.STORE / recovery.REF).exists()
    assert not receipts(root)


def test_capture_rejects_new_included_record_and_ignores_recovery_receipts(tmp_path):
    root = workspace(tmp_path / "area")
    with recovery.capture_state(root) as capture:
        recovery.take_snapshot(root)
        capture.validate()
        fact(root, "Newly added included data.", "added.md")
        with pytest.raises(SnapshotError, match="coverage"):
            capture.validate()


def test_no_change_transaction_rejects_stale_reference(tmp_path):
    root = workspace(tmp_path / "area")
    recovery.take_snapshot(root)
    transaction = recovery.prepare_snapshot(root)
    assert transaction.result.no_changes
    # Release the read lock only in the fault fixture, to deterministically
    # witness a completed competing publication on Windows too.
    transaction.history.ref.close()
    (root / recovery.STORE / recovery.REF).write_bytes(b"1" * 40 + b"\n")
    try:
        with pytest.raises(SnapshotError, match="reference"):
            transaction.commit()
    finally:
        transaction.close()
    assert (root / recovery.STORE / recovery.REF).read_bytes() == b"1" * 40 + b"\n"


def test_restore_refuses_malformed_existing_record_before_other_writes(tmp_path):
    root = workspace(tmp_path / "area")
    snapshot = recovery.take_snapshot(root).snapshot
    (root / "AGENTS.md").write_text("Changed custom canon\n")
    (root / "Memory/Facts/sample.md").write_text("Unrelated content\n")
    before = (root / "AGENTS.md").read_bytes()
    with pytest.raises(SnapshotError):
        recovery.restore_snapshot(root, snapshot.identifier)
    assert (root / "AGENTS.md").read_bytes() == before


def test_restore_final_failure_rolls_back_changed_and_created_files(tmp_path, monkeypatch):
    root = workspace(tmp_path / "area")
    snapshot = recovery.take_snapshot(root).snapshot
    (root / "AGENTS.md").unlink()
    fact(root, "Keep current data on failed restore.")
    before = (root / "Memory/Facts/sample.md").read_bytes()
    original = recovery.RestorePlan._validate_published
    def fail(self):
        original(self)
        raise OSError("synthetic restore checkpoint failure")
    monkeypatch.setattr(recovery.RestorePlan, "_validate_published", fail)
    with pytest.raises(OSError):
        recovery.restore_snapshot(root, snapshot.identifier)
    assert not (root / "AGENTS.md").exists()
    assert (root / "Memory/Facts/sample.md").read_bytes() == before


@pytest.mark.parametrize("after_publication", [False, True])
def test_restore_receipt_failure_compensates_files_and_receipt(tmp_path, monkeypatch, after_publication):
    root = workspace(tmp_path / "area")
    snapshot = recovery.take_snapshot(root).snapshot
    (root / "AGENTS.md").unlink()
    fact(root, "Keep current content on failed receipt.")
    before = (root / "Memory/Facts/sample.md").read_bytes()
    old_receipts = receipts(root)
    if after_publication:
        original = recovery.ReceiptPublication.close
        def close(self):
            is_restore = "-restore" in self.path.name
            original(self)
            if is_restore:
                raise OSError("synthetic error after restore receipt close")
        monkeypatch.setattr(recovery.ReceiptPublication, "close", close)
        write = recovery.write_receipt
    else:
        def write(*args, **kwargs):
            raise OSError("synthetic restore receipt writer failure")
    with pytest.raises((OSError, SnapshotError)):
        recovery.restore_snapshot(root, snapshot.identifier, write=write)
    assert not (root / "AGENTS.md").exists()
    assert (root / "Memory/Facts/sample.md").read_bytes() == before
    assert receipts(root) == old_receipts


def test_reachable_stage_excludes_unreachable_objects_and_recovers(tmp_path):
    root = workspace(tmp_path / "area")
    first = recovery.take_snapshot(root).snapshot
    fact(root, "Second context.")
    second = recovery.take_snapshot(root).snapshot
    with recovery.Store(root) as store:
        unreachable = recovery._git(store.anchor, ["hash-object", "-w", "--stdin"], run=subprocess.run,
                                    content=b"Unreachable synthetic sentinel").decode().strip()
    destination = tmp_path / "store"
    with recovery.stage_reachable_history(root, destination) as proof:
        proof.validate()
        assert f"objects/{unreachable[:2]}/{unreachable[2:]}" not in proof.files
        assert proof.files[recovery.REF] == (second.identifier + "\n").encode()
        assert json.loads(proof.files["apparatus-owner.json"])["schema"] == recovery.OWNER_SCHEMA
        with WorkspaceAnchor(destination) as anchor:
            assert recovery._git(anchor, ["cat-file", "-t", first.identifier], run=subprocess.run) == b"commit\n"


def test_manifest_extra_paths_are_rejected_without_restore_writes(tmp_path):
    root = workspace(tmp_path / "area")
    recovery.take_snapshot(root)
    with recovery.Store(root) as store:
        history = recovery.History(store)
        files = dict(history.files[history.head])
        manifest = recovery._manifest(store.layout.workspace_id, files)
        history.close()
        tree = recovery._write_tree(store, {**files, recovery.MANIFEST: manifest, "project-a/secret.txt": b"sentinel"})
        commit = recovery._git(store.anchor, ["commit-tree", tree], run=subprocess.run, content=b"Invalid synthetic snapshot\n").decode().strip()
        recovery._git(store.anchor, ["update-ref", recovery.REF, commit], run=subprocess.run)
    before = (root / "AGENTS.md").read_bytes()
    with pytest.raises(SnapshotError, match="manifest"):
        recovery.restore_snapshot(root, commit)
    assert (root / "AGENTS.md").read_bytes() == before
