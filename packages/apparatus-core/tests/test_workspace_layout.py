"""Routing cannot downgrade malformed or partially lost work-area state."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.workspace_layout import LayoutError, read_layout


def marker(root, **changes):
    from apparatus_core import records
    data = {"schema": "apparatus/workspace@v0", "id": str(uuid4()),
            "layout": "sibling-projects", "recovery": "managed-state", **changes}
    (root / "System").mkdir(exist_ok=True)
    path = root / "System/workspace.yaml"
    path.write_text(records.yaml.safe_dump(data))
    return path, data


def test_clean_absence_is_read_only_and_does_not_guess_an_ancestor(tmp_path):
    marker(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    assert read_layout(project) is None
    assert list(project.iterdir()) == []


def test_valid_layout_binds_exact_bytes_and_root_without_directory_mtime(tmp_path):
    path, data = marker(tmp_path)
    layout = read_layout(tmp_path)
    assert layout.workspace_id == data["id"]
    assert layout.content == path.read_bytes()
    # Normal work changes directory metadata without replacing the root object.
    (tmp_path / "unrelated.txt").write_text("Synthetic project work")
    with WorkspaceAnchor(tmp_path) as anchor:
        layout.validate(anchor)


@pytest.mark.parametrize("changes", [
    {"id": "invalid"}, {"id": "00000000-0000-1000-8000-000000000000"},
    {"id": None}, {"id": []}, {"schema": "apparatus/workspace@v1"},
    {"layout": "automatic"}, {"recovery": "root-git"}, {"query": "Synthetic text"},
])
def test_invalid_or_unknown_layout_never_falls_back(tmp_path, changes):
    path, _ = marker(tmp_path, **changes)
    before = path.read_bytes()
    with pytest.raises(LayoutError):
        read_layout(tmp_path)
    assert path.read_bytes() == before
    assert not (tmp_path / ".git").exists()
    assert not (tmp_path / "System/recovery").exists()


@pytest.mark.parametrize("content", [b"not a mapping", b"\xff", b"x" * 4097])
def test_malformed_marker_never_falls_back(tmp_path, content):
    path, _ = marker(tmp_path)
    path.write_bytes(content)
    with pytest.raises(LayoutError):
        read_layout(tmp_path)
    assert path.read_bytes() == content


def test_duplicate_key_is_not_a_valid_enrollment(tmp_path):
    path, data = marker(tmp_path)
    path.write_text(path.read_text() + "id: " + data["id"] + "\n")
    with pytest.raises(LayoutError):
        read_layout(tmp_path)


def test_archive_control_serialization_omits_comment_content(tmp_path):
    path, _ = marker(tmp_path)
    path.write_text(path.read_text() + "# Synthetic task-content sentinel\n")
    layout = read_layout(tmp_path)
    assert b"Synthetic" in layout.content
    assert b"Synthetic" not in layout.canonical_bytes()
    with WorkspaceAnchor(tmp_path) as anchor:
        layout.validate(anchor)


@pytest.mark.parametrize("kind", ["directory", "file"])
def test_residual_recovery_requires_repair_before_legacy_routing(tmp_path, kind):
    (tmp_path / "System").mkdir()
    recovery = tmp_path / "System/recovery"
    if kind == "directory":
        recovery.mkdir()
    else:
        recovery.write_text("Foreign sentinel")
    with pytest.raises(LayoutError):
        read_layout(tmp_path)
    assert recovery.exists()
    assert not (tmp_path / "System/workspace.yaml").exists()


@pytest.mark.parametrize("change", ["delete", "replace", "rewrite"])
def test_published_layout_proof_rejects_changed_enrollment(tmp_path, change):
    path, _ = marker(tmp_path)
    layout = read_layout(tmp_path)
    if change == "delete":
        path.unlink()
    elif change == "replace":
        original = path.read_bytes()
        path.rename(path.with_suffix(".held"))
        path.write_bytes(original)
    else:
        marker(tmp_path)
    with WorkspaceAnchor(tmp_path) as anchor, pytest.raises(LayoutError):
        layout.validate(anchor)


def test_layout_proof_cannot_cross_workspaces(tmp_path):
    one = tmp_path / "one"
    other = tmp_path / "other"
    one.mkdir()
    other.mkdir()
    marker(one)
    layout = read_layout(one)
    marker(other, id=layout.workspace_id)
    with WorkspaceAnchor(other) as anchor, pytest.raises(LayoutError):
        layout.validate(anchor)


@pytest.mark.parametrize("state", ["invalid", "partial"])
def test_public_recovery_never_uses_git_after_enrollment_damage(tmp_path, state):
    from apparatus_core import snapshots, backup
    path, _ = marker(tmp_path)
    if state == "invalid":
        path.write_text("schema: unknown\n")
    else:
        path.unlink()
        (tmp_path / "System/recovery").mkdir()
    before = {p.relative_to(tmp_path): p.read_bytes()
              for p in tmp_path.rglob("*") if p.is_file()}

    def forbidden(*args, **kwargs):
        raise AssertionError("damaged enrollment must stop before Git or capture")

    for call in (
        lambda: snapshots.ensure_snapshot_store(tmp_path, run=forbidden),
        lambda: snapshots.take_snapshot(tmp_path, run=forbidden),
        lambda: snapshots.prepare_snapshot(tmp_path, label="Synthetic", capture=forbidden,
                                           run=forbidden),
        lambda: snapshots.list_snapshots(tmp_path, run=forbidden),
        lambda: snapshots.resolve_snapshot_id(tmp_path, "a" * 40, run=forbidden),
        lambda: snapshots.restore_snapshot(tmp_path, "a" * 40, run=forbidden),
    ):
        with pytest.raises(snapshots.SnapshotError):
            call()
    with pytest.raises(backup.BackupError):
        backup.export_backup(tmp_path, tmp_path / "absent", available=forbidden)
    assert {p.relative_to(tmp_path): p.read_bytes()
            for p in tmp_path.rglob("*") if p.is_file()} == before
    assert not (tmp_path / ".git").exists()


def test_direct_legacy_initializer_cannot_bypass_managed_scope(tmp_path):
    from apparatus_core import snapshots
    marker(tmp_path)
    with pytest.raises(snapshots.SnapshotError, match="managed-state"):
        snapshots.ensure_snapshot_store(tmp_path,
            run=lambda *a, **k: pytest.fail("root Git must not run"))
    assert not (tmp_path / ".git").exists()


def test_legacy_git_runner_rechecks_enrollment_immediately_before_execution(tmp_path):
    from apparatus_core import snapshots
    assert read_layout(tmp_path) is None
    marker(tmp_path)
    with pytest.raises(snapshots.SnapshotError, match="managed-state"):
        snapshots._run_git(tmp_path, ["init"],
            run=lambda *a, **k: pytest.fail("late enrollment must not use root Git"))


@pytest.mark.skipif(os.name != "posix", reason="POSIX rename/symlink boundary probe")
def test_layout_proof_rejects_replaced_root_and_symlink_marker(tmp_path):
    root = tmp_path / "area"
    root.mkdir()
    marker(root)
    layout = read_layout(root)
    root.rename(tmp_path / "held")
    root.mkdir()
    marker(root, id=layout.workspace_id)
    with WorkspaceAnchor(root) as anchor, pytest.raises(LayoutError):
        layout.validate(anchor)
    path = root / "System/workspace.yaml"
    path.unlink()
    path.symlink_to(tmp_path / "held/System/workspace.yaml")
    with pytest.raises(LayoutError):
        read_layout(root)
