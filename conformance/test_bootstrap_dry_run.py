from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MACOS_SCRIPT = REPO_ROOT / "installer/macos/bootstrap-apparatus.sh"
WINDOWS_SCRIPT = REPO_ROOT / "installer/windows/bootstrap-apparatus.ps1"
STEP_LABELS = (
    "Operating system:",
    "Target safety:",
    "uv:",
    "Managed Python:",
    "Git:",
    "Apparatus tool:",
    "Workspace:",
    "Doctor:",
    "Network:",
)


def _tree(root: Path) -> dict[str, bytes]:
    state: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            state[relative] = b"symlink:" + os.fsencode(os.readlink(path))
        elif path.is_dir():
            state[relative] = b"directory"
        elif path.is_file():
            state[relative] = b"file:" + path.read_bytes()
        else:
            state[relative] = b"other"
    return state


def _native_command(home: Path, target: Path) -> list[str]:
    if sys.platform == "darwin":
        bash = shutil.which("bash")
        if bash is None:
            pytest.skip("bash is unavailable on this macOS host")
        uv = home / ".local/bin/uv"
        uv.parent.mkdir(parents=True)
        uv.write_text("#!/bin/sh\nprintf invoked > \"$HOME/command-ran\"\n", encoding="utf-8")
        uv.chmod(0o700)
        return [bash, str(MACOS_SCRIPT), "--dry-run", "--path", str(target)]
    if sys.platform == "win32":
        # Windows PowerShell is the declared 5.1 baseline; the direct workflow
        # smoke also runs the same script under PowerShell 7.
        pwsh = shutil.which("powershell") or shutil.which("pwsh")
        if pwsh is None:
            pytest.skip("PowerShell is unavailable on this Windows host")
        return [
            pwsh,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(WINDOWS_SCRIPT),
            "-DryRun",
            "-Path",
            str(target),
        ]
    pytest.skip("bootstrap dry-run is native to Windows and macOS")


def test_native_bootstrap_dry_run_is_complete_and_has_zero_effects(tmp_path):
    home = tmp_path / "profile"
    work = tmp_path / "working"
    home.mkdir()
    work.mkdir()
    if sys.platform == "win32":
        # These are harness-owned environment roots. Windows PowerShell creates
        # them at process startup even when the script is never entered.
        (home / "AppData/Local").mkdir(parents=True)
        (home / "AppData/Roaming").mkdir(parents=True)
    target = home / "Projects/Apparatus"
    command = _native_command(home, target)
    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "APPDATA": str(home / "AppData/Roaming"),
            "LOCALAPPDATA": str(home / "AppData/Local"),
            "XDG_DATA_HOME": str(home / ".local/share"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "ALL_PROXY": "http://127.0.0.1:9",
            "NO_PROXY": "",
        }
    )
    if sys.platform == "win32":
        # Both native PowerShell families may publish interpreter-owned startup
        # data on first use. Warm the selected interpreter in the exact test
        # environment, then bracket only the complete bootstrap invocation.
        warmed = subprocess.run(
            [command[0], "-NoProfile", "-NonInteractive", "-Command", "exit"],
            cwd=work,
            env=environment,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        assert warmed.returncode == 0, warmed.stdout + warmed.stderr
    before = _tree(tmp_path)

    completed = subprocess.run(
        command,
        cwd=work,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "read-only detection; no install, network, or workspace commands" in completed.stdout
    assert all(label in completed.stdout for label in STEP_LABELS)
    assert all(
        word in completed.stdout
        for word in ("present", "missing", "planned")
    )
    assert _tree(tmp_path) == before
    assert not (home / "command-ran").exists()
    assert not target.exists()


def test_bootstrap_sources_and_payload_boundary_are_explicit():
    macos = MACOS_SCRIPT.read_text(encoding="utf-8")
    windows = WINDOWS_SCRIPT.read_text(encoding="utf-8")
    readme = (REPO_ROOT / "installer/README.md").read_text(encoding="utf-8")
    scripts = macos + windows
    combined = scripts + readme
    allowed_sources = {
        "https://astral.sh/uv/install.sh",
        "https://astral.sh/uv/install.ps1",
        "https://releases.astral.sh/installers/uv/latest/uv-installer.sh",
        "https://releases.astral.sh/installers/uv/latest/uv-installer.ps1",
        "https://releases.astral.sh/github/uv/releases/download",
        "https://github.com/astral-sh/uv/releases/download",
        "https://github.com/astral-sh/python-build-standalone/releases/download",
        "https://pypi.org/simple",
        "https://files.pythonhosted.org",
    }
    assert set(re.findall(r"https://[^\s`\"']+", combined)) == allowed_sources
    assert "apparatus init" not in scripts  # invoked as an argument array, never a shell string
    assert "--payload" not in scripts
    assert "apparatus-payload" not in scripts
    assert "sudo" not in scripts.casefold()


def test_dry_run_exit_precedes_every_mutating_or_network_stage():
    macos = MACOS_SCRIPT.read_text(encoding="utf-8")
    windows = WINDOWS_SCRIPT.read_text(encoding="utf-8")

    macos_exit = macos.index("if ((DRY_RUN)); then")
    macos_exit = macos.index("exit 0", macos_exit)
    for token in ("/usr/bin/curl", '"$APPARATUS_BIN" init', '"$APPARATUS_BIN" doctor'):
        assert macos.index(token) > macos_exit

    windows_exit = windows.index("if ($DryRun)")
    windows_exit = windows.index("exit 0", windows_exit)
    for token in ("Invoke-RestMethod", "Invoke-Expression", "& $ApparatusBin init", "& $ApparatusBin doctor"):
        assert windows.index(token) > windows_exit

    assert "UV_NO_MODIFY_PATH=1 /bin/sh" in macos
    assert '$env:UV_NO_MODIFY_PATH = "1"' in windows


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows path regression")
def test_windows_dry_run_preserves_drive_and_unc_roots(tmp_path):
    home = tmp_path / "profile"
    home.mkdir()
    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "APPDATA": str(home / "AppData/Roaming"),
            "LOCALAPPDATA": str(home / "AppData/Local"),
        }
    )
    pwsh = shutil.which("powershell") or shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell is unavailable")

    drive_root = Path(tmp_path.anchor)
    targets = [str(drive_root)]
    drive = drive_root.drive.rstrip(":")
    unc_root = f"\\\\localhost\\{drive}$\\"
    if Path(unc_root).exists():
        targets.append(unc_root)

    for target in targets:
        completed = subprocess.run(
            [
                pwsh,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(WINDOWS_SCRIPT),
                "-DryRun",
                "-Path",
                target,
            ],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        target_line = next(
            line for line in completed.stdout.splitlines() if "Target safety:" in line
        )
        reported = target_line.split("present (", 1)[1].split(";", 1)[0]
        assert PureWindowsPath(reported) == PureWindowsPath(target)


def test_macos_script_has_valid_bash_syntax():
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is unavailable")
    completed = subprocess.run(
        [bash, "-n", str(MACOS_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_windows_script_parses_when_powershell_is_available():
    pwsh = shutil.which("powershell") or shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell is unavailable")
    parser = (
        "$e=$null; $t=$null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{WINDOWS_SCRIPT}',[ref]$t,[ref]$e) > $null; "
        "if ($e.Count) { $e | ForEach-Object { Write-Error $_ }; exit 1 }"
    )
    completed = subprocess.run(
        [pwsh, "-NoProfile", "-Command", parser],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
