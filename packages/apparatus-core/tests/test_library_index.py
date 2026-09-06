from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sqlite3
import stat
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from apparatus_core.commands import library
from apparatus_core.library import index
from apparatus_core.library.ingest import ingest_library
from apparatus_core.render import render_workspace
from apparatus_core.retention import operation


def _workspace(path: Path) -> Path:
    path.mkdir()
    (path / "AGENTS.md").write_text("# Fixture canon\n", encoding="utf-8")
    (path / "Welcome.md").write_text("Welcome\n", encoding="utf-8")
    for relative in ("Goals", "Decisions", "Projects", "Library", "Deliverables", "Memory/People", "Memory/Facts", "System"):
        (path / relative).mkdir(parents=True, exist_ok=True)
    render_workspace(path)
    return path


def _prepared(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    (workspace / "Library/alpha.txt").write_text("needle alpha phrase", encoding="utf-8")
    (workspace / "Library/beta.txt").write_text("needle beta phrase needle", encoding="utf-8")
    return workspace, ingest_library(workspace).cache


def test_search_builds_ranked_deterministic_json_parity(monkeypatch, tmp_path, capsys):
    workspace, cache = _prepared(monkeypatch, tmp_path)
    index.refresh(cache, workspace)
    first = index.search(cache, "needle")
    second = index.search(cache, "needle")
    assert first == second and first[0].source_path == "Library/beta.txt"
    assert all(math.isfinite(hit.score) for hit in first)
    assert "[needle]" in first[0].snippet
    assert library.run_search(argparse.Namespace(workspace=str(workspace), query="needle", limit=5, as_json=True, rebuild=False)) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload == [{"source_path": hit.source_path, "snippet": hit.snippet, "score": hit.score} for hit in first]
    assert "System/ignore is missing" in captured.err
    assert "skipped 0 path(s)" in captured.err
    assert not (workspace / "index.sqlite3").exists()


def test_refresh_changed_status_stale_and_rebuild(monkeypatch, tmp_path):
    workspace, cache = _prepared(monkeypatch, tmp_path)
    index.refresh(cache, workspace)
    before = {row[0]: row[1:] for row in index._database(cache).execute("SELECT source_path, source_sha256, indexed_at FROM indexed_sources")}
    (workspace / "Library/alpha.txt").write_text("updated content", encoding="utf-8")
    ingest_library(workspace); index.refresh(cache, workspace)
    after = {row[0]: row[1:] for row in index._database(cache).execute("SELECT source_path, source_sha256, indexed_at FROM indexed_sources")}
    assert after["Library/beta.txt"] == before["Library/beta.txt"]
    assert after["Library/alpha.txt"][0] != before["Library/alpha.txt"][0]
    record = cache / "extractions/beta.txt.json"
    data = json.loads(record.read_text(encoding="utf-8")); data["status"] = "unsupported"; data["error"] = "fixture"; data["character_count"] = 0
    record.write_text(json.dumps(data), encoding="utf-8"); record.with_suffix(".txt").unlink()
    index.refresh(cache, workspace)
    assert not index.search(cache, "needle")
    (workspace / "Library/alpha.txt").unlink(); ingest_library(workspace); index.refresh(cache, workspace)
    assert index.search(cache, "updated") == []
    (workspace / "Library/alpha.txt").write_text("restored needle", encoding="utf-8"); ingest_library(workspace)
    index.refresh(cache, workspace); expected = index.search(cache, "needle")
    (cache / "index.sqlite3").unlink()
    index.refresh(cache, workspace)
    assert index.search(cache, "needle") == expected
    index.rebuild(cache, workspace)
    assert index.search(cache, "needle") == expected


def test_search_degraded_query_safety_and_cache_containment(monkeypatch, tmp_path, capsys):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    assert library.run_search(argparse.Namespace(workspace=str(workspace), query="anything", limit=5, as_json=False, rebuild=False)) == 1
    output = capsys.readouterr().out
    assert output.startswith("Nothing from your Library has been ingested yet.")
    assert "System/ignore is missing" in output
    assert library.run(argparse.Namespace(workspace=str(workspace))) == 0
    (workspace / "Library/q.txt").write_text("quoted token", encoding="utf-8"); cache = ingest_library(workspace).cache
    for query in ('"unbalanced', "apostrophe's", "token OR NOT - punctuation"):
        index.refresh(cache, workspace)
        assert isinstance(index.search(cache, query), list)
    outside = tmp_path / "outside"; outside.write_text("sentinel", encoding="utf-8")
    database = cache / "index.sqlite3"; database.unlink(); database.symlink_to(outside)
    with pytest.raises(index.IndexError): index.refresh(cache, workspace)
    assert outside.read_text(encoding="utf-8") == "sentinel"


def test_fts_unavailable_is_honest(monkeypatch, tmp_path, capsys):
    workspace, cache = _prepared(monkeypatch, tmp_path)
    monkeypatch.setattr(index, "_create_schema", lambda _connection: (_ for _ in ()).throw(index.FtsUnavailable("local search is unavailable because this Python does not include SQLite FTS5")))
    assert library.run_search(argparse.Namespace(workspace=str(workspace), query="needle", limit=5, as_json=False, rebuild=False)) == 1
    assert "SQLite FTS5" in capsys.readouterr().out


def test_private_database_rejects_dangling_endpoints_and_sidecars(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    cache = ingest_library(tmp_path / "workspace").cache
    database = cache / "index.sqlite3"
    database.symlink_to(tmp_path / "outside.sqlite3")
    with pytest.raises(index.IndexError): index.refresh(cache, workspace)
    assert not (tmp_path / "outside.sqlite3").exists()
    database.unlink()
    if os.name == "posix":
        prior_umask = os.umask(0o777)
        try:
            index.refresh(cache, workspace)
        finally:
            os.umask(prior_umask)
        assert database.stat().st_mode & 0o777 == 0o600
    else:
        index.refresh(cache, workspace)
    assert not list(cache.glob(".apparatus-index-*"))
    sidecar = Path(str(database) + "-wal")
    sidecar.symlink_to(tmp_path / "outside-wal")
    with pytest.raises(index.IndexError): index.refresh(cache, workspace)
    assert not (tmp_path / "outside-wal").exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX fchmod failure path")
def test_private_database_creation_fchmod_failure_cleans_up_and_retries(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    cache = ingest_library(tmp_path / "workspace").cache
    database = cache / "index.sqlite3"
    original_fchmod = index.os.fchmod
    monkeypatch.setattr(
        index.os,
        "fchmod",
        lambda _fd, _mode: (_ for _ in ()).throw(OSError("injected fchmod failure")),
    )
    prior_umask = os.umask(0o777)
    try:
        with pytest.raises(OSError, match="injected fchmod failure"):
            index._open_database_fd(database)
    finally:
        os.umask(prior_umask)
    assert not database.exists()

    monkeypatch.setattr(index.os, "fchmod", original_fchmod)
    descriptor = index._open_database_fd(database)
    os.close(descriptor)
    assert database.stat().st_mode & 0o777 == 0o600
    index.refresh(cache, workspace)
    assert index.search(cache, "anything") == []


def test_windows_publication_does_not_require_fchmod(monkeypatch, tmp_path):
    workspace, cache = _prepared(monkeypatch, tmp_path)
    monkeypatch.setattr(index, "_is_posix", lambda: False)
    monkeypatch.delattr(index.os, "fchmod", raising=False)
    index.refresh(cache, workspace)
    assert index.search(cache, "needle")[0].source_path == "Library/beta.txt"
    assert (cache / "index.sqlite3").read_bytes()
    assert not list(cache.glob(".apparatus-index-*"))


def test_raw_index_reads_request_windows_binary_mode(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    (tmp_path / "workspace/Library/a.txt").write_text("needle", encoding="utf-8")
    cache = ingest_library(tmp_path / "workspace").cache
    index.refresh(cache, workspace)
    binary = 0x8000
    opened: list[int] = []
    original_open = index.os.open

    def capture_binary_open(path, flags, mode=0o777):
        opened.append(flags)
        return original_open(path, flags & ~binary, mode)

    monkeypatch.setattr(index.os, "O_BINARY", binary, raising=False)
    monkeypatch.setattr(index.os, "open", capture_binary_open)
    assert index._read_database(cache / "index.sqlite3")
    assert index._read_private_file(cache / "extractions/a.txt.json")
    assert all(flags & binary for flags in opened)


def test_rebuild_rolls_back_on_schema_failure(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    source = tmp_path / "workspace/Library/a.txt"; source.write_text("needle", encoding="utf-8")
    cache = ingest_library(tmp_path / "workspace").cache
    index.refresh(cache, workspace)
    expected = index.search(cache, "needle")
    before = (cache / "index.sqlite3").read_bytes()
    original_schema = index._create_schema
    monkeypatch.setattr(index, "_create_schema", lambda _connection: (_ for _ in ()).throw(index.FtsUnavailable("injected")))
    with pytest.raises(index.FtsUnavailable): index.rebuild(cache, workspace)
    monkeypatch.setattr(index, "_create_schema", original_schema)
    assert (cache / "index.sqlite3").read_bytes() == before
    assert index.search(cache, "needle") == expected


def test_rebuild_recovers_corrupt_index_without_reading_old_image(monkeypatch, tmp_path, capsys):
    workspace, cache = _prepared(monkeypatch, tmp_path)
    index.refresh(cache, workspace)
    database = cache / "index.sqlite3"
    database.write_bytes(b"not a sqlite database")
    original_read = index._read_database
    monkeypatch.setattr(
        index,
        "_read_database",
        lambda _path: (_ for _ in ()).throw(AssertionError("rebuild read old database")),
    )
    index.rebuild(cache, workspace)
    monkeypatch.setattr(index, "_read_database", original_read)
    assert index.search(cache, "needle")[0].source_path == "Library/beta.txt"
    assert not list(cache.glob(".apparatus-index-*"))

    database.write_bytes(b"not a sqlite database")
    assert library.run_search(
        argparse.Namespace(
            workspace=str(workspace), query="needle", limit=5, as_json=True, rebuild=True
        )
    ) == 0
    assert json.loads(capsys.readouterr().out)[0]["source_path"] == "Library/beta.txt"


def test_cli_rebuild_keeps_ignored_extractions_out_of_search(monkeypatch, tmp_path, capsys):
    workspace, cache = _prepared(monkeypatch, tmp_path)
    index.refresh(cache, workspace)
    assert index.search(cache, "beta")
    (workspace / "System/ignore").write_text("Library/beta.txt\n", encoding="utf-8")

    assert library.run_search(
        argparse.Namespace(
            workspace=str(workspace), query="beta", limit=5, as_json=True, rebuild=True
        )
    ) == 0

    captured = capsys.readouterr()
    assert json.loads(captured.out) == []
    assert "skipped 1 path(s)" in captured.err
    assert "built-in=0, user=1" in captured.err
    assert index.search(cache, "beta") == []


@pytest.mark.parametrize("rebuild", [False, True])
@pytest.mark.parametrize(
    ("pattern", "expected_skipped"),
    [
        ("Library/private", 1),
        ("/Library/private", 1),
        ("Library/*", 2),
    ],
)
def test_directory_patterns_prune_cache_for_refresh_and_cli_rebuild(
    monkeypatch, tmp_path, capsys, pattern, expected_skipped, rebuild
):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    private = workspace / "Library/private"
    private.mkdir()
    (private / "secret.txt").write_text(
        "cobalt directory sentinel", encoding="utf-8"
    )
    (private / "second.txt").write_text(
        "cobalt second private sentinel", encoding="utf-8"
    )
    (workspace / "Library/visible.txt").write_text(
        "ordinary visible fixture", encoding="utf-8"
    )
    cache = ingest_library(workspace).cache
    index.refresh(cache, workspace)
    assert index.search(cache, "cobalt")
    (workspace / "System/ignore").write_text(f"{pattern}\n", encoding="utf-8")

    private_cache = cache / "extractions/private"
    original_scandir = index.os.scandir
    original_read = index._read_private_file

    def reject_private_directory(path):
        if Path(path) == private_cache:
            raise AssertionError("ignored extraction directory was traversed")
        return original_scandir(path)

    def reject_private_record(path):
        if private_cache in Path(path).parents:
            raise AssertionError("ignored extraction record was opened")
        return original_read(path)

    monkeypatch.setattr(index.os, "scandir", reject_private_directory)
    monkeypatch.setattr(index, "_read_private_file", reject_private_record)

    assert library.run_search(
        argparse.Namespace(
            workspace=str(workspace),
            query="cobalt",
            limit=5,
            as_json=True,
            rebuild=rebuild,
        )
    ) == 0

    captured = capsys.readouterr()
    assert json.loads(captured.out) == []
    assert f"skipped {expected_skipped} path(s)" in captured.err
    assert f"built-in=0, user={expected_skipped}" in captured.err
    assert "System/ignore (1 user pattern(s))" in captured.err
    assert index.search(cache, "cobalt") == []


def test_invalid_ignore_stops_search_before_extraction_reads(monkeypatch, tmp_path, capsys):
    workspace, _cache = _prepared(monkeypatch, tmp_path)
    (workspace / "System/ignore").write_bytes(b"\xff")
    monkeypatch.setattr(
        index,
        "has_extractions",
        lambda *_args: (_ for _ in ()).throw(AssertionError("cache was inspected")),
    )

    assert library.run_search(
        argparse.Namespace(
            workspace=str(workspace), query="needle", limit=5, as_json=False, rebuild=False
        )
    ) == 1
    assert "must be UTF-8 text" in capsys.readouterr().out


def test_corrupt_index_is_a_stable_cli_error(monkeypatch, tmp_path, capsys):
    workspace, cache = _prepared(monkeypatch, tmp_path)
    index.refresh(cache, workspace)
    (cache / "index.sqlite3").write_bytes(b"not a sqlite database")
    assert library.run_search(
        argparse.Namespace(
            workspace=str(workspace), query="needle", limit=5, as_json=False, rebuild=False
        )
    ) == 2
    assert capsys.readouterr().out == "library search: Library index could not be opened\n"


@pytest.mark.skipif(os.name != "posix", reason="legacy retained-fd rebuild path")
def test_legacy_rebuild_recovers_corruption_and_rolls_back_valid_old_index(monkeypatch, tmp_path):
    workspace, cache = _prepared(monkeypatch, tmp_path)
    monkeypatch.setattr(index.sqlite3, "Connection", type("LegacyConnection", (), {}))
    index.refresh(cache, workspace)
    expected = index.search(cache, "needle")
    database = cache / "index.sqlite3"
    database.write_bytes(b"not a sqlite database")
    index.rebuild(cache, workspace)
    assert index.search(cache, "needle") == expected

    prior = database.read_bytes()
    original_schema = index._create_schema
    monkeypatch.setattr(
        index,
        "_create_schema",
        lambda _connection: (_ for _ in ()).throw(index.FtsUnavailable("injected")),
    )
    with pytest.raises(index.FtsUnavailable):
        index.rebuild(cache, workspace)
    monkeypatch.setattr(index, "_create_schema", original_schema)
    assert database.read_bytes() == prior
    assert index.search(cache, "needle") == expected


@pytest.mark.skipif(os.name != "posix", reason="legacy retained-fd rebuild path")
def test_legacy_rebuild_recovers_later_wrapped_corruption(monkeypatch, tmp_path):
    workspace, cache = _prepared(monkeypatch, tmp_path)
    monkeypatch.setattr(index.sqlite3, "Connection", type("LegacyConnection", (), {}))
    index.refresh(cache, workspace)
    original_schema = index._create_schema
    calls = [0]

    def wrapped_corruption(connection):
        calls[0] += 1
        if calls[0] == 1:
            try:
                raise sqlite3.DatabaseError("database disk image is malformed")
            except sqlite3.DatabaseError as error:
                raise index.IndexError("Library index could not be prepared") from error
        return original_schema(connection)

    monkeypatch.setattr(index, "_create_schema", wrapped_corruption)
    index.rebuild(cache, workspace)
    assert index.search(cache, "needle")[0].source_path == "Library/beta.txt"


@pytest.mark.skipif(os.name != "posix", reason="legacy retained-fd rebuild path")
def test_legacy_rebuild_closes_second_corruption_carrier(monkeypatch, tmp_path):
    workspace, cache = _prepared(monkeypatch, tmp_path)
    monkeypatch.setattr(index.sqlite3, "Connection", type("LegacyConnection", (), {}))
    index.refresh(cache, workspace)
    (cache / "index.sqlite3").write_bytes(b"not a sqlite database")
    original_database = index._database
    calls = [0]

    def second_corrupt_database(path):
        calls[0] += 1
        connection = original_database(path)
        if calls[0] == 2:
            raise index._CorruptDatabaseError(connection)
        return connection

    baseline_fds = dict(index._DATABASE_FDS)
    baseline_handles = dict(index._DATABASE_HANDLES)
    monkeypatch.setattr(index, "_database", second_corrupt_database)
    with pytest.raises(index.IndexError, match="could not be rebuilt"):
        index.rebuild(cache, workspace)
    assert index._DATABASE_FDS == baseline_fds
    assert index._DATABASE_HANDLES == baseline_handles


@pytest.mark.skipif(os.name != "posix", reason="descriptor-relative cleanup path")
def test_legacy_corrupt_cleanup_preserves_substituted_endpoints(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    (tmp_path / "workspace/Library/a.txt").write_text("needle", encoding="utf-8")
    cache = ingest_library(tmp_path / "workspace").cache
    monkeypatch.setattr(index.sqlite3, "Connection", type("LegacyConnection", (), {}))
    index.refresh(cache, workspace)
    database = cache / "index.sqlite3"
    outside = tmp_path / "outside.sqlite3"
    outside.write_bytes(b"sentinel")
    os.chmod(outside, 0o600)
    database.write_bytes(b"not a sqlite database")
    original_exchange = index.fs_transactions.exchange_names
    exchanges = [0]

    def substitute(parent, first, second):
        if exchanges[0] == 0:
            database.unlink()
            os.link(outside, database)
        exchanges[0] += 1
        original_exchange(parent, first, second)

    baseline_fds = dict(index._DATABASE_FDS)
    baseline_handles = dict(index._DATABASE_HANDLES)
    monkeypatch.setattr(index.fs_transactions, "exchange_names", substitute)
    with pytest.raises(index.IndexError):
        index.rebuild(cache, workspace)
    assert outside.read_bytes() == b"sentinel"
    assert database.read_bytes() == b"sentinel"
    assert index._DATABASE_FDS == baseline_fds
    assert index._DATABASE_HANDLES == baseline_handles


@pytest.mark.skipif(os.name != "posix", reason="exchange quarantine rollback path")
def test_legacy_quarantine_stat_failure_restores_corrupt_index(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    (tmp_path / "workspace/Library/a.txt").write_text("needle", encoding="utf-8")
    cache = ingest_library(tmp_path / "workspace").cache
    monkeypatch.setattr(index.sqlite3, "Connection", type("LegacyConnection", (), {}))
    index.refresh(cache, workspace)
    database = cache / "index.sqlite3"
    corrupt = b"corrupt"
    database.write_bytes(corrupt)
    original_stat = index.os.stat
    failures = [0]

    def fail_first_quarantine_stat(path, *args, **kwargs):
        if str(path).startswith(".apparatus-index-quarantine-") and failures[0] == 0:
            failures[0] += 1
            raise OSError("injected quarantine stat failure")
        return original_stat(path, *args, **kwargs)

    baseline_fds = dict(index._DATABASE_FDS)
    baseline_handles = dict(index._DATABASE_HANDLES)
    with operation(workspace):
        monkeypatch.setattr(index.os, "stat", fail_first_quarantine_stat)
        with pytest.raises(index.IndexError):
            index.rebuild(cache, workspace)
        assert database.read_bytes() == corrupt
        assert not list(cache.glob(".apparatus-index-quarantine-*"))
        assert index._DATABASE_FDS == baseline_fds
        assert index._DATABASE_HANDLES == baseline_handles
        monkeypatch.setattr(index.os, "stat", original_stat)
        index.rebuild(cache, workspace)
        assert index.search(cache, "needle")[0].source_path == "Library/a.txt"


def test_windows_corrupt_cleanup_closes_alias_before_exact_handle_delete(monkeypatch, tmp_path):
    events: list[str] = []

    class Connection:
        def close(self):
            events.append("connection-close")

    connection = Connection()
    index._DATABASE_HANDLES[id(connection)] = 17
    monkeypatch.setattr(index, "_is_windows", lambda: True)
    monkeypatch.setattr(
        index.fs_transactions,
        "_win_delete_handle",
        lambda handle: events.append(f"delete-{handle}"),
    )
    monkeypatch.setattr(
        index.fs_transactions,
        "_win_close",
        lambda handle: events.append(f"handle-close-{handle}"),
    )
    index._discard_corrupt_database(tmp_path, connection)  # type: ignore[arg-type]
    assert events == ["connection-close", "delete-17", "handle-close-17"]
    assert id(connection) not in index._DATABASE_HANDLES


def test_index_connect_record_endpoints_and_sidecar_races_fail_closed(monkeypatch, tmp_path):
    workspace, cache = _prepared(monkeypatch, tmp_path)
    index.refresh(cache, workspace)
    database = cache / "index.sqlite3"; outside = tmp_path / "outside-db"
    if hasattr(sqlite3.Connection, "deserialize"):
        original_read = index._read_database
        def swap_database(path):
            content = original_read(path)
            database.unlink(); database.symlink_to(outside)
            return content
        monkeypatch.setattr(index, "_read_database", swap_database)
    else:
        original_open = index._open_database_fd
        def swap_database(path):
            descriptor = original_open(path)
            database.unlink(); database.symlink_to(outside)
            return descriptor
        monkeypatch.setattr(index, "_open_database_fd", swap_database)
    with pytest.raises(index.IndexError): index.refresh(cache, workspace)
    assert not outside.exists()
    if hasattr(sqlite3.Connection, "deserialize"):
        monkeypatch.setattr(index, "_read_database", original_read)
    else:
        monkeypatch.setattr(index, "_open_database_fd", original_open)
    database.unlink()
    index.refresh(cache, workspace)
    record = cache / "extractions/alpha.txt.json"; external_record = tmp_path / "external-record.json"; external_record.write_bytes(record.read_bytes())
    record.unlink(); os.link(external_record, record)
    with pytest.raises(index.IndexError): index.refresh(cache, workspace)
    assert external_record.read_bytes()
    record.unlink()
    if os.name == "posix":
        os.mkfifo(record)
        with pytest.raises(index.IndexError): index.refresh(cache, workspace)
        record.unlink()
    original_replaceable = index._assert_replaceable_database
    sidecar = Path(str(database) + "-journal"); external_sidecar = tmp_path / "external-journal"
    def inject_sidecar(path):
        sidecar.symlink_to(external_sidecar)
        return original_replaceable(path)
    monkeypatch.setattr(index, "_assert_replaceable_database", inject_sidecar)
    with pytest.raises(index.IndexError): index.refresh(cache, workspace)
    assert not external_sidecar.exists()


def test_concurrent_refresh_rebuild_and_search_keep_a_usable_snapshot(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    (tmp_path / "workspace/Library/a.txt").write_text("needle", encoding="utf-8")
    cache = ingest_library(tmp_path / "workspace").cache
    index.refresh(cache, workspace)
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(index.refresh, cache, workspace),
            executor.submit(index.rebuild, cache, workspace),
            executor.submit(index.search, cache, "needle"),
        ]
        for future in futures:
            future.result()
    assert index.search(cache, "needle")[0].source_path == "Library/a.txt"


def test_legacy_windows_uses_retained_name_lock_and_closes_it(monkeypatch, tmp_path):
    workspace, cache = _prepared(monkeypatch, tmp_path)
    monkeypatch.setattr(index.sqlite3, "Connection", type("LegacyConnection", (), {}))
    monkeypatch.setattr(index, "_legacy_windows_unavailable", lambda: True)
    closed = []
    connection = sqlite3.connect(":memory:")
    monkeypatch.setattr(index, "_windows_legacy_connection", lambda _path: connection)
    original_close = index._close_database
    monkeypatch.setattr(index, "_close_database", lambda value: (closed.append(value), original_close(value))[1])
    index.refresh(cache, workspace)
    assert closed == [connection]


def test_writer_lock_serializes_stale_snapshots_and_cleans_up(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    source = tmp_path / "workspace/Library/a.txt"; source.write_text("old needle", encoding="utf-8")
    cache = ingest_library(tmp_path / "workspace").cache
    entered = threading.Event(); release = threading.Event(); original_sources = index._extracted_sources
    calls = [0]
    def pause_first(path, rules):
        value = original_sources(path, rules)
        calls[0] += 1
        if calls[0] == 1:
            entered.set(); assert release.wait(5)
        return value
    monkeypatch.setattr(index, "_extracted_sources", pause_first)
    first = threading.Thread(target=index.refresh, args=(cache, workspace)); first.start(); assert entered.wait(5)
    source.write_text("current needle", encoding="utf-8"); ingest_library(tmp_path / "workspace")
    second = threading.Thread(target=index.refresh, args=(cache, workspace)); second.start()
    release.set(); first.join(5); second.join(5)
    assert not first.is_alive() and not second.is_alive()
    assert "current" in index.search(cache, "current")[0].snippet
    assert not (cache / ".apparatus-index.lock").exists()
    outside = tmp_path / "outside-lock"; lock = cache / ".apparatus-index.lock"; lock.symlink_to(outside)
    with pytest.raises(index.IndexError): index.refresh(cache, workspace)
    assert not outside.exists()


def test_windows_writer_lock_rejects_reparse_endpoint(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    cache = ingest_library(tmp_path / "workspace").cache
    lock = cache / ".apparatus-index.lock"
    lock.symlink_to(tmp_path / "outside-lock")
    monkeypatch.setattr(index, "_is_windows", lambda: True)
    monkeypatch.setattr(index, "_is_posix", lambda: False)
    monkeypatch.setattr(
        index.fs_transactions,
        "_win_open",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(FileExistsError()),
    )
    monkeypatch.setattr(index.time, "sleep", lambda _seconds: pytest.fail("reparse endpoint must not retry"))
    with pytest.raises(index.IndexError, match="writer lock is not private"):
        with index._windows_writer_lock(lock):
            pass


def test_windows_writer_lock_retries_only_transient_regular_metadata(monkeypatch, tmp_path):
    lock = tmp_path / ".apparatus-index.lock"
    statuses = [
        os.stat_result((stat.S_IFREG, 0, 0, 0, 0, 0, 0, 0, 0, 0)),
        os.stat_result((stat.S_IFREG, 0, 0, 1, 0, 0, 0, 0, 0, 0)),
    ]
    opens = [FileExistsError(), 101]
    sleeps = []
    deletes = []
    def win_open(*_args, **_kwargs):
        result = opens.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(index.fs_transactions, "_win_open", win_open)
    monkeypatch.setattr(index.os, "lstat", lambda _path: statuses.pop(0))
    monkeypatch.setattr(index, "_is_posix", lambda: False)
    monkeypatch.setattr(index, "is_reparse_path", lambda _path: False)
    monkeypatch.setattr(index.time, "sleep", sleeps.append)
    monkeypatch.setattr(index.fs_transactions, "_win_delete_handle", deletes.append)
    monkeypatch.setattr(index.fs_transactions, "_win_close", lambda _handle: None)

    with index._windows_writer_lock(lock):
        pass

    assert sleeps == [0.01]
    assert deletes == [101]


def test_windows_writer_lock_rejects_persistent_unsafe_regular_metadata(monkeypatch, tmp_path):
    lock = tmp_path / ".apparatus-index.lock"
    unsafe = os.stat_result((stat.S_IFREG, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    sleeps = []
    monkeypatch.setattr(
        index.fs_transactions,
        "_win_open",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(FileExistsError()),
    )
    monkeypatch.setattr(index.os, "lstat", lambda _path: unsafe)
    monkeypatch.setattr(index, "_is_posix", lambda: False)
    monkeypatch.setattr(index, "is_reparse_path", lambda _path: False)
    monkeypatch.setattr(index.time, "sleep", sleeps.append)

    with pytest.raises(index.IndexError, match="writer lock is not private"):
        with index._windows_writer_lock(lock):
            pass

    assert sleeps == [0.01, 0.01]


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode bits are required for this regression")
def test_writer_lock_repairs_restrictive_umask_and_cleans_up_failed_acquisition(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    (tmp_path / "workspace/Library/a.txt").write_text("needle", encoding="utf-8")
    cache = ingest_library(tmp_path / "workspace").cache
    lock = cache / ".apparatus-index.lock"

    prior_umask = os.umask(0o777)
    try:
        with index._writer_lock(cache):
            assert lock.stat().st_mode & 0o777 == 0o600
    finally:
        os.umask(prior_umask)
    assert not lock.exists()

    original_fchmod = index.os.fchmod
    monkeypatch.setattr(index.os, "fchmod", lambda _fd, _mode: (_ for _ in ()).throw(OSError("injected fchmod failure")))
    with pytest.raises(OSError, match="injected fchmod failure"):
        index.refresh(cache, workspace)
    assert not lock.exists()

    monkeypatch.setattr(index.os, "fchmod", original_fchmod)
    index.refresh(cache, workspace)
    assert index.search(cache, "needle")[0].source_path == "Library/a.txt"
    assert not lock.exists()
