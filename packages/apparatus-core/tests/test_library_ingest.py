from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import os
import stat
import sys
from types import SimpleNamespace

import pytest

from apparatus_core.check import check_workspace
from apparatus_core.commands import library
from apparatus_core.library.ingest import IngestResult, _safe, ingest_library
from apparatus_core.library import index
from apparatus_core import recall
import apparatus_core.library.ingest as ingest_module
from apparatus_core.cache import library_cache_root
import apparatus_core.cache as cache_module
from apparatus_core.render import render_workspace
from .fixture_docs import write_docx, write_pdf


def _workspace(path: Path) -> Path:
    path.mkdir()
    (path / "AGENTS.md").write_text("# Fixture canon\n", encoding="utf-8")
    (path / "Welcome.md").write_text("Welcome\n", encoding="utf-8")
    for relative in ("Goals", "Decisions", "Projects", "Library", "Deliverables", "Memory/People", "Memory/Facts", "System"):
        (path / relative).mkdir(parents=True, exist_ok=True)
    render_workspace(path)
    return path


def _record(cache: Path, relative: str) -> dict:
    return json.loads((cache / "extractions" / (relative + ".json")).read_text(encoding="utf-8"))


def test_ingest_extracts_supported_documents_to_derived_cache(monkeypatch, tmp_path, capsys):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "apparatus-home"))
    library_dir = workspace / "Library"
    (library_dir / "note.md").write_text("markdown phrase", encoding="utf-8")
    (library_dir / "note.txt").write_text("text phrase", encoding="utf-8")
    write_docx(library_dir / "note.docx", "docx phrase")
    write_pdf(library_dir / "note.pdf", "pdf phrase")

    result = ingest_library(workspace)
    assert result.ok and result.counts["extracted"] == 4
    assert result.cache.is_relative_to(tmp_path / "apparatus-home")
    assert not result.cache.is_relative_to(workspace)
    for relative, phrase in (("note.md", "markdown phrase"), ("note.txt", "text phrase"), ("note.docx", "docx phrase"), ("note.pdf", "pdf phrase")):
        assert phrase in (result.cache / "extractions" / (relative + ".txt")).read_text(encoding="utf-8")
        record = _record(result.cache, relative)
        assert record["status"] == "extracted" and len(record["source_sha256"]) == 64
    assert check_workspace(workspace).ok
    assert library.run(argparse.Namespace(workspace=str(workspace))) == 0
    assert "Library cache:" in capsys.readouterr().out


def test_ingest_is_incremental_and_deletes_stale_cache_pairs(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "apparatus-home"))
    source = workspace / "Library" / "note.txt"
    source.write_text("first", encoding="utf-8")
    first = ingest_library(workspace)
    record_path = first.cache / "extractions" / "note.txt.json"
    initial = record_path.read_bytes()
    first_hash = _record(first.cache, "note.txt")["source_sha256"]
    second = ingest_library(workspace)
    assert second.counts["unchanged"] == 1 and record_path.read_bytes() == initial
    source.write_text("second", encoding="utf-8")
    third = ingest_library(workspace)
    assert third.counts["extracted"] == 1
    assert _record(third.cache, "note.txt")["source_sha256"] != first_hash
    source.unlink()
    ingest_library(workspace)
    assert not record_path.exists() and not record_path.with_suffix(".txt").exists()
    source.write_text("rebuilt", encoding="utf-8")
    shutil.rmtree(third.cache)
    rebuilt = ingest_library(workspace)
    assert rebuilt.counts["extracted"] == 1
    assert (rebuilt.cache / "extractions" / "note.txt.txt").read_text(encoding="utf-8") == "rebuilt"


def test_ignore_skips_source_before_open_and_evicts_index_and_recall(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "apparatus-home"))
    source = workspace / "Library/private.txt"
    source.write_text("cobalt sentinel phrase", encoding="utf-8")
    (workspace / "Library/visible.txt").write_text("ordinary fixture phrase", encoding="utf-8")
    first = ingest_library(workspace)
    index.refresh(first.cache, workspace)
    assert recall.recall(workspace, "cobalt sentinel")["status"] == "grounded"
    (workspace / "System/ignore").write_text("Library/private.txt\n", encoding="utf-8")

    original_read = ingest_module._read_source

    def fail_if_opened(path, *args, **kwargs):
        if Path(path) == source:
            raise AssertionError("an ignored Library source was opened")
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(ingest_module, "_read_source", fail_if_opened)
    result = ingest_library(workspace)
    assert result.counts["ignored"] == 1
    assert not (result.cache / "extractions/private.txt.json").exists()
    index.refresh(result.cache, workspace)
    assert index.search(result.cache, "cobalt") == []
    assert recall.recall(workspace, "cobalt sentinel")["status"] == "abstained"
    receipts = (workspace / "System/receipts").glob("*-library-ingest*.md")
    assert any("ignored=1" in receipt.read_text(encoding="utf-8") for receipt in receipts)


def test_ingest_flags_unsupported_and_corrupt_sources_and_command_exits_one(monkeypatch, tmp_path, capsys):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "apparatus-home"))
    (workspace / "Library" / "image.png").write_bytes(b"not an image")
    (workspace / "Library" / "broken.docx").write_bytes(b"not a docx")
    result = ingest_library(workspace)
    assert {status for _path, status, _reason in result.flagged} == {"unsupported", "error"}
    receipt = next((workspace / "System/receipts").glob("*-library-ingest.md"))
    assert "image.png: unsupported" in receipt.read_text(encoding="utf-8")
    assert library.run(argparse.Namespace(workspace=str(workspace))) == 1
    assert "flagged" in capsys.readouterr().out


def test_hostile_paths_and_cache_targets_do_not_escape(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(workspace / "inside"))
    with pytest.raises(ValueError): ingest_library(workspace)
    outside = tmp_path / "outside.txt"; outside.write_text("sentinel")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    (workspace / "Library" / "link.txt").symlink_to(outside)
    result = ingest_library(workspace)
    assert result.counts["error"] == 1 and outside.read_text() == "sentinel"
    source = workspace / "Library" / "safe.txt"; source.write_text("safe")
    result = ingest_library(workspace)
    cache = result.cache; target = cache / "extractions" / "safe.txt.json"
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(ValueError): ingest_library(workspace)
    assert outside.read_text() == "sentinel"


def test_typed_pairs_safe_errors_and_stale_orphans(monkeypatch, tmp_path, capsys):
    workspace = _workspace(tmp_path / "workspace"); monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    good = workspace / "Library" / "good.txt"; good.write_text("good")
    first = ingest_library(workspace); record = first.cache / "extractions/good.txt.json"; text = first.cache / "extractions/good.txt.txt"
    data = json.loads(record.read_text()); data.pop("status"); record.write_text(json.dumps(data))
    assert ingest_library(workspace).counts["extracted"] == 1
    text.unlink(); assert ingest_library(workspace).counts["extracted"] == 1
    orphan = first.cache / "extractions/orphan.txt.txt"; orphan.write_text("orphan")
    bad = workspace / "Library" / "bad-name.png"; bad.write_bytes(b"x")
    flagged = ingest_library(workspace)
    assert _safe("bad\x1b\u200b\nname") == "bad   name"
    assert not orphan.exists()
    (workspace / "Library" / "secret.pdf").write_bytes(b"TOPSECRET invalid pdf")
    ingest_library(workspace)
    captured = capsys.readouterr()
    assert captured.err == "" and "TOPSE" not in captured.err


def test_read_error_continues_and_pair_rollback(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace"); monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    broken = workspace / "Library" / "broken.txt"; broken.write_text("broken")
    good = workspace / "Library" / "good.txt"; good.write_text("good")
    original_read = ingest_module._read_source
    monkeypatch.setattr(ingest_module, "_read_source", lambda path, *args: (_ for _ in ()).throw(PermissionError()) if path == broken else original_read(path, *args))
    result = ingest_library(workspace)
    assert result.counts["error"] == 1 and result.counts["extracted"] == 1
    monkeypatch.setattr(ingest_module, "_read_source", original_read)
    before = (result.cache / "extractions/good.txt.json").read_bytes(), (result.cache / "extractions/good.txt.txt").read_bytes()
    good.write_text("changed")
    calls = [0]; original_write = ingest_module._atomic_write
    def fail_second(*args):
        calls[0] += 1
        if calls[0] == 2: raise OSError("injected")
        return original_write(*args)
    monkeypatch.setattr(ingest_module, "_atomic_write", fail_second)
    with pytest.raises(OSError): ingest_library(workspace)
    assert ((result.cache / "extractions/good.txt.json").read_bytes(), (result.cache / "extractions/good.txt.txt").read_bytes()) == before


def test_cache_home_components_and_var_alias_are_safe(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    outside = tmp_path / "outside"; outside.mkdir()
    configured = tmp_path / "configured"; configured.symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv("APPARATUS_HOME", str(configured))
    with pytest.raises(ValueError): ingest_library(workspace)
    assert list(outside.iterdir()) == []
    home = tmp_path / "home"; home.mkdir(); (home / "library").symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv("APPARATUS_HOME", str(home))
    with pytest.raises(ValueError): ingest_library(workspace)
    assert list(outside.iterdir()) == []
    nested = tmp_path / "base"; nested.mkdir(); (nested / "link").symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv("APPARATUS_HOME", str(nested / "link" / "child"))
    with pytest.raises(ValueError): ingest_library(workspace)
    assert list(outside.iterdir()) == []
    if sys.platform == "darwin":
        raw_var = Path("/var") / tmp_path.relative_to("/private/var") / "var-home"
        monkeypatch.setenv("APPARATUS_HOME", str(raw_var))
        result = ingest_library(workspace)
        assert result.cache.is_relative_to(raw_var.resolve())


def test_descriptor_source_race_and_cache_targets_do_not_publish_external_bytes(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace"); monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    source = workspace / "Library/race.txt"; source.write_text("private")
    secret = tmp_path / "secret.txt"; secret.write_text("TOPSECRET")
    original_read = ingest_module._read_source
    def swap_after_open(path, *args):
        captured = original_read(path, *args)
        if Path(path) == source:
            source.unlink(); source.symlink_to(secret)
        return captured
    monkeypatch.setattr(ingest_module, "_read_source", swap_after_open)
    result = ingest_library(workspace)
    assert result.counts["error"] == 1
    assert "TOPSECRET" not in "".join(path.read_text(errors="ignore") for path in result.cache.rglob("*") if path.is_file())
    monkeypatch.setattr(ingest_module, "_read_source", original_read)
    source.unlink(); source.write_text("private")
    result = ingest_library(workspace)
    record = result.cache / "extractions/race.txt.json"; target = tmp_path / "sentinel"; target.write_text("sentinel")
    record.unlink(); os.link(target, record)
    with pytest.raises(ValueError): ingest_library(workspace)
    assert target.read_text() == "sentinel"


def test_strict_record_contract_fifo_and_case_only_rename(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace"); monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    source = workspace / "Library/Note.txt"; source.write_text("text")
    result = ingest_library(workspace); record = result.cache / "extractions/Note.txt.json"
    for field, value in (("size_bytes", True), ("extractor", "pypdf"), ("timestamp", "2026-01-01T00:00:00+00:00")):
        data = json.loads(record.read_text()); data[field] = value; record.write_text(json.dumps(data))
        assert ingest_library(workspace).counts["extracted"] == 1
    source.rename(workspace / "Library/note.txt")
    assert ingest_library(workspace).counts["extracted"] == 1
    assert any((result.cache / "extractions").glob("*.json"))
    fifo = result.cache / "extractions/note.txt.json"
    if hasattr(os, "mkfifo"):
        fifo.unlink(missing_ok=True); os.mkfifo(fifo)
        with pytest.raises(ValueError): ingest_library(workspace)


def test_initial_stat_and_nested_cache_reparse_are_contained(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace"); monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    broken = workspace / "Library/broken.txt"; broken.write_text("broken")
    good = workspace / "Library/good.txt"; good.write_text("good")
    original_stat = Path.stat
    monkeypatch.setattr(Path, "stat", lambda self, *args, **kwargs: (_ for _ in ()).throw(PermissionError()) if self == broken else original_stat(self, *args, **kwargs))
    result = ingest_library(workspace)
    assert result.counts["error"] == 1 and result.counts["extracted"] == 1
    monkeypatch.setattr(Path, "stat", original_stat)
    nested_source = workspace / "Library/nested"; nested_source.mkdir(); (nested_source / "safe.txt").write_text("safe")
    nested_cache = result.cache / "extractions/nested"; outside = tmp_path / "outside"; outside.mkdir()
    nested_cache.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError): ingest_library(workspace)
    assert list(outside.iterdir()) == []


def test_cli_sanitizes_control_characters(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(library, "ingest_library", lambda _workspace: IngestResult(Path("cache/\x1b\u200b"), {"scanned": 1}, (("bad\x1b", "error", "why\u200b"),)))
    assert library.run(argparse.Namespace(workspace=str(tmp_path))) == 1
    output = capsys.readouterr().out
    assert "\x1b" not in output and "\u200b" not in output


def test_cli_rejects_unsafe_cache_configuration(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(library, "ingest_library", lambda _workspace: (_ for _ in ()).throw(ValueError("bad\x1b cache")))
    assert library.run(argparse.Namespace(workspace=str(tmp_path))) == 2
    assert "\x1b" not in capsys.readouterr().out


@pytest.mark.skipif(os.name == "nt", reason="Windows does not allow newline filename components")
def test_record_provenance_is_raw_while_human_output_is_sanitized(monkeypatch, tmp_path, capsys):
    workspace = _workspace(tmp_path / "workspace"); monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    (workspace / "Library/a\nb.png").write_bytes(b"one")
    (workspace / "Library/a b.png").write_bytes(b"two")
    result = ingest_library(workspace)
    paths = {_record(result.cache, "a\nb.png")["source_path"], _record(result.cache, "a b.png")["source_path"]}
    assert paths == {"Library/a\nb.png", "Library/a b.png"}
    assert library.run(argparse.Namespace(workspace=str(workspace))) == 1
    output = capsys.readouterr().out
    assert "a\nb.png" not in output and "a b.png" in output


def test_library_scandir_failures_are_honest_and_other_sources_continue(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace"); monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    library_dir = workspace / "Library"; good = library_dir / "good.txt"; good.write_text("good")
    original_scandir = ingest_module.os.scandir
    def deny_library(path):
        if path == library_dir or isinstance(path, int):
            raise PermissionError()
        return original_scandir(path)
    monkeypatch.setattr(ingest_module.os, "scandir", deny_library)
    root_failure = ingest_library(workspace)
    assert root_failure.counts["error"] == 1 and root_failure.counts["scanned"] == 1
    assert root_failure.flagged == (("Library", "error", "Library directory could not be traversed"),)
    monkeypatch.setattr(ingest_module.os, "scandir", original_scandir)
    nested = library_dir / "nested"; nested.mkdir(); (nested / "hidden.txt").write_text("hidden")
    def deny_nested(path):
        if not isinstance(path, int) and Path(path) == nested:
            raise PermissionError()
        return original_scandir(path)
    monkeypatch.setattr(ingest_module.os, "scandir", deny_nested)
    nested_failure = ingest_library(workspace)
    assert nested_failure.counts["error"] == 1 and nested_failure.counts["extracted"] == 1
    assert ("nested", "error", "Library directory could not be traversed") in nested_failure.flagged


def test_cache_creation_and_library_root_swap_do_not_escape(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace"); outside = tmp_path / "outside"; outside.mkdir()
    home = tmp_path / "home"; monkeypatch.setenv("APPARATUS_HOME", str(home))
    if os.name == "posix":
        original_mkdir = cache_module.os.mkdir
        injected = [False]
        def inject_library_link(name, mode=0o777, *, dir_fd=None):
            if name == "library" and dir_fd is not None and not injected[0]:
                injected[0] = True
                (home / "library").symlink_to(outside, target_is_directory=True)
            return original_mkdir(name, mode, dir_fd=dir_fd)
        monkeypatch.setattr(cache_module.os, "mkdir", inject_library_link)
        with pytest.raises(ValueError): library_cache_root(workspace)
        assert list(outside.iterdir()) == []
        (home / "library").unlink()
        monkeypatch.setattr(cache_module.os, "mkdir", original_mkdir)
    source = workspace / "Library/private.txt"; source.write_text("private")
    secret_library = tmp_path / "secret-library"; secret_library.mkdir(); (secret_library / "private.txt").write_text("TOPSECRET")
    original_entries = ingest_module._library_entries
    def swap_root(library_path, descriptor):
        library_path.rename(workspace / "Library-old")
        library_path.symlink_to(secret_library, target_is_directory=True)
        return original_entries(library_path, descriptor)
    monkeypatch.setattr(ingest_module, "_library_entries", swap_root)
    result = ingest_library(workspace)
    assert result.counts["error"] == 1
    assert "TOPSECRET" not in "".join(path.read_text(errors="ignore") for path in result.cache.rglob("*") if path.is_file())


def test_atomic_identity_and_descriptor_stale_cleanup_resist_substitution(monkeypatch, tmp_path):
    target = tmp_path / "target"; target.write_bytes(b"old")
    replacement = tmp_path / "replacement"; replacement.write_bytes(b"same")
    original_replace = ingest_module.os.replace
    def substitute(source, destination):
        if Path(source).name.startswith(".apparatus-library-"):
            original_replace(replacement, source)
        return original_replace(source, destination)
    monkeypatch.setattr(ingest_module.os, "replace", substitute)
    with pytest.raises(OSError): ingest_module._atomic_write(target, b"same")
    monkeypatch.setattr(ingest_module.os, "replace", original_replace)
    if os.name != "posix":
        return
    workspace = _workspace(tmp_path / "workspace"); monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    nested = workspace / "Library/nested"; nested.mkdir(); source = nested / "gone.txt"; source.write_text("gone")
    result = ingest_library(workspace); source.unlink()
    cache_parent = result.cache / "extractions/nested"; outside = tmp_path / "outside"; outside.mkdir()
    for suffix in (".json", ".txt"):
        (outside / ("gone.txt" + suffix)).write_text("sentinel")
    original_stat = ingest_module.os.stat
    swapped = [False]
    def swap_parent(name, *args, **kwargs):
        if name == "gone.txt.json" and kwargs.get("dir_fd") is not None and not swapped[0]:
            swapped[0] = True
            cache_parent.rename(result.cache / "extractions/retained")
            cache_parent.symlink_to(outside, target_is_directory=True)
        return original_stat(name, *args, **kwargs)
    monkeypatch.setattr(ingest_module.os, "stat", swap_parent)
    with pytest.raises(OSError):
        ingest_library(workspace)
    assert (outside / "gone.txt.json").read_text() == "sentinel"
    assert (outside / "gone.txt.txt").read_text() == "sentinel"


def test_windows_publication_mode_and_anchor_close_are_platform_safe(monkeypatch, tmp_path):
    target = tmp_path / "target"; target.write_bytes(b"same")
    workspace = _workspace(tmp_path / "workspace")
    status = target.stat()
    monkeypatch.setattr(ingest_module.os, "lstat", lambda _path: SimpleNamespace(st_mode=stat.S_IFREG | 0o666, st_nlink=1, st_dev=status.st_dev, st_ino=status.st_ino))
    monkeypatch.setattr(ingest_module, "_requires_private_mode", lambda: False)
    assert ingest_module._published_matches(target, (status.st_dev, status.st_ino), b"same")
    closed = []
    class FakeAnchor:
        def __init__(self, _root): pass
        def close(self): closed.append(True)
    monkeypatch.setattr(ingest_module, "_windows_source_anchor", lambda _root: FakeAnchor(_root))
    monkeypatch.setattr(ingest_module, "library_cache_root", lambda _root: (_ for _ in ()).throw(ValueError("injected")))
    with pytest.raises(ValueError): ingest_library(workspace)
    assert closed == [True]


def test_relative_and_symlinked_cache_homes_cannot_enter_workspace(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.chdir(workspace); monkeypatch.setenv("APPARATUS_HOME", "relative-home")
    with pytest.raises(ValueError): library_cache_root(workspace)
    outside = tmp_path / "outside-home"; outside.mkdir()
    link = outside / "library"; link.symlink_to(workspace, target_is_directory=True)
    monkeypatch.chdir(tmp_path); monkeypatch.setenv("APPARATUS_HOME", str(outside))
    with pytest.raises(ValueError): library_cache_root(workspace)


def test_invalid_record_character_count_reextracts(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path / "workspace"); monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    (workspace / "Library/a.txt").write_text("text")
    result = ingest_library(workspace); record = result.cache / "extractions/a.txt.json"
    data = json.loads(record.read_text()); data["character_count"] = 99; record.write_text(json.dumps(data))
    assert ingest_library(workspace).counts["extracted"] == 1
