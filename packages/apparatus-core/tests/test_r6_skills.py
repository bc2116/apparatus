"""Seven-Skill enrollment, compatibility and retained publication boundaries."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import zipfile

import pytest

from apparatus_core import managed_state_backup as backup, managed_state_recovery as recovery, records
from apparatus_core.check import _skill_findings, check_workspace
from apparatus_core.commands import init
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.ignore import load_ignore_rules
from apparatus_core.instruction_updates import ECONOMY_PREVIOUS_INSTRUCTIONS, _digest, instruction_updates
from apparatus_core.overlays import ManifestError, OverlayPlan, load_manifest
from apparatus_core.payload import PayloadError, shipped_payload
from apparatus_core.retention import start_task
from apparatus_core.skills import (
    BUILTIN_PATHS, HISTORICAL_SKILL_INDEX, HISTORICAL_SKILL_PATHS, LEGACY_PROCEDURES,
    NEW_SKILL_PATHS, SKILL_INDEX, is_legacy_pointer, legacy_pointer,
)

FIXTURES = Path(__file__).parent / "fixtures/instruction_updates_pr39"


def args(root, *, payload=None, task=None):
    return argparse.Namespace(workspace=str(root), payload=payload, privacy_mode=None,
                              work_types=None, adopt=True, task=task)


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def historical_payload(root, *, crlf=False):
    shutil.copytree(shipped_payload(), root)
    for relative in NEW_SKILL_PATHS:
        shutil.rmtree((root / relative).parent)
    for relative, expected in ECONOMY_PREVIOUS_INSTRUCTIONS.items():
        content = (FIXTURES / relative).read_bytes().replace(b"\r\n", b"\n")
        assert _digest(content) == expected
        (root / relative).write_bytes(content.replace(b"\n", b"\r\n") if crlf else content)
    return root


@pytest.mark.parametrize("crlf", [False, True])
def test_five_to_seven_updates_exact_stock_guidance_and_repeat_is_noop(tmp_path, crlf):
    root = historical_payload(tmp_path / "area", crlf=crlf)
    profile = (root / "System/profile.yaml").read_bytes()
    unrelated = {".git/HEAD": b"ref: refs/heads/project\n", ".git/index": b"project index",
                 ".git/config": b"project config", "project/draft.txt": b"Project-owned work"}
    for relative, content in unrelated.items():
        path = root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
    assert init.run(args(root), available=lambda: False) == 0
    for relative in (*BUILTIN_PATHS, *ECONOMY_PREVIOUS_INSTRUCTIONS):
        assert (root / relative).read_bytes() == (shipped_payload() / relative).read_bytes()
    assert (root / "System/profile.yaml").read_bytes() == profile
    assert all((root / p).read_bytes() == value for p, value in unrelated.items())
    assert not (root / "System/procedures").exists()
    assert check_workspace(root).ok
    before = files(root)
    assert init.run(args(root), available=lambda: False) == 0
    assert files(root) == before


def test_custom_canon_guidance_and_seven_bodies_survive_upgrade(tmp_path):
    root = historical_payload(tmp_path / "area")
    custom = {}
    for relative in (*HISTORICAL_SKILL_PATHS, "AGENTS.md", "Welcome.md", "System/README.md",
                     "System/guidance/model-guidance.md"):
        p = root / relative; p.write_bytes(p.read_bytes() + b"\nUser-owned customization.\n")
        custom[relative] = p.read_bytes()
    for relative in NEW_SKILL_PATHS:
        p = root / relative; p.parent.mkdir(parents=True)
        p.write_bytes((shipped_payload() / relative).read_bytes() + b"\nCustom new Skill.\n")
        custom[relative] = p.read_bytes()
    for relative in (".agents/skills/third-party/SKILL.md", ".agents/skills/apparatus-humanizer/reference.txt"):
        p = root / relative; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"Unrelated data."); custom[relative] = p.read_bytes()
    assert init.run(args(root), available=lambda: False) == 0
    assert all((root / relative).read_bytes() == content for relative, content in custom.items())


def test_historical_five_source_and_manifest_remain_usable(tmp_path):
    payload = historical_payload(tmp_path / "old/payload")
    manifest_path = payload.parent / "profiles/profiles.yaml"
    manifest_path.parent.mkdir(); shutil.copyfile(FIXTURES / "profiles.yaml", manifest_path)
    manifest = load_manifest(manifest_path, payload)
    assert set(manifest.managed_workflow_paths) == set(HISTORICAL_SKILL_PATHS)
    root = tmp_path / "area"
    assert init.run(args(root, payload=str(payload)), available=lambda: False) == 0
    assert all((root / p).is_file() for p in HISTORICAL_SKILL_PATHS)
    assert not any((root / p).exists() for p in NEW_SKILL_PATHS)
    findings = check_workspace(root).findings
    assert {f.path for f in findings if f.code == "skill-missing"} == set(NEW_SKILL_PATHS)
    assert all("Upgrade" in f.hint for f in findings if f.code == "skill-missing")
    assert init.run(args(root), available=lambda: False) == 0
    assert check_workspace(root).ok


@pytest.mark.parametrize("evidence", ["new-directory", "new-body", "index", "welcome", "system-readme"])
@pytest.mark.parametrize("crlf", [False, True])
def test_new_source_evidence_requires_all_seven_even_with_old_manifest(tmp_path, evidence, crlf):
    payload = historical_payload(tmp_path / "old/payload")
    first = next(iter(NEW_SKILL_PATHS))
    if evidence.startswith("new-"):
        path = payload / first; path.parent.mkdir(parents=True)
        if evidence == "new-body":
            path.write_bytes((shipped_payload() / first).read_bytes())
    else:
        relative = {"index": "AGENTS.md", "welcome": "Welcome.md", "system-readme": "System/README.md"}[evidence]
        content = (shipped_payload() / relative).read_bytes().replace(b"\r\n", b"\n")
        (payload / relative).write_bytes(content.replace(b"\n", b"\r\n") if crlf else content)
    root = tmp_path / "area"; root.mkdir()
    for action in (lambda: load_manifest(FIXTURES / "profiles.yaml", payload),
                   lambda: instruction_updates(root, payload, OverlayPlan((), ()))):
        with pytest.raises((ManifestError, PayloadError), match="complete portable Skill payload"):
            action()
    assert not list(root.iterdir())


@pytest.mark.parametrize("relative", list(NEW_SKILL_PATHS))
@pytest.mark.parametrize("where", ["source", "target"])
@pytest.mark.parametrize("content", [b"Foreign text", b"---\nname: other\ndescription: Different Skill.\n---\nBody\n"])
def test_invalid_new_occupants_fail_before_target_writes(tmp_path, relative, where, content):
    root = historical_payload(tmp_path / "area")
    payload = tmp_path / "payload"; shutil.copytree(shipped_payload(), payload)
    path = (payload if where == "source" else root) / relative
    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
    before = files(root)
    assert init.run(args(root, payload=str(payload)), available=lambda: False) == 2
    assert files(root) == before


@pytest.mark.parametrize("relative", [*NEW_SKILL_PATHS, "System/guidance/model-guidance.md", "AGENTS.md"])
def test_new_absence_and_stock_byte_preimages_reject_competing_edit(tmp_path, monkeypatch, relative):
    root = historical_payload(tmp_path / "area")
    before = files(root); original = init.deploy_init_plan
    competitor = b"A concurrent owner wrote this.\n"
    def race(*values, **options):
        p = root / relative; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(competitor)
        return original(*values, **options)
    monkeypatch.setattr(init, "deploy_init_plan", race)
    assert init.run(args(root), available=lambda: False) == 2
    assert files(root) == {**before, relative: competitor}


def test_late_new_skill_failure_compensates_without_erasing_competitor(tmp_path, monkeypatch):
    root = historical_payload(tmp_path / "area")
    relative = next(iter(NEW_SKILL_PATHS)); before = files(root)
    stock = (shipped_payload() / relative).read_bytes(); competitor = b"Concurrent new Skill owner.\n"
    original = WorkspaceAnchor.matches_owned; witnessed = []
    def fail(anchor, proof):
        if not witnessed and proof.content == stock:
            try:
                (root / relative).write_bytes(competitor)
            except PermissionError:
                witnessed.append("native-denied")
            else:
                witnessed.append("written")
            return False
        return original(anchor, proof)
    monkeypatch.setattr(WorkspaceAnchor, "matches_owned", fail)
    assert init.run(args(root), available=lambda: False) == 2
    assert witnessed
    expected = {**before, relative: competitor} if witnessed == ["written"] else before
    assert files(root) == expected


@pytest.mark.parametrize("index", [HISTORICAL_SKILL_INDEX, SKILL_INDEX])
def test_deleted_bodies_remain_actionable_with_each_full_index(tmp_path, index):
    root = historical_payload(tmp_path / "area")
    shutil.rmtree(root / ".agents")
    (root / "Welcome.md").write_bytes(b"Custom orientation.")
    (root / "System/README.md").write_bytes(b"Custom orientation.")
    (root / "AGENTS.md").write_text(index, encoding="utf-8")
    before = files(root)
    findings, count, _, _ = _skill_findings(root, load_ignore_rules(root))
    assert count == 0
    assert {f.path for f in findings if f.code == "skill-missing"} == set(BUILTIN_PATHS)
    assert files(root) == before


@pytest.mark.parametrize("save", [False, True])
def test_generic_upgrade_preserves_task_profile_without_extra_capture(tmp_path, save):
    root = historical_payload(tmp_path / "area")
    context = start_task(root, save_memory=save)
    controls = files(root / "System/tasks"); profile = (root / "System/profile.yaml").read_bytes()
    def forbidden(*values, **options):
        pytest.fail("no-save generic upgrade attempted an automatic snapshot")
    options = {"available": lambda: False} if save else {"available": lambda: True, "take": forbidden}
    assert init.run(args(root, task=context.task_id), **options) == 0
    assert files(root / "System/tasks") == controls
    assert (root / "System/profile.yaml").read_bytes() == profile
    receipt_events = [records.parse_record(p.read_text())[0]["event"]
                      for p in (root / "System/receipts").glob("*.md")]
    # Keep the existing init and unavailable-snapshot evidence; R6 adds none.
    assert sorted(receipt_events) == (["init", "snapshot"] if save else ["init"])
    assert not (root / "System/recovery").exists()
    for directory in ("Memory", "Goals", "Library"):
        assert not list((root / directory).rglob("*.md"))
    assert all((root / path).is_file() for path in BUILTIN_PATHS)


@pytest.mark.skipif(shutil.which("git") is None, reason="actual Git reachable-history validation")
def test_five_skill_history_archive_restore_and_remigration_preserve_new_additions(tmp_path):
    payload = historical_payload(tmp_path / "old/payload")
    manifest = payload.parent / "profiles/profiles.yaml"; manifest.parent.mkdir()
    shutil.copyfile(FIXTURES / "profiles.yaml", manifest)
    root = tmp_path / "area"
    assert init.run(args(root, payload=str(payload)), available=lambda: False) == 0
    old = recovery.take_snapshot(root).snapshot
    assert old is not None
    assert init.run(args(root), available=lambda: False) == 0
    relative = next(iter(NEW_SKILL_PATHS))
    custom = (root / relative).read_bytes() + b"\nCustom economy guidance.\n"
    (root / relative).write_bytes(custom)
    foreign = root / ".agents/skills/unrelated/SKILL.md"; foreign.parent.mkdir()
    foreign.write_bytes(b"Unmanaged instructions.")
    (root / relative).with_name("reference.txt").write_bytes(b"Not declared coverage.")
    recovery.take_snapshot(root)
    destination = tmp_path / "exports"; destination.mkdir()
    exported = backup.export_backup(root, destination)
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(exported.archive) as archive:
        assert set(BUILTIN_PATHS) <= set(archive.namelist())
        assert "System/guidance/model-guidance.md" in archive.namelist()
        assert not any("unrelated" in p or p.endswith("reference.txt") for p in archive.namelist())
        archive.extractall(extracted)
    assert len(recovery.list_snapshots(extracted)) >= 2
    recovery.restore_snapshot(extracted, old.identifier)
    assert (extracted / relative).read_bytes() == custom
    assert all((extracted / p).is_file() for p in NEW_SKILL_PATHS)
    assert (extracted / "System/guidance/model-guidance.md").read_bytes() == (payload / "System/guidance/model-guidance.md").read_bytes()
    assert init.run(args(extracted), available=lambda: False) == 0
    assert (extracted / relative).read_bytes() == custom
    assert (extracted / "System/guidance/model-guidance.md").read_bytes() == (shipped_payload() / "System/guidance/model-guidance.md").read_bytes()
    assert check_workspace(extracted).ok


def test_only_five_historical_procedure_pointers_exist():
    assert len(LEGACY_PROCEDURES) == len(HISTORICAL_SKILL_PATHS) == 5
    assert len(BUILTIN_PATHS) == 7 and len(NEW_SKILL_PATHS) == 2
    for old in LEGACY_PROCEDURES:
        assert is_legacy_pointer(old, legacy_pointer(old))
    with pytest.raises(KeyError):
        legacy_pointer("System/procedures/economizer.md")


@pytest.mark.parametrize("relative", ["Welcome.md", "System/README.md"])
def test_edited_seven_orientation_does_not_claim_current_source_ownership(tmp_path, relative):
    payload = historical_payload(tmp_path / "old/payload")
    (payload / relative).write_bytes((shipped_payload() / relative).read_bytes() + b"\nCustom orientation.\n")
    manifest = load_manifest(FIXTURES / "profiles.yaml", payload)
    assert set(manifest.managed_workflow_paths) == set(HISTORICAL_SKILL_PATHS)
    root = tmp_path / "area"; root.mkdir()
    plan, _ = instruction_updates(root, payload, OverlayPlan((), ()))
    assert not set(NEW_SKILL_PATHS) & {write.relative for write in plan.writes}
