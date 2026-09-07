from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from apparatus_core.overlays import (
    ManifestError, OverlayManifest, OverlayPlan, OverlayWrite, apply_overlay, apply_overlay_plan,
    load_manifest, plan_overlay,
)
from apparatus_core.payload import shipped_payload
from apparatus_core.skills import BUILTIN_PATHS, NEW_SKILL_PATHS


def source(tmp_path):
    root = Path(__file__).parents[3]
    payload = tmp_path / "payload"
    shutil.copytree(shipped_payload(), payload)
    manifest = root / "starter/profiles/profiles.yaml"
    return payload, manifest


def test_native_overlay_preserves_custom_body_and_unrelated_resources(tmp_path):
    payload, path = source(tmp_path)
    manifest = load_manifest(path, payload)
    area = tmp_path / "area"
    area.mkdir()
    apply_overlay(payload, area, manifest, privacy_mode="standard", work_types=("analysis",))
    relative = next(iter(BUILTIN_PATHS))
    custom = (area / relative).read_bytes() + b"\nCustom workflow remains authoritative.\n"
    (area / relative).write_bytes(custom)
    other = area / ".agents/skills/other/SKILL.md"
    other.parent.mkdir()
    other.write_bytes(b"Outside managed scope")
    resource = (area / relative).parent / "reference.txt"
    resource.write_bytes(b"Custom resource")
    apply_overlay(payload, area, manifest, privacy_mode="private", work_types=("writing",))
    assert (area / relative).read_bytes() == custom
    assert other.read_bytes() == b"Outside managed scope"
    assert resource.read_bytes() == b"Custom resource"
    assert set(manifest.managed_workflow_paths) == set(BUILTIN_PATHS)


@pytest.mark.parametrize("valid", [False, True])
@pytest.mark.parametrize("first", [next(iter(BUILTIN_PATHS)), *NEW_SKILL_PATHS])
def test_deselection_preserves_valid_custom_skill_and_rejects_invalid_occupant(tmp_path, valid, first):
    payload, path = source(tmp_path)
    stock = load_manifest(path, payload)
    others = [path for path in BUILTIN_PATHS if path != first]
    manifest = OverlayManifest(stock.privacy_modes, {"one": (first,), "others": tuple(others)},
                               "standard", ("one",))
    area = tmp_path / "area"
    area.mkdir()
    apply_overlay(payload, area, manifest, privacy_mode="standard", work_types=("one",))
    custom = (area / first).read_bytes() + b"\nCustom workflow.\n" if valid else b"Invalid custom content"
    (area / first).write_bytes(custom)
    if valid:
        apply_overlay(payload, area, manifest, privacy_mode="standard", work_types=("others",))
    else:
        before = {p.relative_to(area): p.read_bytes() for p in area.rglob("*") if p.is_file()}
        with pytest.raises(ManifestError):
            apply_overlay(payload, area, manifest, privacy_mode="standard", work_types=("others",))
        assert {p.relative_to(area): p.read_bytes() for p in area.rglob("*") if p.is_file()} == before
    assert (area / first).read_bytes() == custom


@pytest.mark.parametrize("change", ["missing", "invalid", "foreign"])
def test_partial_or_invalid_native_source_fails_before_target_changes(tmp_path, change):
    payload, path = source(tmp_path)
    manifest = load_manifest(path, payload)
    victim = payload / next(iter(BUILTIN_PATHS))
    if change == "missing":
        victim.unlink()
    elif change == "invalid":
        victim.write_bytes(b"Invalid portable metadata")
    else:
        victim.write_bytes(b"---\nname: foreign\ndescription: Other.\n---\nBody")
    area = tmp_path / "area"
    area.mkdir()
    for action in (lambda: load_manifest(path, payload), lambda: plan_overlay(
        payload, area, manifest, privacy_mode="standard", work_types=("analysis",)
    )):
        with pytest.raises(ManifestError):
            action()
    assert not list(area.iterdir())


@pytest.mark.parametrize("relative", [".agents/skills/other/SKILL.md", ".agents/skills/apparatus-welcome/reference.txt"])
def test_external_overlay_plan_cannot_claim_third_party_skills_or_resources(tmp_path, relative):
    area = tmp_path / "area"
    area.mkdir()
    for plan in (OverlayPlan((OverlayWrite(relative, b"Other content"),), ()),
                 OverlayPlan((), (relative,))):
        with pytest.raises(ManifestError):
            apply_overlay_plan(area, plan)
    assert not list(area.iterdir())
