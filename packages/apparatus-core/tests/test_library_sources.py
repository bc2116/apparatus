"""Catalog selection, read ownership, and one-source publication contracts."""
from __future__ import annotations

import errno
import hashlib
import os
from pathlib import Path

import pytest
import yaml

from apparatus_core.library import sources
from apparatus_core.retention import RetentionSuppressed, start_task


@pytest.fixture
def workspace(tmp_path):
    root = (tmp_path / "workspace").resolve()
    (root / "System").mkdir(parents=True)
    (root / "Library").mkdir()
    (root / "project").mkdir()
    (root / "project/report.txt").write_bytes(b"selected original")
    (root / "project/unselected.txt").write_bytes(b"unselected sentinel")
    (root / "System/profile.yaml").write_text(
        "schema: apparatus/profile@v0\nstatus: configured\nprivacy_mode: standard\n"
        "work_types: []\nreview_day: null\n", encoding="utf-8",
    )
    return root


def _tree(root):
    return {p.relative_to(root).as_posix(): None if p.is_dir() else p.read_bytes() for p in root.rglob("*")}



def _attempt_change(action):
    """Witness native name/write denial; never invent a concurrent mutation."""
    try:
        action()
    except PermissionError as error:
        assert os.name == "nt" and error.errno == errno.EACCES
        return False
    return True


def _record(root, path):
    return root / sources.registration_path(path)


def test_register_read_remove_keeps_original_and_never_reads_sibling(workspace, monkeypatch):
    original = sources.WorkspaceAnchor.capture_file
    reads = []

    def capture(self, relative, **kwargs):
        reads.append((self.workspace / relative).relative_to(workspace).as_posix())
        assert Path(relative).name != "unselected.txt"
        return original(self, relative, **kwargs)

    monkeypatch.setattr(sources.WorkspaceAnchor, "capture_file", capture)
    result = sources.register_source(workspace, "project/report.txt")
    assert result.changed and not result.implicit
    key = hashlib.sha256(b"project/report.txt").hexdigest()
    assert result.source.key == key and len(key) == 64
    assert result.source.cache_relative == f"references/{key}"
    assert yaml.safe_load(_record(workspace, "project/report.txt").read_bytes()) == {
        "schema": sources.SCHEMA, "source": "project/report.txt",
    }
    before = _tree(workspace)
    assert not sources.register_source(workspace, "project/report.txt").changed
    assert _tree(workspace) == before
    with sources.Catalog(workspace) as catalog:
        with catalog.read(catalog.source("project/report.txt")) as reader:
            assert reader.content == b"selected original"
            assert reader.size_bytes == 17
            assert reader.sha256 == hashlib.sha256(reader.content).hexdigest()
            reader.validate()
    assert sources.unregister_source(workspace, "project/report.txt").changed
    assert not sources.list_sources(workspace)
    assert (workspace / "project/report.txt").read_bytes() == b"selected original"
    assert not sources.unregister_source(workspace, "project/report.txt").changed
    assert "project/report.txt" in reads


def test_library_selection_is_implicit_and_keeps_old_cache_identity(workspace):
    (workspace / "Library/report.txt").write_bytes(b"legacy")
    before = _tree(workspace)
    result = sources.register_source(workspace, "Library/report.txt")
    assert result.implicit and not result.changed
    assert result.source.cache_relative == "extractions/report.txt"
    assert sources.unregister_source(workspace, "Library/report.txt").implicit
    assert _tree(workspace) == before
    with sources.Catalog(workspace) as catalog:
        with catalog.read(catalog.source("Library/report.txt")) as reader:
            assert reader.content == b"legacy"


@pytest.mark.parametrize("path", [
    "", "/project/a", "project//a", "project/../a", "./project/a", "project/./a",
    "project\\a", "C:/a", "project/a\n", "project/a\x00", "project/a.", "project/a ",
    "project/CON", "project/nul.txt", "project/LPT1.txt", "project/e\u0301.txt",
    "System/file", "memory/file", "Goals/file", "Decisions/file", "project/.git/a",
    "project/.AGENTS/a", "project/.apparatus/a", "project/.claude/a", "project/.cursor/a",
    "project/.github/a", "library/a", "Library", "project/token=synthetic-value.txt",
])
def test_reject_unsafe_paths_without_writes(workspace, path):
    before = _tree(workspace)
    with pytest.raises(sources.SourceError):
        sources.register_source(workspace, path)
    assert _tree(workspace) == before


@pytest.mark.parametrize("content", [
    b"schema: apparatus/library-source@v0\nsource: project/report.txt\nsource: project/report.txt\n",
    b"schema: apparatus/library-source@v0\nsource: &path project/report.txt\n",
    b"schema: &v apparatus/library-source@v0\nsource: *v\n",
    b"schema: apparatus/library-source@v0\nsource: project/report.txt\nextra: true\n",
    b"schema: apparatus/library-source@v0\nsource: [project/report.txt]\n",
    b"schema: apparatus/library-source@v0\nsource: Library/report.txt\n",
    b"schema: apparatus/library-source@v0\nsource: ../escape\n",
    b"schema: wrong\nsource: project/report.txt\n", b"\xff", b"x" * 8193,
])
def test_closed_parser_rejects_malformed_records(content):
    with pytest.raises(sources.SourceError, match="Invalid Library source registration"):
        sources.parse_registration(content, sources.registration_path("project/report.txt"))


def test_parser_binds_full_filename_and_catalog_validates_all_entries(workspace):
    sources.register_source(workspace, "project/report.txt")
    record = _record(workspace, "project/report.txt")
    with pytest.raises(sources.SourceError):
        sources.parse_registration(record.read_bytes(), "System/library/sources/other.yaml")
    (record.parent / "unexpected.txt").write_bytes(b"unrelated")
    before = _tree(workspace)
    with pytest.raises(sources.SourceError, match="Unknown entry"):
        sources.unregister_source(workspace, "project/report.txt")
    assert _tree(workspace) == before


def test_catalog_rejects_case_collision_even_if_sources_missing(workspace):
    sources.register_source(workspace, "project/report.txt")
    other = sources.Source("PROJECT/report.txt")
    _record(workspace, other.source_path).write_bytes(sources._record_bytes(other))
    with pytest.raises(sources.SourceError, match="collide"):
        sources.Catalog(workspace)


@pytest.mark.parametrize("mutation", ["add", "remove", "replace"])
def test_catalog_detects_inventory_or_same_byte_inode_change(workspace, mutation):
    sources.register_source(workspace, "project/report.txt")
    record = _record(workspace, "project/report.txt")
    with sources.Catalog(workspace) as catalog:
        if mutation == "add":
            other = sources.Source("project/other.txt")
            _record(workspace, other.source_path).write_bytes(sources._record_bytes(other))
        elif mutation == "remove":
            if not _attempt_change(record.unlink):
                assert record.read_bytes() == catalog._records[record.name][1].content
                catalog.validate()
                return
        else:
            replacement = workspace / "replacement"
            replacement.write_bytes(record.read_bytes())
            if not _attempt_change(lambda: replacement.replace(record)):
                assert record.read_bytes() == replacement.read_bytes()
                catalog.validate()
                return
        with pytest.raises(sources.SourceError, match="changed"):
            catalog.validate()


@pytest.mark.parametrize("existing", ["System", "System/library"])
def test_catalog_preserves_absent_directory_preimage(workspace, existing):
    (workspace / existing).mkdir(exist_ok=True)
    with sources.Catalog(workspace) as catalog:
        assert catalog.sources == ()
        (workspace / sources.REGISTRATION_ROOT).mkdir(parents=True)
        with pytest.raises(sources.SourceError, match="changed"):
            catalog.validate()


@pytest.mark.parametrize("mutation", ["bytes", "inode"])
def test_source_proof_detects_stale_bytes_or_identity(workspace, mutation):
    sources.register_source(workspace, "project/report.txt")
    path = workspace / "project/report.txt"
    with sources.Catalog(workspace) as catalog:
        with catalog.read(catalog.sources[0]) as reader:
            previous = path.stat()
            if mutation == "bytes":
                def write():
                    assert path.write_bytes(b"different content") == len(reader.content)
                if not _attempt_change(write):
                    assert path.read_bytes() == reader.content
                    reader.validate()
                    return
                os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns))
            else:
                replacement = workspace / "replacement"
                replacement.write_bytes(path.read_bytes())
                if not _attempt_change(lambda: replacement.replace(path)):
                    assert path.read_bytes() == reader.content
                    reader.validate()
                    return
            with pytest.raises(sources.SourceUnavailable) as caught:
                reader.validate()
            assert caught.value.reason == "unavailable"


def test_source_selection_cannot_be_forged(workspace):
    with sources.Catalog(workspace) as catalog:
        with pytest.raises(sources.SourceError, match="not selected"):
            catalog.read(sources.Source("project/unselected.txt"))


def test_list_reports_missing_ignored_without_reading_sources(workspace, monkeypatch):
    sources.register_source(workspace, "project/report.txt")
    sources.register_source(workspace, "project/unselected.txt")
    (workspace / "project/report.txt").unlink()
    (workspace / "System/ignore").write_text("project/unselected.txt\n", encoding="utf-8")
    original = sources.WorkspaceAnchor.capture_file

    def capture(self, relative, **kwargs):
        assert "project" not in (self.workspace / relative).relative_to(workspace).parts
        return original(self, relative, **kwargs)

    monkeypatch.setattr(sources.WorkspaceAnchor, "capture_file", capture)
    before = _tree(workspace)
    assert [(item.source_path, item.status) for item in sources.list_sources(workspace)] == [
        ("project/report.txt", "missing"), ("project/unselected.txt", "ignored"),
    ]
    assert _tree(workspace) == before


def test_ignore_checked_before_source_capture(workspace, monkeypatch):
    (workspace / "System/ignore").write_text("project/report.txt\n", encoding="utf-8")
    original = sources.WorkspaceAnchor.capture_file

    def capture(self, relative, **kwargs):
        assert Path(relative).name != "report.txt"
        return original(self, relative, **kwargs)

    monkeypatch.setattr(sources.WorkspaceAnchor, "capture_file", capture)
    before = _tree(workspace)
    with pytest.raises(sources.SourceUnavailable) as caught:
        sources.register_source(workspace, "project/report.txt")
    assert caught.value.reason == "ignored"
    assert _tree(workspace) == before


def test_no_save_guard_precedes_content_and_only_explicit_exception_works(workspace, monkeypatch):
    task = start_task(workspace, save_memory=False)
    original = sources.SourceRead.__init__

    def forbidden(*args, **kwargs):
        raise AssertionError("retention guard must precede source reads")

    monkeypatch.setattr(sources.SourceRead, "__init__", forbidden)
    before = _tree(workspace)
    with pytest.raises(RetentionSuppressed):
        sources.register_source(workspace, "project/report.txt", task_id=task.task_id)
    assert _tree(workspace) == before
    monkeypatch.setattr(sources.SourceRead, "__init__", original)
    assert sources.register_source(workspace, "project/report.txt", task_id=task.task_id, requested=True).changed
    with pytest.raises(RetentionSuppressed):
        sources.unregister_source(workspace, "project/report.txt", task_id=task.task_id)
    assert sources.unregister_source(workspace, "project/report.txt", task_id=task.task_id, requested=True).changed


def test_disabled_feature_prevents_registration_but_allows_remove(workspace, monkeypatch):
    sources.register_source(workspace, "project/report.txt")
    monkeypatch.setattr(sources, "enabled", lambda *_args: False)
    before = _tree(workspace)
    with pytest.raises(sources.SourceError, match="disabled"):
        sources.register_source(workspace, "project/unselected.txt")
    assert _tree(workspace) == before
    assert sources.unregister_source(workspace, "project/report.txt").changed


def test_late_source_mutation_compensates_registration_and_created_directories(workspace, monkeypatch):
    original = sources.WorkspaceAnchor.create_file
    outcomes = []

    def create(self, relative, content):
        proof = original(self, relative, content)
        if self.workspace.name == "sources":
            def write():
                assert (workspace / "project/report.txt").write_bytes(b"concurrent content") == 18
            outcomes.append(_attempt_change(write))
        return proof

    monkeypatch.setattr(sources.WorkspaceAnchor, "create_file", create)
    try:
        result = sources.register_source(workspace, "project/report.txt")
    except sources.SourceUnavailable:
        assert outcomes == [True]
        assert not (workspace / "System/library").exists()
        assert (workspace / "project/report.txt").read_bytes() == b"concurrent content"
    else:
        assert outcomes == [False] and os.name == "nt"
        assert result.changed
        assert (workspace / "project/report.txt").read_bytes() == b"selected original"
        with sources.Catalog(workspace) as catalog:
            assert catalog.sources == (result.source,)
            catalog.validate()


def test_late_catalog_addition_preserved_while_own_registration_compensated(workspace, monkeypatch):
    original = sources.WorkspaceAnchor.create_file
    other = sources.Source("project/other.txt")

    def create(self, relative, content):
        proof = original(self, relative, content)
        if self.workspace.name == "sources":
            _record(workspace, other.source_path).write_bytes(sources._record_bytes(other))
        return proof

    monkeypatch.setattr(sources.WorkspaceAnchor, "create_file", create)
    with pytest.raises(sources.SourceError, match="changed"):
        sources.register_source(workspace, "project/report.txt")
    assert not _record(workspace, "project/report.txt").exists()
    assert _record(workspace, other.source_path).read_bytes() == sources._record_bytes(other)


def test_late_removal_failure_restores_exact_record(workspace, monkeypatch):
    sources.register_source(workspace, "project/report.txt")
    before = _tree(workspace)
    original = sources.Catalog.validate
    removed = False
    unlink = sources.WorkspaceAnchor.unlink_owned_if_present

    def remove(self, proof):
        nonlocal removed
        result = unlink(self, proof)
        removed = True
        return result

    def validate(self):
        original(self)
        if removed:
            raise sources.SourceError("injected late boundary failure")

    monkeypatch.setattr(sources.WorkspaceAnchor, "unlink_owned_if_present", remove)
    monkeypatch.setattr(sources.Catalog, "validate", validate)
    with pytest.raises(sources.SourceError, match="late boundary"):
        sources.unregister_source(workspace, "project/report.txt")
    assert _tree(workspace) == before


@pytest.mark.skipif(os.name != "posix", reason="POSIX symlink fixture")
@pytest.mark.parametrize("directory", [False, True])
def test_reject_symlink_source_or_parent_without_reading_target(workspace, directory):
    if directory:
        (workspace / "alias").symlink_to(workspace / "project", target_is_directory=True)
        path = "alias/report.txt"
    else:
        (workspace / "project/alias.txt").symlink_to(workspace / "project/report.txt")
        path = "project/alias.txt"
    with pytest.raises(sources.SourceUnavailable):
        sources.register_source(workspace, path)
    assert not (workspace / sources.REGISTRATION_ROOT).exists()


def test_unavailable_reader_exposes_only_bounded_reason(workspace, monkeypatch):
    sources.register_source(workspace, "project/report.txt")
    original = sources.WorkspaceAnchor.capture_file

    def capture(self, relative, **kwargs):
        if Path(relative).name == "report.txt":
            raise PermissionError("synthetic-private-host-path")
        return original(self, relative, **kwargs)

    monkeypatch.setattr(sources.WorkspaceAnchor, "capture_file", capture)
    with sources.Catalog(workspace) as catalog:
        with pytest.raises(sources.SourceUnavailable) as caught:
            catalog.read(catalog.sources[0])
        assert caught.value.reason == "unavailable"
        assert "synthetic-private-host-path" not in str(caught.value)


def test_add_from_work_area_without_catalog_or_system(workspace):
    (workspace / "System/profile.yaml").unlink()
    (workspace / "System").rmdir()
    assert sources.register_source(workspace, "project/report.txt").changed
    assert sources.list_sources(workspace)[0].status == "available"


@pytest.mark.skipif(os.name != "posix", reason="POSIX permits replacing retained source directories")
def test_same_byte_source_parent_substitution_invalidates_read(workspace):
    sources.register_source(workspace, "project/report.txt")
    with sources.Catalog(workspace) as catalog:
        with catalog.read(catalog.sources[0]) as reader:
            (workspace / "project").rename(workspace / "old-project")
            (workspace / "project").mkdir()
            (workspace / "project/report.txt").write_bytes(reader.content)
            with pytest.raises(sources.SourceUnavailable):
                reader.validate()


def test_remove_compensation_preserves_concurrent_registration(workspace, monkeypatch):
    sources.register_source(workspace, "project/report.txt")
    path = _record(workspace, "project/report.txt")
    content = path.read_bytes() + b"# competing writer\n"
    original = sources.WorkspaceAnchor.unlink_owned_if_present

    def remove(self, proof):
        result = original(self, proof)
        path.write_bytes(content)
        return result

    monkeypatch.setattr(sources.WorkspaceAnchor, "unlink_owned_if_present", remove)
    with pytest.raises(sources.SourceError, match="changed"):
        sources.unregister_source(workspace, "project/report.txt")
    assert path.read_bytes() == content
    assert (workspace / "project/report.txt").read_bytes() == b"selected original"
