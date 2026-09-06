from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from apparatus_core import records
from apparatus_core.commands import memory
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.labeler import render_record, split_record_exact
from apparatus_core.memory import recall, record_path
from apparatus_core.retention import start_task


def area(tmp_path):
    root = tmp_path / "area"
    for folder in ("System", "Memory/People", "Memory/Facts", "Memory/Decisions", "Decisions"):
        (root / folder).mkdir(parents=True)
    (root / "System/profile.yaml").write_text(
        "schema: apparatus/profile@v0\nstatus: configured\nprivacy_mode: standard\n"
        "work_types: []\nreview_day: null\n", encoding="utf-8")
    return root


def decision(path, title="Synthetic decision", body="Use the cobalt option."):
    path.write_bytes(render_record({"schema": "apparatus/decision@v0", "title": title,
                                    "date": "2026-09-06"}, body).encode("utf-8"))


def run(root, action, record, **options):
    return memory.run(argparse.Namespace(workspace=str(root), memory_action=action,
                                         record=record, **options))


@pytest.mark.parametrize("folder", ["Memory/Decisions", "Decisions"])
def test_decisions_use_existing_correction_outdated_and_forgetting_controls(tmp_path, folder):
    root = area(tmp_path)
    relative = f"{folder}/choose-option.md"
    target = root / relative
    decision(target)
    original = target.read_bytes()
    assert record_path(relative) == (Path(relative), "decision")
    with WorkspaceAnchor(root) as anchor:
        assert recall(anchor, "cobalt")["results"][0]["source"] == relative
    assert target.read_bytes() == original
    replacement = tmp_path / "replacement.md"
    decision(replacement, title="Corrected decision", body="Use the amber option.")
    assert run(root, "correct", relative, from_file=str(replacement)) == 0
    with WorkspaceAnchor(root) as anchor:
        assert recall(anchor, "cobalt")["results"] == []
        assert recall(anchor, "amber")["results"][0]["source"] == relative
    assert run(root, "outdated", relative) == 0
    with WorkspaceAnchor(root) as anchor:
        assert recall(anchor, "amber")["results"] == []
    assert run(root, "forget", relative) == 0
    assert split_record_exact(target.read_text()) == ({"schema": "apparatus/decision@v0", "status": "forgotten"}, "")
    before = target.read_bytes()
    assert run(root, "forget", relative) == 0
    assert run(root, "label", relative) == 0
    assert target.read_bytes() == before
    assert run(root, "correct", relative, from_file=str(replacement)) == 0
    assert target.is_file()  # no migration or source relocation


def test_same_named_legacy_and_new_decisions_are_distinct_sources(tmp_path):
    root = area(tmp_path)
    for folder in ("Decisions", "Memory/Decisions"):
        decision(root / folder / "same-name.md")
    with WorkspaceAnchor(root) as anchor:
        assert [entry["source"] for entry in recall(anchor, "cobalt")["results"]] == [
            "Decisions/same-name.md", "Memory/Decisions/same-name.md"]


def test_no_save_blocks_decision_correction_before_reading_replacement(tmp_path):
    root = area(tmp_path)
    relative = "Memory/Decisions/choose-option.md"
    target = root / relative
    decision(target)
    task = start_task(root, save_memory=False)
    before = target.read_bytes()
    assert run(root, "correct", relative, task=task.task_id,
               from_file=str(tmp_path / "does-not-exist.md")) != 0
    assert target.read_bytes() == before
    assert run(root, "outdated", relative, task=task.task_id) == 0
    assert run(root, "forget", relative, task=task.task_id) == 0


def test_forgotten_decision_schema_rejects_remaining_content():
    clean = {"schema": "apparatus/decision@v0", "status": "forgotten"}
    assert records.validate("decision", clean, filename="example.md", body="") == []
    assert records.validate("decision", {**clean, "title": "Old title"}, filename="example.md", body="")
    assert records.validate("decision", {**clean, "date": "2026-09-06"}, filename="example.md", body="")
    assert records.validate("decision", clean, filename="example.md", body="Old reason")
