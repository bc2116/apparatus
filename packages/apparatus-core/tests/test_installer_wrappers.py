"""Checks for the native wrappers around the canonical bootstrap scripts."""

from pathlib import Path
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_native_wrapper_text_inputs_are_lf_pinned_across_checkouts(tmp_path: Path) -> None:
    paths = (
        "installer/windows/bootstrap-apparatus.ps1",
        "installer/windows/build-installer.ps1",
        "installer/windows/apparatus-installer.iss",
        "installer/macos/bootstrap-apparatus.sh",
        "installer/macos/build-package.sh",
        "installer/macos/verify-package.sh",
        "installer/macos/package-scripts/postinstall",
    )
    attributes = subprocess.run(
        ["git", "check-attr", "text", "eol", "--", *paths],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    expected = {
        f"{path}: {attribute}: {value}"
        for path in paths
        for attribute, value in (("text", "set"), ("eol", "lf"))
    }
    assert set(attributes) == expected

    subprocess.run(
        [
            "git",
            "-c",
            "core.autocrlf=true",
            "checkout-index",
            f"--prefix={tmp_path}/",
            "--",
            paths[0],
            paths[3],
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
    for path in (paths[0], paths[3]):
        assert (tmp_path / path).read_bytes() == (REPOSITORY_ROOT / path).read_bytes()


def test_windows_wrapper_embeds_and_verifies_only_the_canonical_script() -> None:
    definition = (
        REPOSITORY_ROOT / "installer" / "windows" / "apparatus-installer.iss"
    ).read_text(encoding="utf-8")
    build_script = (
        REPOSITORY_ROOT / "installer" / "windows" / "build-installer.ps1"
    ).read_text(encoding="utf-8")

    assert '#define BootstrapPath AddBackslash(SourceRoot) + "bootstrap-apparatus.ps1"' in definition
    assert "#define BootstrapHash GetSHA256OfFile(BootstrapPath)" in definition
    assert 'Source: "{#BootstrapPath}"' in definition
    assert "Flags: dontcopy noencryption" in definition
    assert "ExtractTemporaryFile('bootstrap-apparatus.ps1')" in definition
    assert "GetSHA256OfFile(ExtractedPath)" in definition
    assert "Embedded bootstrap SHA-256 verified." in definition
    assert "ExecAndLogOutput(" in definition
    assert "BootstrapExitCode := ResultCode" in definition
    assert "function GetCustomSetupExitCode(): Integer" in definition
    assert "PrivilegesRequired=lowest" in definition
    assert "PrivilegesRequiredOverridesAllowed keeps its blank default" in definition
    assert "PrivilegesRequiredOverridesAllowed=" not in definition
    assert "CreateAppDir=no" in definition
    assert "Uninstallable=no" in definition
    assert "SetupLogging=no" in definition
    assert "'/DRYRUN'" in definition
    assert "'/WORKSPACEPATH='" in definition
    assert "'/ADOPT'" in definition and "AdoptSeen" in definition
    assert "ParsedBootstrapArguments + '-Adopt'" in definition
    assert "Unsupported installer option" in definition
    assert "DryRunSeen" in definition and "WorkspacePathSeen" in definition
    assert "Pos(#10, WorkspacePath)" in definition
    assert "Pos(#13, WorkspacePath)" in definition
    assert 'Join-Path $ScriptDirectory "bootstrap-apparatus.ps1"' in build_script
    assert '"/DSourceRoot=$ScriptDirectory"' in build_script
    assert '"/DVersion=$Version"' in build_script


def test_macos_dispatcher_drops_session_and_identity_before_bootstrap() -> None:
    dispatcher = (
        REPOSITORY_ROOT / "installer" / "macos" / "package-scripts" / "postinstall"
    ).read_text(encoding="utf-8")
    verifier = (
        REPOSITORY_ROOT / "installer" / "macos" / "verify-package.sh"
    ).read_text(encoding="utf-8")

    assert "/usr/bin/stat -f '%Su' /dev/console" in dispatcher
    assert "console_user != root" in dispatcher
    assert "console_user != loginwindow" in dispatcher
    assert "console_user != nobody" in dispatcher
    assert "console_uid -gt 0" in dispatcher
    assert "/usr/bin/stat -f '%u' \"$console_home\"" in dispatcher
    assert "! -L $console_home" in dispatcher
    assert '/bin/launchctl asuser "$console_uid"' in dispatcher
    assert '/usr/bin/sudo -u "$console_user"' in dispatcher
    assert "/usr/bin/env -i" in dispatcher
    assert "PATH=/usr/bin:/bin:/usr/sbin:/sbin" in dispatcher
    assert '/bin/cat "$bootstrap" |' in dispatcher
    assert "/bin/bash -s --" in dispatcher

    assert "! -e $component/Payload" in verifier
    assert "$'Distribution\\napparatus-bootstrap.pkg'" in verifier
    assert "$'PackageInfo\\nScripts'" in verifier
    assert "/bin/ls -A" in verifier
    assert 'cmp "$bootstrap" "$scripts/bootstrap-apparatus.sh"' in verifier
    assert 'cmp "$postinstall" "$scripts/postinstall"' in verifier


@pytest.mark.skipif(sys.platform != "darwin", reason="native package tools require macOS")
def test_macos_wrapper_build_contains_exact_scripts_and_no_payload(tmp_path: Path) -> None:
    package = tmp_path / "apparatus-installer.pkg"
    subprocess.run(
        [
            str(REPOSITORY_ROOT / "installer" / "macos" / "build-package.sh"),
            "--output",
            str(package),
            "--version",
            "0.0.1",
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
    )

    assert package.is_file()
    subprocess.run(
        [
            str(REPOSITORY_ROOT / "installer" / "macos" / "verify-package.sh"),
            str(package),
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_installer_docs_state_wrapper_limits_and_flag_mapping() -> None:
    readme = (REPOSITORY_ROOT / "installer" / "README.md").read_text(encoding="utf-8")
    brief = (REPOSITORY_ROOT / "docs" / "design" / "design-brief.md").read_text(
        encoding="utf-8"
    )

    assert "`/DRYRUN` maps to\nthe script's `-DryRun`" in readme
    assert "`/WORKSPACEPATH=` maps to `-Path`" in readme
    assert "minimal native progress interface" in readme
    assert "macOS Installer\nmay require an administrator authentication prompt" in readme
    assert "standard package receipt" in readme
    assert "native package interface has no safe custom-option channel" in readme
    assert "Inno Setup on Windows" in brief
    assert "`pkgbuild` plus\n  `productbuild` on macOS" in brief
    assert "rather than claiming a console-only experience" in brief

    prompt = (
        REPOSITORY_ROOT / "docs" / "plan" / "PR-26-installer-wrapper.md"
    ).read_text(encoding="utf-8")
    assert "reproducible means a repeatable pinned build recipe" in prompt
    assert "does\n   not promise bit-identical outer `.exe` or `.pkg` bytes" in prompt
    assert "smallest surviving default is its minimal\n  progress interface" in prompt
