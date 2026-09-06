from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from apparatus_core import cli, project_binding as binding
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.workspace_layout import new_layout_bytes


def workarea(path):
    (path / "System").mkdir(parents=True)
    (path / "System/workspace.yaml").write_bytes(new_layout_bytes())
    (path / "System/profile.yaml").write_text(
        "schema: apparatus/profile@v0\nstatus: configured\nprivacy_mode: standard\n"
        "work_types: []\nreview_day: null\n", encoding="utf-8")
    for folder in ("Memory/People", "Memory/Facts", "Memory/Decisions", "Library"):
        (path / folder).mkdir(parents=True)
    return path


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_two_siblings_and_nested_legacy_project_select_one_area_without_copies(tmp_path):
    root = workarea(tmp_path / "area")
    original = root / "Library/source.md"
    original.write_text("One original source", encoding="utf-8")
    for name in ("alpha", "beta", "Projects/old-project"):
        project = root / name
        project.mkdir(parents=True)
        content = b"# Custom instructions\r\nKeep these exact bytes.\r\n"
        (project / "AGENTS.md").write_bytes(content)
        (project / "report.md").write_bytes(b"Finished project work")
        assert binding.bind_project(project, root).changed
        assert (project / "AGENTS.md").read_bytes().startswith(content)
        before = files(project)
        assert not binding.bind_project(project, root).changed
        assert files(project) == before
        with binding.resolve_project_context(project) as context:
            assert context.workspace == root
            assert (context.workspace / "Library/source.md") == original
            context.validate()
        assert not (project / "Library").exists()
        assert (project / "report.md").read_bytes() == b"Finished project work"


def test_missing_pointer_is_repaired_but_customized_block_is_preserved(tmp_path):
    root = workarea(tmp_path / "area")
    project = root / "project"
    project.mkdir()
    binding.bind_project(project, root)
    (project / "AGENTS.md").unlink()
    assert binding.bind_project(project, root).changed
    binding.check_project_pointer(project)
    pointer = project / "AGENTS.md"
    pointer.write_bytes(pointer.read_bytes().replace(b"Read .apparatus", b"Custom .apparatus"))
    before = files(project)
    with pytest.raises(binding.BindingError, match="customized"):
        binding.bind_project(project, root)
    assert files(project) == before


def test_incomplete_or_unknown_extra_pointer_never_becomes_an_owned_noop(tmp_path):
    root = workarea(tmp_path / "area")
    project = root / "project"
    project.mkdir()
    pointer = project / "AGENTS.md"
    pointer.write_bytes(binding.BLOCK_END)
    with pytest.raises(binding.BindingError, match="missing"):
        binding.read_project_binding(project)
    pointer.unlink()
    binding.bind_project(project, root)
    pointer.write_bytes(pointer.read_bytes() + b"<!-- Apparatus project link: future -->\n")
    before = files(project)
    with pytest.raises(binding.BindingError, match="edited or duplicated"):
        binding.bind_project(project, root)
    assert files(project) == before


def test_noop_rechecks_pointer_and_preserves_a_concurrent_edit(tmp_path, monkeypatch):
    root = workarea(tmp_path / "area")
    project = root / "project"
    project.mkdir()
    binding.bind_project(project, root)
    pointer = project / "AGENTS.md"
    concurrent = pointer.read_bytes() + b"\nA concurrent custom instruction.\n"
    original = binding._pointer_content

    def edit_after_planning(content):
        result = original(content)
        pointer.write_bytes(concurrent)
        return result

    monkeypatch.setattr(binding, "_pointer_content", edit_after_planning)
    with pytest.raises(binding.BindingError, match="instructions changed"):
        binding.bind_project(project, root)
    assert pointer.read_bytes() == concurrent


@pytest.mark.parametrize("target", ["Library/project", "Memory/project", "System/project", "Goals/project"])
def test_managed_roots_cannot_be_enrolled_as_projects(tmp_path, target):
    root = workarea(tmp_path / "area")
    project = root / target
    project.mkdir(parents=True)
    before = files(root)
    with pytest.raises(binding.BindingError):
        binding.bind_project(project, root)
    assert files(root) == before


@pytest.mark.parametrize("target", [".git", "project/.git", "project/.git/objects",
                                    ".apparatus", "project/.agents/skills", "project/.claude"])
def test_git_and_app_control_directories_cannot_be_bound(tmp_path, target):
    root = workarea(tmp_path / "area")
    project = root / target
    project.mkdir(parents=True)
    (project / "sentinel").write_bytes(b"Existing metadata stays unchanged.")
    before = files(root)
    with pytest.raises(binding.BindingError, match="control folders"):
        binding.bind_project(project, root)
    assert files(root) == before


@pytest.mark.parametrize("command", ["check", "render", "show", "init"])
def test_special_commands_reject_late_rebinding_without_following_new_area(tmp_path, capsys, command):
    from apparatus_core.commands import check as check_command, render as render_command

    outer = workarea(tmp_path / "outer")
    inner = workarea(outer / "inner")
    project = inner / "project"
    project.mkdir()
    binding.bind_project(project, inner)
    assert cli.main(["task", "start", str(project), "--no-memory"]) == 0
    identifier = json.loads(capsys.readouterr().out)["task_id"]
    arguments = (["project", "show", str(project)] if command == "show" else
                 [command, str(project), *(["--adopt"] if command == "init" else [])])
    args = cli.build_parser().parse_args(["--task", identifier, *arguments])
    selected_handler = args.func
    after_rebind = None

    def unexpected_engine(_workspace):
        pytest.fail("A late binding change reached an engine instead of rejecting the stale context")

    def change_between_selection_and_handler(parsed):
        nonlocal after_rebind
        binding.bind_project(project, outer, replace=True)
        after_rebind = files(outer)
        if command == "check":
            return check_command.run(parsed, engine=unexpected_engine)
        if command == "render":
            return render_command.run(parsed, engine=unexpected_engine)
        return selected_handler(parsed)

    assert cli._dispatch(args, change_between_selection_and_handler) == 2
    assert files(outer) == after_rebind
    assert not (project / "System").exists()
    assert not (outer / "System/tasks").exists()


def test_init_remains_rejected_if_selected_project_binding_is_removed(tmp_path):
    area = workarea(tmp_path / "area")
    project = area / "project"
    project.mkdir()
    binding.bind_project(project, area)
    args = cli.build_parser().parse_args(["init", str(project), "--adopt"])
    handler = args.func

    def remove_before_handler(parsed):
        (project / binding.CONTROL).unlink()
        (project / binding.CONTROL_DIRECTORY).rmdir()
        (project / "AGENTS.md").unlink()
        return handler(parsed)

    assert cli._dispatch(args, remove_before_handler) == 2
    assert list(project.iterdir()) == []


def test_absence_and_lost_controls_never_guess_an_ancestor(tmp_path):
    root = workarea(tmp_path / "area")
    project = root / "project"
    project.mkdir()
    assert binding.read_project_binding(project) is None
    with pytest.raises(binding.BindingError, match="no work-area link"):
        binding.resolve_project_context(project)
    binding.bind_project(project, root)
    (project / binding.CONTROL).unlink()
    with pytest.raises(binding.BindingError, match="missing"):
        binding.read_project_binding(project)
    (project / binding.CONTROL_DIRECTORY).rmdir()
    with pytest.raises(binding.BindingError, match="missing"):
        binding.read_project_binding(project)


@pytest.mark.parametrize("relative", ["/absolute", "C:/area", "\\\\server\\area", "../other", "../", "./..", "..//.."])
def test_control_accepts_only_normalized_parent_components(tmp_path, relative):
    root = workarea(tmp_path / "area")
    project = root / "project"
    (project / binding.CONTROL_DIRECTORY).mkdir(parents=True)
    raw = binding._bytes(relative, str(uuid4()))
    (project / binding.CONTROL).write_bytes(raw)
    with pytest.raises(binding.BindingError, match="closed metadata"):
        binding.read_project_binding(project)
    assert (project / binding.CONTROL).read_bytes() == raw


def test_moved_project_requires_explicit_retarget_and_preserves_instructions(tmp_path):
    old = workarea(tmp_path / "old")
    new = workarea(tmp_path / "new")
    project = old / "project"
    project.mkdir()
    binding.bind_project(project, old)
    pointer = (project / "AGENTS.md").read_bytes()
    moved = new / "project"
    project.rename(moved)
    with pytest.raises(binding.BindingError, match="identity does not match"):
        binding.resolve_project_context(moved)
    with pytest.raises(binding.BindingError, match="--replace"):
        binding.bind_project(moved, new)
    assert binding.bind_project(moved, new, replace=True).changed
    assert (moved / "AGENTS.md").read_bytes() == pointer
    with binding.resolve_project_context(moved) as context:
        assert context.workspace == new


def test_pointer_failure_compensates_control_and_directory(tmp_path, monkeypatch):
    root = workarea(tmp_path / "area")
    project = root / "project"
    project.mkdir()
    original = WorkspaceAnchor.create_file

    def fail(anchor, path, content, *args, **kwargs):
        if anchor.workspace == project and str(path) == "AGENTS.md":
            raise OSError("injected pointer publication failure")
        return original(anchor, path, content, *args, **kwargs)

    monkeypatch.setattr(WorkspaceAnchor, "create_file", fail)
    with pytest.raises(binding.BindingError):
        binding.bind_project(project, root)
    assert list(project.iterdir()) == []
    monkeypatch.setattr(WorkspaceAnchor, "create_file", original)
    assert binding.bind_project(project, root).changed


def test_concurrent_control_content_survives_failed_binding(tmp_path, monkeypatch):
    root = workarea(tmp_path / "area")
    project = root / "project"
    project.mkdir()
    original = WorkspaceAnchor.create_file

    def fail(anchor, path, content, *args, **kwargs):
        if anchor.workspace == project and str(path) == "AGENTS.md":
            (project / ".apparatus/concurrent.txt").write_bytes(b"keep concurrent content")
            raise OSError("injected pointer failure")
        return original(anchor, path, content, *args, **kwargs)

    monkeypatch.setattr(WorkspaceAnchor, "create_file", fail)
    with pytest.raises(binding.BindingError, match="concurrent content was preserved"):
        binding.bind_project(project, root)
    assert (project / ".apparatus/concurrent.txt").read_bytes() == b"keep concurrent content"
    assert not (project / binding.CONTROL).exists()
    assert not (project / "AGENTS.md").exists()


def test_tasks_resolve_project_before_enforcing_retention(tmp_path, capsys):
    root = workarea(tmp_path / "area")
    project = root / "project"
    project.mkdir()
    binding.bind_project(project, root)
    assert cli.main(["task", "start", str(project), "--no-memory"]) == 0
    task_id = json.loads(capsys.readouterr().out)["task_id"]
    assert (root / f"System/tasks/{task_id}.yaml").is_file()
    assert not (project / "System").exists()
    assert cli.main(["task", "show", str(project), task_id]) == 0
    assert json.loads(capsys.readouterr().out)["memory"] == "no-save"
    assert cli.main(["--task", task_id, "snapshot", str(project)]) == 1
    assert "does not save Memory" in capsys.readouterr().out
    assert not (project / ".git").exists()
    assert not (root / "System/recovery").exists()
    assert cli.main(["--task", task_id, "memory", "add-fact", str(project),
                     "--title", "Synthetic", "--body", "Automatic content"]) != 0
    assert not list((root / "Memory/Facts").iterdir())


@pytest.mark.skipif(os.name != "posix", reason="POSIX link substitution; Windows retains directory handles")
def test_resolution_rejects_a_replaced_project_and_symlinked_control(tmp_path):
    root = workarea(tmp_path / "area")
    project = root / "project"
    project.mkdir()
    binding.bind_project(project, root)
    with binding.resolve_project_context(project) as context:
        project.rename(root / "held")
        project.mkdir()
        with pytest.raises(binding.BindingError):
            context.validate()
    pointer = root / "held" / binding.CONTROL
    (project / binding.CONTROL_DIRECTORY).mkdir()
    (project / binding.CONTROL).symlink_to(pointer)
    with pytest.raises(binding.BindingError):
        binding.read_project_binding(project)
