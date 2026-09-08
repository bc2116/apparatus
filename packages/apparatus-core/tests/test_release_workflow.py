"""Static checks for the release workflow's safety-critical contract."""

from pathlib import Path
import os
import shutil
import subprocess
import sys

import pytest
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
    assert release["needs"] == ["build", "publish-pypi", "assemble-release"]
    assert release["environment"] == "release"
    assert release["permissions"] == {"contents": "write"}
    assert "needs.build.result == 'success'" in release["if"]
    assert "needs.publish-pypi.result == 'success'" in release["if"]
    assert "needs.build.outputs.dry_run == 'false'" in release["if"]
    release_step = release["steps"][-1]
    assert "uses" not in release_step
    assert release_step["env"] == {
        "GH_TOKEN": "${{ github.token }}",
        "GH_REPO": "${{ github.repository }}",
        "VERSION": "${{ needs.build.outputs.version }}",
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
    assert '"release-files/${SDIST_NAME}"' in content
    assert '"release-files/${WHEEL_NAME}"' in content
    assert "apparatus_core-${VERSION}.tar.gz" not in content
    assert "apparatus_core-${VERSION}-py3-none-any.whl" not in content
    assert 'vars.APPARATUS_SIGN_WINDOWS == \'enabled\'' in content
    assert 'vars.APPARATUS_SIGN_MACOS == \'enabled\'' in content
    assert "runs-on: [self-hosted, Windows, X64, apparatus-signing-windows]" in content
    assert "APPARATUS_WINDOWS_SIGNING_RUNNER" not in content
    assert "Cert:\\CurrentUser\\My" in content
    assert "$sdkBin = 'C:\\Program Files (x86)\\Windows Kits\\10\\bin'" in content
    assert "Get-AuthenticodeSignature -FilePath $signTool.FullName" in content
    assert "& $signTool.FullName sign /sha1" in content
    assert "APPARATUS_SIGNTOOL_PATH" not in content
    assert ".Thumbprint -ceq" in content
    assert ".Subject -cne" in content
    assert ".NotBefore.ToUniversalTime()" in content
    assert ".NotAfter.ToUniversalTime()" in content
    assert "1.3.6.1.5.5.7.3.3" in content
    assert ".HasPrivateKey" in content
    assert "GetRSAPrivateKey" in content
    assert "installer/windows/bootstrap-apparatus.ps1" in content
    assert "installer/macos/bootstrap-apparatus.sh" in content
    assert "dist/windows/apparatus-installer.exe" in content
    assert "dist/macos/apparatus-installer.pkg" in content
    assert "runs-on: windows-2025" in content
    assert "runs-on: macos-15" in content
    assert "INNO_SETUP_VERSION: '7.0.2'" in content
    assert "2b8734490a83f1ed074022b85d46c5ce9c3e2fbe9b63a45c28a74b478ac3a94f" in content
    assert "Get-AuthenticodeSignature -FilePath $download" in content
    assert "CN=Pyrsys B\\.V\\." in content
    assert content.count("shell: pwsh") >= 3
    assert content.count("[System.Diagnostics.ProcessStartInfo]::new()") == 3
    assert content.count("$startInfo.UseShellExecute = $false") == 3
    assert content.count("$startInfo.ArgumentList.Add($argument)") == 3
    assert content.count("$process.WaitForExit()") == 3
    assert "apparatus-injection-marker';" in content
    assert r"@('C:\Runner Temp\Apparatus\', 'C:\Runner Temp\Apparatus\\')" in content
    assert "apparatus-unsigned-windows-installer" in content
    assert "apparatus-signed-windows-installer" in content
    assert "apparatus-unsigned-macos-installer" in content
    assert "apparatus-signed-macos-installer" in content
    assert "'unsigned-windows/apparatus-installer.exe'" in content
    assert "productsign --keychain" in content
    assert '--keychain "$keychain_path"' in content
    assert "security set-key-partition-list" in content
    assert 'pkgutil --check-signature "$package_path"' in content
    assert 'spctl --assess --type install --verbose=2 "$package_path"' in content
    assert 'xcrun stapler validate "$package_path"' in content
    assert "needs.build-windows-installer.result == 'success'" in content
    assert "needs.build-macos-installer.result == 'success'" in content
    assert "canary-uid=$runner_uid" in content
    assert "canary-path=/usr/bin:/bin:/usr/sbin:/sbin" in content
    assert "> SHA256SUMS" in content
    assert "shasum -a 256 --check SHA256SUMS" in content
    assert "path: dist/release-files" in content
    assert 'cp "release-inputs/packages/${SDIST_NAME}" final-release/' in content
    assert 'cp "release-inputs/packages/${WHEEL_NAME}" final-release/' in content
    assert "needs: [build, assemble-release]" in content
    assert "xcrun notarytool store-credentials apparatus-notary" in content
    assert '"apparatus-installer.exe"' in content
    assert '"apparatus-installer.pkg"' in content
    assert '"release-files/apparatus-installer.exe"' in content
    assert '"release-files/apparatus-installer.pkg"' in content
    assert content.count("OPERATOR:") >= 10
    assert "windows_signing_provider: ${{ steps.release.outputs.windows_signing_provider }}" in content
    assert "Azure/login@7184910d9eb2b1c5e48f7073824a90609bb9b6d6" in content
    assert "Azure/artifact-signing-action@c7ab2a863ab5f9a846ddb8265964877ef296ee82" in content
    assert "trusted-signing-account-name" not in content
    assert "signing-account-name:" in content
    assert "id-token: write" in content
    assert "cache-dependencies: false" in content
    assert "exclude-environment-credential: true" in content
    assert "exclude-azure-cli-credential: false" in content
    assert "timestamp-rfc3161: http://timestamp.acs.microsoft.com" in content
    assert "files: ${{ github.workspace }}/unsigned-windows/apparatus-installer.exe" in content
    assert "verify /pa /tw" in content
    assert "1.3.6.1.4.1.311.10.3.13" in content


def test_signing_documents_pin_operator_configuration_and_it_claims() -> None:
    runbook = (REPOSITORY_ROOT / "docs" / "signing-runbook.md").read_text(
        encoding="utf-8"
    )
    for secret_name in (
        "APPARATUS_MACOS_SIGNING_CERTIFICATE_BASE64",
        "APPARATUS_MACOS_SIGNING_CERTIFICATE_PASSWORD",
        "APPARATUS_MACOS_SIGNING_IDENTITY",
        "APPARATUS_MACOS_NOTARY_APPLE_ID",
        "APPARATUS_MACOS_NOTARY_TEAM_ID",
        "APPARATUS_MACOS_NOTARY_APP_PASSWORD",
    ):
        assert secret_name in runbook
    assert (
        "Complete the CA or service's organization or individual identity checks" in runbook
    )
    assert "Environment-level variables cannot select a runner" in runbook
    assert "never route pull requests, fork code, or unrelated workloads" in runbook
    assert "APPARATUS_WINDOWS_SIGNING_RUNNER" not in runbook

    one_pager = (REPOSITORY_ROOT / "docs" / "it-onepager.md").read_text(
        encoding="utf-8"
    )
    headings = [
        "## What gets installed and where",
        "## Workspace data",
        "## Network and channels",
        "## Privacy model",
        "## Receipts",
        "## Clean uninstall",
    ]
    positions = [one_pager.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert len(one_pager.split()) <= 600
    assert "Releases include an Inno Setup `.exe` and a no-payload macOS `.pkg`" in one_pager
    assert "standard receipt and log metadata" in one_pager
    assert "`SHA256SUMS` covers the seven distributable artifacts" in one_pager


def _release_metadata_script() -> str:
    workflow = yaml.safe_load(
        (REPOSITORY_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    )
    return workflow["jobs"]["build"]["steps"][3]["run"]


def _run_release_metadata(
    temporary_path: Path, changelog: str, *, event: str = "workflow_dispatch", provider: str = ""
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
        "APPARATUS_WINDOWS_SIGNING_PROVIDER": provider,
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
    assert output == "version=0.0.1\ndry_run=true\nwindows_signing_provider=certificate-store\n"


def test_release_metadata_resolves_only_supported_windows_signing_providers(tmp_path: Path) -> None:
    _notes, azure_output = _run_release_metadata(
        tmp_path / "azure", "# Changelog\n", provider="azure-artifact-signing"
    )
    assert azure_output.endswith("windows_signing_provider=azure-artifact-signing\n")

    invalid = subprocess.run(
        [sys.executable, "-c", _release_metadata_script()],
        cwd=tmp_path / "azure",
        env={
            **os.environ,
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF_NAME": "v0.0.1",
            "GITHUB_OUTPUT": str(tmp_path / "invalid-output"),
            "APPARATUS_RELEASE_MODE": "publish",
            "APPARATUS_WINDOWS_SIGNING_PROVIDER": "other",
        },
        capture_output=True,
        text=True,
    )
    assert invalid.returncode != 0
    assert "certificate-store or azure-artifact-signing" in invalid.stderr


def test_release_metadata_does_not_prefix_match_changelog_versions(tmp_path: Path) -> None:
    notes, _output = _run_release_metadata(tmp_path, "# Changelog\n\n## v0.0.10\n\n- Other notes.\n")

    assert "Release date:" in notes
    assert "Update CHANGELOG.md" in notes
    assert "bare Windows and macOS bootstrap scripts" in notes
    assert "Windows and macOS installer wrappers" in notes
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
    release_files = tmp_path / "release-files"
    release_files.mkdir()
    for relative_path in (
        "release-notes.md",
        "apparatus-payload-0.0.1.zip",
        "apparatus_core-0.0.1.tar.gz",
        "apparatus_core-0.0.1-py3-none-any.whl",
        "bootstrap-apparatus.ps1",
        "bootstrap-apparatus.sh",
        "apparatus-installer.exe",
        "apparatus-installer.pkg",
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
    assert "release-files/bootstrap-apparatus.ps1" in arguments
    assert "release-files/bootstrap-apparatus.sh" in arguments
    assert "release-files/apparatus-installer.exe" in arguments
    assert "release-files/apparatus-installer.pkg" in arguments
    assert "release-files/SHA256SUMS" in arguments
    assert not (tmp_path / "should-not-exist").exists()


def _job_step_run(job_name: str, step_name: str) -> str:
    workflow = yaml.safe_load(
        (REPOSITORY_ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
    )
    steps = workflow["jobs"][job_name]["steps"]
    return next(step["run"] for step in steps if step.get("name") == step_name)


def _run_azure_configuration(tmp_path: Path, **values: str) -> subprocess.CompletedProcess[str]:
    output = tmp_path / "github-output"
    output.parent.mkdir(parents=True, exist_ok=True)
    defaults = {
        "APPARATUS_AZURE_SIGNING_TENANT_ID": "11111111-1111-1111-1111-111111111111",
        "APPARATUS_AZURE_SIGNING_CLIENT_ID": "22222222-2222-2222-2222-222222222222",
        "APPARATUS_AZURE_SIGNING_SUBSCRIPTION_ID": "33333333-3333-3333-3333-333333333333",
        "APPARATUS_AZURE_SIGNING_ENDPOINT": "https://westus.codesigning.azure.net",
        "APPARATUS_AZURE_SIGNING_ACCOUNT_NAME": "apparatus-signing",
        "APPARATUS_AZURE_SIGNING_CERTIFICATE_PROFILE_NAME": "public-trust",
        "APPARATUS_WINDOWS_SIGNING_CERTIFICATE_SUBJECT": "CN=Apparatus Publisher",
    }
    defaults.update(values)
    return subprocess.run(
        [sys.executable, "-c", _job_step_run("sign-windows-installer-azure", "Validate Azure signing configuration")],
        env={**os.environ, **defaults, "GITHUB_OUTPUT": str(output)},
        capture_output=True,
        text=True,
    )


def test_azure_signing_configuration_rejects_malformed_and_injected_metadata(tmp_path: Path) -> None:
    valid = _run_azure_configuration(tmp_path / "valid")
    assert valid.returncode == 0, valid.stderr
    assert (tmp_path / "valid" / "github-output").read_text(encoding="utf-8").splitlines() == [
        "apparatus_azure_signing_tenant_id=11111111-1111-1111-1111-111111111111",
        "apparatus_azure_signing_client_id=22222222-2222-2222-2222-222222222222",
        "apparatus_azure_signing_subscription_id=33333333-3333-3333-3333-333333333333",
        "apparatus_azure_signing_endpoint=https://westus.codesigning.azure.net",
        "apparatus_azure_signing_account_name=apparatus-signing",
        "apparatus_azure_signing_certificate_profile_name=public-trust",
        "apparatus_windows_signing_certificate_subject=CN=Apparatus Publisher",
    ]
    for index, (name, value) in enumerate((
        ("APPARATUS_AZURE_SIGNING_TENANT_ID", "not-a-uuid"),
        ("APPARATUS_AZURE_SIGNING_CLIENT_ID", "22222222-2222-2222-2222-222222222222\nextra"),
        ("APPARATUS_AZURE_SIGNING_ENDPOINT", "https://user@westus.codesigning.azure.net"),
        ("APPARATUS_AZURE_SIGNING_ENDPOINT", "https://westus.codesigning.azure.net:443"),
        ("APPARATUS_AZURE_SIGNING_ENDPOINT", "https://westus.codesigning.azure.net/sign"),
        ("APPARATUS_AZURE_SIGNING_ENDPOINT", "http://westus.codesigning.azure.net"),
        ("APPARATUS_AZURE_SIGNING_ENDPOINT", " https://westus.codesigning.azure.net"),
        ("APPARATUS_AZURE_SIGNING_ACCOUNT_NAME", "not a name"),
        ("APPARATUS_AZURE_SIGNING_ACCOUNT_NAME", "a" * 25),
        ("APPARATUS_AZURE_SIGNING_ACCOUNT_NAME", "account-"),
        ("APPARATUS_AZURE_SIGNING_CERTIFICATE_PROFILE_NAME", "p" * 101),
        ("APPARATUS_AZURE_SIGNING_CERTIFICATE_PROFILE_NAME", "profile_name"),
        ("APPARATUS_WINDOWS_SIGNING_CERTIFICATE_SUBJECT", " CN=Apparatus Publisher"),
        ("APPARATUS_WINDOWS_SIGNING_CERTIFICATE_SUBJECT", "CN=Apparatus\u0085Publisher"),
    )):
        rejected = _run_azure_configuration(tmp_path / f"invalid-{index}", **{name: value})
        assert rejected.returncode != 0

    maximum_names = _run_azure_configuration(
        tmp_path / "maximum-names",
        APPARATUS_AZURE_SIGNING_ACCOUNT_NAME="a" * 24,
        APPARATUS_AZURE_SIGNING_CERTIFICATE_PROFILE_NAME="p" * 100,
    )
    assert maximum_names.returncode == 0, maximum_names.stderr
    for name in (
        "APPARATUS_AZURE_SIGNING_TENANT_ID", "APPARATUS_AZURE_SIGNING_CLIENT_ID",
        "APPARATUS_AZURE_SIGNING_SUBSCRIPTION_ID", "APPARATUS_AZURE_SIGNING_ENDPOINT",
        "APPARATUS_AZURE_SIGNING_ACCOUNT_NAME", "APPARATUS_AZURE_SIGNING_CERTIFICATE_PROFILE_NAME",
        "APPARATUS_WINDOWS_SIGNING_CERTIFICATE_SUBJECT",
    ):
        missing = _run_azure_configuration(tmp_path / f"missing-{name}", **{name: ""})
        assert missing.returncode != 0
        assert not (tmp_path / f"missing-{name}" / "github-output").exists()


def test_azure_signing_job_has_only_the_selected_oidc_credential_path() -> None:
    workflow = yaml.safe_load((REPOSITORY_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"))
    job = workflow["jobs"]["sign-windows-installer-azure"]
    assert job["runs-on"] == "windows-2025"
    assert job["environment"] == "signing"
    assert job["permissions"] == {"contents": "read", "id-token": "write"}
    assert "windows_signing_provider == 'azure-artifact-signing'" in job["if"]
    steps = job["steps"]
    names = [step["name"] for step in steps]
    assert names.index("Validate Azure signing configuration") < names.index("Authenticate Azure signing identity with OIDC") < names.index("Sign the downloaded Windows installer")
    action = next(step for step in steps if step["name"] == "Sign the downloaded Windows installer")
    assert action["with"] == {
        "endpoint": "${{ steps.azure-config.outputs.apparatus_azure_signing_endpoint }}",
        "signing-account-name": "${{ steps.azure-config.outputs.apparatus_azure_signing_account_name }}",
        "certificate-profile-name": "${{ steps.azure-config.outputs.apparatus_azure_signing_certificate_profile_name }}",
        "files": "${{ github.workspace }}/unsigned-windows/apparatus-installer.exe", "file-digest": "SHA256",
        "timestamp-rfc3161": "http://timestamp.acs.microsoft.com", "timestamp-digest": "SHA256",
        "cache-dependencies": False, "exclude-environment-credential": True,
        "exclude-workload-identity-credential": True, "exclude-managed-identity-credential": True,
        "exclude-shared-token-cache-credential": True, "exclude-visual-studio-credential": True,
        "exclude-visual-studio-code-credential": True, "exclude-azure-cli-credential": False,
        "exclude-azure-powershell-credential": True, "exclude-azure-developer-cli-credential": True,
        "exclude-interactive-browser-credential": True,
    }
    assert names.index("Verify Azure-signed Windows installer") < names.index("Exercise Azure-signed Windows installer dry-run") < names.index("Upload Azure-signed Windows installer")
    dry_run = next(step["run"] for step in steps if step["name"] == "Exercise Azure-signed Windows installer dry-run")
    assert '"/LOG=$log"' in dry_run and "Embedded bootstrap SHA-256 verified" in dry_run and "Apparatus setup dry-run" in dry_run


@pytest.mark.parametrize("windows_provider", ["certificate-store", "azure-artifact-signing"])
def test_assembled_release_checksums_match_flat_github_asset_names(tmp_path: Path, windows_provider: str) -> None:
    version = "0.0.1"
    sdist_name = "apparatus_core-0.0.1.tar.gz"
    wheel_name = "apparatus_core-0.0.1-py3-none-any.whl"
    release_inputs = tmp_path / "release-inputs"
    files = {
        f"apparatus-payload-{version}.zip": b"payload",
        f"packages/{sdist_name}": b"sdist",
        f"packages/{wheel_name}": b"wheel",
        "release-notes.md": b"notes",
        "installer/windows/bootstrap-apparatus.ps1": b"unsigned windows",
        "installer/macos/bootstrap-apparatus.sh": b"macos",
    }
    for relative_path, contents in files.items():
        path = release_inputs / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    unsigned_windows = tmp_path / "unsigned-windows" / "apparatus-installer.exe"
    unsigned_windows.parent.mkdir()
    unsigned_windows.write_bytes(b"unsigned windows installer")
    unsigned_macos = tmp_path / "unsigned-macos" / "apparatus-installer.pkg"
    unsigned_macos.parent.mkdir()
    unsigned_macos.write_bytes(b"unsigned macos installer")

    environment = {
        **os.environ,
        "VERSION": version,
        "SDIST_NAME": sdist_name,
        "WHEEL_NAME": wheel_name,
    }
    subprocess.run(
        ["bash", "-c", _job_step_run("assemble-release", "Normalize release inputs")],
        cwd=tmp_path,
        env=environment,
        check=True,
    )
    signed_windows = tmp_path / "signed-windows" / "apparatus-installer.exe"
    signed_windows.parent.mkdir()
    signed_windows.write_bytes(b"signed windows")
    azure_signed_windows = tmp_path / "azure-signed-windows" / "apparatus-installer.exe"
    azure_signed_windows.parent.mkdir()
    azure_signed_windows.write_bytes(b"azure signed windows")
    install_step = (
        "Install Azure-signed Windows installer"
        if windows_provider == "azure-artifact-signing"
        else "Install signed Windows installer"
    )
    subprocess.run(
        [
            "bash",
            "-c",
            _job_step_run("assemble-release", install_step),
        ],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["bash", "-c", _job_step_run("assemble-release", "Generate SHA256SUMS")],
        cwd=tmp_path,
        env=environment,
        check=True,
    )

    final_release = tmp_path / "final-release"
    checksum_text = (final_release / "SHA256SUMS").read_text(encoding="utf-8")
    checksum_names = {line.split(maxsplit=1)[1] for line in checksum_text.splitlines()}
    assert checksum_names == {
        f"apparatus-payload-{version}.zip",
        sdist_name,
        wheel_name,
        "bootstrap-apparatus.ps1",
        "bootstrap-apparatus.sh",
        "apparatus-installer.exe",
        "apparatus-installer.pkg",
    }
    assert all("/" not in name and "\\" not in name for name in checksum_names)
    expected_windows = b"azure signed windows" if windows_provider == "azure-artifact-signing" else b"signed windows"
    assert (final_release / "apparatus-installer.exe").read_bytes() == expected_windows
    subprocess.run(
        ["shasum", "-a", "256", "--check", "SHA256SUMS"],
        cwd=final_release,
        check=True,
    )


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
        "needs.build.outputs.dry_run == 'false'": dry_run == "false",
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
    assert not _github_release_is_eligible(
        build_result="success", assemble_result="success", dry_run="true", publish_result="skipped"
    )
    assert _github_release_is_eligible(
        build_result="success", assemble_result="success", dry_run="false", publish_result="success"
    )
    assert not _github_release_is_eligible(
        build_result="success", assemble_result="success", dry_run="false", publish_result="failure"
    )
    assert not _github_release_is_eligible(
        build_result="success",
        assemble_result="success",
        dry_run="true",
        publish_result="skipped",
        event="workflow_dispatch",
    )


def _run_publish_signing_assertion(
    *,
    dry_run: str,
    provider: str,
    store_signer: str,
    azure_signer: str,
    macos_signer: str,
):
    return subprocess.run(
        ["bash", "-c", _job_step_run("assemble-release", "Require signed installers for publication")],
        env={
            **os.environ,
            "DRY_RUN": dry_run,
            "WINDOWS_SIGNING_PROVIDER": provider,
            "WINDOWS_STORE_SIGNER_RESULT": store_signer,
            "WINDOWS_AZURE_SIGNER_RESULT": azure_signer,
            "MACOS_SIGNER_RESULT": macos_signer,
        },
        capture_output=True,
        text=True,
    )


def test_assembly_requires_exactly_one_selected_windows_signature_and_macos_for_publish() -> None:
    assert _run_publish_signing_assertion(
        dry_run="true", provider="certificate-store", store_signer="skipped", azure_signer="skipped", macos_signer="skipped"
    ).returncode == 0
    assert _run_publish_signing_assertion(
        dry_run="true", provider="azure-artifact-signing", store_signer="skipped", azure_signer="skipped", macos_signer="skipped"
    ).returncode == 0

    missing = _run_publish_signing_assertion(
        dry_run="false", provider="certificate-store", store_signer="skipped", azure_signer="skipped", macos_signer="skipped"
    )
    assert missing.returncode != 0
    assert "exactly one successful Windows installer signing" in missing.stderr

    one = _run_publish_signing_assertion(
        dry_run="false", provider="certificate-store", store_signer="success", azure_signer="skipped", macos_signer="skipped"
    )
    assert one.returncode != 0
    assert "successful macOS installer signing; got skipped" in one.stderr

    assert _run_publish_signing_assertion(
        dry_run="false", provider="certificate-store", store_signer="success", azure_signer="skipped", macos_signer="success"
    ).returncode == 0
    assert _run_publish_signing_assertion(
        dry_run="false", provider="azure-artifact-signing", store_signer="skipped", azure_signer="success", macos_signer="success"
    ).returncode == 0
    assert _run_publish_signing_assertion(
        dry_run="false", provider="azure-artifact-signing", store_signer="success", azure_signer="skipped", macos_signer="success"
    ).returncode != 0
    assert _run_publish_signing_assertion(
        dry_run="false", provider="certificate-store", store_signer="success", azure_signer="success", macos_signer="success"
    ).returncode != 0
    assert _run_publish_signing_assertion(
        dry_run="false", provider="certificate-store", store_signer="failure", azure_signer="skipped", macos_signer="success"
    ).returncode != 0
    assert _run_publish_signing_assertion(
        dry_run="false", provider="azure-artifact-signing", store_signer="skipped", azure_signer="failure", macos_signer="success"
    ).returncode != 0
    assert _run_publish_signing_assertion(
        dry_run="false", provider="azure-artifact-signing", store_signer="skipped", azure_signer="cancelled", macos_signer="success"
    ).returncode != 0
    assert _run_publish_signing_assertion(
        dry_run="false", provider="certificate-store", store_signer="success", azure_signer="skipped", macos_signer="cancelled"
    ).returncode != 0
    assert _run_publish_signing_assertion(
        dry_run="false", provider="azure-artifact-signing", store_signer="skipped", azure_signer="success", macos_signer="skipped"
    ).returncode != 0
    assert _run_publish_signing_assertion(
        dry_run="false", provider="certificate-store", store_signer="unknown", azure_signer="skipped", macos_signer="success"
    ).returncode != 0
    assert _run_publish_signing_assertion(
        dry_run="bogus", provider="certificate-store", store_signer="skipped", azure_signer="skipped", macos_signer="skipped"
    ).returncode != 0
    assert _run_publish_signing_assertion(
        dry_run="true", provider="certificate-store", store_signer="success", azure_signer="success", macos_signer="skipped"
    ).returncode != 0


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
