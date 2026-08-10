"""Static checks for the release workflow's safety-critical contract."""

from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_release_workflow_keeps_dispatch_and_publishing_separate() -> None:
    workflow = yaml.safe_load(
        (REPOSITORY_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    )

    assert workflow[True]["push"]["tags"] == ["v*"]
    assert workflow[True]["workflow_dispatch"] is None
    publish = workflow["jobs"]["publish-pypi"]
    assert "github.event_name == 'push'" in publish["if"]
    assert publish["environment"] == "pypi"
    assert publish["permissions"] == {"id-token": "write"}
    action = publish["steps"][-1]
    assert action["uses"] == "pypa/gh-action-pypi-publish@release/v1"
    assert "token" not in str(action).lower()


def test_release_workflow_builds_and_attaches_every_release_file() -> None:
    content = (REPOSITORY_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    assert "uv run python tools/build_payload.py" in content
    assert "uv build --package apparatus-core --out-dir dist/packages" in content
    assert "release tag {ref_name!r} must exactly match package version" in content
    assert "dist/apparatus-payload-${{ steps.release.outputs.version }}.zip" in content
    assert "dist/packages/apparatus_core-${{ steps.release.outputs.version }}.tar.gz" in content
    assert "dist/packages/apparatus_core-${{ steps.release.outputs.version }}-py3-none-any.whl" in content
