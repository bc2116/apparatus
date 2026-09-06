from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pytest

from apparatus_core import cli, records
from apparatus_core.check import check_workspace
from apparatus_core.commands import init
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.instruction_updates import (
    LEGACY_INSTRUCTIONS, _digest, has_retired_gate,
)
from apparatus_core.payload import shipped_payload
from apparatus_core.render import render_workspace


FIXTURES = Path(__file__).parent / "fixtures/instruction_updates"


def _args(workspace: Path, payload: Path | None = None) -> argparse.Namespace:
    return argparse.Namespace(workspace=str(workspace), payload=payload,
                              privacy_mode=None, work_types=None)


def _legacy_workspace(workspace: Path, *, crlf: bool = False) -> None:
    shutil.copytree(shipped_payload(), workspace)
    for source in FIXTURES.rglob("*"):
        if not source.is_file():
            continue
        content = source.read_bytes()
        relative = source.relative_to(FIXTURES).as_posix()
        assert _digest(content) == LEGACY_INSTRUCTIONS[relative]
        (workspace / relative).write_bytes(
            content.replace(b"\n", b"\r\n") if crlf else content
        )
    (workspace / "Projects/keep.bin").write_bytes(b"untouched\x00\xff")


def _files(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("crlf", [False, True])
def test_original_instructions_upgrade_and_repeat_preserves_history(tmp_path, crlf):
    workspace = tmp_path / "work"
    _legacy_workspace(workspace, crlf=crlf)
    receipt = workspace / "System/receipts/2026-08-08-120000-egress.md"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    history = (
        "---\nschema: apparatus/receipt@v0\nevent: egress\n"
        "timestamp: '2026-08-08T12:00:00Z'\nsummary: Historical decision.\n---\n"
        "This records an old decision, not authority for a new action.\n"
    ).encode()
    receipt.write_bytes(history)
    assert any(f.code == "retired-sharing-instructions"
               for f in check_workspace(workspace).findings)
    assert init.run(_args(workspace), available=lambda: False) == 0
    for relative in ("AGENTS.md", "System/policy/standard.md"):
        assert (workspace / relative).read_bytes() == (shipped_payload() / relative).read_bytes()
        assert not has_retired_gate((workspace / relative).read_bytes())
    assert (workspace / "Projects/keep.bin").read_bytes() == b"untouched\x00\xff"
    assert receipt.read_bytes() == history
    assert check_workspace(workspace).ok
    assert init.run(_args(workspace), available=lambda: False) == 0
    assert receipt.read_bytes() == history
    events = [records.parse_record(p.read_text())[0]["event"]
              for p in receipt.parent.glob("*.md")]
    assert events.count("egress") == 1


@pytest.mark.parametrize("relative", ["AGENTS.md", "Welcome.md", "System/policy/standard.md"])
def test_custom_legacy_instruction_conflict_preserves_entire_workspace(tmp_path, capsys, relative):
    workspace = tmp_path / "work"
    _legacy_workspace(workspace)
    path = workspace / relative
    path.write_bytes(path.read_bytes() + b"\nCustom team-independent workflow.\n")
    before = _files(workspace)
    assert init.run(_args(workspace), available=lambda: False) == 2
    output = capsys.readouterr().out
    assert relative in output and "preserve your edits" in output
    assert "rerun apparatus init" in output
    assert _files(workspace) == before


def test_stale_instruction_plan_does_not_overwrite_new_edit(tmp_path, monkeypatch):
    workspace = tmp_path / "work"
    _legacy_workspace(workspace)
    original = init.deploy_init_plan
    new_edit = b"New user-owned instructions.\n"
    old_policy = (workspace / "System/policy/standard.md").read_bytes()

    def raced(*args, **kwargs):
        (workspace / "AGENTS.md").write_bytes(new_edit)
        return original(*args, **kwargs)

    monkeypatch.setattr(init, "deploy_init_plan", raced)
    assert init.run(_args(workspace), available=lambda: False) == 2
    assert (workspace / "AGENTS.md").read_bytes() == new_edit
    assert (workspace / "System/policy/standard.md").read_bytes() == old_policy


@pytest.mark.parametrize("fresh", [False, True])
def test_expected_absence_preserves_concurrently_created_policy(tmp_path, monkeypatch, fresh):
    workspace = tmp_path / "work"
    if not fresh:
        _legacy_workspace(workspace)
        (workspace / "System/policy/standard.md").unlink()
    original = init.deploy_init_plan
    custom = b"Concurrent user policy; keep this.\n"

    def raced(*args, **kwargs):
        policy = workspace / "System/policy/standard.md"
        policy.parent.mkdir(parents=True, exist_ok=True)
        policy.write_bytes(custom)
        return original(*args, **kwargs)

    monkeypatch.setattr(init, "deploy_init_plan", raced)
    assert init.run(_args(workspace), available=lambda: False) == 2
    assert (workspace / "System/policy/standard.md").read_bytes() == custom


def test_unchanged_instruction_preimage_detects_concurrent_legacy_content(tmp_path, monkeypatch):
    workspace = tmp_path / "work"
    shutil.copytree(shipped_payload(), workspace)
    original = init.deploy_init_plan
    custom = (FIXTURES / "Welcome.md").read_bytes() + b"\nA user edit.\n"

    def raced(*args, **kwargs):
        (workspace / "Welcome.md").write_bytes(custom)
        return original(*args, **kwargs)

    monkeypatch.setattr(init, "deploy_init_plan", raced)
    assert init.run(_args(workspace), available=lambda: False) == 2
    assert (workspace / "Welcome.md").read_bytes() == custom


def test_reconciled_custom_policy_can_finish_repair_without_losing_edits(tmp_path):
    workspace = tmp_path / "work"
    _legacy_workspace(workspace)
    policy = workspace / "System/policy/standard.md"
    custom = b"\nUse sentence case in headings.\n"
    policy.write_bytes(policy.read_bytes() + custom)
    assert init.run(_args(workspace), available=lambda: False) == 2
    reconciled = (shipped_payload() / "System/policy/standard.md").read_bytes() + custom
    policy.write_bytes(reconciled)
    assert init.run(_args(workspace), available=lambda: False) == 0
    assert init.run(_args(workspace), available=lambda: False) == 0
    assert policy.read_bytes() == reconciled
    assert check_workspace(workspace).ok


def test_reconciled_custom_canon_gets_actionable_render_then_safe_retry(tmp_path, capsys):
    workspace = tmp_path / "work"
    _legacy_workspace(workspace)
    canon = (shipped_payload() / "AGENTS.md").read_bytes() + b"\nUse sentence case.\n"
    (workspace / "AGENTS.md").write_bytes(canon)
    before = _files(workspace)
    assert init.run(_args(workspace), available=lambda: False) == 2
    assert "apparatus render WORKSPACE" in capsys.readouterr().out
    assert _files(workspace) == before
    render_workspace(workspace)
    assert init.run(_args(workspace), available=lambda: False) == 0
    assert (workspace / "AGENTS.md").read_bytes() == canon
    assert check_workspace(workspace).ok


def test_custom_old_shim_is_preserved_and_not_claimed_as_migrated(tmp_path, capsys):
    workspace = tmp_path / "work"
    _legacy_workspace(workspace)
    shim = workspace / "CLAUDE.md"
    shim.write_bytes(shim.read_bytes() + b"\nCustom pointer instruction.\n")
    before = _files(workspace)
    assert init.run(_args(workspace), available=lambda: False) == 2
    assert "apparatus render WORKSPACE" in capsys.readouterr().out
    assert _files(workspace) == before


def test_failed_late_instruction_replacement_rolls_back_earlier_updates(tmp_path, monkeypatch):
    workspace = tmp_path / "work"
    _legacy_workspace(workspace)
    before = _files(workspace)
    original = WorkspaceAnchor.replace_if_unchanged
    replaced = []

    def fail_canon(self, relative, identity, expected, content):
        if str(relative) == "AGENTS.md":
            raise OSError("injected replacement failure")
        replaced.append(str(relative))
        return original(self, relative, identity, expected, content)

    monkeypatch.setattr(WorkspaceAnchor, "replace_if_unchanged", fail_canon)
    assert init.run(_args(workspace), available=lambda: False) == 2
    assert "standard.md" in replaced
    assert _files(workspace) == before


def test_retired_custom_payload_is_rejected_before_workspace_creation(tmp_path, capsys):
    payload = tmp_path / "payload"
    _legacy_workspace(payload)
    workspace = tmp_path / "work"
    assert init.run(_args(workspace, payload), available=lambda: False) == 2
    assert "use the updated starter payload" in capsys.readouterr().out
    assert not workspace.exists()


def test_sharing_command_is_absent_but_legacy_receipts_remain_valid(capsys):
    assert cli.main(["egress", "check", "workspace"]) == 2
    assert "invalid choice" in capsys.readouterr().err
    data, _ = records.parse_record(
        "---\nschema: apparatus/receipt@v0\nevent: egress\n"
        "timestamp: '2026-08-08T12:00:00Z'\nsummary: Historical decision.\n---\n"
    )
    assert records.validate("receipt", data, filename="2026-08-08-120000-egress.md") == []
