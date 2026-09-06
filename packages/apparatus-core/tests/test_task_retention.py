"""Task-control protocol, invocation isolation, and monotonic opt-out proofs."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import shutil
import subprocess
from uuid import UUID, uuid4

import pytest

from apparatus_core import fs_transactions, records, retention
from apparatus_core.commands import init
from apparatus_core.retention import (
    RetentionSuppressed,
    TaskRetentionError,
    context_for,
    operation,
    set_no_memory,
    start_task,
)


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "workspace"
    assert init.run(argparse.Namespace(workspace=str(root), payload=None,
                                      privacy_mode=None, work_types=None),
                    available=lambda: False) == 0
    return root


def tree(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file() and not path.is_symlink()}


def control_path(workspace, task):
    return workspace / "System/tasks" / f"{task.task_id}.yaml"


@pytest.mark.parametrize(("privacy", "explicit", "expected"), [
    ("standard", None, True), ("private", None, False),
    ("private", True, True), ("standard", False, False),
])
def test_task_default_and_explicit_choice_write_only_opaque_closed_metadata(
    workspace, privacy, explicit, expected
):
    profile_path = workspace / "System/profile.yaml"
    profile = records.yaml.safe_load(profile_path.read_text())
    profile["privacy_mode"] = privacy
    profile_path.write_text(records.yaml.safe_dump(profile))
    before = tree(workspace)
    task = start_task(workspace, save_memory=explicit)
    assert task.save_memory is expected and task.legacy is False
    identifier = UUID(task.task_id)
    assert identifier.version == 4 and str(identifier) == task.task_id
    path = control_path(workspace, task)
    assert records.yaml.safe_load(path.read_bytes()) == {
        "schema": "apparatus/task@v0", "id": task.task_id,
        "memory": "save" if expected else "no-save",
    }
    assert tree(workspace) == {**before, path.relative_to(workspace).as_posix(): path.read_bytes()}
    with pytest.raises(FrozenInstanceError):
        task.save_memory = not expected
    assert context_for(workspace, task_id=task.task_id) == task


def test_enrollment_requires_explicit_identity_but_allows_anonymous_maintenance(workspace):
    legacy = context_for(workspace)
    assert legacy.legacy and legacy.save_memory
    legacy.require_memory_write()
    task = start_task(workspace)
    anonymous = context_for(workspace)
    assert not anonymous.legacy and not anonymous.save_memory and anonymous.task_id is None
    for guard in (anonymous.require_memory_write, anonymous.require_library_write,
                  anonymous.require_snapshot):
        with pytest.raises(TaskRetentionError) as caught:
            guard()
        assert not isinstance(caught.value, RetentionSuppressed)
    with pytest.raises(TaskRetentionError):
        context_for(workspace, require_task=True)
    context_for(workspace, task_id=task.task_id, require_task=True).require_memory_write()


@pytest.mark.parametrize("identifier", ["../escape", "NOT-A-UUID", "", 5,
    "00000000-0000-1000-8000-000000000000", "00000000-0000-4000-8000-000000000000"])
def test_invalid_or_unknown_id_never_changes_controls(workspace, identifier):
    start_task(workspace)
    before = tree(workspace)
    for action in (lambda: context_for(workspace, task_id=identifier),
                   lambda: set_no_memory(workspace, identifier)):
        with pytest.raises(TaskRetentionError):
            action()
    assert tree(workspace) == before


@pytest.mark.parametrize("mutation", ["unknown-key", "missing-key", "duplicate-key", "wrong-id",
                                        "invalid-decision", "invalid-utf8", "oversized"])
def test_invalid_task_yaml_is_not_treated_as_a_saving_context(workspace, mutation):
    task = start_task(workspace)
    path = control_path(workspace, task)
    data = records.yaml.safe_load(path.read_bytes())
    if mutation == "unknown-key":
        data["title"] = "Synthetic content must not become task metadata"
    elif mutation == "missing-key":
        del data["memory"]
    elif mutation == "wrong-id":
        data["id"] = str(uuid4())
    elif mutation == "invalid-decision":
        data["memory"] = "maybe"
    content = records.yaml.safe_dump(data).encode()
    if mutation == "duplicate-key":
        content += b"memory: no-save\n"
    elif mutation == "invalid-utf8":
        content = b"\xff"
    elif mutation == "oversized":
        content += b"#" * 4097
    path.write_bytes(content)
    for action in (lambda: context_for(workspace, task_id=task.task_id),
                   lambda: set_no_memory(workspace, task.task_id)):
        with pytest.raises(TaskRetentionError):
            action()
    assert path.read_bytes() == content


@pytest.mark.parametrize("boundary", ["task-file", "task-directory"])
def test_symlink_task_state_is_rejected_without_touching_target(workspace, tmp_path, boundary):
    task = start_task(workspace)
    path = control_path(workspace, task)
    if boundary == "task-file":
        outside = tmp_path / "outside.yaml"
        path.replace(outside)
        path.symlink_to(outside)
    else:
        path = path.parent
        outside = tmp_path / "outside-tasks"
        path.replace(outside)
        path.symlink_to(outside, target_is_directory=True)
    before = tree(tmp_path)
    for action in (lambda: context_for(workspace, task_id=task.task_id),
                   lambda: set_no_memory(workspace, task.task_id)):
        with pytest.raises(TaskRetentionError):
            action()
    assert path.is_symlink() and tree(tmp_path) == before


def test_regular_file_cannot_masquerade_as_task_directory(workspace):
    task_root = workspace / "System/tasks"
    task_root.write_bytes(b"Synthetic unrelated file")
    with pytest.raises(TaskRetentionError):
        context_for(workspace)
    assert task_root.read_bytes() == b"Synthetic unrelated file"


def test_resumption_is_frozen_for_invocation_and_restored_after_exception(workspace):
    saving = start_task(workspace)
    no_save = start_task(workspace, save_memory=False)
    with operation(workspace, task_id=saving.task_id):
        assert context_for(workspace).task_id == saving.task_id
        with pytest.raises(RuntimeError):
            with operation(workspace, task_id=no_save.task_id):
                assert context_for(workspace).task_id == no_save.task_id
                raise RuntimeError("synthetic task failure")
        assert context_for(workspace).task_id == saving.task_id
        set_no_memory(workspace, saving.task_id)
        assert context_for(workspace, task_id=saving.task_id).save_memory is True
    assert context_for(workspace, task_id=saving.task_id).save_memory is False
    assert context_for(workspace).task_id is None


def test_parallel_async_contexts_do_not_share_a_current_task(workspace):
    tasks = (start_task(workspace), start_task(workspace, save_memory=False))
    async def execute(task):
        with operation(workspace, task_id=task.task_id):
            await asyncio.sleep(0)
            assert context_for(workspace).task_id == task.task_id
            return context_for(workspace).save_memory
    async def run_both():
        return await asyncio.gather(*(execute(task) for task in tasks))
    assert asyncio.run(run_both()) == [True, False]
    assert context_for(workspace).task_id is None


def test_task_context_and_id_cannot_be_inherited_in_another_workspace(workspace, tmp_path):
    task = start_task(workspace)
    other = tmp_path / "other"
    other.mkdir()
    with operation(workspace, task_id=task.task_id):
        with pytest.raises(TaskRetentionError, match="another workspace"):
            context_for(other)
        with pytest.raises(TaskRetentionError):
            context_for(other, task_id=task.task_id)


@pytest.mark.parametrize("requested", [(), ("library",), ("snapshot",), ("library", "snapshot")])
def test_requested_exceptions_are_scoped_and_never_enable_memory(workspace, requested):
    task = start_task(workspace, save_memory=False)
    other = start_task(workspace, save_memory=False)
    with operation(workspace, task_id=task.task_id, requested=requested) as context:
        with pytest.raises(RetentionSuppressed):
            context.require_memory_write()
        for name, guard in (("library", context.require_library_write),
                            ("snapshot", context.require_snapshot)):
            if name in requested:
                guard()
            else:
                with pytest.raises(RetentionSuppressed):
                    guard()
        with operation(workspace, task_id=other.task_id) as nested:
            assert nested.requested == frozenset()
    assert context_for(workspace, task_id=task.task_id).requested == frozenset()


def test_no_memory_is_monotonic_and_idempotent(workspace):
    task = start_task(workspace)
    restricted = set_no_memory(workspace, task.task_id)
    before = tree(workspace)
    assert not restricted.save_memory
    assert set_no_memory(workspace, task.task_id) == restricted
    assert tree(workspace) == before
    next_task = start_task(workspace, save_memory=True)
    assert next_task.task_id != task.task_id and next_task.save_memory
    assert not context_for(workspace, task_id=task.task_id).save_memory


@pytest.mark.parametrize("boundary", ["validate_commit", "commit"])
def test_failure_after_no_save_publication_never_restores_save(workspace, monkeypatch, boundary):
    task = start_task(workspace)
    def fail(_transaction):
        raise OSError("synthetic post-publication failure")
    monkeypatch.setattr(fs_transactions.ReplacementTransaction, boundary, fail)
    with pytest.raises(TaskRetentionError):
        set_no_memory(workspace, task.task_id)
    assert context_for(workspace, task_id=task.task_id).save_memory is False
    assert not list((workspace / "System/tasks").glob(".apparatus*"))


def test_repeat_no_memory_rejects_stale_noop_and_preserves_replacement(workspace, monkeypatch):
    task = start_task(workspace, save_memory=False)
    path = control_path(workspace, task)
    original = fs_transactions.WorkspaceAnchor.read_file
    injected = False
    def read(anchor, relative):
        nonlocal injected
        result = original(anchor, relative)
        if Path(relative).as_posix() == f"System/tasks/{task.task_id}.yaml" and not injected:
            injected = True
            substitute = path.with_suffix(".new")
            substitute.write_bytes(result[0])
            substitute.replace(path)
        return result
    monkeypatch.setattr(fs_transactions.WorkspaceAnchor, "read_file", read)
    with pytest.raises(TaskRetentionError):
        set_no_memory(workspace, task.task_id)
    assert injected and records.yaml.safe_load(path.read_bytes())["memory"] == "no-save"
    assert not list(path.parent.glob(".apparatus*"))


def cli(*arguments, expected=0):
    executable = shutil.which("apparatus")
    assert executable
    result = subprocess.run([executable, *(str(argument) for argument in arguments)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == expected, (result.stdout, result.stderr)
    return result


def test_installed_task_cli_and_global_task_dispatch(workspace):
    task = json.loads(cli("task", "start", workspace, "--no-memory").stdout)
    assert set(task) == {"task_id", "memory"} and task["memory"] == "no-save"
    assert json.loads(cli("task", "show", workspace, task["task_id"]).stdout) == task
    assert json.loads(cli("task", "no-memory", workspace, task["task_id"]).stdout) == task
    before = tree(workspace)
    cli("--task", task["task_id"], "memory", "add-fact", workspace,
        "--title", "Synthetic blocked sentinel", "--body", "Synthetic blocked body", expected=1)
    assert tree(workspace) == before
    cli("task", "start", workspace, "--save-memory", "--no-memory", expected=2)
    cli("task", "show", workspace, "../invalid", expected=2)
    assert tree(workspace) == before


def test_invalid_start_inputs_do_not_enroll_or_write_controls(workspace):
    before = tree(workspace)
    with pytest.raises(TaskRetentionError):
        start_task(workspace, save_memory="save")
    assert tree(workspace) == before
    profile = workspace / "System/profile.yaml"
    profile.write_bytes(b"invalid profile")
    before = tree(workspace)
    with pytest.raises(TaskRetentionError):
        start_task(workspace)
    assert tree(workspace) == before
    assert not (workspace / "System/tasks").exists()


def test_concurrent_optout_before_replacement_is_preserved(workspace, monkeypatch):
    task = start_task(workspace)
    path = control_path(workspace, task)
    original = fs_transactions.WorkspaceAnchor.replace_if_unchanged
    restrictive = records.yaml.safe_dump({"schema": "apparatus/task@v0",
                                         "id": task.task_id, "memory": "no-save"}).encode()
    def replace(anchor, *args, **kwargs):
        path.write_bytes(restrictive)
        return original(anchor, *args, **kwargs)
    monkeypatch.setattr(fs_transactions.WorkspaceAnchor, "replace_if_unchanged", replace)
    with pytest.raises(TaskRetentionError):
        set_no_memory(workspace, task.task_id)
    assert path.read_bytes() == restrictive
    assert not list(path.parent.glob(".apparatus*"))


def test_unknown_requested_exception_cannot_enable_or_replace_context(workspace):
    task = start_task(workspace, save_memory=False)
    with operation(workspace, task_id=task.task_id):
        with pytest.raises(TaskRetentionError):
            with operation(workspace, requested=("memory",)):
                pytest.fail("unknown exception was accepted")
        assert context_for(workspace).task_id == task.task_id
        with pytest.raises(RetentionSuppressed):
            context_for(workspace).require_memory_write()
