from __future__ import annotations

import os
from pathlib import Path
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
        pwsh = shutil.which("pwsh") or shutil.which("powershell")
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
    assert "detection only; no commands will run" in completed.stdout
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
    combined = macos + windows

    for source in (
        "https://astral.sh/uv/install.sh",
        "https://astral.sh/uv/install.ps1",
        "https://github.com/astral-sh/python-build-standalone/releases/download",
        "https://pypi.org/simple",
    ):
        assert source in combined or source in readme
    assert "apparatus init" not in combined  # invoked as an argument array, never a shell string
    assert "--payload" not in combined
    assert "apparatus-payload" not in combined
    assert "sudo" not in combined.casefold()


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
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
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
