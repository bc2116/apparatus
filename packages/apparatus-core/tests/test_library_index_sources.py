"""Direct index writers use the same selected-source proofs as retrieval."""
from __future__ import annotations

import os

import pytest

from apparatus_core.library import index, ingest, sources
from apparatus_core.retention import RetentionSuppressed, start_task


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    root = (tmp_path / "area").resolve()
    for directory in ("System", "Library", "project"):
        (root / directory).mkdir(parents=True)
    (root / "System/profile.yaml").write_text(
        "schema: apparatus/profile@v0\nstatus: configured\nprivacy_mode: standard\n"
        "work_types: []\nreview_day: null\n", encoding="utf-8")
    for name in ("selected", "healthy"):
        path = f"project/{name}.txt"
        (root / path).write_text(f"Cobalt {name} evidence", encoding="utf-8")
        sources.register_source(root, path)
    cache = ingest.ingest_library(root).cache
    return root, cache


@pytest.mark.parametrize("writer", [index.refresh, index.rebuild])
@pytest.mark.parametrize("change", ["stale", "unregistered", "ignored"])
def test_direct_writer_keeps_selected_rows_and_excludes_ineligible_evidence(prepared, writer, change):
    root, cache = prepared
    writer(cache, root)
    assert {hit.source_path for hit in index.search(cache, "cobalt")} == {
        "project/selected.txt", "project/healthy.txt"}
    selected = root / "project/selected.txt"
    if change == "stale":
        previous = selected.stat()
        selected.write_bytes(selected.read_bytes().replace(b"Cobalt", b"Zircon"))
        os.utime(selected, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    elif change == "unregistered":
        sources.unregister_source(root, "project/selected.txt")
    else:
        (root / "System/ignore").write_text("project/selected.txt\n", encoding="utf-8")
    writer(cache, root)
    assert [hit.source_path for hit in index.search(cache, "cobalt")] == ["project/healthy.txt"]
    assert index.search(cache, "zircon") == []
    assert not (cache / ".apparatus-index.lock").exists()


@pytest.mark.parametrize("writer", [index.refresh, index.rebuild])
def test_default_writer_cannot_bypass_no_save(prepared, writer):
    root, cache = prepared
    task = start_task(root, save_memory=False)
    before = {p.relative_to(cache): p.read_bytes() for p in cache.rglob("*") if p.is_file()}
    with pytest.raises(RetentionSuppressed):
        writer(cache, root, task_id=task.task_id)
    assert {p.relative_to(cache): p.read_bytes() for p in cache.rglob("*") if p.is_file()} == before
    writer(cache, root, task_id=task.task_id, requested=True)
    assert len(index.search(cache, "cobalt")) == 2


@pytest.mark.parametrize("writer", [index.refresh, index.rebuild])
def test_explicit_empty_cache_index_remains_supported(prepared, tmp_path, writer):
    root, _ = prepared
    empty = tmp_path / "empty-cache"
    empty.mkdir(mode=0o700)
    writer(empty, root)
    assert index.search(empty, "cobalt") == []
    assert (empty / "index.sqlite3").is_file()
    assert not (empty / ".apparatus-index.lock").exists()


@pytest.mark.parametrize("writer", [index.refresh, index.rebuild])
def test_default_writer_retains_source_proofs_through_database_publication(prepared, monkeypatch, writer):
    import errno

    root, cache = prepared
    source = root / "project/selected.txt"
    before = source.read_bytes()
    changed = before.replace(b"Cobalt", b"Zircon")
    publish = index._publish_database
    outcomes = []

    def mutate_after_publication(*args, **kwargs):
        publish(*args, **kwargs)
        try:
            count = source.write_bytes(changed)
        except PermissionError as error:
            assert os.name == "nt" and error.errno == errno.EACCES
            outcomes.append("blocked")
        else:
            assert count == len(changed)
            outcomes.append("written")

    monkeypatch.setattr(index, "_publish_database", mutate_after_publication)
    try:
        writer(cache, root)
    except sources.SourceUnavailable:
        assert outcomes == ["written"]
    else:
        assert outcomes == ["blocked"], "A source changed after publication but the writer accepted stale evidence"
    assert source.read_bytes() == (changed if outcomes == ["written"] else before)
    assert not (cache / ".apparatus-index.lock").exists()
