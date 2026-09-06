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
from apparatus_core.skills import legacy_pointer


FIXTURES = Path(__file__).parent / "fixtures/instruction_updates"


def _args(workspace: Path, payload: Path | None = None) -> argparse.Namespace:
    return argparse.Namespace(workspace=str(workspace), payload=payload,
                              privacy_mode=None, work_types=None, adopt=True)


def _legacy_workspace(workspace: Path, *, crlf: bool = False) -> None:
    shutil.copytree(shipped_payload(), workspace)
    for source in FIXTURES.rglob("*"):
        if not source.is_file():
            continue
        content = source.read_bytes().replace(b"\r\n", b"\n")
        relative = source.relative_to(FIXTURES).as_posix()
        assert _digest(content) == LEGACY_INSTRUCTIONS[relative]
        (workspace / relative).parent.mkdir(parents=True, exist_ok=True)
        (workspace / relative).write_bytes(
            content.replace(b"\n", b"\r\n") if crlf else content
        )
    (workspace / "Projects").mkdir(exist_ok=True)
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


def test_custom_canon_updates_recognized_pointers_without_losing_edits(tmp_path, capsys):
    workspace = tmp_path / "work"
    _legacy_workspace(workspace)
    canon = (shipped_payload() / "AGENTS.md").read_bytes() + b"\nUse sentence case.\n"
    (workspace / "AGENTS.md").write_bytes(canon)
    assert init.run(_args(workspace), available=lambda: False) == 0
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
    assert "preserve and reconcile" in capsys.readouterr().out
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


def test_deployment_reads_preimages_through_retained_immediate_parents(tmp_path, monkeypatch):
    workspace = tmp_path / "work"
    original_deploy = init.deploy_init_plan
    original_read = WorkspaceAnchor.read_file

    def deploy(*args, **kwargs):
        def read(self, relative):
            if len(Path(relative).parts) > 1:
                raise PermissionError("nested reopen conflicts with owned directory handle")
            return original_read(self, relative)

        # Enrollment validates binding/marker state independently; exempt only
        # that callback. All deployment/preimage reads still reject nested reopen.
        validate_enrollment = kwargs["validate_enrollment"]

        def validate(*values):
            with monkeypatch.context() as validation_patch:
                validation_patch.setattr(WorkspaceAnchor, "read_file", original_read)
                return validate_enrollment(*values)

        kwargs["validate_enrollment"] = validate
        with monkeypatch.context() as patch:
            patch.setattr(WorkspaceAnchor, "read_file", read)
            return original_deploy(*args, **kwargs)

    monkeypatch.setattr(init, "deploy_init_plan", deploy)
    assert init.run(_args(workspace), available=lambda: False) == 0
    assert check_workspace(workspace).ok


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


@pytest.mark.parametrize("crlf", [False, True])
def test_gate_free_workspace_updates_memory_guidance_without_losing_records(tmp_path, crlf):
    workspace = tmp_path / "work"
    shutil.copytree(shipped_payload(), workspace)
    fixtures = FIXTURES.parent / "instruction_updates_pr32"
    for source in fixtures.rglob("*"):
        if source.is_file():
            content = source.read_bytes().replace(b"\r\n", b"\n")
            (workspace / source.relative_to(fixtures)).parent.mkdir(parents=True, exist_ok=True)
            (workspace / source.relative_to(fixtures)).write_bytes(
                content.replace(b"\n", b"\r\n") if crlf else content
            )
    fact = workspace / "Memory/Facts/a-preference.md"
    original = b"---\nschema: apparatus/fact@v0\ntitle: A preference\n---\nKeep this.\n"
    fact.write_bytes(original)
    assert init.run(_args(workspace), available=lambda: False) == 0
    assert "apparatus memory recall" in (workspace / "AGENTS.md").read_text()
    assert check_workspace(workspace).ok
    assert init.run(_args(workspace), available=lambda: False) == 0
    assert fact.read_bytes() == original


@pytest.mark.parametrize("crlf", [False, True])
def test_pr33_instructions_gain_task_controls_preserving_private_default(tmp_path, crlf):
    workspace = tmp_path / "work"
    shutil.copytree(shipped_payload(), workspace)
    fixtures = FIXTURES.parent / "instruction_updates_pr33"
    for source in fixtures.rglob("*"):
        if source.is_file():
            content = source.read_bytes().replace(b"\r\n", b"\n")
            (workspace / source.relative_to(fixtures)).parent.mkdir(parents=True, exist_ok=True)
            (workspace / source.relative_to(fixtures)).write_bytes(
                content.replace(b"\n", b"\r\n") if crlf else content)
    profile = workspace / "System/profile.yaml"
    data = records.yaml.safe_load(profile.read_text())
    data["privacy_mode"] = "private"
    profile.write_text(records.yaml.safe_dump(data))
    assert init.run(_args(workspace), available=lambda: False) == 0
    for relative in ("AGENTS.md", "Welcome.md",
                     "System/policy/private.md", "System/policy/standard.md"):
        assert (workspace / relative).read_bytes() == (shipped_payload() / relative).read_bytes()
    assert (workspace / "System/procedures/welcome.md").read_bytes() == legacy_pointer("System/procedures/welcome.md")
    assert records.yaml.safe_load(profile.read_text())["privacy_mode"] == "private"
    assert "apparatus task start" in (workspace / "AGENTS.md").read_text()
    assert "Should privacy mode be" not in (workspace / "System/procedures/welcome.md").read_text()
    assert init.run(_args(workspace), available=lambda: False) == 0
    assert check_workspace(workspace).ok


@pytest.mark.parametrize("relative", ["AGENTS.md", "System/procedures/welcome.md",
                                     "System/policy/private.md"])
def test_custom_obsolete_task_guidance_requires_non_destructive_reconciliation(tmp_path, capsys, relative):
    workspace = tmp_path / "work"
    shutil.copytree(shipped_payload(), workspace)
    original = FIXTURES.parent / "instruction_updates_pr33" / relative
    (workspace / relative).parent.mkdir(parents=True, exist_ok=True)
    (workspace / relative).write_bytes(original.read_bytes() + b"\nCustom workflow.\n")
    before = _files(workspace)
    assert init.run(_args(workspace), available=lambda: False) == 2
    assert "preserve your edits" in capsys.readouterr().out
    assert _files(workspace) == before


@pytest.mark.parametrize("crlf", [False, True])
def test_pr34_payload_migrates_exact_bytes_to_project_local_guidance(tmp_path, crlf):
    from apparatus_core.instruction_updates import LAYOUT_PREVIOUS_INSTRUCTIONS
    workspace = tmp_path / "area"
    shutil.copytree(shipped_payload(), workspace)
    fixtures = FIXTURES.parent / "instruction_updates_pr34"
    for source in fixtures.rglob("*"):
        if source.is_file():
            relative = source.relative_to(fixtures)
            content = source.read_bytes().replace(b"\r\n", b"\n")
            assert _digest(content) == LAYOUT_PREVIOUS_INSTRUCTIONS[relative.as_posix()]
            (workspace / relative).parent.mkdir(parents=True, exist_ok=True)
            (workspace / relative).write_bytes(content.replace(b"\n", b"\r\n") if crlf else content)
    (workspace / "Projects").mkdir()
    (workspace / "Deliverables").mkdir()
    (workspace / "Decisions").mkdir()
    old = workspace / "Deliverables/keep.txt"
    old.write_bytes(b"finished work remains here")
    assert init.run(_args(workspace), available=lambda: False) == 0
    assert (workspace / "AGENTS.md").read_bytes() == (shipped_payload() / "AGENTS.md").read_bytes()
    assert old.read_bytes() == b"finished work remains here"
    assert (workspace / "Decisions").is_dir()
    assert (workspace / "Memory/Decisions").is_dir()
    assert check_workspace(workspace).ok


def test_adoption_generates_missing_pointers_from_preserved_custom_canon(tmp_path):
    from apparatus_core.render import rendered_shims
    workspace = tmp_path / "area"
    workspace.mkdir()
    custom = b"# Existing canon\r\nPreserve project-specific instructions.\r\n"
    (workspace / "AGENTS.md").write_bytes(custom)
    assert init.run(_args(workspace), available=lambda: False) == 0
    assert (workspace / "AGENTS.md").read_bytes() == custom
    for shim in rendered_shims(workspace):
        assert (workspace / shim.target).read_bytes() == shim.content
    assert check_workspace(workspace).ok
