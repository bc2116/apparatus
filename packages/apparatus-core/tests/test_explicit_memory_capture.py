"""Exact PR-49 canon migration adds explicit fact-capture guidance."""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from apparatus_core.commands import init, memory
from apparatus_core.instruction_updates import EXPLICIT_MEMORY_PREVIOUS_INSTRUCTIONS, _digest
from apparatus_core.payload import shipped_payload
from apparatus_core.retention import start_task


FIXTURES = Path(__file__).parent / "fixtures" / "instruction_updates_pr49"


@pytest.mark.parametrize("crlf", [False, True])
@pytest.mark.parametrize("custom", [False, True])
def test_pr49_stock_canon_upgrade_adds_explicit_fact_capture_and_preserves_user_files(
    tmp_path, monkeypatch, crlf, custom,
):
    root = tmp_path / "area"
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    args = argparse.Namespace(workspace=str(root), payload=None, privacy_mode=None, work_types=None)
    assert init.run(args, available=lambda: False) == 0

    stock = (FIXTURES / "AGENTS.md").read_bytes().replace(b"\r\n", b"\n")
    assert _digest(stock) == EXPLICIT_MEMORY_PREVIOUS_INSTRUCTIONS["AGENTS.md"]
    canon = root / "AGENTS.md"
    canon.write_bytes(stock.replace(b"\n", b"\r\n") if crlf else stock)
    project = root / "project" / "kept.txt"
    project.parent.mkdir()
    project.write_text("Keep this project file.\n")
    saving_task = start_task(root).task_id
    fact_args = argparse.Namespace(
        workspace=str(root), memory_action="add-fact", title="Source-backed fact",
        body="A durable fact. Source: project/kept.txt", from_file=None,
    )
    assert memory.run(fact_args, task_id=saving_task) == 0
    fact = next((root / "Memory/Facts").glob("*.md"))
    before_fact = fact.read_bytes()
    task = start_task(root, save_memory=False).task_id
    if custom:
        canon.write_bytes(canon.read_bytes() + b"\nCustom project guidance.\n")
    before_canon = canon.read_bytes()
    before_task = (root / "System/tasks" / f"{task}.yaml").read_bytes()

    assert init.run(args, available=lambda: False) == 0
    assert project.read_text() == "Keep this project file.\n"
    assert (root / "System/tasks" / f"{task}.yaml").read_bytes() == before_task
    assert fact.read_bytes() == before_fact
    if custom:
        assert canon.read_bytes() == before_canon
    else:
        assert canon.read_bytes() == (shipped_payload() / "AGENTS.md").read_bytes()
        text = canon.read_text()
        assert "explicitly asks to remember, save, or keep a durable fact" in text
        assert "apparatus --task ID memory add-fact WORKSPACE" in text
        assert "include its source when known" in " ".join(text.split())
