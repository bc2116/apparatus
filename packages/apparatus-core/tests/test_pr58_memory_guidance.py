"""PR-58 canon migration preserves managed state while updating Memory guidance."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from apparatus_core.commands import init
from apparatus_core.instruction_updates import (
    VERIFIABLE_MEMORY_PREVIOUS_INSTRUCTIONS,
    _digest,
)
from apparatus_core.payload import shipped_payload
from apparatus_core.render import rendered_shims, rendered_shims_from_bytes
from apparatus_core.retention import start_task


FIXTURE = Path(__file__).parent / "fixtures" / "instruction_updates_pr58" / "AGENTS.md"


def _args(workspace: Path) -> argparse.Namespace:
    return argparse.Namespace(
        workspace=str(workspace), payload=None, privacy_mode=None, work_types=None,
    )


@pytest.mark.parametrize("crlf", [False, True])
def test_pr58_stock_canon_migrates_without_touching_memory_task_or_project_files(
    tmp_path, monkeypatch, crlf,
):
    workspace = tmp_path / "area"
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    args = _args(workspace)
    assert init.run(args, available=lambda: False) == 0

    predecessor = FIXTURE.read_bytes().replace(b"\r\n", b"\n")
    assert _digest(predecessor) == VERIFIABLE_MEMORY_PREVIOUS_INSTRUCTIONS["AGENTS.md"]
    canon = workspace / "AGENTS.md"
    canon.write_bytes(predecessor.replace(b"\n", b"\r\n") if crlf else predecessor)
    for shim in rendered_shims_from_bytes(canon.read_bytes()):
        target = workspace / shim.target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(shim.content)

    records = {
        "Memory/Facts/kept-fact.md": (
            b"---\nschema: apparatus/fact@v0\ntitle: Kept fact\n---\n"
            b"Source-backed synthetic fact.\n"
        ),
        "Memory/People/kept-person.md": (
            b"---\nschema: apparatus/person@v0\nname: Kept person\n---\n"
            b"Synthetic role context.\n"
        ),
        "Memory/Decisions/kept-decision.md": (
            b"---\nschema: apparatus/decision@v0\ntitle: Kept decision\n"
            b"date: 2026-09-18\n---\nSynthetic reason.\n"
        ),
        "Decisions/legacy-decision.md": (
            b"---\nschema: apparatus/decision@v0\ntitle: Legacy decision\n"
            b"date: 2026-09-17\n---\nPreserve legacy content.\n"
        ),
        "project/kept.txt": b"Requested project deliverable.\n",
    }
    for relative, content in records.items():
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    task = start_task(workspace, save_memory=False).task_id
    task_path = workspace / "System" / "tasks" / f"{task}.yaml"
    before = {relative: (workspace / relative).read_bytes() for relative in records}
    before[task_path.relative_to(workspace).as_posix()] = task_path.read_bytes()

    assert init.run(args, available=lambda: False) == 0
    assert canon.read_bytes() == (shipped_payload() / "AGENTS.md").read_bytes()
    guidance = " ".join(canon.read_text(encoding="utf-8").split())
    assert "memory add-person" in guidance
    assert "memory add-decision" in guidance
    assert "Record: PATH" in guidance
    for shim in rendered_shims(workspace):
        assert (workspace / shim.target).read_bytes() == shim.content
    for relative, content in before.items():
        assert (workspace / relative).read_bytes() == content

    assert init.run(args, available=lambda: False) == 0
    for relative, content in before.items():
        assert (workspace / relative).read_bytes() == content


def test_pr58_custom_canon_remains_user_owned(tmp_path, monkeypatch):
    workspace = tmp_path / "area"
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    args = _args(workspace)
    assert init.run(args, available=lambda: False) == 0
    predecessor = FIXTURE.read_bytes()
    custom = predecessor + b"\nCustom project Memory convention.\n"
    canon = workspace / "AGENTS.md"
    canon.write_bytes(custom)

    assert init.run(args, available=lambda: False) == 0
    assert canon.read_bytes() == custom
