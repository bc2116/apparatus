"""PR-60 stock-only canon migration and generated-shim contract."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from apparatus_core.commands import init
from apparatus_core.instruction_updates import RESUME_PREVIOUS_INSTRUCTIONS, _digest
from apparatus_core.payload import shipped_payload
from apparatus_core.render import rendered_shims, rendered_shims_from_bytes
from apparatus_core.retention import start_task


FIXTURE = Path(__file__).parent / "fixtures/instruction_updates_pr60/AGENTS.md"


def _args(workspace: Path) -> argparse.Namespace:
    return argparse.Namespace(
        workspace=str(workspace), payload=None, privacy_mode=None, work_types=None,
    )


@pytest.mark.parametrize("crlf", [False, True])
def test_pr60_stock_canon_migrates_exactly_and_preserves_managed_and_project_files(
    tmp_path, monkeypatch, crlf,
):
    workspace = tmp_path / "area"
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    args = _args(workspace)
    assert init.run(args, available=lambda: False) == 0

    predecessor = FIXTURE.read_bytes().replace(b"\r\n", b"\n")
    assert _digest(predecessor) == RESUME_PREVIOUS_INSTRUCTIONS["AGENTS.md"]
    canon = workspace / "AGENTS.md"
    canon.write_bytes(predecessor.replace(b"\n", b"\r\n") if crlf else predecessor)
    for shim in rendered_shims_from_bytes(canon.read_bytes()):
        target = workspace / shim.target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(shim.content)

    preserved = {
        "Memory/Facts/kept.md": b"---\nschema: apparatus/fact@v0\ntitle: Kept\n---\nFact.\n",
        "Goals/kept.md": (
            b"---\nschema: apparatus/goal@v0\ntitle: Kept\nowner: Owner\n"
            b"status: active\ndone-when: Done\nnext-action: Continue\n---\nGoal.\n"
        ),
        "project/kept.txt": b"Requested project work.\n",
        ".agents/skills/learned-kept/SKILL.md": (
            b"---\nname: learned-kept\ndescription: Synthetic retained workflow.\n---\n# Kept\n"
        ),
    }
    for relative, content in preserved.items():
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    task = start_task(workspace, save_memory=False).task_id
    task_relative = f"System/tasks/{task}.yaml"
    before = {relative: (workspace / relative).read_bytes() for relative in preserved}
    before[task_relative] = (workspace / task_relative).read_bytes()

    assert init.run(args, available=lambda: False) == 0
    assert canon.read_bytes() == (shipped_payload() / "AGENTS.md").read_bytes()
    guidance = " ".join(canon.read_text(encoding="utf-8").split())
    assert "apparatus resume WORKSPACE" in guidance
    assert "no-save task may read this evidence but creates no managed content" in guidance
    assert "requested project work remains available" in guidance
    for shim in rendered_shims(workspace):
        assert (workspace / shim.target).read_bytes() == shim.content
    for relative, content in before.items():
        assert (workspace / relative).read_bytes() == content

    after = {path.relative_to(workspace).as_posix(): path.read_bytes()
             for path in workspace.rglob("*") if path.is_file()}
    assert init.run(args, available=lambda: False) == 0
    assert {path.relative_to(workspace).as_posix(): path.read_bytes()
            for path in workspace.rglob("*") if path.is_file()} == after


def test_pr60_custom_canon_remains_user_owned(tmp_path, monkeypatch):
    workspace = tmp_path / "area"
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    args = _args(workspace)
    assert init.run(args, available=lambda: False) == 0
    custom = FIXTURE.read_bytes() + b"\nCustom continuation convention.\n"
    canon = workspace / "AGENTS.md"
    canon.write_bytes(custom)
    assert init.run(args, available=lambda: False) == 0
    assert canon.read_bytes() == custom


def test_source_embedded_and_golden_shims_are_exact():
    source = Path("starter/payload")
    embedded = shipped_payload()
    assert (source / "AGENTS.md").read_bytes() == (embedded / "AGENTS.md").read_bytes()
    goldens = Path("conformance/golden/shims")
    names = {
        "CLAUDE.md": "CLAUDE.md",
        ".cursor/rules/apparatus.mdc": "apparatus.mdc",
        ".github/copilot-instructions.md": "copilot-instructions.md",
    }
    for relative, golden in names.items():
        assert (source / relative).read_bytes() == (embedded / relative).read_bytes()
        assert (source / relative).read_bytes() == (goldens / golden).read_bytes()
