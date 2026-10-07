"""Create-only module deployment against synthetic enrolled work areas."""

import argparse
import builtins
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest

from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.workspace_layout import new_layout_bytes
from apparatus_mailbox_survey import deployment as deploy
from apparatus_mailbox_survey.__main__ import main


@pytest.fixture
def area(tmp_path):
    root = tmp_path / "area"
    (root / "System").mkdir(parents=True)
    (root / "System/workspace.yaml").write_bytes(new_layout_bytes())
    return root


def creation_anchor(monkeypatch):
    """Patch this operation's adapter, including POSIX creation overrides."""
    core = deploy._core()
    monkeypatch.setattr(deploy, "_core", lambda: core)
    return core.anchor


def assets(root):
    return {relative: (root / relative).read_bytes() for relative in deploy.ASSETS if (root / relative).is_file()}


def tree(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


def test_absent_status_is_readonly(area):
    before = tree(area)
    result = deploy.operate(area)
    assert result["package"] == "apparatus-mailbox-survey"
    assert result["version"] == "0.1.3"
    assert result["state"] == "absent"
    assert set(result["assets"].values()) == {"missing"}
    assert tree(area) == before
    assert not (area / ".agents").exists()


def test_enrollment_rereads_coexist_with_retained_publication_proof(area, monkeypatch):
    original = WorkspaceAnchor.capture_file
    rereads = []

    def require_compatible_read(self, relative, **kwargs):
        if str(relative).replace("\\", "/") == "System/workspace.yaml":
            # Windows rejects DELETE access while the first enrollment proof
            # pins its name; this contract must hold on every reread.
            if kwargs.get("publication_compatible") is not True:
                raise PermissionError("Simulated Windows sharing violation")
            rereads.append(relative)
        return original(self, relative, **kwargs)

    monkeypatch.setattr(WorkspaceAnchor, "capture_file", require_compatible_read)
    assert deploy.operate(area, "install")["state"] == "current"
    assert len(rereads) > 1


def test_install_only_exact_assets_and_repeat_untouched(area):
    before = tree(area)
    assert deploy.operate(area, "install")["state"] == "current"
    expected = deploy._sources(deploy._core())
    assert assets(area) == expected
    assert tree(area) == {**before, **expected}
    times = {relative: (area / relative).stat().st_mtime_ns for relative in expected}
    assert deploy.operate(area, "install")["state"] == "current"
    assert deploy.operate(area, "repair")["state"] == "current"
    assert times == {relative: (area / relative).stat().st_mtime_ns for relative in expected}


@pytest.mark.parametrize("missing", list(deploy.ASSETS))
def test_partial_exact_repair_preserves_other_asset(area, missing):
    deploy.operate(area, "install")
    (area / missing).unlink()
    other = next(relative for relative in deploy.ASSETS if relative != missing)
    before = (area / other).stat().st_mtime_ns
    assert deploy.operate(area)["state"] == "partial"
    assert deploy.operate(area, "repair")["state"] == "current"
    assert (area / other).stat().st_mtime_ns == before


@pytest.mark.parametrize("modified", list(deploy.ASSETS))
def test_foreign_asset_blocks_all_writes(area, modified):
    path = area / modified
    path.parent.mkdir(parents=True)
    path.write_bytes(b"User authored PRIVATE_MARKER\n")
    before = tree(area)
    assert deploy.operate(area)["state"] == "conflict"
    assert deploy.operate(area)["assets"][modified] == "modified"
    with pytest.raises(deploy.DeploymentError) as failure:
        deploy.operate(area, "repair")
    assert failure.value.code == 1
    assert "PRIVATE_MARKER" not in str(failure.value)
    assert tree(area) == before
    assert not (area / next(relative for relative in deploy.ASSETS if relative != modified)).exists()


@pytest.mark.parametrize("invalid", ["missing", "malformed", "duplicate", "bound-project"])
def test_invalid_enrollment_and_bound_project(area, invalid):
    if invalid == "missing":
        (area / "System/workspace.yaml").unlink()
    elif invalid == "malformed":
        (area / "System/workspace.yaml").write_bytes(b"invalid")
    elif invalid == "duplicate":
        with (area / "System/workspace.yaml").open("ab") as output:
            output.write(b"layout: sibling-projects\n")
    else:
        (area / ".apparatus").mkdir()
        (area / ".apparatus/workspace.yaml").write_bytes(b"project control")
    before = tree(area)
    with pytest.raises(deploy.DeploymentError) as failure:
        deploy.operate(area, "install")
    assert failure.value.code == 2
    if invalid == "bound-project":
        assert "work-area root" in str(failure.value)
    assert tree(area) == before
    assert not (area / ".agents").exists()


def test_missing_root_is_not_created(tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(deploy.DeploymentError):
        deploy.operate(missing, "install")
    assert not missing.exists()


@pytest.mark.parametrize("relative", [".agents", ".agents/skills", deploy.SKILL_ROOT, f"{deploy.SKILL_ROOT}/references", f"{deploy.SKILL_ROOT}/SKILL.md"])
def test_symlink_boundaries_preserve_external_files(area, tmp_path, relative):
    target = tmp_path / "outside"
    target.mkdir()
    (target / "foreign").write_bytes(b"Unrelated content")
    path = area / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation not permitted")
    with pytest.raises(deploy.DeploymentError) as failure:
        deploy.operate(area, "install")
    assert failure.value.code == 2
    assert (target / "foreign").read_bytes() == b"Unrelated content"
    assert set(target.iterdir()) == {target / "foreign"}
    assert path.is_symlink()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction boundary")
def test_windows_junction_boundary(area, tmp_path):
    target = tmp_path / "outside"
    target.mkdir()
    junction = area / ".agents"
    completed = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(target)], capture_output=True)
    assert completed.returncode == 0
    try:
        with pytest.raises(deploy.DeploymentError):
            deploy.operate(area, "install")
        assert not list(target.iterdir())
    finally:
        junction.rmdir()


def test_directory_final_asset_rejected_without_writes(area):
    (area / f"{deploy.SKILL_ROOT}/SKILL.md").mkdir(parents=True)
    with pytest.raises(deploy.DeploymentError):
        deploy.operate(area, "install")
    assert not (area / f"{deploy.SKILL_ROOT}/references").exists()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO")
def test_fifo_final_asset_rejected_without_blocking(area):
    path = area / f"{deploy.SKILL_ROOT}/SKILL.md"
    path.parent.mkdir(parents=True)
    os.mkfifo(path)
    result = subprocess.run([sys.executable, "-m", "apparatus_mailbox_survey", "install", str(area)],
                            capture_output=True, timeout=5)
    assert result.returncode == 2
    assert not (path.parent / "references").exists()


def test_injected_file_failure_preserves_exact_partial_and_repairs(area, monkeypatch):
    before = tree(area)
    anchor = creation_anchor(monkeypatch)
    original = anchor.create_file
    count = 0
    def fail(self, *args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("Injected second file failure")
        return original(self, *args, **kwargs)
    monkeypatch.setattr(anchor, "create_file", fail)
    with pytest.raises(deploy.DeploymentError) as failure:
        deploy.operate(area, "install")
    assert "Installation may be partial" in str(failure.value)
    expected = deploy._sources(deploy._core())
    body = f"{deploy.SKILL_ROOT}/SKILL.md"
    assert tree(area) == {**before, body: expected[body]}
    assert (area / f"{deploy.SKILL_ROOT}/references").is_dir()
    assert deploy.operate(area)["state"] == "partial"
    monkeypatch.setattr(anchor, "create_file", original)
    assert deploy.operate(area, "repair")["state"] == "current"


@pytest.mark.skipif(os.name != "posix", reason="Windows retains write/name locks")
def test_concurrent_substitution_preserves_foreign_file_and_reports_incomplete(area, monkeypatch):
    anchor = creation_anchor(monkeypatch)
    original = anchor.create_file
    count = 0
    foreign_path = area / f"{deploy.SKILL_ROOT}/SKILL.md"
    def substitute(self, *args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            foreign_path.unlink()
            foreign_path.write_bytes(b"Concurrent foreign file")
            raise OSError("Injected substitution")
        return original(self, *args, **kwargs)
    monkeypatch.setattr(anchor, "create_file", substitute)
    with pytest.raises(deploy.DeploymentError) as failure:
        deploy.operate(area, "install")
    assert failure.value.code == 2
    assert "Installation may be partial" in str(failure.value)
    assert foreign_path.read_bytes() == b"Concurrent foreign file"
    assert not (foreign_path.parent / "references/report-format.md").exists()


@pytest.mark.skipif(os.name != "posix", reason="Windows retains enrollment write locks")
def test_enrollment_edit_during_publication_preserves_partial(area, monkeypatch):
    anchor = creation_anchor(monkeypatch)
    original = anchor.create_file
    def change(self, *args, **kwargs):
        proof = original(self, *args, **kwargs)
        (area / "System/workspace.yaml").write_bytes(new_layout_bytes())
        return proof
    monkeypatch.setattr(anchor, "create_file", change)
    with pytest.raises(deploy.DeploymentError):
        deploy.operate(area, "install")
    body = f"{deploy.SKILL_ROOT}/SKILL.md"
    assert (area / body).read_bytes() == deploy._sources(deploy._core())[body]
    assert not (area / f"{deploy.SKILL_ROOT}/references/report-format.md").exists()


@pytest.mark.skipif(os.name != "posix", reason="Windows retains directory name locks")
def test_parent_substitution_during_preflight_stops_before_writes(area, monkeypatch):
    leaf = area / deploy.SKILL_ROOT
    leaf.mkdir(parents=True)
    original = deploy._existing_child
    def change(core, parent, name):
        child = original(core, parent, name)
        if name == "apparatus-mailbox-survey":
            leaf.rename(leaf.with_name("detached"))
            leaf.mkdir()
            (leaf / "foreign").write_bytes(b"Foreign directory")
        return child
    monkeypatch.setattr(deploy, "_existing_child", change)
    with pytest.raises(deploy.DeploymentError):
        deploy.operate(area, "install")
    assert (leaf / "foreign").read_bytes() == b"Foreign directory"
    assert not (leaf / "SKILL.md").exists()
    assert not list(leaf.with_name("detached").iterdir())


def test_generic_install_no_network_or_retention_writes(area, monkeypatch):
    before = tree(area)
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected provider or retention access")
    monkeypatch.setattr(socket, "socket", forbidden)
    from apparatus_core import retention
    monkeypatch.setattr(retention, "operation", forbidden)
    assert deploy.operate(area, "install")["state"] == "current"
    assert set(tree(area)) - set(before) == set(deploy.ASSETS)


def test_packaged_skill_invalid_blocks_before_any_write(area, monkeypatch):
    original = deploy._core
    def invalid():
        core = original()
        core.validate_skill = lambda *args: ["Invalid"]
        return core
    monkeypatch.setattr(deploy, "_core", invalid)
    before = tree(area)
    with pytest.raises(deploy.DeploymentError):
        deploy.operate(area, "install")
    assert tree(area) == before


def test_cli_fixed_output_and_exit_codes(area, capsys):
    assert main(["status", str(area)]) == 0
    output = capsys.readouterr().out
    assert str(area) not in output
    assert json.loads(output)["state"] == "absent"
    assert main(["install", str(area)]) == 0
    capsys.readouterr()
    path = area / next(iter(deploy.ASSETS))
    path.write_bytes(b"PRIVATE_MARKER")
    assert main(["repair", str(area)]) == 1
    assert "PRIVATE_MARKER" not in capsys.readouterr().err
    assert main(["status", str(area / "missing")]) == 2


def test_missing_core_is_unavailable_and_validate_remains_independent(area, monkeypatch, capsys):
    real_import = builtins.__import__
    def no_core(name, *args, **kwargs):
        if name.startswith("apparatus_core"):
            raise ImportError("Not installed")
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", no_core)
    assert main(["install", str(area)]) == 2
    assert "lifecycle extra" in capsys.readouterr().err
    sample = deploy.resources.files("apparatus_mailbox_survey").joinpath("resources", "report-example.yaml")
    assert main(["validate", str(sample)]) == 0


def test_core_init_preserves_module_assets_and_recovery_excludes_them(tmp_path, monkeypatch):
    from apparatus_core.commands import init
    from apparatus_core import managed_state_recovery as recovery
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    root = tmp_path / "full-area"
    args = argparse.Namespace(workspace=str(root), payload=None, privacy_mode=None, work_types=None)
    assert init.run(args, available=lambda: False) == 0
    deploy.operate(root, "install")
    before = assets(root)
    assert init.run(args, available=lambda: False) == 0
    assert assets(root) == before
    with WorkspaceAnchor(root) as anchor:
        covered = recovery._collect(anchor)
    assert not set(deploy.ASSETS) & set(covered)


@pytest.mark.skipif(os.name != "posix", reason="POSIX bounded reader adapter")
def test_enrollment_fifo_rejected_without_blocking(area):
    marker = area / "System/workspace.yaml"
    marker.unlink()
    os.mkfifo(marker)
    result = subprocess.run([sys.executable, "-m", "apparatus_mailbox_survey", "status", str(area)],
                            capture_output=True, timeout=5)
    assert result.returncode == 2
    assert not (area / ".agents").exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX FIFO substitutions; Windows locks names")
@pytest.mark.parametrize("stage", ["capture", "validate", "failure"])
def test_fifo_substitution_during_operation_is_nonblocking_and_preserved(area, stage):
    if stage == "capture":
        deploy.operate(area, "install")
    script = r'''
import os
import sys
from pathlib import Path
from unittest.mock import patch
from apparatus_mailbox_survey.__main__ import main
from apparatus_mailbox_survey import deployment as deployment
root = Path(sys.argv[1])
stage = sys.argv[2]
path = root / deployment.SKILL_ROOT / "SKILL.md"
core = deployment._core()
anchor = core.anchor
deployment._core = lambda: core

def substitute():
    path.unlink()
    os.mkfifo(path)

if stage == "capture":
    original = anchor.capture_file
    def intercept(self, name, *args, **kwargs):
        if str(name) == "SKILL.md":
            substitute()
        return original(self, name, *args, **kwargs)
    with patch.object(anchor, "capture_file", intercept):
        code = main(["repair", str(root)])
else:
    original = anchor.create_file
    def intercept(self, name, *args, **kwargs):
        if stage == "failure" and str(name) == "report-format.md":
            substitute()
            raise OSError("Injected publication failure")
        proof = original(self, name, *args, **kwargs)
        if stage == "validate" and str(name) == "SKILL.md":
            substitute()
        return proof
    with patch.object(anchor, "create_file", intercept):
        code = main(["install", str(root)])
assert code == 2
assert path.exists()
raise SystemExit(code)
'''
    result = subprocess.run([sys.executable, "-c", script, str(area), stage],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 2
    path = area / f"{deploy.SKILL_ROOT}/SKILL.md"
    import stat
    assert stat.S_ISFIFO(path.lstat().st_mode)
    if stage != "capture":
        assert "Installation may be partial" in result.stderr


@pytest.mark.skipif(os.name != "posix", reason="POSIX bounded reader adapter")
@pytest.mark.parametrize("enrollment", [False, True])
def test_oversized_asset_and_enrollment_block_without_changes(area, enrollment):
    path = area / ("System/workspace.yaml" if enrollment else f"{deploy.SKILL_ROOT}/SKILL.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * (deploy.MAX_ASSET_BYTES + 1))
    before = tree(area)
    with pytest.raises(deploy.DeploymentError):
        deploy.operate(area, "install")
    assert tree(area) == before
    assert not (area / f"{deploy.SKILL_ROOT}/references").exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX bounded reader adapter")
def test_reader_bounds_growth_and_closes_its_descriptor(area, monkeypatch):
    reader = deploy._core().anchor._read_at
    path = area / "growing"
    path.write_bytes(b"start")
    parent = os.open(area, os.O_RDONLY | os.O_DIRECTORY)
    original_read = os.read
    original_close = os.close
    received = []
    closed = []
    grew = False
    def grow(descriptor, count):
        nonlocal grew
        received.append(count)
        if not grew:
            grew = True
            with path.open("ab") as output:
                output.write(b"x" * (deploy.MAX_ASSET_BYTES + 1))
        return original_read(descriptor, count)
    def close(descriptor):
        closed.append(descriptor)
        return original_close(descriptor)
    monkeypatch.setattr(os, "read", grow)
    monkeypatch.setattr(os, "close", close)
    try:
        with pytest.raises(OSError):
            reader(parent, "growing")
        assert sum(received) == deploy.MAX_ASSET_BYTES + 1
        assert len(closed) == 1
        assert closed[0] != parent
    finally:
        original_close(parent)


@pytest.mark.skipif(os.name != "posix", reason="POSIX bounded reader adapter")
def test_reader_closes_on_unsafe_type(area, monkeypatch):
    path = area / "pipe"
    os.mkfifo(path)
    reader = deploy._core().anchor._read_at
    parent = os.open(area, os.O_RDONLY | os.O_DIRECTORY)
    original_close = os.close
    closed = []
    def close(descriptor):
        closed.append(descriptor)
        return original_close(descriptor)
    monkeypatch.setattr(os, "close", close)
    try:
        with pytest.raises(OSError):
            reader(parent, "pipe")
        assert len(closed) == 1
        assert closed[0] != parent
    finally:
        original_close(parent)


@pytest.mark.skipif(os.name != "posix", reason="Windows keeps parent name locks")
def test_foreign_directory_during_creation_handoff_preserved(area, monkeypatch):
    anchor = creation_anchor(monkeypatch)
    original = anchor.create_directory
    leaf = area / deploy.SKILL_ROOT
    def foreign(self, name, *args, **kwargs):
        if str(name) == "apparatus-mailbox-survey":
            leaf.mkdir()
            (leaf / "foreign").write_bytes(b"Foreign directory content")
        return original(self, name, *args, **kwargs)
    monkeypatch.setattr(anchor, "create_directory", foreign)
    with pytest.raises(deploy.DeploymentError) as failure:
        deploy.operate(area, "install")
    assert failure.value.code == 2
    assert "Installation may be partial" in str(failure.value)
    assert (leaf / "foreign").read_bytes() == b"Foreign directory content"
    assert not (leaf / "SKILL.md").exists()


@pytest.mark.skipif(os.name != "posix", reason="Windows keeps root name locks")
def test_root_substitution_preserves_foreign_root_and_detached_assets(area, tmp_path, monkeypatch):
    anchor = creation_anchor(monkeypatch)
    original = anchor.create_file
    detached = tmp_path / "detached-area"
    swapped = False
    def foreign(self, *args, **kwargs):
        nonlocal swapped
        proof = original(self, *args, **kwargs)
        if not swapped:
            swapped = True
            area.rename(detached)
            area.mkdir()
            (area / "foreign").write_bytes(b"Foreign root content")
        return proof
    monkeypatch.setattr(anchor, "create_file", foreign)
    with pytest.raises(deploy.DeploymentError):
        deploy.operate(area, "install")
    assert tree(area) == {"foreign": b"Foreign root content"}
    body = f"{deploy.SKILL_ROOT}/SKILL.md"
    assert (detached / body).read_bytes() == deploy._sources(deploy._core())[body]
    assert (detached / "System/workspace.yaml").is_file()


@pytest.mark.skipif(os.name != "posix", reason="Windows retains directory ownership handles")
def test_created_directory_substitution_before_handoff_never_receives_assets(area, monkeypatch):
    anchor = creation_anchor(monkeypatch)
    original = anchor.create_directory
    leaf = area / deploy.SKILL_ROOT
    detached = leaf.with_name("detached-created-directory")

    def substitute(self, name, *args, **kwargs):
        proof = original(self, name, *args, **kwargs)
        if str(name) == "apparatus-mailbox-survey":
            leaf.rename(detached)
            leaf.mkdir()
            (leaf / "foreign").write_bytes(b"Concurrent foreign directory")
        return proof

    monkeypatch.setattr(anchor, "create_directory", substitute)
    with pytest.raises(deploy.DeploymentError) as failure:
        deploy.operate(area, "install")
    assert failure.value.code == 2
    assert "Installation may be partial" in str(failure.value)
    assert tree(leaf) == {"foreign": b"Concurrent foreign directory"}
    assert not list(detached.iterdir())


def test_former_final_unlink_boundary_is_never_reached(area, monkeypatch, capsys):
    anchor = creation_anchor(monkeypatch)
    original_create = anchor.create_file
    original_unlink = os.unlink
    body = area / deploy.SKILL_ROOT / "SKILL.md"
    deletions = []
    def fail(self, name, *args, **kwargs):
        if str(name) == "report-format.md":
            raise OSError("Injected second asset failure")
        return original_create(self, name, *args, **kwargs)
    def raced_unlink(name, *args, **kwargs):
        deletions.append(str(name))
        if str(name) == "SKILL.md":
            # This recreates the former last-check-to-unlink substitution gap.
            # The hardened module must never enter this boundary on failure.
            substitute = body.with_name("foreign.tmp")
            substitute.write_bytes(b"Concurrent foreign replacement")
            os.replace(substitute, body)
        return original_unlink(name, *args, **kwargs)
    monkeypatch.setattr(anchor, "create_file", fail)
    monkeypatch.setattr(os, "unlink", raced_unlink)
    # Preserve core's capability inventory while intercepting the syscall.
    monkeypatch.setattr(os, "supports_dir_fd", os.supports_dir_fd | {raced_unlink})
    assert main(["install", str(area)]) == 2
    assert deletions == []
    expected = deploy._sources(deploy._core())[f"{deploy.SKILL_ROOT}/SKILL.md"]
    assert body.read_bytes() == expected
    output = capsys.readouterr().err
    assert "Installation may be partial" in output
    assert "Do not use the Skill until status reports current" in output
    assert not any(word in output.lower() for word in ("rollback", "cleanup", "atomic"))


@pytest.mark.skipif(os.name != "posix", reason="Module POSIX write adapter")
@pytest.mark.parametrize("fault", ["partial-write", "zero-write", "sync"])
def test_low_level_write_failure_preserves_bytes_and_retry_contract(area, monkeypatch, capsys, fault):
    creation_anchor(monkeypatch)
    original_write = os.write
    original_sync = os.fsync
    written = False
    body = area / deploy.SKILL_ROOT / "SKILL.md"
    expected = deploy._sources(deploy._core())[f"{deploy.SKILL_ROOT}/SKILL.md"]
    def fail_write(descriptor, content):
        nonlocal written
        if fault == "zero-write":
            return 0
        if fault == "partial-write":
            if written:
                raise OSError("Injected partial write failure")
            written = True
            return original_write(descriptor, content[:12])
        return original_write(descriptor, content)
    def fail_sync(descriptor):
        if fault == "sync":
            raise OSError("Injected sync failure")
        return original_sync(descriptor)
    def no_deletion(*args, **kwargs):
        raise AssertionError("Failed module installation attempted deletion")
    monkeypatch.setattr(os, "write", fail_write)
    monkeypatch.setattr(os, "fsync", fail_sync)
    monkeypatch.setattr(os, "unlink", no_deletion)
    monkeypatch.setattr(os, "rmdir", no_deletion)
    monkeypatch.setattr(os, "supports_dir_fd", os.supports_dir_fd | {no_deletion})
    assert main(["install", str(area)]) == 2
    assert "Installation may be partial" in capsys.readouterr().err
    retained = body.read_bytes()
    assert retained == (expected if fault == "sync" else b"" if fault == "zero-write" else expected[:12])
    assert (body.parent / "references").is_dir()
    before = body.stat().st_mtime_ns
    monkeypatch.setattr(os, "write", original_write)
    monkeypatch.setattr(os, "fsync", original_sync)
    if fault == "sync":
        assert deploy.operate(area)["state"] == "partial"
        assert main(["repair", str(area)]) == 0
    else:
        assert deploy.operate(area)["state"] == "conflict"
        assert main(["repair", str(area)]) == 1
        assert body.read_bytes() == retained
    assert body.stat().st_mtime_ns == before


@pytest.mark.skipif(os.name != "posix", reason="POSIX retained-parent substitution")
def test_low_level_detached_file_parent_preserves_both_occupants(area, monkeypatch, capsys):
    anchor = creation_anchor(monkeypatch)
    original = anchor._write_at
    leaf = area / deploy.SKILL_ROOT
    detached = leaf.with_name("detached-written-leaf")
    def detach(parent, name, content, mode):
        identity = original(parent, name, content, mode)
        if str(name) == "SKILL.md":
            leaf.rename(detached)
            leaf.mkdir()
            (leaf / "SKILL.md").write_bytes(b"Concurrent foreign replacement")
        return identity
    monkeypatch.setattr(anchor, "_write_at", staticmethod(detach))
    assert main(["install", str(area)]) == 2
    assert "Installation may be partial" in capsys.readouterr().err
    assert (leaf / "SKILL.md").read_bytes() == b"Concurrent foreign replacement"
    expected = deploy._sources(deploy._core())[f"{deploy.SKILL_ROOT}/SKILL.md"]
    assert (detached / "SKILL.md").read_bytes() == expected
    assert not (detached / "references/report-format.md").exists()
    assert deploy.operate(area)["state"] == "conflict"


@pytest.mark.skipif(os.name != "posix", reason="POSIX retained-parent substitution")
def test_low_level_detached_directory_parent_preserves_created_directory(area, monkeypatch, capsys):
    creation_anchor(monkeypatch)
    original = os.mkdir
    leaf = area / deploy.SKILL_ROOT
    detached = leaf.with_name("detached-directory-parent")
    def detach(name, *args, **kwargs):
        original(name, *args, **kwargs)
        if str(name) == "references":
            leaf.rename(detached)
            leaf.mkdir()
            (leaf / "foreign").write_bytes(b"Concurrent foreign directory")
    monkeypatch.setattr(os, "mkdir", detach)
    assert main(["install", str(area)]) == 2
    assert "Installation may be partial" in capsys.readouterr().err
    assert tree(leaf) == {"foreign": b"Concurrent foreign directory"}
    assert (detached / "references").is_dir()
    assert not list((detached / "references").iterdir())
    assert not (detached / "SKILL.md").exists()


def test_failed_child_handoff_leaves_new_directory_for_retry(area, monkeypatch, capsys):
    anchor = creation_anchor(monkeypatch)
    original = anchor.open_directory
    failed = False
    def fail(self, relative, **kwargs):
        nonlocal failed
        if str(relative) == "apparatus-mailbox-survey" and not failed:
            failed = True
            raise OSError("Injected handoff failure")
        return original(self, relative, **kwargs)
    monkeypatch.setattr(anchor, "open_directory", fail)
    assert main(["install", str(area)]) == 2
    assert "Installation may be partial" in capsys.readouterr().err
    leaf = area / deploy.SKILL_ROOT
    assert leaf.is_dir()
    assert not list(leaf.iterdir())
    assert deploy.operate(area)["state"] == "absent"
    monkeypatch.setattr(anchor, "open_directory", original)
    assert main(["repair", str(area)]) == 0
    assert deploy.operate(area)["state"] == "current"
