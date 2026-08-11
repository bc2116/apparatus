from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess

import pytest
import yaml

from apparatus_core import machine_report
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.machine_report import render_machine_report, write_machine_report


def _detections(*, git_present=True, risk=False):
    return {
        "os": {"name": "Darwin", "version": "15.0"},
        "python": {"version": "3.12.4", "executable": "/python"},
        "git": {"present": git_present, "version": "git version 2.50" if git_present else None},
        "uv": {"present": True, "version": "uv 0.9"},
        "ai_apps": ["Cursor"],
        "sync_redirection": {
            "at_risk": risk,
            "reason": "The path contains a OneDrive sync-location marker." if risk else "No common sync-redirection marker was found.",
        },
        "workspace": "/Projects/Apparatus",
    }


def _clock():
    return datetime(2026, 8, 9, 12, 34, 56, tzinfo=timezone.utc)


def test_report_is_parseable_yaml_with_stable_key_order_and_plain_language_body():
    report = render_machine_report(_detections(), clock=_clock)
    frontmatter = report.split("---", 2)[1]
    data = yaml.safe_load(frontmatter)
    assert list(data) == [
        "generated_at", "generator", "version", "os", "python", "git", "uv", "snapshots",
        "detected_ai_apps", "sync_redirection",
    ]
    assert data["generated_at"] == "2026-08-09T12:34:56Z"
    assert data["snapshots"] == "available"
    assert "Operating system: Darwin 15.0." in report
    assert "repository" not in report.casefold()


def test_report_uses_null_and_unavailable_when_git_is_missing():
    report = render_machine_report(_detections(git_present=False), clock=_clock)
    data = yaml.safe_load(report.split("---", 2)[1])
    assert data["git"] is None
    assert data["snapshots"] == "unavailable"


def test_write_machine_report_creates_system_and_is_idempotent(tmp_path):
    first = write_machine_report(tmp_path, _detections(), clock=_clock)
    initial = first.read_text(encoding="utf-8")
    second = write_machine_report(tmp_path, _detections(), clock=_clock)
    assert second == tmp_path / "System/machine-report.md"
    assert second.read_text(encoding="utf-8") == initial


@pytest.mark.skipif(os.name != "posix", reason="POSIX descriptor regression")
@pytest.mark.parametrize("redirect", ["System", "System/machine-report.md"])
def test_report_rejects_symlink_boundaries_without_touching_outside(tmp_path, redirect):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    foreign = outside / "foreign.md"
    foreign.write_text("foreign\n", encoding="utf-8")

    if redirect == "System":
        (workspace / "System").symlink_to(outside, target_is_directory=True)
    else:
        (workspace / "System").mkdir()
        (workspace / "System/machine-report.md").symlink_to(foreign)

    with pytest.raises(OSError):
        write_machine_report(workspace, _detections(), clock=_clock)

    assert foreign.read_text(encoding="utf-8") == "foreign\n"
    assert sorted(path.name for path in outside.iterdir()) == ["foreign.md"]


@pytest.mark.skipif(os.name != "posix", reason="POSIX descriptor regression")
def test_report_rejects_system_substitution_during_anchored_selection(
    monkeypatch, tmp_path
):
    workspace = tmp_path / "workspace"
    system = workspace / "System"
    system.mkdir(parents=True)
    displaced = tmp_path / "displaced-system"
    foreign = b"foreign\n"
    original_create = WorkspaceAnchor.create_file

    def substitute_after_marker(anchor, relative, content, mode=0o600, **kwargs):
        owned = original_create(anchor, relative, content, mode, **kwargs)
        if Path(relative).name.startswith(".apparatus-machine-report-"):
            system.rename(displaced)
            system.mkdir()
            (system / "machine-report.md").write_bytes(foreign)
        return owned

    monkeypatch.setattr(machine_report.WorkspaceAnchor, "create_file", substitute_after_marker)

    with pytest.raises(OSError, match="System directory changed"):
        write_machine_report(workspace, _detections(), clock=_clock)

    assert (system / "machine-report.md").read_bytes() == foreign
    assert not list(displaced.glob(".apparatus-machine-report-*.tmp"))


@pytest.mark.skipif(os.name != "posix", reason="POSIX descriptor regression")
@pytest.mark.parametrize("replaced", ["root", "System"])
def test_report_rolls_back_when_destination_is_replaced_after_create(
    monkeypatch, tmp_path, replaced
):
    workspace = tmp_path / "workspace"
    system = workspace / "System"
    system.mkdir(parents=True)
    displaced = tmp_path / f"displaced-{replaced}"
    foreign = b"foreign\n"
    original_create = WorkspaceAnchor.create_file

    def replace_after_create(anchor, relative, content, mode=0o600, **kwargs):
        owned = original_create(anchor, relative, content, mode, **kwargs)
        if Path(relative) != Path("machine-report.md"):
            return owned
        if replaced == "root":
            workspace.rename(displaced)
            (workspace / "System").mkdir(parents=True)
            (workspace / "System/machine-report.md").write_bytes(foreign)
        else:
            system.rename(displaced)
            system.mkdir()
            (system / "machine-report.md").write_bytes(foreign)
        return owned

    monkeypatch.setattr(machine_report.WorkspaceAnchor, "create_file", replace_after_create)

    with pytest.raises(OSError, match="destination changed"):
        write_machine_report(workspace, _detections(), clock=_clock)

    assert (workspace / "System/machine-report.md").read_bytes() == foreign
    moved_report = (
        displaced / "System/machine-report.md"
        if replaced == "root"
        else displaced / "machine-report.md"
    )
    assert not moved_report.exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX descriptor regression")
def test_report_restores_original_when_system_is_replaced_after_update(
    monkeypatch, tmp_path
):
    workspace = tmp_path / "workspace"
    system = workspace / "System"
    system.mkdir(parents=True)
    report = system / "machine-report.md"
    original = b"original\n"
    foreign = b"foreign\n"
    report.write_bytes(original)
    displaced = tmp_path / "displaced-system"
    original_replace = WorkspaceAnchor.replace_if_unchanged

    def replace_system_after_publish(anchor, *args, **kwargs):
        transaction = original_replace(anchor, *args, **kwargs)
        system.rename(displaced)
        system.mkdir()
        (system / "machine-report.md").write_bytes(foreign)
        return transaction

    monkeypatch.setattr(
        machine_report.WorkspaceAnchor,
        "replace_if_unchanged",
        replace_system_after_publish,
    )

    with pytest.raises(OSError, match="destination changed"):
        write_machine_report(workspace, _detections(), clock=_clock)

    assert report.read_bytes() == foreign
    assert (displaced / "machine-report.md").read_bytes() == original


@pytest.mark.skipif(os.name != "nt", reason="native Windows reparse regression")
def test_windows_report_rejects_workspace_system_and_report_junctions(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    foreign = outside / "foreign.md"
    foreign.write_text("foreign\n", encoding="utf-8")

    for boundary in ("workspace", "System", "machine-report"):
        workspace = tmp_path / f"workspace-{boundary}"
        if boundary == "workspace":
            junction = workspace
        elif boundary == "System":
            workspace.mkdir()
            junction = workspace / "System"
        else:
            (workspace / "System").mkdir(parents=True)
            junction = workspace / "System/machine-report.md"
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        with pytest.raises(OSError):
            write_machine_report(workspace, _detections(), clock=_clock)
        assert foreign.read_text(encoding="utf-8") == "foreign\n"
        assert sorted(path.name for path in outside.iterdir()) == ["foreign.md"]


@pytest.mark.skipif(os.name != "nt", reason="native Windows retained-handle regression")
@pytest.mark.parametrize("boundary", ["workspace", "System"])
def test_windows_report_retained_handles_block_directory_replacement(
    monkeypatch, tmp_path, boundary
):
    workspace = tmp_path / "workspace"
    system = workspace / "System"
    system.mkdir(parents=True)
    attempted = []
    original_create = WorkspaceAnchor.create_file

    def attempt_replacement(anchor, relative, content, mode=0o600, **kwargs):
        owned = original_create(anchor, relative, content, mode, **kwargs)
        if Path(relative) == Path("machine-report.md"):
            source = workspace if boundary == "workspace" else system
            try:
                source.rename(tmp_path / f"replaced-{boundary}")
            except OSError:
                attempted.append("blocked")
            else:  # pragma: no cover - would expose a native containment defect
                attempted.append("replaced")
        return owned

    monkeypatch.setattr(machine_report.WorkspaceAnchor, "create_file", attempt_replacement)

    written = write_machine_report(workspace, _detections(), clock=_clock)

    assert attempted == ["blocked"]
    assert written.is_file()
    assert not (tmp_path / f"replaced-{boundary}").exists()


@pytest.mark.skipif(os.name != "nt", reason="native Windows retained-handle regression")
def test_windows_report_retained_handle_blocks_file_replacement(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    report = workspace / "System/machine-report.md"
    report.parent.mkdir(parents=True)
    report.write_bytes(b"original\n")
    substitute = tmp_path / "substitute.md"
    substitute.write_bytes(b"foreign\n")
    attempted = []
    original_replace = WorkspaceAnchor.replace_if_unchanged

    def attempt_replacement(anchor, *args, **kwargs):
        transaction = original_replace(anchor, *args, **kwargs)
        try:
            os.replace(substitute, report)
        except OSError:
            attempted.append("blocked")
        else:  # pragma: no cover - would expose a native containment defect
            attempted.append("replaced")
        return transaction

    monkeypatch.setattr(
        machine_report.WorkspaceAnchor,
        "replace_if_unchanged",
        attempt_replacement,
    )

    write_machine_report(workspace, _detections(), clock=_clock)

    assert attempted == ["blocked"]
    assert substitute.read_bytes() == b"foreign\n"
    assert b"generated_at" in report.read_bytes()
