from __future__ import annotations

from pathlib import Path

from apparatus_core.render import render_workspace
from apparatus_core.shims import SHIM_REGISTRY
from payload_check import MANIFEST, PAYLOAD_DIR


REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDENS = REPO_ROOT / "conformance" / "golden" / "shims"


def _golden_for(target: str) -> Path:
    return GOLDENS / Path(target).name


def test_payload_canon_renders_to_exact_shim_goldens(tmp_path):
    (tmp_path / "AGENTS.md").write_bytes((PAYLOAD_DIR / "AGENTS.md").read_bytes())
    assert set(render_workspace(tmp_path).written) == {target for target, _ in SHIM_REGISTRY}
    for target, _template in SHIM_REGISTRY:
        assert (tmp_path / target).read_bytes() == _golden_for(target).read_bytes()


def test_payload_shims_are_byte_identical_to_the_goldens():
    for target, _template in SHIM_REGISTRY:
        assert (PAYLOAD_DIR / target).read_bytes() == _golden_for(target).read_bytes()


def test_every_registered_shim_is_in_the_payload_manifest():
    manifest = set(MANIFEST.read_text(encoding="utf-8").splitlines())
    assert {target for target, _template in SHIM_REGISTRY} <= manifest


def test_builtin_skills_render_portable_owned_work_area_adapters(tmp_path):
    from apparatus_core.skill_adapters import owns_adapter
    from apparatus_core.skills import BUILTIN_PATHS, validate_skill

    (tmp_path / "AGENTS.md").write_bytes((PAYLOAD_DIR / "AGENTS.md").read_bytes())
    for relative in BUILTIN_PATHS:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((PAYLOAD_DIR / relative).read_bytes())

    result = render_workspace(tmp_path)
    for relative, name in BUILTIN_PATHS.items():
        adapter_rel = f".claude/skills/{name}/SKILL.md"
        assert adapter_rel in result.written
        adapter_bytes = (tmp_path / adapter_rel).read_bytes()
        assert not validate_skill(adapter_bytes, name)
        assert owns_adapter(adapter_bytes, adapter_rel, is_project=False)
        assert relative.encode("utf-8") in adapter_bytes
    assert not any(
        (PAYLOAD_DIR / f".claude/skills/{name}/SKILL.md").exists()
        for name in BUILTIN_PATHS.values()
    )
