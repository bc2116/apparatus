"""Static checks for the release workflow's safety-critical contract."""

from pathlib import Path
import os
import subprocess
import sys

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
    release = workflow["jobs"]["github-release"]
    assert release["permissions"] == {"contents": "write"}
    assert "needs.publish-pypi.result == 'success'" in release["if"]
    assert "needs.build.outputs.dry_run == 'true'" in release["if"]
    release_step = release["steps"][-1]
    assert "uses" not in release_step
    assert release_step["env"] == {
        "GH_TOKEN": "${{ github.token }}",
        "VERSION": "${{ needs.build.outputs.version }}",
        "DRY_RUN": "${{ needs.build.outputs.dry_run }}",
    }
    assert "gh release create" in release_step["run"]


def test_release_workflow_builds_and_attaches_every_release_file() -> None:
    content = (REPOSITORY_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    assert "uv run python tools/build_payload.py" in content
    assert "uv build --package apparatus-core --out-dir dist/packages" in content
    assert "release tag {ref_name!r} must exactly match package version" in content
    assert "softprops/action-gh-release" not in content
    assert "dist/apparatus-payload-${{ steps.release.outputs.version }}.zip" in content
    assert "dist/packages/apparatus_core-${{ steps.release.outputs.version }}.tar.gz" in content
    assert "dist/packages/apparatus_core-${{ steps.release.outputs.version }}-py3-none-any.whl" in content


def _release_metadata_script() -> str:
    workflow = yaml.safe_load(
        (REPOSITORY_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    )
    return workflow["jobs"]["build"]["steps"][3]["run"]


def _run_release_metadata(
    temporary_path: Path, changelog: str, *, event: str = "workflow_dispatch"
) -> tuple[str, str]:
    (temporary_path / "packages" / "apparatus-core").mkdir(parents=True)
    (temporary_path / "packages" / "apparatus-core" / "pyproject.toml").write_text(
        '[project]\nversion = "0.0.1"\n', encoding="utf-8"
    )
    (temporary_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    output = temporary_path / "github-output"
    environment = {
        **os.environ,
        "GITHUB_EVENT_NAME": event,
        "GITHUB_REF_NAME": "v0.0.1",
        "GITHUB_OUTPUT": str(output),
        "APPARATUS_RELEASE_MODE": "publish",
    }
    subprocess.run(
        [sys.executable, "-c", _release_metadata_script()],
        cwd=temporary_path,
        env=environment,
        check=True,
    )
    return (temporary_path / "dist" / "release-notes.md").read_text(encoding="utf-8"), output.read_text(
        encoding="utf-8"
    )


def test_release_metadata_creates_dist_in_a_fresh_tree_and_uses_exact_heading(tmp_path: Path) -> None:
    notes, output = _run_release_metadata(
        tmp_path,
        "# Changelog\n\n## v0.0.1\n\n- Exact notes.\n\n## v0.0.2\n\n- Later notes.\n",
    )

    assert notes == "# Dry-run release — not published to PyPI\n\n## v0.0.1\n\n- Exact notes.\n"
    assert output == "version=0.0.1\ndry_run=true\n"


def test_release_metadata_does_not_prefix_match_changelog_versions(tmp_path: Path) -> None:
    notes, _output = _run_release_metadata(tmp_path, "# Changelog\n\n## v0.0.10\n\n- Other notes.\n")

    assert "Release date:" in notes
    assert "Update CHANGELOG.md" in notes
    assert "Other notes." not in notes
