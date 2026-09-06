"""Task controls guard Memory and profile capture before reading new content."""

from __future__ import annotations

import argparse
from io import StringIO

import pytest

from apparatus_core import records
from apparatus_core.commands import init, memory, profile
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.retention import (
    RetentionSuppressed,
    TaskRetentionError,
    operation,
    set_no_memory,
    start_task,
)


@pytest.fixture
def workspace(tmp_path):
    path = tmp_path / "workspace"
    assert init.run(argparse.Namespace(workspace=str(path), payload=None,
                                      privacy_mode=None, work_types=None),
                    available=lambda: False) == 0
    return path


def tree(workspace):
    return {path.relative_to(workspace).as_posix(): path.read_bytes()
            for path in workspace.rglob("*") if path.is_file()}


def memory_args(workspace, action="add-fact", **kwargs):
    return argparse.Namespace(workspace=str(workspace), memory_action=action,
                              **{"title": "Synthetic retention sentinel", "body": None,
                                 "from_file": str(workspace.parent / "unread-input.md"),
                                 **kwargs})


def profile_args(workspace):
    return argparse.Namespace(workspace=str(workspace), profile_action="apply",
                              payload=None, candidate_stdin=True)


class UnreadInput:
    def read(self):
        raise AssertionError("suppressed task content must not be read")


def candidate(workspace):
    data = records.yaml.safe_load((workspace / "System/profile.yaml").read_text())
    data.update(status="configured",
                key_people=[{"name": "Synthetic Person", "role": "Review lead"}],
                current_efforts=[{"title": "Synthetic effort", "done_when": "Checked",
                                  "next_action": "Draft"}])
    return records.yaml.safe_dump(data)


@pytest.mark.parametrize("action", ["add-fact", "add-person", "correct"])
def test_no_save_blocks_memory_before_reading_content(workspace, action):
    task = start_task(workspace, save_memory=False)
    before = tree(workspace)
    args = memory_args(workspace, action, name="Synthetic Person",
                       record="Memory/Facts/absent.md")
    assert memory.run(args, task_id=task.task_id) == 1
    assert tree(workspace) == before


def test_no_save_blocks_profile_input_and_every_seed(workspace):
    task = start_task(workspace, save_memory=False)
    before = tree(workspace)
    assert profile.run(profile_args(workspace), task_id=task.task_id,
                       input_stream=UnreadInput()) == 1
    assert tree(workspace) == before


@pytest.mark.parametrize("task_id", [None, "malformed", "00000000-0000-4000-8000-000000000000"])
def test_task_enabled_missing_or_invalid_context_cannot_capture(workspace, task_id):
    start_task(workspace, save_memory=True)
    before = tree(workspace)
    assert memory.run(memory_args(workspace), task_id=task_id) == 2
    assert profile.run(profile_args(workspace), task_id=task_id,
                       input_stream=UnreadInput()) == 2
    assert tree(workspace) == before


def test_saving_task_overrides_legacy_private_for_memory_and_profile(workspace):
    path = workspace / "System/profile.yaml"
    data = records.yaml.safe_load(path.read_text())
    data["privacy_mode"] = "private"
    path.write_text(records.yaml.safe_dump(data))
    assert start_task(workspace).save_memory is False
    saving = start_task(workspace, save_memory=True)
    args = memory_args(workspace, "add-person", name="Synthetic Direct Person", role="Lead",
                       body="password=synthetic-secret contact sample@example.invalid",
                       from_file=None)
    assert memory.run(args, task_id=saving.task_id) == 0
    saved = (workspace / "Memory/People/synthetic-direct-person.md").read_text()
    assert "synthetic-secret" not in saved
    assert "[redacted-password]" in saved and "pii/email" in saved
    assert profile.run(profile_args(workspace), task_id=saving.task_id,
                       input_stream=StringIO(candidate(workspace))) == 0
    assert (workspace / "Memory/People/synthetic-person.md").is_file()
    assert (workspace / "Goals/synthetic-effort.md").is_file()
    assert records.yaml.safe_load(path.read_text())["privacy_mode"] == "private"


def test_internal_seed_writer_cannot_bypass_no_save(workspace):
    task = start_task(workspace, save_memory=False)
    before = tree(workspace)
    with operation(workspace, task_id=task.task_id), WorkspaceAnchor(workspace) as anchor:
        with pytest.raises(RetentionSuppressed):
            memory._new_record(anchor, kind="fact", metadata={"title": "Synthetic bypass"},
                               body="Synthetic body", mode="standard", write=lambda *a, **k: None)
        with pytest.raises(RetentionSuppressed):
            profile._seed_plan(anchor, records.yaml.safe_load(candidate(workspace)))
    assert tree(workspace) == before


def test_nested_contexts_are_inherited_and_do_not_leak(workspace):
    saving = start_task(workspace, save_memory=True)
    no_save = start_task(workspace, save_memory=False)
    args = memory_args(workspace, body="Ordinary context", from_file=None)
    with operation(workspace, task_id=saving.task_id):
        assert memory.run(args) == 0
        assert memory.run(args, task_id=no_save.task_id) == 1
        assert memory.run(args) == 0
    assert memory.run(args) == 2
    assert len(list((workspace / "Memory/Facts").glob("*.md"))) == 2


def test_opt_out_applies_to_next_invocation_not_inflight_profile(workspace):
    saving = start_task(workspace, save_memory=True)
    text = candidate(workspace)
    class OptOutInput:
        def read(self):
            set_no_memory(workspace, saving.task_id)
            return text
    assert profile.run(profile_args(workspace), task_id=saving.task_id,
                       input_stream=OptOutInput()) == 0
    before = tree(workspace)
    assert profile.run(profile_args(workspace), task_id=saving.task_id,
                       input_stream=UnreadInput()) == 1
    assert tree(workspace) == before


def test_no_save_maintenance_and_reads_still_work_without_capture(workspace):
    args = memory_args(workspace, body="Current cobalt context", from_file=None)
    assert memory.run(args) == 0
    task = start_task(workspace, save_memory=False)
    target = "Memory/Facts/synthetic-retention-sentinel.md"
    before = tree(workspace)
    assert memory.run(memory_args(workspace, "recall", query="cobalt", limit=5),
                      task_id=task.task_id) == 0
    assert tree(workspace) == before
    # Maintenance is also allowed without an ID after enrollment.
    assert memory.run(memory_args(workspace, "outdated", record=target)) == 0
    assert memory.run(memory_args(workspace, "label"), task_id=task.task_id) == 0
    assert memory.run(memory_args(workspace, "forget", record=target),
                      task_id=task.task_id) == 0
    tombstone = (workspace / target).read_text()
    assert "forgotten" in tombstone and "cobalt" not in tombstone


def test_requested_library_or_snapshot_never_enables_memory_capture(workspace):
    task = start_task(workspace, save_memory=False)
    before = tree(workspace)
    with operation(workspace, task_id=task.task_id, requested=("library", "snapshot")):
        assert memory.run(memory_args(workspace)) == 1
        assert profile.run(profile_args(workspace), input_stream=UnreadInput()) == 1
    assert tree(workspace) == before


def test_passed_seed_context_cannot_cross_workspace(workspace, tmp_path):
    task = start_task(workspace, save_memory=True)
    other = tmp_path / "other"
    other.mkdir()
    before = tree(other)
    with WorkspaceAnchor(other) as anchor:
        with pytest.raises(TaskRetentionError, match="another workspace"):
            memory._new_record(anchor, kind="fact", metadata={"title": "Synthetic bypass"},
                               body="Synthetic body", mode="standard", task_context=task,
                               write=lambda *a, **k: None)
        with pytest.raises(TaskRetentionError, match="another workspace"):
            profile._seed_plan(anchor, {}, task_context=task)
    assert tree(other) == before
