"""Static checks for the release workflow's safety-critical contract."""

from pathlib import Path
import os
import shutil
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
    assert "needs.build.result == 'success'" in release["if"]
    assert "needs.publish-pypi.result == 'success'" in release["if"]
    assert "needs.build.outputs.dry_run == 'true'" in release["if"]
    release_step = release["steps"][-1]
    assert "uses" not in release_step
    assert release_step["env"] == {
        "GH_TOKEN": "${{ github.token }}",
        "GH_REPO": "${{ github.repository }}",
        "VERSION": "${{ needs.build.outputs.version }}",
        "DRY_RUN": "${{ needs.build.outputs.dry_run }}",
        "SDIST_NAME": "${{ needs.build.outputs.sdist_name }}",
        "WHEEL_NAME": "${{ needs.build.outputs.wheel_name }}",
    }
    assert "gh release create" in release_step["run"]
    assert '--repo "$GH_REPO"' in release_step["run"]


def test_release_workflow_builds_and_attaches_every_release_file() -> None:
    content = (REPOSITORY_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    assert "uv run python tools/build_payload.py" in content
    assert "uv build --package apparatus-core --out-dir dist/packages" in content
    assert "release tag {ref_name!r} must exactly match package version" in content
    assert "softprops/action-gh-release" not in content
    assert 'cp "dist/apparatus-payload-${VERSION}.zip" dist/release-files/' in content
    assert 'cp "dist/packages/${SDIST_NAME}" dist/release-files/packages/' in content
    assert 'cp "dist/packages/${WHEEL_NAME}" dist/release-files/packages/' in content
    assert '"release-files/packages/${SDIST_NAME}"' in content
    assert '"release-files/packages/${WHEEL_NAME}"' in content
    assert "apparatus_core-${VERSION}.tar.gz" not in content
    assert "apparatus_core-${VERSION}-py3-none-any.whl" not in content
    assert 'vars.APPARATUS_SIGN_WINDOWS == \'enabled\'' in content
    assert 'vars.APPARATUS_SIGN_MACOS == \'enabled\'' in content
    assert "runs-on: ${{ vars.APPARATUS_WINDOWS_SIGNING_RUNNER }}" in content
    assert "Cert:\\CurrentUser\\My" in content
    assert "signtool.exe sign /sha1" in content
    assert '"installer/windows/bootstrap-apparatus.ps1"' in content
    assert '"installer/macos/bootstrap-apparatus.sh"' in content
    assert "> SHA256SUMS" in content
    assert "path: dist/release-files" in content
    assert "cp -a release-inputs/. final-release/" in content
    assert "needs: [build, assemble-release]" in content
    assert "xcrun notarytool store-credentials apparatus-notary" in content
    assert 'release_files+=("installer/macos/apparatus-installer.pkg")' in content
    assert 'release_files+=("release-files/installer/macos/apparatus-installer.pkg")' in content


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


def test_github_release_uses_explicit_quoted_repo_without_git_checkout(tmp_path: Path) -> None:
    workflow = yaml.safe_load(
        (REPOSITORY_ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
    )
    release_step = workflow["jobs"]["github-release"]["steps"][-1]
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    captured = tmp_path / "gh-arguments"
    fake_gh = fake_bin / "gh"
    fake_gh.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$GH_ARGUMENTS\"\n",
        encoding="utf-8",
    )
    fake_gh.chmod(0o755)
    release_files = tmp_path / "release-files" / "packages"
    release_files.mkdir(parents=True)
    for relative_path in (
        "release-notes.md",
        "apparatus-payload-0.0.1.zip",
        "packages/apparatus_core-0.0.1.tar.gz",
        "packages/apparatus_core-0.0.1-py3-none-any.whl",
        "installer/windows/bootstrap-apparatus.ps1",
        "installer/macos/bootstrap-apparatus.sh",
        "SHA256SUMS",
    ):
        path = tmp_path / "release-files" / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test", encoding="utf-8")

    repository = "owner/repository; touch should-not-exist"
    environment = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "GH_ARGUMENTS": str(captured),
        "GH_REPO": repository,
        "GH_TOKEN": "test-token",
        "VERSION": "0.0.1",
        "DRY_RUN": "true",
        "SDIST_NAME": "apparatus_core-0.0.1.tar.gz",
        "WHEEL_NAME": "apparatus_core-0.0.1-py3-none-any.whl",
    }
    subprocess.run(
        ["bash", "-c", release_step["run"]],
        cwd=tmp_path,
        env=environment,
        check=True,
    )

    arguments = captured.read_text(encoding="utf-8").splitlines()
    assert arguments[:5] == ["release", "create", "v0.0.1", "--repo", repository]
    assert "release-files/installer/windows/bootstrap-apparatus.ps1" in arguments
    assert "release-files/installer/macos/bootstrap-apparatus.sh" in arguments
    assert "release-files/SHA256SUMS" in arguments
    assert not (tmp_path / "should-not-exist").exists()


def _github_release_is_eligible(
    *,
    build_result: str,
    assemble_result: str,
    dry_run: str,
    publish_result: str,
    event: str = "push",
) -> bool:
    workflow = yaml.safe_load(
        (REPOSITORY_ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
    )
    expression = workflow["jobs"]["github-release"]["if"]
    substitutions = {
        "always()": True,
        "github.event_name == 'push'": event == "push",
        "needs.build.result == 'success'": build_result == "success",
        "needs.assemble-release.result == 'success'": assemble_result == "success",
        "needs.build.outputs.dry_run == 'true'": dry_run == "true",
        "needs.publish-pypi.result == 'success'": publish_result == "success",
    }
    for term, value in substitutions.items():
        expression = expression.replace(term, str(value))
    expression = expression.replace("&&", " and ").replace("||", " or ")
    assert not any(character not in "TrueFalsandor ()" for character in expression)
    return bool(eval(expression, {"__builtins__": {}}, {}))


def test_github_release_requires_a_successful_build_for_every_path() -> None:
    assert not _github_release_is_eligible(
        build_result="failure", assemble_result="skipped", dry_run="true", publish_result="skipped"
    )
    assert not _github_release_is_eligible(
        build_result="failure", assemble_result="skipped", dry_run="false", publish_result="success"
    )
    assert not _github_release_is_eligible(
        build_result="success", assemble_result="failure", dry_run="true", publish_result="skipped"
    )
    assert _github_release_is_eligible(
        build_result="success", assemble_result="success", dry_run="true", publish_result="skipped"
    )
    assert _github_release_is_eligible(
        build_result="success", assemble_result="success", dry_run="false", publish_result="success"
    )
    assert not _github_release_is_eligible(
        build_result="success", assemble_result="success", dry_run="false", publish_result="failure"
    )


def _distribution_resolver_script() -> str:
    workflow = yaml.safe_load(
        (REPOSITORY_ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
    )
    steps = workflow["jobs"]["build"]["steps"]
    return next(step["run"] for step in steps if step.get("id") == "packages")


def _run_distribution_resolver(temporary_path: Path, names: tuple[str, ...]) -> str:
    package_dir = temporary_path / "dist" / "packages"
    package_dir.mkdir(parents=True)
    for name in names:
        (package_dir / name).write_text("distribution", encoding="utf-8")
    output = temporary_path / "github-output"
    subprocess.run(
        [sys.executable, "-c", _distribution_resolver_script()],
        cwd=temporary_path,
        env={**os.environ, "GITHUB_OUTPUT": str(output)},
        check=True,
    )
    return output.read_text(encoding="utf-8")


def _run_real_build_and_resolver(temporary_path: Path, *, version: str | None = None) -> str:
    source = REPOSITORY_ROOT / "packages" / "apparatus-core"
    if version is not None:
        copied_source = temporary_path / "apparatus-core"
        shutil.copytree(source, copied_source)
        pyproject = copied_source / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8")
        text = text.replace('version = "0.0.1"', f'version = "{version}"', 1)
        pyproject.write_text(text, encoding="utf-8")
        source = copied_source
    package_dir = temporary_path / "dist" / "packages"
    subprocess.run(
        ["uv", "build", str(source), "--out-dir", str(package_dir)],
        cwd=temporary_path,
        check=True,
    )
    assert (package_dir / ".gitignore").read_bytes() == b"*"
    output = temporary_path / "github-output"
    subprocess.run(
        [sys.executable, "-c", _distribution_resolver_script()],
        cwd=temporary_path,
        env={**os.environ, "GITHUB_OUTPUT": str(output)},
        check=True,
    )
    return output.read_text(encoding="utf-8")


def test_distribution_resolver_accepts_current_real_uv_build(tmp_path: Path) -> None:
    output = _run_real_build_and_resolver(tmp_path)

    assert output == (
        "sdist_name=apparatus_core-0.0.1.tar.gz\n"
        "wheel_name=apparatus_core-0.0.1-py3-none-any.whl\n"
    )


def test_distribution_resolver_uses_normalized_real_prerelease_build(tmp_path: Path) -> None:
    output = _run_real_build_and_resolver(tmp_path, version="1.0.0-rc1")

    assert output == (
        "sdist_name=apparatus_core-1.0.0rc1.tar.gz\n"
        "wheel_name=apparatus_core-1.0.0rc1-py3-none-any.whl\n"
    )


def test_distribution_resolver_rejects_missing_or_ambiguous_files(tmp_path: Path) -> None:
    package_dir = tmp_path / "dist" / "packages"
    package_dir.mkdir(parents=True)
    output = tmp_path / "github-output"
    environment = {**os.environ, "GITHUB_OUTPUT": str(output)}

    missing = subprocess.run(
        [sys.executable, "-c", _distribution_resolver_script()],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert missing.returncode != 0
    assert "exactly one sdist and one wheel" in missing.stderr

    for name in (
        "apparatus_core-1.0.0.tar.gz",
        "apparatus_core-1.0.0-py3-none-any.whl",
        "apparatus_core-1.0.0-py2-none-any.whl",
    ):
        (package_dir / name).write_text("distribution", encoding="utf-8")
    ambiguous = subprocess.run(
        [sys.executable, "-c", _distribution_resolver_script()],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert ambiguous.returncode != 0
    assert "exactly one sdist and one wheel" in ambiguous.stderr


def test_distribution_resolver_rejects_unexpected_entry_or_metadata_content(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "dist" / "packages"
    package_dir.mkdir(parents=True)
    for name in (
        "apparatus_core-1.0.0.tar.gz",
        "apparatus_core-1.0.0-py3-none-any.whl",
    ):
        (package_dir / name).write_text("distribution", encoding="utf-8")
    output = tmp_path / "github-output"
    environment = {**os.environ, "GITHUB_OUTPUT": str(output)}

    unexpected = package_dir / "unexpected.txt"
    unexpected.write_text("unexpected", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-c", _distribution_resolver_script()],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "unexpected entry" in result.stderr
    unexpected.unlink()

    (package_dir / ".gitignore").write_text("*.whl", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-c", _distribution_resolver_script()],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert ".gitignore has unexpected content" in result.stderr

    (package_dir / ".gitignore").unlink()
    metadata_target = tmp_path / "metadata-target"
    metadata_target.write_text("*", encoding="utf-8")
    (package_dir / ".gitignore").symlink_to(metadata_target)
    result = subprocess.run(
        [sys.executable, "-c", _distribution_resolver_script()],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "only regular distribution files" in result.stderr
