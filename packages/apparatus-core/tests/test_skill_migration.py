from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pytest

from apparatus_core.commands import init
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.instruction_updates import (
    SKILLS_PREVIOUS_INSTRUCTIONS, _digest, instruction_updates,
)
from apparatus_core.overlays import OverlayPlan
from apparatus_core.payload import PayloadError, shipped_payload
from apparatus_core.retention import start_task
from apparatus_core.skills import (
    BUILTIN_PATHS, LEGACY_PROCEDURES, SKILL_INDEX, canonical_path, legacy_pointer, validate_skill,
)

FIXTURES = Path(__file__).parent / "fixtures/instruction_updates_pr36"
LEGACY = "System/procedures/welcome.md"
CANONICAL = canonical_path(LEGACY_PROCEDURES[LEGACY])


def arguments(root, *, task=None):
    return argparse.Namespace(workspace=str(root), payload=None, privacy_mode=None,
                              work_types=None, adopt=True, task=task)


def files(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


def legacy_area(root, *, crlf=False):
    for source in FIXTURES.rglob("*"):
        if source.is_file():
            relative = source.relative_to(FIXTURES)
            content = source.read_bytes().replace(b"\r\n", b"\n")
            assert _digest(content) == SKILLS_PREVIOUS_INSTRUCTIONS[relative.as_posix()]
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content.replace(b"\n", b"\r\n") if crlf else content)
    shutil.copyfile(shipped_payload() / "System/profile.yaml", root / "System/profile.yaml")
    return root


@pytest.mark.parametrize("crlf", [False, True])
def test_legacy_fixture_converts_crlf_checkout_once(tmp_path, monkeypatch, crlf):
    checkout = tmp_path / "crlf-checkout"
    expected = {}
    for source in FIXTURES.rglob("*"):
        if source.is_file():
            relative = source.relative_to(FIXTURES)
            normalized = source.read_bytes().replace(b"\r\n", b"\n")
            expected[relative] = normalized.replace(b"\n", b"\r\n") if crlf else normalized
            target = checkout / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(normalized.replace(b"\n", b"\r\n"))
    monkeypatch.setitem(globals(), "FIXTURES", checkout)
    root = legacy_area(tmp_path / "area", crlf=crlf)
    for relative, content in expected.items():
        assert (root / relative).read_bytes() == content
        assert b"\r\r\n" not in content


def custom_skill(root):
    path = root / CANONICAL
    path.parent.mkdir(parents=True, exist_ok=True)
    content = ("---\r\nname: apparatus-welcome\r\ndescription: Custom introduction.\r\n"
               "---\r\n\r\nPreserve this custom body exactly.\r\n").encode()
    path.write_bytes(content)
    return content


@pytest.mark.parametrize("crlf", [False, True])
def test_pr36_upgrade_has_one_body_exact_pointers_and_repeat_is_unchanged(tmp_path, crlf):
    root = legacy_area(tmp_path / "area", crlf=crlf)
    assert init.run(arguments(root), available=lambda: False) == 0
    for relative, name in BUILTIN_PATHS.items():
        assert (root / relative).read_bytes() == (shipped_payload() / relative).read_bytes()
        assert not validate_skill((root / relative).read_bytes(), name)
    for relative in LEGACY_PROCEDURES:
        assert (root / relative).read_bytes() == legacy_pointer(relative)
    assert (root / "System/README.md").read_bytes() == (shipped_payload() / "System/README.md").read_bytes()
    before = files(root)
    assert init.run(arguments(root), available=lambda: False) == 0
    assert files(root) == before


def test_valid_custom_canonical_and_custom_canon_keep_exact_bytes_and_stock_stub_points_there(tmp_path):
    root = legacy_area(tmp_path / "area")
    custom = custom_skill(root)
    canon = (root / "AGENTS.md").read_bytes() + b"\nCustom local guidance.\n"
    (root / "AGENTS.md").write_bytes(canon)
    orientation = (root / "System/README.md").read_bytes() + b"\nCustom orientation.\n"
    (root / "System/README.md").write_bytes(orientation)
    foreign = root / ".agents/skills/unrelated/SKILL.md"
    foreign.parent.mkdir(parents=True)
    foreign.write_bytes(b"Unrelated native Skill is not ours to validate.\n")
    old_custom = root / "System/procedures/custom-work.md"
    old_custom.write_bytes(b"Existing custom workflow outside the migration mapping.\n")
    assert init.run(arguments(root), available=lambda: False) == 0
    assert (root / CANONICAL).read_bytes() == custom
    assert (root / LEGACY).read_bytes() == legacy_pointer(LEGACY)
    assert (root / "AGENTS.md").read_bytes() == canon
    assert (root / "System/README.md").read_bytes() == orientation
    assert foreign.read_bytes() == b"Unrelated native Skill is not ours to validate.\n"
    assert old_custom.read_bytes() == b"Existing custom workflow outside the migration mapping.\n"


@pytest.mark.parametrize("canonical_present", [False, True])
def test_custom_legacy_builtin_is_preflight_conflict_even_with_valid_canonical(tmp_path, capsys, canonical_present):
    root = legacy_area(tmp_path / "area")
    (root / LEGACY).write_bytes((root / LEGACY).read_bytes() + b"\nCustom workflow.\n")
    if canonical_present:
        custom_skill(root)
    before = files(root)
    assert init.run(arguments(root), available=lambda: False) == 2
    output = capsys.readouterr().out
    assert LEGACY in output and "preserve your edits" in output
    assert files(root) == before


@pytest.mark.parametrize("content", [b"foreign text", b"---\nname: foreign\ndescription: Other skill.\n---\nBody.\n"])
def test_invalid_or_foreign_canonical_collision_has_zero_writes(tmp_path, capsys, content):
    root = legacy_area(tmp_path / "area")
    path = root / CANONICAL
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    before = files(root)
    assert init.run(arguments(root), available=lambda: False) == 2
    assert CANONICAL in capsys.readouterr().out
    assert files(root) == before


def test_exact_crlf_stub_is_preserved_without_treating_header_as_ownership(tmp_path):
    root = legacy_area(tmp_path / "area")
    pointer = legacy_pointer(LEGACY).replace(b"\n", b"\r\n")
    (root / LEGACY).write_bytes(pointer)
    assert init.run(arguments(root), available=lambda: False) == 0
    assert (root / LEGACY).read_bytes() == pointer
    modified = pointer + b"\r\nA changed pointer is custom.\r\n"
    (root / LEGACY).write_bytes(modified)
    before = files(root)
    assert init.run(arguments(root), available=lambda: False) == 2
    assert files(root) == before


@pytest.mark.parametrize("relative", [LEGACY, CANONICAL])
def test_stale_migration_preimage_preserves_concurrent_edit_before_publication(tmp_path, monkeypatch, relative):
    root = legacy_area(tmp_path / "area")
    original = init.deploy_init_plan
    competing = b"Concurrent user-owned content.\n"
    before = files(root)
    def raced(*values, **options):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(competing)
        return original(*values, **options)
    monkeypatch.setattr(init, "deploy_init_plan", raced)
    assert init.run(arguments(root), available=lambda: False) == 2
    assert files(root) == {**before, relative: competing}


def test_late_skill_publication_failure_rolls_back_canonical_and_legacy_changes(tmp_path, monkeypatch):
    root = legacy_area(tmp_path / "area")
    before = files(root)
    original = WorkspaceAnchor.matches_owned
    observed = []
    def reject_skill(anchor, proof):
        if proof.relative == Path("SKILL.md"):
            observed.append(proof.content)
            return False
        return original(anchor, proof)
    monkeypatch.setattr(WorkspaceAnchor, "matches_owned", reject_skill)
    assert init.run(arguments(root), available=lambda: False) == 2
    assert observed
    assert files(root) == before


def test_no_save_installs_only_generic_guidance_without_snapshot(tmp_path):
    root = legacy_area(tmp_path / "area")
    task = start_task(root, save_memory=False)
    task_path = root / f"System/tasks/{task.task_id}.yaml"
    before = task_path.read_bytes()
    def forbidden(*_values, **_options):
        pytest.fail("no-save generic guidance installation took an automatic snapshot")
    assert init.run(arguments(root, task=task.task_id), available=lambda: True, take=forbidden) == 0
    assert task_path.read_bytes() == before
    assert all((root / relative).is_file() for relative in BUILTIN_PATHS)
    assert not (root / "System/recovery").exists()


def test_incomplete_native_source_is_rejected_and_entirely_legacy_source_remains_supported(tmp_path):
    root = legacy_area(tmp_path / "area")
    payload = tmp_path / "payload"
    shutil.copytree(FIXTURES, payload)
    before = files(root)
    plan, expected = instruction_updates(root, payload, OverlayPlan((), ()))
    assert not any(write.relative in BUILTIN_PATHS for write in plan.writes)
    assert not set(BUILTIN_PATHS) & expected.keys()
    path = payload / CANONICAL
    path.parent.mkdir(parents=True)
    path.write_bytes((shipped_payload() / CANONICAL).read_bytes())
    with pytest.raises(PayloadError, match="complete portable Skill payload"):
        instruction_updates(root, payload, OverlayPlan((), ()))
    assert files(root) == before


@pytest.mark.parametrize("evidence", ["empty-directory", "stock-index"])
def test_source_with_all_bodies_missing_cannot_masquerade_as_legacy(tmp_path, evidence):
    root = legacy_area(tmp_path / "area")
    payload = tmp_path / "payload"
    shutil.copytree(FIXTURES, payload)
    if evidence == "empty-directory":
        (payload / CANONICAL).parent.mkdir(parents=True)
    else:
        (payload / "AGENTS.md").write_text(SKILL_INDEX, encoding="utf-8")
    with pytest.raises(PayloadError, match="complete portable Skill payload"):
        instruction_updates(root, payload, OverlayPlan((), ()))


@pytest.mark.parametrize("pointer", [False, True])
def test_native_source_cannot_publish_a_second_legacy_workflow(tmp_path, pointer):
    root = legacy_area(tmp_path / "area")
    payload = tmp_path / "payload"
    shutil.copytree(shipped_payload(), payload)
    path = payload / LEGACY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(legacy_pointer(LEGACY) if pointer else (FIXTURES / LEGACY).read_bytes())
    before = files(root)
    with pytest.raises(PayloadError, match="native payload contains legacy workflow"):
        instruction_updates(root, payload, OverlayPlan((), ()))
    assert files(root) == before
