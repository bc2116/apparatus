from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from apparatus_core import recall
from apparatus_core.cache import library_cache_root
from apparatus_core.commands import library as library_command
from apparatus_core.commands import recall as recall_command
from apparatus_core.library import index
from apparatus_core.library.ingest import ingest_library
from apparatus_core.retention import (
    RetentionSuppressed, TaskRetentionError, context_for, operation, start_task,
)


def _workspace(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    (workspace / "Library").mkdir(parents=True)
    (workspace / "System").mkdir()
    (workspace / "System/profile.yaml").write_text(
        "schema: apparatus/profile@v0\nstatus: configured\nprivacy_mode: standard\n"
        "work_types: []\nreview_day: null\n", encoding="utf-8",
    )
    (workspace / "Library/source.txt").write_text("cobalt synthetic task evidence", encoding="utf-8")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    return workspace


def _tree(root: Path):
    return {
        path.relative_to(root).as_posix(): None if path.is_dir() else path.read_bytes()
        for path in root.rglob("*")
    }


def _forbidden(*_args, **_kwargs):
    raise AssertionError("read-only retrieval attempted durable cache work")


@pytest.mark.parametrize("legacy_sqlite", [False, True])
def test_no_save_retrieval_uses_extractions_without_any_persistence(tmp_path, monkeypatch, legacy_sqlite):
    workspace = _workspace(tmp_path, monkeypatch)
    ingest_library(workspace)
    task = start_task(workspace, save_memory=False)
    if legacy_sqlite:
        monkeypatch.setattr(index.sqlite3, "Connection", type("LegacyConnection", (), {}))
    for symbol in ("_database", "_database_for_operation", "_writer_lock", "_publish_database"):
        monkeypatch.setattr(index, symbol, _forbidden)
    before = _tree(tmp_path)
    hits, _report = index.retrieve(workspace, "cobalt", task_id=task.task_id)
    assert hits[0].source_path == "Library/source.txt"
    envelope = recall.recall(workspace, "cobalt", task_id=task.task_id, write=_forbidden)
    assert envelope["status"] == "grounded"
    assert "synthetic" in envelope["evidence"][0]["snippet"]
    assert _tree(tmp_path) == before


def test_missing_cache_is_unavailable_and_creates_nothing(tmp_path, monkeypatch, capsys):
    workspace = _workspace(tmp_path, monkeypatch)
    task = start_task(workspace, save_memory=False)
    before = _tree(tmp_path)
    assert not library_cache_root(workspace, create=False).exists()
    with pytest.raises(index.NoExtractionsError):
        recall.recall(workspace, "cobalt", task_id=task.task_id)
    assert recall_command.run(argparse.Namespace(
        workspace=str(workspace), question="cobalt", task=task.task_id,
        limit=5, as_json=False,
    )) == 1
    assert "unavailable" in capsys.readouterr().out
    assert _tree(tmp_path) == before


@pytest.mark.parametrize("damage", ["json", "missing-text", "invalid-text"])
def test_invalid_existing_evidence_is_unavailable_without_repair(tmp_path, monkeypatch, damage):
    workspace = _workspace(tmp_path, monkeypatch)
    cache = ingest_library(workspace).cache
    task = start_task(workspace, save_memory=False)
    if damage == "json":
        (cache / "extractions/source.txt.json").write_bytes(b"not json")
    elif damage == "missing-text":
        (cache / "extractions/source.txt.txt").unlink()
    else:
        (cache / "extractions/source.txt.txt").write_bytes(b"\xff")
    before = _tree(tmp_path)
    with pytest.raises(index.NoExtractionsError):
        index.retrieve(workspace, "cobalt", task_id=task.task_id)
    assert _tree(tmp_path) == before


def test_no_save_read_obeys_current_ignore_without_rewriting_old_index(tmp_path, monkeypatch):
    workspace = _workspace(tmp_path, monkeypatch)
    cache = ingest_library(workspace).cache
    index.refresh(cache, workspace)
    task = start_task(workspace, save_memory=False)
    (workspace / "System/ignore").write_text("Library/source.txt\n", encoding="utf-8")
    before = _tree(tmp_path)
    hits, report = index.retrieve(workspace, "cobalt", task_id=task.task_id)
    assert hits == []
    assert report.skipped_paths == 1
    assert _tree(tmp_path) == before


def test_engine_writes_require_task_and_explicit_library_exception(tmp_path, monkeypatch):
    workspace = _workspace(tmp_path, monkeypatch)
    cache = ingest_library(workspace).cache
    task = start_task(workspace, save_memory=False)
    before = _tree(tmp_path)
    for writer in (
        lambda **kwargs: ingest_library(workspace, **kwargs),
        lambda **kwargs: index.refresh(cache, workspace, **kwargs),
        lambda **kwargs: index.rebuild(cache, workspace, **kwargs),
    ):
        with pytest.raises(TaskRetentionError):
            writer()
        with pytest.raises(RetentionSuppressed):
            writer(task_id=task.task_id)
    assert _tree(tmp_path) == before
    with operation(workspace, task_id=task.task_id, requested=("library",)):
        ingest_library(workspace)
        with pytest.raises(RetentionSuppressed):
            context_for(workspace).require_memory_write()
    with pytest.raises(RetentionSuppressed):
        ingest_library(workspace, task_id=task.task_id)
    index.retrieve(workspace, "cobalt", task_id=task.task_id, rebuild_index=True, requested=True)
    assert (cache / "index.sqlite3").is_file()


def test_requested_ingest_is_scoped_and_invalid_task_never_creates_cache(tmp_path, monkeypatch):
    workspace = _workspace(tmp_path, monkeypatch)
    task = start_task(workspace, save_memory=False)
    before = _tree(tmp_path)
    with pytest.raises(TaskRetentionError):
        ingest_library(workspace, task_id="not-a-task", requested=True)
    assert _tree(tmp_path) == before
    result = ingest_library(workspace, task_id=task.task_id, requested=True)
    assert result.counts["extracted"] == 1
    assert not context_for(workspace, task_id=task.task_id).save_memory
    assert (result.cache / "extractions/source.txt.txt").is_file()


@pytest.mark.parametrize("legacy_sqlite", [False, True])
def test_low_level_search_cannot_create_or_modify_durable_index(tmp_path, monkeypatch, legacy_sqlite):
    workspace = _workspace(tmp_path, monkeypatch)
    cache = ingest_library(workspace).cache
    index.refresh(cache, workspace)
    if legacy_sqlite:
        monkeypatch.setattr(index.sqlite3, "Connection", type("LegacyConnection", (), {}))
    before = _tree(tmp_path)
    assert index.search(cache, "cobalt")
    assert _tree(tmp_path) == before
    (cache / "index.sqlite3").unlink()
    before = _tree(tmp_path)
    with pytest.raises(index.IndexError):
        index.search(cache, "cobalt")
    assert _tree(tmp_path) == before


def test_cli_read_paths_share_no_save_behavior(tmp_path, monkeypatch, capsys):
    workspace = _workspace(tmp_path, monkeypatch)
    ingest_library(workspace)
    task = start_task(workspace, save_memory=False)
    before = _tree(tmp_path)
    assert library_command.run_search(argparse.Namespace(
        workspace=str(workspace), query="cobalt", task=task.task_id,
        limit=5, as_json=True, rebuild=False,
    )) == 0
    assert json.loads(capsys.readouterr().out)["hits"][0]["source_path"] == "Library/source.txt"
    assert recall_command.run(argparse.Namespace(
        workspace=str(workspace), question="cobalt", task=task.task_id,
        limit=5, as_json=True,
    )) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "grounded"
    assert _tree(tmp_path) == before


@pytest.mark.parametrize(("filename", "content", "status"), [
    ("empty.txt", b"", "no_text"),
    ("unsupported.bin", b"synthetic unsupported source", "unsupported"),
    ("invalid.docx", b"not a document archive", "error"),
])
def test_valid_terminal_extractions_do_not_hide_available_evidence(
    tmp_path, monkeypatch, filename, content, status
):
    workspace = _workspace(tmp_path, monkeypatch)
    (workspace / "Library" / filename).write_bytes(content)
    ingested = ingest_library(workspace)
    assert ingested.counts[status] == 1
    task = start_task(workspace, save_memory=False)
    before = _tree(tmp_path)
    hits, _ = index.retrieve(workspace, "cobalt", task_id=task.task_id)
    assert [hit.source_path for hit in hits] == ["Library/source.txt"]
    envelope = recall.recall(workspace, "cobalt", task_id=task.task_id, write=_forbidden)
    assert envelope["status"] == "grounded"
    assert _tree(tmp_path) == before


@pytest.mark.parametrize("damage", ["timestamp", "missing-field", "invalid-type", "unexpected-text"])
def test_terminal_extraction_requires_valid_metadata_and_no_text_pair(tmp_path, monkeypatch, damage):
    workspace = _workspace(tmp_path, monkeypatch)
    (workspace / "Library/empty.txt").write_bytes(b"")
    cache = ingest_library(workspace).cache
    record_path = cache / "extractions/empty.txt.json"
    metadata = json.loads(record_path.read_text())
    if damage == "timestamp":
        metadata["timestamp"] = "invalid"
    elif damage == "missing-field":
        del metadata["size_bytes"]
    elif damage == "invalid-type":
        metadata["extractor"] = ["utf-8"]
    else:
        (cache / "extractions/empty.txt.txt").write_bytes(b"unexpected cached text")
    record_path.write_text(json.dumps(metadata))
    task = start_task(workspace, save_memory=False)
    before = _tree(tmp_path)
    result = index.retrieve(workspace, "cobalt", task_id=task.task_id)
    assert [hit.source_path for hit in result.hits] == ["Library/source.txt"]
    assert result.coverage.issues == (("Library/empty.txt", "invalid_cache"),)
    assert _tree(tmp_path) == before


def test_extractions_disappearing_after_preflight_are_unavailable_without_writes(tmp_path, monkeypatch):
    workspace = _workspace(tmp_path, monkeypatch)
    cache = ingest_library(workspace).cache
    task = start_task(workspace, save_memory=False)
    has_extractions = index.has_extractions
    after_disappearance = {}
    def disappear_after_preflight(candidate_cache, rules):
        assert has_extractions(candidate_cache, rules)
        (cache / "extractions").rename(tmp_path / "moved-extractions")
        after_disappearance.update(_tree(tmp_path))
        return True
    monkeypatch.setattr(index, "has_extractions", disappear_after_preflight)
    monkeypatch.setattr(index, "_fresh_database", _forbidden)
    with pytest.raises(index.NoExtractionsError) as error:
        index.retrieve(workspace, "cobalt", task_id=task.task_id)
    assert error.value.readonly is True
    assert _tree(tmp_path) == after_disappearance
