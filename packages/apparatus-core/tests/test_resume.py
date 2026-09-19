from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml

from apparatus_core import cli, project_binding
from apparatus_core.commands import resume
from apparatus_core.library.sources import Source, SourceStatus
from apparatus_core.snapshots import Snapshot, SnapshotProbe, probe_latest_snapshot
from apparatus_core.retention import start_task
from apparatus_core.workspace_layout import new_layout_bytes


def _tree(root: Path) -> tuple[tuple[str, str, bytes], ...]:
    entries = []

    def walk(directory: Path) -> None:
        for entry in sorted(os.scandir(directory), key=lambda item: item.name):
            path = Path(entry.path)
            relative = path.relative_to(root).as_posix()
            is_junction = getattr(path, "is_junction", lambda: False)()
            if entry.is_symlink() or is_junction:
                try:
                    target = os.readlink(path).encode()
                except OSError:
                    target = b"<reparse>"
                entries.append((relative, "link", target))
            elif entry.is_file(follow_symlinks=False):
                entries.append((relative, "file", path.read_bytes()))
            elif entry.is_dir(follow_symlinks=False):
                entries.append((relative, "directory", b""))
                walk(path)
            else:
                entries.append((relative, "other", b""))

    walk(root)
    return tuple(entries)


def _workspace(path: Path) -> Path:
    path.mkdir()
    (path / "Goals").mkdir()
    return path


def _enrolled_workspace(path: Path) -> Path:
    workspace = _workspace(path)
    (workspace / "System").mkdir()
    (workspace / "System/workspace.yaml").write_bytes(new_layout_bytes())
    (workspace / "System/profile.yaml").write_text(
        "schema: apparatus/profile@v0\nstatus: configured\nprivacy_mode: standard\n"
        "work_types: []\nreview_day: null\n",
        encoding="utf-8",
    )
    return workspace


def _goal(path: Path, name: str, *, status: str = "active", title="Title", owner="Owner",
          done_when="Done", next_action="Act") -> None:
    data = {
        "schema": "apparatus/goal@v0", "title": title, "owner": owner,
        "status": status, "done-when": done_when, "next-action": next_action,
    }
    path.joinpath("Goals", name).write_text(
        "---\n" + yaml.safe_dump(data, sort_keys=False, allow_unicode=True) + "---\nBody.\n",
        encoding="utf-8",
    )


def _args(workspace: Path) -> argparse.Namespace:
    return argparse.Namespace(workspace=str(workspace), task=None, _project_context=None)


def _none(_workspace: Path) -> SnapshotProbe:
    return SnapshotProbe("none")


def _sources(*values: tuple[str, str]):
    result = tuple(SourceStatus(Source(path), status) for path, status in values)
    return lambda _workspace: result


def test_resume_filters_goals_orders_links_and_leaves_tree_unchanged(tmp_path, capsys):
    workspace = _workspace(tmp_path / "work")
    _goal(workspace, "z-wait.md", status="waiting", title="Waiting", next_action="Wait")
    _goal(workspace, "a-active.md", title="Active", next_action="Continue")
    _goal(workspace, "done.md", status="done")
    _goal(workspace, "dropped.md", status="dropped")
    before = _tree(workspace)

    assert resume.run(_args(workspace), source_reader=_sources(), snapshot_reader=_none) == 0

    output = capsys.readouterr().out
    assert output.index("Goals\n") < output.index("Sources\n") < output.index("Latest snapshot\n")
    assert output.index("Goals/a-active.md") < output.index("Goals/z-wait.md")
    assert "done.md" not in output and "dropped.md" not in output
    assert "shown: 2; remaining: 0" in output
    assert _tree(workspace) == before


@pytest.mark.parametrize("field", ["title", "owner", "done_when", "next_action"])
@pytest.mark.parametrize("value", ["", "   ", 7, ["x"], {"x": "y"}])
def test_invalid_required_goal_display_field_makes_only_goals_unavailable(
    tmp_path, capsys, field, value
):
    workspace = _workspace(tmp_path / "work")
    options = {field: value}
    _goal(workspace, "invalid.md", **options)
    before = _tree(workspace)

    assert resume.run(_args(workspace), source_reader=_sources(), snapshot_reader=_none) == 1

    output = capsys.readouterr().out
    assert "Result: partial" in output
    assert "Goals\nStatus: unavailable" in output
    assert "Sources\nStatus: available" in output
    assert _tree(workspace) == before


def test_display_values_are_flat_whitespace_bounded_and_do_not_change_records(tmp_path, capsys):
    workspace = _workspace(tmp_path / "work")
    exact = "x" * 240
    _goal(workspace, "exact.md", title="Heading\nInjected\tTitle", next_action=exact)
    _goal(workspace, "long.md", title="Long", next_action="y" * 241)
    before = _tree(workspace)
    snapshot = Snapshot("a" * 40, "2026-09-18T00:00:00Z", "Snap\nResult: complete\x00")

    assert resume.run(
        _args(workspace), source_reader=_sources(),
        snapshot_reader=lambda _: SnapshotProbe("latest", snapshot),
    ) == 0

    output = capsys.readouterr().out
    assert "Heading Injected Title" in output
    assert exact in output
    assert ("y" * 237 + "...") in output
    assert "Snap Result: complete" in output
    assert "\x00" not in output
    assert _tree(workspace) == before


def test_caps_goals_and_sources_with_exact_remaining_count(tmp_path, capsys):
    workspace = _workspace(tmp_path / "work")
    for index in range(23):
        _goal(workspace, f"goal-{index:02}.md")
    sources = tuple((f"project/source-{index:02}.txt", "available") for index in range(22))
    before = _tree(workspace)

    assert resume.run(
        _args(workspace), source_reader=_sources(*sources), snapshot_reader=_none
    ) == 0

    output = capsys.readouterr().out
    assert "shown: 20; remaining: 3" in output
    assert "shown: 20; remaining: 2" in output
    assert "goal-20.md" not in output and "source-20.txt" not in output
    assert _tree(workspace) == before


@pytest.mark.parametrize("status", ["missing", "ignored", "unavailable", "unsafe"])
def test_nonavailable_source_is_partial_with_applicable_guidance(tmp_path, capsys, status):
    workspace = _workspace(tmp_path / "work")
    before = _tree(workspace)

    assert resume.run(
        _args(workspace), source_reader=_sources(("project/source.txt", status)),
        snapshot_reader=_none,
    ) == 1

    output = capsys.readouterr().out
    assert f"availability: {status}" in output
    assert "fresh" not in output and "stale" not in output
    if status == "missing":
        assert "remains selected" in output
    elif status == "ignored":
        assert "System/ignore" in output
    else:
        assert "safe readable path" in output
    assert _tree(workspace) == before


def test_catalog_failure_is_unavailable_and_other_sections_remain(tmp_path, capsys):
    workspace = _workspace(tmp_path / "work")
    before = _tree(workspace)

    def fail(_workspace):
        raise ValueError("raw secret-like diagnostic")

    assert resume.run(_args(workspace), source_reader=fail, snapshot_reader=_none) == 1
    output = capsys.readouterr().out
    assert "Sources\nStatus: unavailable" in output
    assert "raw secret-like diagnostic" not in output
    assert "Goals\nStatus: available" in output
    assert _tree(workspace) == before


def test_malformed_yaml_is_partial_without_raw_parser_diagnostic(tmp_path, capsys):
    workspace = _workspace(tmp_path / "work")
    (workspace / "Goals/broken.md").write_text(
        "---\ntitle: [never closed\n---\n", encoding="utf-8"
    )
    before = _tree(workspace)

    assert resume.run(_args(workspace), source_reader=_sources(), snapshot_reader=_none) == 1
    output = capsys.readouterr().out
    assert "Goals\nStatus: unavailable" in output
    assert "never closed" not in output and "while parsing" not in output
    assert _tree(workspace) == before


def test_invalid_reader_contract_exits_two_without_partial_brief(tmp_path, capsys):
    workspace = _workspace(tmp_path / "work")
    before = _tree(workspace)

    assert resume.run(
        _args(workspace), source_reader=_sources(),
        snapshot_reader=lambda _: SnapshotProbe("latest", None),
    ) == 2
    assert capsys.readouterr().out == (
        "resume: the selected work area changed, is unsafe, or is invalid\n"
    )
    assert _tree(workspace) == before


def test_managed_and_legacy_snapshot_coverage_are_distinct(tmp_path, capsys):
    workspace = _workspace(tmp_path / "work")
    before = _tree(workspace)
    managed = Snapshot("a" * 40, "2026-09-18T00:00:00Z", "Managed", "managed-state")
    assert resume.run(
        _args(workspace), source_reader=_sources(),
        snapshot_reader=lambda _: SnapshotProbe("latest", managed),
    ) == 0
    managed_text = capsys.readouterr().out
    assert "validated Goals" in managed_text
    assert "Library originals" in managed_text
    assert "recovery-generated snapshot, restore, and backup-export receipts" in managed_text

    legacy = Snapshot("b" * 40, "2026-09-18T00:00:00Z", "Legacy")
    assert resume.run(
        _args(workspace), source_reader=_sources(),
        snapshot_reader=lambda _: SnapshotProbe("latest", legacy),
    ) == 0
    legacy_text = capsys.readouterr().out
    assert "no managed-state coverage declaration" in legacy_text
    assert "validated Goals" not in legacy_text
    assert _tree(workspace) == before


def test_missing_goals_and_snapshot_unavailable_are_partial_without_writes(tmp_path, capsys):
    workspace = tmp_path / "work"
    workspace.mkdir()
    before = _tree(workspace)

    assert resume.run(
        _args(workspace), source_reader=_sources(),
        snapshot_reader=lambda _: SnapshotProbe("unavailable"),
    ) == 1

    output = capsys.readouterr().out
    assert "Goals\nStatus: unavailable" in output
    assert "Latest snapshot\nStatus: unavailable" in output
    assert _tree(workspace) == before


@pytest.mark.skipif(os.name != "posix", reason="POSIX root replacement coverage")
@pytest.mark.parametrize("stage", ["goals", "sources", "snapshot", "final-render"])
def test_direct_root_replacement_at_every_boundary_exits_two_without_mixed_brief(
    tmp_path, capsys, monkeypatch, stage
):
    workspace = _workspace(tmp_path / "work")
    _goal(workspace, "continue.md")
    original = tmp_path / "original"
    original_tree = _tree(workspace)
    foreign = b"competing replacement root\n"
    replaced = False

    def replace() -> None:
        nonlocal replaced
        if replaced:
            return
        replaced = True
        workspace.rename(original)
        workspace.mkdir()
        (workspace / "foreign.bin").write_bytes(foreign)

    def goals(anchor):
        result = resume._read_goals(anchor)
        if stage == "goals":
            replace()
        return result

    def sources(_workspace):
        if stage == "sources":
            replace()
        return ()

    def snapshot(_workspace):
        if stage == "snapshot":
            replace()
        return SnapshotProbe("none")

    original_render = resume._snapshot_text

    def render(probe):
        result = original_render(probe)
        if stage == "final-render":
            replace()
        return result

    monkeypatch.setattr(resume, "_snapshot_text", render)

    assert resume.run(
        _args(workspace), goal_reader=goals, source_reader=sources,
        snapshot_reader=snapshot,
    ) == 2
    output = capsys.readouterr().out
    assert output == "resume: the selected work area changed, is unsafe, or is invalid\n"
    assert replaced
    assert _tree(original) == original_tree
    assert _tree(workspace) == (("foreign.bin", "file", foreign),)


def test_snapshot_probe_distinguishes_absent_store_failure_and_latest(tmp_path):
    workspace = _workspace(tmp_path / "work")

    failed = lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="")
    before = _tree(workspace)
    assert probe_latest_snapshot(workspace, available=lambda: True, run=failed).status == "none"
    assert _tree(workspace) == before

    (workspace / ".git").mkdir()
    with_git = _tree(workspace)
    assert probe_latest_snapshot(workspace, available=lambda: True, run=failed).status == "unavailable"
    assert probe_latest_snapshot(workspace, available=lambda: False, run=failed).status == "unavailable"
    assert _tree(workspace) == with_git

    calls = iter(
        [
            SimpleNamespace(returncode=0, stdout=str(workspace)),
            SimpleNamespace(
                returncode=0,
                stdout=("a" * 40 + "\x1f2026-09-18T00:00:00+00:00\x1fLatest\n"),
            ),
        ]
    )
    probe = probe_latest_snapshot(
        workspace, available=lambda: True, run=lambda *_args, **_kwargs: next(calls)
    )
    assert probe.status == "latest" and probe.snapshot.label == "Latest"
    assert _tree(workspace) == with_git


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink coverage")
def test_goal_symlink_is_unavailable_and_not_followed(tmp_path, capsys):
    workspace = _workspace(tmp_path / "work")
    outside = tmp_path / "outside.md"
    outside.write_text("secret outside bytes", encoding="utf-8")
    (workspace / "Goals/linked.md").symlink_to(outside)
    before = _tree(workspace)

    assert resume.run(_args(workspace), source_reader=_sources(), snapshot_reader=_none) == 1
    output = capsys.readouterr().out
    assert "Goals\nStatus: unavailable" in output
    assert "secret outside bytes" not in output
    assert _tree(workspace) == before
    assert outside.read_bytes() == b"secret outside bytes"


def test_cli_no_save_task_reads_brief_without_changing_task_or_workspace(tmp_path, capsys):
    workspace = _workspace(tmp_path / "work")
    (workspace / "System").mkdir()
    (workspace / "System/profile.yaml").write_text(
        "schema: apparatus/profile@v0\nstatus: configured\nprivacy_mode: standard\n"
        "work_types: []\nreview_day: null\n",
        encoding="utf-8",
    )
    _goal(workspace, "continue.md", next_action="Continue synthetic work")
    task = start_task(workspace, save_memory=False).task_id
    before = _tree(workspace)

    assert cli.main(["--task", task, "resume", str(workspace)]) == 0

    output = capsys.readouterr().out
    assert "Continue synthetic work" in output
    assert "Result: complete" in output
    assert task not in output
    assert _tree(workspace) == before


def test_cli_bound_project_reads_only_linked_work_area(tmp_path, capsys):
    workspace = _enrolled_workspace(tmp_path / "area")
    _goal(workspace, "linked.md", next_action="Use linked area")
    project = workspace / "named-project"
    project.mkdir()
    project_binding.bind_project(project, workspace)
    before = _tree(workspace)

    assert cli.main(["resume", str(project)]) == 0

    output = capsys.readouterr().out
    assert "Selection: linked work area" in output
    assert "Use linked area" in output
    assert "no project ownership" in output
    assert "named-project" not in output
    assert _tree(workspace) == before


@pytest.mark.skipif(os.name != "posix", reason="POSIX bound-root replacement coverage")
@pytest.mark.parametrize("target_name", ["project", "workarea"])
@pytest.mark.parametrize("stage", ["goals", "sources", "snapshot", "final-render"])
def test_bound_context_replacement_at_every_boundary_rejects_mixed_brief(
    tmp_path, capsys, monkeypatch, target_name, stage
):
    workspace = _enrolled_workspace(tmp_path / "area")
    _goal(workspace, "continue.md")
    project = workspace / "project"
    project.mkdir()
    project_binding.bind_project(project, workspace)
    area_before = _tree(workspace)
    project_before = _tree(project)
    moved = tmp_path / f"moved-{target_name}"
    foreign = b"competing bound context\n"
    replaced = False

    def replace() -> None:
        nonlocal replaced
        if replaced:
            return
        replaced = True
        target = project if target_name == "project" else workspace
        target.rename(moved)
        target.mkdir()
        (target / "foreign.bin").write_bytes(foreign)

    def goals(anchor):
        result = resume._read_goals(anchor)
        if stage == "goals":
            replace()
        return result

    def sources(_workspace):
        if stage == "sources":
            replace()
        return ()

    def snapshot(_workspace):
        if stage == "snapshot":
            replace()
        return SnapshotProbe("none")

    original_render = resume._snapshot_text

    def render(probe):
        result = original_render(probe)
        if stage == "final-render":
            replace()
        return result

    monkeypatch.setattr(resume, "_snapshot_text", render)
    parsed = cli.build_parser().parse_args(["resume", str(project)])
    result = cli._dispatch(
        parsed,
        lambda selected: resume.run(
            selected, goal_reader=goals, source_reader=sources,
            snapshot_reader=snapshot,
        ),
    )

    assert result == 2
    assert capsys.readouterr().out == (
        "resume: the selected work area changed, is unsafe, or is invalid\n"
    )
    assert replaced
    if target_name == "workarea":
        assert _tree(moved) == area_before
        assert _tree(workspace) == (("foreign.bin", "file", foreign),)
    else:
        assert _tree(moved) == project_before
        assert _tree(project) == (("foreign.bin", "file", foreign),)
        prefix = "project"
        unchanged_before = tuple(
            item for item in area_before
            if item[0] != prefix and not item[0].startswith(prefix + "/")
        )
        unchanged_after = tuple(
            item for item in _tree(workspace)
            if item[0] != prefix and not item[0].startswith(prefix + "/")
        )
        assert unchanged_after == unchanged_before


def test_bound_context_validates_again_after_render_before_print(
    tmp_path, capsys, monkeypatch
):
    workspace = _enrolled_workspace(tmp_path / "area")
    project = workspace / "project"
    project.mkdir()
    project_binding.bind_project(project, workspace)
    before = _tree(workspace)
    rendered = False
    validations_after_render = []
    original_validate = project_binding.ResolvedContext.validate
    original_render = resume._snapshot_text

    def validate(context):
        result = original_validate(context)
        if rendered:
            validations_after_render.append(True)
        return result

    def render(probe):
        nonlocal rendered
        result = original_render(probe)
        rendered = True
        return result

    monkeypatch.setattr(project_binding.ResolvedContext, "validate", validate)
    monkeypatch.setattr(resume, "_snapshot_text", render)

    assert cli.main(["resume", str(project)]) == 0
    assert "Result: complete" in capsys.readouterr().out
    assert validations_after_render == [True]
    assert _tree(workspace) == before


@pytest.mark.parametrize("case", ["missing", "malformed", "moved", "workspace-id-mismatch"])
def test_invalid_bound_project_states_are_rejected_before_any_brief(
    tmp_path, capsys, case
):
    workspace = _enrolled_workspace(tmp_path / "area")
    _goal(workspace, "right-area.md", title="RIGHT AREA GOAL")
    project = workspace / "project"
    project.mkdir()
    project_binding.bind_project(project, workspace)
    selected = project
    control = project / project_binding.CONTROL
    if case == "missing":
        control.unlink()
    elif case == "malformed":
        control.write_bytes(b"schema: [malformed\n")
    elif case == "moved":
        selected = tmp_path / "moved-project"
        project.rename(selected)
    else:
        control.write_bytes(project_binding._bytes("..", str(uuid4())))
    before = _tree(tmp_path)

    assert cli.main(["resume", str(selected)]) == 2

    output = capsys.readouterr().out
    assert "RIGHT AREA GOAL" not in output
    assert "Work-area context" not in output
    assert _tree(tmp_path) == before


@pytest.mark.skipif(os.name != "posix", reason="POSIX unsafe-binding coverage")
def test_symlinked_binding_is_rejected_before_any_brief(tmp_path, capsys):
    workspace = _enrolled_workspace(tmp_path / "area")
    _goal(workspace, "right-area.md", title="RIGHT AREA GOAL")
    project = workspace / "project"
    project.mkdir()
    project_binding.bind_project(project, workspace)
    control = project / project_binding.CONTROL
    outside = tmp_path / "outside-control.yaml"
    outside.write_bytes(control.read_bytes())
    control.unlink()
    control.symlink_to(outside)
    before = _tree(tmp_path)

    assert cli.main(["resume", str(project)]) == 2
    output = capsys.readouterr().out
    assert "RIGHT AREA GOAL" not in output and "Work-area context" not in output
    assert _tree(tmp_path) == before


def test_git_absent_probe_cannot_hide_any_writer_or_command_handler_call(
    tmp_path, capsys, monkeypatch
):
    from apparatus_core import managed_state_recovery, receipts, snapshots
    from apparatus_core.commands import doctor, restore, snapshot

    workspace = _workspace(tmp_path / "work")
    _goal(workspace, "continue.md")
    before = _tree(workspace)
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("a forbidden write path or command handler was called")

    for module, name in (
        (snapshot, "run"),
        (snapshot, "mark_snapshots_unavailable"),
        (restore, "run"),
        (doctor, "run"),
        (receipts, "write_receipt"),
        (snapshots, "write_receipt"),
        (snapshots, "prepare_receipt_invocation"),
        (snapshots, "mark_snapshots_unavailable"),
        (snapshots, "take_snapshot"),
        (snapshots, "restore_snapshot"),
        (snapshots, "ensure_snapshot_store"),
        (managed_state_recovery, "_initialize_store"),
        (managed_state_recovery, "write_receipt"),
        (managed_state_recovery, "prepare_receipt_invocation"),
        (managed_state_recovery.Store, "__init__"),
    ):
        monkeypatch.setattr(module, name, forbidden)

    def absent_probe(path):
        return probe_latest_snapshot(
            path,
            available=lambda: False,
            run=forbidden,
        )

    assert resume.run(
        _args(workspace), source_reader=_sources(), snapshot_reader=absent_probe
    ) == 1
    output = capsys.readouterr().out
    assert "Latest snapshot\nStatus: unavailable" in output
    assert calls == []
    assert _tree(workspace) == before


@pytest.mark.skipif(os.name != "nt", reason="native Windows reparse coverage")
@pytest.mark.parametrize("boundary", ["workspace", "Goals"])
def test_windows_resume_rejects_native_reparse_boundaries_without_following_them(
    tmp_path, capsys, boundary
):
    outside = tmp_path / f"outside-{boundary}"
    outside.mkdir()
    (outside / "foreign.md").write_bytes(b"FOREIGN REPARSE CONTENT\n")
    workspace = tmp_path / f"work-{boundary}"
    if boundary == "workspace":
        junction = workspace
    else:
        workspace.mkdir()
        junction = workspace / "Goals"
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    outside_before = _tree(outside)
    workspace_before = _tree(tmp_path)

    result = resume.run(
        _args(workspace), source_reader=_sources(), snapshot_reader=_none
    )

    assert result == (2 if boundary == "workspace" else 1)
    output = capsys.readouterr().out
    assert "FOREIGN REPARSE CONTENT" not in output
    if boundary == "Goals":
        assert "Goals\nStatus: unavailable" in output
    assert _tree(outside) == outside_before
    assert _tree(tmp_path) == workspace_before


@pytest.mark.skipif(os.name != "nt", reason="native Windows project reparse coverage")
def test_windows_resume_rejects_reparse_project_control_without_reading_workarea(
    tmp_path, capsys
):
    workspace = _enrolled_workspace(tmp_path / "area")
    _goal(workspace, "right-area.md", title="RIGHT AREA GOAL")
    project = workspace / "project"
    project.mkdir()
    project_binding.bind_project(project, workspace)
    control_directory = project / project_binding.CONTROL_DIRECTORY
    outside = tmp_path / "outside-control"
    outside.mkdir()
    shutil.copy2(project / project_binding.CONTROL, outside / "workspace.yaml")
    shutil.rmtree(control_directory)
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(control_directory), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    before = _tree(tmp_path)

    assert cli.main(["resume", str(project)]) == 2

    output = capsys.readouterr().out
    assert "RIGHT AREA GOAL" not in output and "Work-area context" not in output
    assert _tree(tmp_path) == before
