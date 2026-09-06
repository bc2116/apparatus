from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import zipfile

import pytest

from apparatus_core import managed_state_backup as backup, managed_state_recovery as recovery
from apparatus_core.check import check_workspace
from apparatus_core.commands import init
from apparatus_core.project_binding import bind_project, resolve_project_context
from apparatus_core.skills import BUILTIN_PATHS, BUILTIN_SKILLS, is_legacy_pointer
from apparatus_core.snapshots import SnapshotError


def setup(root):
    assert init.run(argparse.Namespace(workspace=str(root), payload=None, privacy_mode=None,
                                      work_types=None, adopt=True, task=None), available=lambda: False) == 0
    return root


def test_two_bound_projects_read_one_canonical_skill_without_copies(tmp_path):
    root = setup(tmp_path / "area")
    relative = next(iter(BUILTIN_PATHS))
    targets = []
    for name in ("alpha", "beta"):
        project = root / name
        project.mkdir()
        (project / "finished.md").write_bytes(b"Project-owned finished work")
        assert bind_project(project, root).changed
        with resolve_project_context(project) as context:
            context.validate()
            targets.append(context.workspace / relative)
        assert not (project / ".agents").exists()
        assert not (project / "Library").exists()
        assert (project / "finished.md").read_bytes() == b"Project-owned finished work"
    assert targets == [root / relative, root / relative]
    custom = targets[0].read_bytes() + b"\nA shared custom instruction.\n"
    targets[0].write_bytes(custom)
    assert targets[1].read_bytes() == custom


@pytest.mark.skipif(shutil.which("git") is None, reason="actual managed history round trip")
def test_native_archive_and_historical_restore_remigrate_without_losing_custom_files(tmp_path):
    root = setup(tmp_path / "area")
    fixtures = Path(__file__).parent / "fixtures/instruction_updates_pr36"
    for path in fixtures.rglob("*"):
        if path.is_file():
            target = root / path.relative_to(fixtures)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
    for relative in BUILTIN_PATHS:
        (root / relative).unlink()
        (root / relative).parent.rmdir()
    old = recovery.take_snapshot(root).snapshot
    assert old is not None
    setup(root)
    first = next(iter(BUILTIN_PATHS))
    custom = (root / first).read_bytes() + b"\nCustom readable workflow.\n"
    (root / first).write_bytes(custom)
    outside = {
        ".agents/skills/third-party/SKILL.md": b"Foreign native Skill stays outside coverage",
        str(Path(first).parent / "reference.txt"): b"Extra resources stay outside coverage",
        "project/output.txt": b"Project deliverable stays with project",
        "Library/original.txt": b"Library original is not part of this backup",
    }
    for relative, content in outside.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    saved = recovery.take_snapshot(root).snapshot
    assert saved is not None
    destination = tmp_path / "exports"
    destination.mkdir()
    result = backup.export_backup(root, destination)
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(result.archive) as archive:
        assert set(BUILTIN_PATHS).issubset(archive.namelist())
        assert all(relative not in archive.namelist() for relative in outside)
        assert b"optional Skill resources" in archive.read(backup.SCOPE_NOTE)
        archive.extractall(extracted)
    assert (extracted / first).read_bytes() == custom
    assert len(recovery.list_snapshots(extracted)) >= 2
    recovery.restore_snapshot(extracted, old.identifier)
    assert (extracted / first).read_bytes() == custom  # Later additions are retained.
    findings = check_workspace(extracted).findings
    for old_path in BUILTIN_SKILLS:
        assert any(item.path == old_path and "init" in item.hint for item in findings)
    setup(extracted)
    assert (extracted / first).read_bytes() == custom
    assert all(is_legacy_pointer(path, (extracted / path).read_bytes()) for path in BUILTIN_SKILLS)
    assert check_workspace(extracted).ok
    assert {relative: (root / relative).read_bytes() for relative in outside} == outside


@pytest.mark.parametrize("content", [b"Foreign text", b"---\nname: other\ndescription: Wrong name.\n---\nBody"])
def test_invalid_managed_skill_stops_capture_before_store_or_archive(tmp_path, content):
    root = setup(tmp_path / "area")
    (root / next(iter(BUILTIN_PATHS))).write_bytes(content)
    destination = tmp_path / "exports"
    destination.mkdir()
    with pytest.raises(SnapshotError):
        recovery.take_snapshot(root)
    with pytest.raises(backup.BackupError):
        backup.export_backup(root, destination, available=lambda: False)
    assert not list(destination.iterdir())
    assert not (root / "System/recovery/store/refs/heads/managed").exists()
