"""Synthetic cross-component acceptance for selected project originals."""
from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
from uuid import uuid4
import zipfile

import pytest

from apparatus_core import managed_state_backup, managed_state_recovery, recall
from apparatus_core.cache import library_cache_root
from apparatus_core.commands import library as command
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.library import index, ingest, sources
from apparatus_core.retention import RetentionSuppressed, context_for, operation, start_task

REPORT = "project/report.md"
HEALTHY = "other-project/healthy.txt"


def tree(root):
    return {p.relative_to(root).as_posix(): None if p.is_dir() else p.read_bytes()
            for p in root.rglob("*")}


def forbidden(*_args, **_kwargs):
    pytest.fail("operation crossed its read/write scope")


@pytest.fixture
def area(tmp_path, monkeypatch):
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    root = (tmp_path / "area").resolve()
    for relative in ("System", "Library", "project", "other-project", "Memory"):
        (root / relative).mkdir(parents=True)
    (root / "System/profile.yaml").write_text(
        "schema: apparatus/profile@v0\nstatus: configured\nprivacy_mode: standard\n"
        "work_types: []\nreview_day: null\n", encoding="utf-8")
    (root / "System/workspace.yaml").write_text(
        f"schema: apparatus/workspace@v0\nid: {uuid4()}\n"
        "layout: sibling-projects\nrecovery: managed-state\n", encoding="utf-8")
    (root / REPORT).write_bytes(b"# Report\nCobalt evidence supports this synthetic report.\n")
    (root / HEALTHY).write_bytes(b"Cobalt independent healthy evidence.\n")
    task = start_task(root)
    return root, task.task_id


def add(area, path=REPORT, *, requested=False):
    root, task = area
    return command.run_registration(argparse.Namespace(
        workspace=str(root), task=task, library_action="add", source=path,
        requested=requested))


def readonly(area):
    return start_task(area[0], save_memory=False).task_id


@pytest.mark.parametrize("name", ["cafe\u0301.txt", "legacy:report.txt"])
def test_existing_library_filename_remains_searchable(area, name):
    if os.name == "nt" and ":" in name:
        pytest.skip("colon is not a legal legacy Windows filename")
    root, task = area
    original = root / "Library" / name
    original.write_text("Cobalt synthetic legacy source.", encoding="utf-8")
    assert ingest.ingest_library(root, task_id=task).counts["extracted"] == 1
    result = index.retrieve(root, "cobalt", task_id=task)
    assert [hit.source_path for hit in result.hits] == ["Library/" + name]
    assert result.coverage.status == "complete"
    assert original.read_text(encoding="utf-8") == "Cobalt synthetic legacy source."


def test_add_extract_search_and_recall_cite_original_without_opening_sibling(area, monkeypatch):
    root, task = area
    original = (root / REPORT).read_bytes()
    capture = WorkspaceAnchor.capture_file
    observed = []

    def bounded(anchor, relative, **kwargs):
        full = anchor.workspace / relative
        assert full != root / HEALTHY, "unselected sibling content was opened"
        if full == root / REPORT:
            observed.append(full)
        return capture(anchor, relative, **kwargs)

    monkeypatch.setattr(WorkspaceAnchor, "capture_file", bounded)
    assert add(area) == 0
    result = index.retrieve(root, "cobalt", task_id=task)
    assert result.coverage.status == "complete"
    assert [hit.source_path for hit in result.hits] == [REPORT]
    envelope = recall.recall(root, "cobalt", task_id=task)
    assert envelope["status"] == "grounded"
    assert [item["source"] for item in envelope["evidence"]] == [REPORT]
    assert "synthetic report" in envelope["evidence"][0]["snippet"]
    assert observed and (root / REPORT).read_bytes() == original
    assert list((root / "Library").iterdir()) == []
    cache = library_cache_root(root, create=False)
    record = json.loads((cache / (sources.Source(REPORT).cache_relative + ".json")).read_bytes())
    assert record["source_path"] == REPORT
    assert record["source_sha256"] == hashlib.sha256(original).hexdigest()
    assert [item.source_path for item in sources.list_sources(root)] == [REPORT]


def test_same_size_same_mtime_change_is_partial_until_explicit_reingest(area, tmp_path):
    root, task = area
    assert add(area) == add(area, HEALTHY) == 0
    no_save = readonly(area)
    path = root / REPORT
    previous = path.stat()
    changed = path.read_bytes().replace(b"Cobalt", b"Zircon")
    path.write_bytes(changed)
    os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    assert path.stat().st_size == previous.st_size
    assert path.stat().st_mtime_ns == previous.st_mtime_ns
    before = tree(tmp_path)
    stale = index.retrieve(root, "cobalt", task_id=no_save)
    assert [hit.source_path for hit in stale.hits] == [HEALTHY]
    assert stale.coverage.issues == ((REPORT, "stale"),)
    absent = recall.recall(root, "zircon", task_id=no_save, write=forbidden)
    assert absent["status"] == "abstained" and absent["evidence"] == []
    assert absent["coverage"]["status"] == "partial"
    assert tree(tmp_path) == before
    result = ingest.ingest_source(root, REPORT, task_id=task)
    assert result.counts["extracted"] == 1
    fresh = index.retrieve(root, "zircon", task_id=no_save)
    assert [hit.source_path for hit in fresh.hits] == [REPORT]
    assert fresh.coverage.status == "complete"


@pytest.mark.parametrize("change,reason", [("delete", "missing"), ("move", "missing"), ("ignore", "ignored")])
def test_unavailable_original_is_listed_and_never_cited_or_relocated(area, tmp_path, change, reason):
    root, _ = area
    assert add(area) == add(area, HEALTHY) == 0
    no_save = readonly(area)
    if change == "delete":
        (root / REPORT).unlink()
    elif change == "move":
        (root / REPORT).rename(root / "project/renamed.md")
    else:
        (root / "System/ignore").write_text(REPORT + "\n", encoding="utf-8")
    before = tree(tmp_path)
    listing = {item.source_path: item.status for item in sources.list_sources(root)}
    assert listing == {REPORT: reason, HEALTHY: "available"}
    result = index.retrieve(root, "cobalt", task_id=no_save)
    assert [hit.source_path for hit in result.hits] == [HEALTHY]
    assert result.coverage.issues == ((REPORT, reason),)
    assert tree(tmp_path) == before
    assert (root / sources.registration_path(REPORT)).is_file()
    assert not (root / sources.registration_path("project/renamed.md")).exists()


def test_remove_immediately_excludes_old_index_during_no_save_search(area, tmp_path):
    root, task = area
    assert add(area) == add(area, HEALTHY) == 0
    assert len(index.retrieve(root, "cobalt", task_id=task).hits) == 2
    no_save = readonly(area)
    original = (root / REPORT).read_bytes()
    cache = library_cache_root(root, create=False)
    cached_before = tree(cache)
    assert command.run_registration(argparse.Namespace(
        workspace=str(root), task=no_save, library_action="remove", source=REPORT,
        requested=True)) == 0
    before = tree(tmp_path)
    envelope = recall.recall(root, "cobalt", task_id=no_save, write=forbidden)
    assert [item["source"] for item in envelope["evidence"]] == [HEALTHY]
    assert envelope["coverage"]["status"] == "complete"
    assert tree(tmp_path) == before and tree(cache) == cached_before
    assert (root / REPORT).read_bytes() == original


def test_explicit_no_save_add_extracts_only_one_source_and_has_no_memory_authority(area, monkeypatch):
    root, task = area
    sources.register_source(root, HEALTHY, task_id=task)
    (root / "Library/implicit.txt").write_bytes(b"Unrequested implicit Library text")
    no_save = readonly(area)
    before_memory = tree(root / "Memory")
    read = sources.Catalog.read
    observed = []

    def only_selected(catalog, source, rules=None):
        observed.append(source.source_path)
        assert source.source_path == REPORT
        return read(catalog, source, rules=rules)

    monkeypatch.setattr(sources.Catalog, "read", only_selected)
    monkeypatch.setattr(ingest, "_read_source", forbidden)
    assert add((root, no_save), requested=True) == 0
    assert observed
    cache = library_cache_root(root, create=False)
    assert (cache / (sources.Source(REPORT).cache_relative + ".txt")).is_file()
    assert not (cache / (sources.Source(HEALTHY).cache_relative + ".json")).exists()
    assert list((cache / "extractions").iterdir()) == []
    assert not (cache / "index.sqlite3").exists()
    assert tree(root / "Memory") == before_memory
    assert not (root / "System/recovery").exists()
    receipt_bytes = b"".join(path.read_bytes() for path in (root / "System/receipts").glob("*.md"))
    assert b"synthetic report" not in receipt_bytes and b"Unrequested implicit" not in receipt_bytes
    with operation(root, task_id=no_save, requested=("library",)):
        with pytest.raises(RetentionSuppressed):
            context_for(root).require_memory_write()
    with pytest.raises(RetentionSuppressed):
        ingest.ingest_source(root, REPORT, task_id=no_save)


@pytest.mark.parametrize("blocked", ["no-save", "feature-off"])
def test_add_rejects_before_selected_read_or_any_writes(area, tmp_path, monkeypatch, blocked):
    root, task = area
    if blocked == "no-save":
        task = readonly(area)
    else:
        profile = root / "System/profile.yaml"
        profile.write_text(profile.read_text(encoding="utf-8") +
                           "features:\n  library_indexing: false\n  snapshots: true\n  ignore_rules: true\n",
                           encoding="utf-8")
    before = tree(tmp_path)
    monkeypatch.setattr(sources.Catalog, "read", forbidden)
    monkeypatch.setattr(ingest, "_read_source", forbidden)
    monkeypatch.setattr(WorkspaceAnchor, "create_file", forbidden)
    assert add((root, task)) == (1 if blocked == "no-save" else 2)
    assert tree(tmp_path) == before
    assert not library_cache_root(root, create=False).exists()


@pytest.mark.skipif(shutil.which("git") is None, reason="real Git registration history/export proof")
def test_recovery_captures_registration_only_and_older_restore_preserves_later_selection(area, tmp_path):
    root, task = area
    assert add(area) == 0
    first = managed_state_recovery.take_snapshot(root, task_id=task).snapshot
    assert first is not None
    assert add(area, HEALTHY) == 0
    # Restore may revive historical selection, but never overwrite either original.
    sources.unregister_source(root, REPORT, task_id=task)
    changed = b"Original revised independently after snapshot.\n"
    (root / REPORT).write_bytes(changed)
    original_other = (root / HEALTHY).read_bytes()
    managed_state_recovery.restore_snapshot(root, first.identifier, task_id=task)
    assert {item.source_path for item in sources.list_sources(root)} == {REPORT, HEALTHY}
    assert (root / REPORT).read_bytes() == changed
    assert (root / HEALTHY).read_bytes() == original_other
    with managed_state_recovery.capture_state(root) as captured:
        assert sources.registration_path(REPORT) in captured.files
        assert sources.registration_path(HEALTHY) in captured.files
        assert REPORT not in captured.files and HEALTHY not in captured.files
        assert not any(path.startswith(("references/", "extractions/")) for path in captured.files)
    destination = tmp_path / "exports"
    destination.mkdir()
    exported = managed_state_backup.export_backup(root, destination, task_id=task)
    with zipfile.ZipFile(exported.archive) as archive:
        names = archive.namelist()
        assert REPORT not in names and HEALTHY not in names
        assert not any(path.startswith(("references/", "extractions/", "project/", "other-project/")) for path in names)
        for path in (REPORT, HEALTHY):
            relative = sources.registration_path(path)
            assert archive.read(relative) == (root / relative).read_bytes()
        restored = tmp_path / "exported-area"
        archive.extractall(restored)
    assert {item.source_path: item.status for item in sources.list_sources(restored)} == {
        REPORT: "missing", HEALTHY: "missing"}
    assert managed_state_recovery.list_snapshots(restored)


@pytest.mark.parametrize("path,content,status", [
    ("project/empty.txt", b"", "no_text"),
    ("project/unsupported.bin", b"Synthetic binary-format placeholder", "unsupported"),
    ("project/invalid.pdf", b"Not a PDF document", "error"),
])
def test_terminal_extraction_outcomes_keep_registration_but_are_not_searchable(area, capsys, path, content, status):
    root, _ = area
    (root / path).write_bytes(content)
    capsys.readouterr()
    assert add(area, path) == 1
    output = capsys.readouterr().out
    assert "Registration: added" in output and f"{status}=1" in output
    assert sources.list_sources(root)[0].source_path == path
    assert sources.list_sources(root)[0].status == "available"
    no_save = readonly(area)
    result = index.retrieve(root, "synthetic", task_id=no_save)
    assert result.hits == [] and result.coverage.issues == ((path, status),)
    cache = library_cache_root(root, create=False)
    record = cache / (sources.Source(path).cache_relative + ".json")
    assert json.loads(record.read_bytes())["status"] == status
    assert not record.with_suffix(".txt").exists()
    # A valid terminal record differs from a corrupt pair, which is unavailable.
    record.write_bytes(b"{broken metadata")
    with pytest.raises(index.NoExtractionsError):
        index.retrieve(root, "synthetic", task_id=no_save)


@pytest.mark.parametrize("change", ["delete-cache", "move-work-area"])
def test_registration_survives_cache_loss_or_work_area_move_and_explicit_rebuild(area, tmp_path, change):
    root, task = area
    assert add(area) == 0
    original = (root / REPORT).read_bytes()
    record = sources.registration_path(REPORT)
    registration = (root / record).read_bytes()
    old_cache = library_cache_root(root, create=False)
    no_save = readonly(area)
    if change == "delete-cache":
        shutil.rmtree(old_cache)
    else:
        moved = tmp_path / "moved-area"
        root.rename(moved)
        root = moved
        assert library_cache_root(root, create=False) != old_cache
        assert old_cache.is_dir()
    before = tree(tmp_path)
    assert (root / record).read_bytes() == registration
    assert sources.list_sources(root)[0].status == "available"
    with pytest.raises(index.NoExtractionsError):
        index.retrieve(root, "cobalt", task_id=no_save)
    assert tree(tmp_path) == before
    assert ingest.ingest_library(root, task_id=task).counts["extracted"] == 1
    result = index.retrieve(root, "cobalt", task_id=no_save)
    assert [hit.source_path for hit in result.hits] == [REPORT]
    assert result.coverage.status == "complete"
    assert (root / REPORT).read_bytes() == original
    assert (root / record).read_bytes() == registration


def test_temporarily_unreadable_registered_source_reports_partial_without_deregistering(area, tmp_path, monkeypatch):
    root, _ = area
    assert add(area) == add(area, HEALTHY) == 0
    no_save = readonly(area)
    before = tree(tmp_path)
    original = sources.Catalog.read

    def unavailable(catalog, source, rules=None):
        if source.source_path == REPORT:
            raise sources.SourceUnavailable("unavailable")
        return original(catalog, source, rules=rules)

    monkeypatch.setattr(sources.Catalog, "read", unavailable)
    result = index.retrieve(root, "cobalt", task_id=no_save)
    assert [hit.source_path for hit in result.hits] == [HEALTHY]
    assert result.coverage.issues == ((REPORT, "unavailable"),)
    assert tree(tmp_path) == before
    assert (root / sources.registration_path(REPORT)).is_file()


def test_add_keeps_registration_when_cache_access_is_denied(area, monkeypatch, capsys, tmp_path):
    root, _task = area
    originals = {path: (root / path).read_bytes() for path in (REPORT, HEALTHY)}
    memory_before = tree(root / "Memory")
    home = (tmp_path / "home").resolve()
    original_mkdir = os.mkdir
    denied = []

    def deny_cache(path, *args, **kwargs):
        if Path(path) == home:
            denied.append(path)
            raise PermissionError(errno.EACCES, "synthetic-private-error", "synthetic-private-path")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(os, "mkdir", deny_cache)
    assert add(area) == 1
    output = capsys.readouterr().out
    assert "Registration: added " + REPORT in output
    assert "Registration remains selected; extraction unavailable:" in output
    assert "cache access was denied" in output and "APPARATUS_HOME" in output
    assert "outside the work area" in output
    assert "Card: unavailable; no card was generated." in output
    assert "symbolic link" not in output and "synthetic-private" not in output
    assert len(denied) == 1 and not home.exists()
    assert [item.source_path for item in sources.list_sources(root)] == [REPORT]
    assert {path: (root / path).read_bytes() for path in originals} == originals
    assert tree(root / "Memory") == memory_before
    assert list((root / "Library").iterdir()) == []
