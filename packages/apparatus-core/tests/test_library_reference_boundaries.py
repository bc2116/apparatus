"""Regressions for evidence publication, historical selection, and diagnostics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from uuid import uuid4

import pytest

from apparatus_core import managed_state_recovery as recovery
from apparatus_core.cache import library_cache_root
from apparatus_core.commands import library as library_command
from apparatus_core.commands import recall as recall_command
from apparatus_core.library import index
from apparatus_core.library.ingest import ingest_source
from apparatus_core.library.sources import (
    Catalog, register_source, registration_path, unregister_source,
)
from apparatus_core.snapshots import SnapshotError


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = (tmp_path / "area").resolve()
    (root / "System/receipts").mkdir(parents=True)
    (root / "Library").mkdir()
    (root / "project").mkdir()
    (root / "System/profile.yaml").write_text(
        "schema: apparatus/profile@v0\nstatus: configured\nprivacy_mode: standard\n"
        "work_types: []\nreview_day: null\n", encoding="utf-8",
    )
    (root / "System/workspace.yaml").write_text(
        f"schema: apparatus/workspace@v0\nid: {uuid4()}\n"
        "layout: sibling-projects\nrecovery: managed-state\n", encoding="utf-8",
    )
    (root / "AGENTS.md").write_text("Synthetic managed instructions.\n", encoding="utf-8")
    (root / "project/report.txt").write_text("cobalt selected original evidence", encoding="utf-8")
    (root / "project/unselected.txt").write_text("unselected original sentinel", encoding="utf-8")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "cache"))
    return root


def _tree(root):
    return {path.relative_to(root).as_posix(): None if path.is_dir() else path.read_bytes()
            for path in root.rglob("*")}


def _ingest_selected(workspace):
    selected = register_source(workspace, "project/report.txt")
    result = ingest_source(workspace, selected.source.source_path)
    assert result.counts["extracted"] == 1 and result.ok
    return selected.source


@pytest.mark.parametrize("rebuild", [False, True])
def test_query_uses_its_validated_evidence_after_real_index_competitor(workspace, monkeypatch, rebuild):
    source = _ingest_selected(workspace)
    cache = library_cache_root(workspace)
    update_name = "rebuild" if rebuild else "refresh"
    update = getattr(index, update_name)
    original_search = index.search
    witnesses = []

    def competing_update(*args, **kwargs):
        report = update(*args, **kwargs)
        # The real refresh/rebuild must already have published this invocation's
        # current evidence before the independent writer acquires its lock.
        witnesses.append(("own-publication", [hit.source_path for hit in original_search(cache, "cobalt")]))
        with index._writer_lock(cache):
            connection = index._database_for_operation(cache)
            try:
                with connection:
                    index._refresh_connection(connection, {
                        "project/unselected.txt": (
                            "a" * 64, "synthetic-competitor", "cobalt competing stale evidence",
                        ),
                    })
                index._publish_database(cache, connection)
            finally:
                index._close_database(connection)
        witnesses.append(("competitor-publication", [hit.source_path for hit in original_search(cache, "cobalt")]))
        return report

    monkeypatch.setattr(index, update_name, competing_update)
    result = index.retrieve(workspace, "cobalt", rebuild_index=rebuild)
    assert witnesses == [
        ("own-publication", [source.source_path]),
        ("competitor-publication", ["project/unselected.txt"]),
    ]
    assert [hit.source_path for hit in result.hits] == [source.source_path]
    assert "selected original" in result.hits[0].snippet
    assert "competing stale" not in result.hits[0].snippet
    assert result.coverage.status == "complete"
    assert (workspace / "project/unselected.txt").read_text(encoding="utf-8") == "unselected original sentinel"


def test_historical_registration_collision_rejected_before_any_publication(workspace, monkeypatch):
    register_source(workspace, "project/report.txt")
    snapshot = recovery.take_snapshot(workspace).snapshot
    assert snapshot is not None
    assert unregister_source(workspace, "project/report.txt").changed
    # Use an intermediate spelling so this is a real portable rename even on
    # case-insensitive Windows and macOS filesystems.
    (workspace / "project/report.txt").rename(workspace / "project/moved.txt")
    (workspace / "project/moved.txt").rename(workspace / "project/REPORT.txt")
    assert register_source(workspace, "project/REPORT.txt").changed
    with Catalog(workspace) as catalog:
        assert [source.source_path for source in catalog.sources] == ["project/REPORT.txt"]
    assert not (workspace / registration_path("project/report.txt")).exists()
    assert (workspace / registration_path("project/REPORT.txt")).is_file()
    before = _tree(workspace)
    publications = []
    create = recovery.WorkspaceAnchor.create_file
    replace = recovery.WorkspaceAnchor.replace_if_unchanged

    def witness_create(self, relative, *args, **kwargs):
        publications.append(("create", str(relative)))
        return create(self, relative, *args, **kwargs)

    def witness_replace(self, relative, *args, **kwargs):
        publications.append(("replace", str(relative)))
        return replace(self, relative, *args, **kwargs)

    monkeypatch.setattr(recovery.WorkspaceAnchor, "create_file", witness_create)
    monkeypatch.setattr(recovery.WorkspaceAnchor, "replace_if_unchanged", witness_replace)
    with pytest.raises(SnapshotError, match="(?i)colli|conflict|portable"):
        recovery.restore_snapshot(workspace, snapshot.identifier)
    assert publications == [], "A collision must fail before files or receipts are published."
    assert _tree(workspace) == before
    assert (workspace / "project/REPORT.txt").read_text(encoding="utf-8") == "cobalt selected original evidence"
    assert (workspace / "project/unselected.txt").read_text(encoding="utf-8") == "unselected original sentinel"
    with Catalog(workspace) as catalog:
        assert [source.source_path for source in catalog.sources] == ["project/REPORT.txt"]


@pytest.mark.parametrize("failure", ["foreign_backup_name", "receipt"])
def test_changed_registration_restore_preserves_foreign_files_and_rolls_back(workspace, monkeypatch, failure):
    register_source(workspace, "project/report.txt")
    snapshot = recovery.take_snapshot(workspace).snapshot
    assert snapshot is not None
    record = workspace / registration_path("project/report.txt")
    saved = record.read_bytes()
    record.write_bytes(saved + b"# User annotation\n")
    before = _tree(workspace)
    foreign = record.parent / ".apparatus-memory-unowned.bak"
    validate = recovery.RestorePlan._validate_published
    observed = []

    def assert_published(plan):
        target = next(change.target for change in plan.changes
                      if change.target.relative.as_posix() == registration_path("project/report.txt"))
        assert target.content == saved
        assert plan.store.root.matches_owned(target)

    def published(plan):
        if failure == "foreign_backup_name" and not observed:
            assert_published(plan)
            assert plan.changes, "The actual replacement must retain its backup."
            foreign.write_bytes(b"Foreign file beside the real backup\n")
            observed.append("foreign")
        return validate(plan)

    def fail_receipt(*_args, **_kwargs):
        assert_published(plan)
        observed.append("receipt")
        raise OSError("synthetic late receipt failure")

    monkeypatch.setattr(recovery.RestorePlan, "_validate_published", published)
    plan = recovery.RestorePlan(workspace, snapshot.identifier, subprocess.run)
    try:
        with pytest.raises(SnapshotError, match="catalog|receipt"):
            plan.apply(write=fail_receipt)
    finally:
        plan.close()
    assert observed == (["foreign"] if failure == "foreign_backup_name" else ["receipt"])
    expected = dict(before)
    if failure == "foreign_backup_name":
        expected[foreign.relative_to(workspace).as_posix()] = foreign.read_bytes()
    assert _tree(workspace) == expected


@pytest.mark.parametrize("command", ["search", "recall"])
def test_invalid_existing_extraction_reports_unavailability_not_never_ingested(workspace, capsys, command):
    source = _ingest_selected(workspace)
    metadata = library_cache_root(workspace) / (source.cache_relative + ".json")
    assert json.loads(metadata.read_bytes())["status"] == "extracted"
    assert metadata.write_bytes(b"{}") == 2
    assert json.loads(metadata.read_bytes()) == {}
    before = _tree(workspace)
    args = argparse.Namespace(
        workspace=str(workspace), query="cobalt", question="cobalt", limit=5,
        as_json=False, rebuild=False, requested=False,
    )
    run = library_command.run_search if command == "search" else recall_command.run
    assert run(args) != 0
    output = capsys.readouterr().out.casefold()
    assert "invalid" in output or "unavailable" in output, output
    assert "nothing from your library has been ingested" not in output
    assert "not in your library" not in output
    assert "ingest" in output, "The diagnostic must provide an actionable repair."
    assert metadata.read_bytes() == b"{}"
    assert _tree(workspace) == before


@pytest.mark.parametrize("catalog_state", ["present", "present_changed", "absent_record", "absent_catalog"])
def test_restore_catalog_validation_coexists_with_retained_transaction_proofs(workspace, monkeypatch, catalog_state):
    """Model Win32 reciprocal sharing and also exercise the real platform APIs."""
    selected = register_source(workspace, "project/report.txt").source
    snapshot = recovery.take_snapshot(workspace).snapshot
    assert snapshot is not None
    record_path = workspace / registration_path(selected.source_path)
    saved_record = record_path.read_bytes()
    if catalog_state == "present_changed":
        record_path.write_bytes(saved_record + b"# Local annotation\n")
    if catalog_state.startswith("absent"):
        assert unregister_source(workspace, selected.source_path).changed
    if catalog_state == "absent_catalog":
        record_path.parent.rmdir()
        record_path.parent.parent.rmdir()
    original_files = {path.name: path.read_bytes() for path in (workspace / "project").iterdir()}
    retained_files = []
    retained_directories = []
    witnesses = {"file_aliases": 0, "directory_aliases": 0}
    capture = recovery.WorkspaceAnchor.capture_file
    create_file = recovery.WorkspaceAnchor.create_file
    create_directory = recovery.WorkspaceAnchor.create_directory
    open_directory = recovery.WorkspaceAnchor.open_directory
    initialize = recovery.WorkspaceAnchor.__init__

    def active(proof):
        return getattr(proof, "handle", proof.parent) >= 0

    def held_directory(path):
        return any(held == path and active(proof) for held, proof in retained_directories)

    def capture_with_sharing(self, relative, **kwargs):
        path = self.workspace / relative
        assert path.parent != workspace / "project", "Restore must not read referenced originals."
        if path == record_path:
            held = any(active(proof) for proof in retained_files)
            if held:
                if kwargs.get("publication_compatible", False):
                    raise PermissionError("simulated Win32 file sharing conflict")
                witnesses["file_aliases"] += 1
            proof = capture(self, relative, **kwargs)
            if not kwargs.get("publication_compatible", False):
                retained_files.append(proof)
            return proof
        return capture(self, relative, **kwargs)

    def create_file_with_proof(self, relative, *args, **kwargs):
        proof = create_file(self, relative, *args, **kwargs)
        if self.workspace / relative == record_path:
            retained_files.append(proof)
        return proof

    def create_directory_with_proof(self, relative):
        proof = create_directory(self, relative)
        retained_directories.append((self.workspace / relative, proof))
        return proof

    def open_with_sharing(self, relative, **kwargs):
        if held_directory(self.workspace / relative):
            if not kwargs.get("shares_delete", False):
                raise PermissionError("simulated Win32 directory sharing conflict")
            witnesses["directory_aliases"] += 1
        return open_directory(self, relative, **kwargs)

    def initialize_with_sharing(self, path, **kwargs):
        if held_directory(path) and not kwargs.get("root_shares_delete", False):
            raise PermissionError("simulated Win32 root sharing conflict")
        return initialize(self, path, **kwargs)

    monkeypatch.setattr(recovery.WorkspaceAnchor, "capture_file", capture_with_sharing)
    monkeypatch.setattr(recovery.WorkspaceAnchor, "create_file", create_file_with_proof)
    monkeypatch.setattr(recovery.WorkspaceAnchor, "create_directory", create_directory_with_proof)
    monkeypatch.setattr(recovery.WorkspaceAnchor, "open_directory", open_with_sharing)
    monkeypatch.setattr(recovery.WorkspaceAnchor, "__init__", initialize_with_sharing)
    recovery.restore_snapshot(workspace, snapshot.identifier)
    assert witnesses["file_aliases"] >= 2, "Restore must validate while original/publication proofs remain retained."
    if catalog_state == "absent_catalog":
        assert witnesses["directory_aliases"] >= 2
    assert record_path.read_bytes() == saved_record
    assert {path.name: path.read_bytes() for path in (workspace / "project").iterdir()} == original_files
    with Catalog(workspace) as catalog:
        assert catalog.sources == (selected,)
        catalog.validate()


def test_restored_registration_receipt_failure_rolls_back_only_owned_state(workspace):
    register_source(workspace, "project/report.txt")
    snapshot = recovery.take_snapshot(workspace).snapshot
    assert snapshot is not None
    assert unregister_source(workspace, "project/report.txt").changed
    record_path = workspace / registration_path("project/report.txt")
    record_path.parent.rmdir()
    record_path.parent.parent.rmdir()
    before = _tree(workspace)
    witnessed = []

    def fail_receipt(*_args, **_kwargs):
        assert record_path.is_file(), "The actual registration must have been restored before receipt failure."
        witnessed.append("published-registration")
        raise OSError("synthetic late receipt failure")

    with pytest.raises(SnapshotError, match="receipt"):
        recovery.restore_snapshot(workspace, snapshot.identifier, write=fail_receipt)
    assert witnessed == ["published-registration"]
    assert _tree(workspace) == before
