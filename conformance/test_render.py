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
