from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath
import re
import signal
import shutil
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = REPO_ROOT / ".github/workflows/ci.yml"
MACOS_SCRIPT = REPO_ROOT / "installer/macos/bootstrap-apparatus.sh"
MACOS_NETWORK_CANARY = Path("/usr/bin/nc")
MACOS_SANDBOX = Path("/usr/bin/sandbox-exec")
WINDOWS_SCRIPT = REPO_ROOT / "installer/windows/bootstrap-apparatus.ps1"
WINDOWS_TRACE_CONTROLLER = REPO_ROOT / "conformance/windows_bootstrap_syscall_trace.ps1"
WINDOWS_ETW_TEST = (
    "conformance/test_bootstrap_dry_run.py::"
    "test_windows_dry_run_has_no_file_registry_or_network_syscalls"
)
MACOS_SANDBOX_PROFILE = """
(version 1)
(allow default)
(deny file-write* (with no-log) (with send-signal SIGKILL))
(allow file-write-data (subpath "/dev"))
(deny network* (with no-log) (with send-signal SIGKILL))
""".strip()
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


def _run_macos_sandbox(
    arguments: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(MACOS_SANDBOX),
            "-p",
            MACOS_SANDBOX_PROFILE,
            "/bin/bash",
            "--noprofile",
            "--norc",
            *arguments,
        ],
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
        close_fds=True,
    )


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
    windows_exit = windows.index("return", windows_exit)
    for token in ("Invoke-RestMethod", "Invoke-Expression", "& $ApparatusBin init", "& $ApparatusBin doctor"):
        assert windows.index(token) > windows_exit

    assert "PATH=/usr/bin:/bin:/usr/sbin:/sbin" in macos
    assert "BASH_ENV= ENV= /bin/sh" in macos
    assert '$env:UV_NO_MODIFY_PATH = "1"' in windows


def test_windows_trace_controller_is_built_in_bounded_and_non_vacuous():
    controller = WINDOWS_TRACE_CONTROLLER.read_text(encoding="utf-8")

    for token in (
        "powershell.exe",
        "wpr.exe",
        "tracerpt.exe",
        "logman.exe",
        "[Environment]::SystemDirectory",
        "CREATE_SUSPENDED",
        "JOB_OBJECT_LIMIT_ACTIVE_PROCESS",
        "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE",
        '<Keyword Value="ProcessThread" Strict="true" />',
        '<Keyword Value="FileIO" Strict="true" />',
        '<Keyword Value="FileIOInit" Strict="true" />',
        '<Keyword Value="Registry" Strict="true" />',
        '<Keyword Value="NetworkTrace" Strict="true" />',
        '"-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass"',
        "FileIO/FileIOInit providers did not observe the file canary",
        "Registry provider did not observe the registry canary",
        "Network provider did not observe the TCP canary",
        "ETW/WPR sessions were not restored exactly",
        "trace artifacts survived cleanup",
    ):
        assert token in controller
    assert not re.search(r"(?i)invoke-(?:webrequest|restmethod)|start-bitstransfer", controller)
    assert 'GetEnvironmentVariable("SystemRoot", "Machine")' not in controller


def test_windows_global_trace_is_isolated_to_bootstrap_ci_job():
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    windows_safety = workflow.split("\n  windows-safety:\n", 1)[1].split(
        "\n  bootstrap-windows:\n", 1
    )[0]
    bootstrap_windows = workflow.split("\n  bootstrap-windows:\n", 1)[1].split(
        "\n  bootstrap-macos:\n", 1
    )[0]

    exclusion = f"--deselect {WINDOWS_ETW_TEST}"
    selection = f"uv run pytest {WINDOWS_ETW_TEST}"
    assert windows_safety.count(WINDOWS_ETW_TEST) == 1
    assert exclusion in windows_safety
    assert bootstrap_windows.count(WINDOWS_ETW_TEST) == 2
    assert exclusion in bootstrap_windows
    assert selection in bootstrap_windows
    assert workflow.count(WINDOWS_ETW_TEST) == 3


def test_macos_sandbox_contract_is_generic_and_non_vacuous():
    assert "(deny file-write* (with no-log) (with send-signal SIGKILL))" in (
        MACOS_SANDBOX_PROFILE
    )
    assert "(allow file-write-data (subpath \"/dev\"))" in MACOS_SANDBOX_PROFILE
    assert "(deny network* (with no-log) (with send-signal SIGKILL))" in (
        MACOS_SANDBOX_PROFILE
    )
    assert MACOS_SANDBOX_PROFILE.count("/dev") == 1


@pytest.mark.skipif(sys.platform != "darwin", reason="native macOS syscall regression")
def test_macos_dry_run_has_no_persistent_object_or_network_mutations(tmp_path):
    assert MACOS_SANDBOX.is_file(), "the built-in macOS sandbox is required"
    assert MACOS_NETWORK_CANARY.is_file(), "the built-in network canary is required"

    home = tmp_path / "profile"
    work = tmp_path / "working"
    home.mkdir()
    work.mkdir()
    target = home / "Projects/Apparatus"
    environment = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "BASH_ENV": "",
        "ENV": "",
        "LANG": "C",
        "LC_ALL": "C",
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "ALL_PROXY": "http://127.0.0.1:9",
        "NO_PROXY": "",
    }
    before = _tree(tmp_path)

    completed = _run_macos_sandbox(
        [str(MACOS_SCRIPT), "--dry-run", "--path", str(target)],
        cwd=work,
        environment=environment,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "read-only detection; no install, network, or workspace commands" in (
        completed.stdout
    )
    assert all(label in completed.stdout for label in STEP_LABELS)
    assert _tree(tmp_path) == before
    assert not target.exists()

    persistent_canary = tmp_path / "persistent-canary"
    file_environment = dict(environment)
    file_environment["APPARATUS_PERSISTENT_CANARY"] = str(persistent_canary)
    file_canary = _run_macos_sandbox(
        ["-c", 'printf canary > "$APPARATUS_PERSISTENT_CANARY"'],
        cwd=work,
        environment=file_environment,
    )
    assert file_canary.returncode == -signal.SIGKILL
    assert not persistent_canary.exists()

    network_canary = _run_macos_sandbox(
        ["-c", f"exec {MACOS_NETWORK_CANARY} -z 127.0.0.1 9"],
        cwd=work,
        environment=environment,
    )
    assert network_canary.returncode == -signal.SIGKILL
    assert _tree(tmp_path) == before


@pytest.mark.skipif(sys.platform != "darwin", reason="native macOS git regression")
def test_macos_broken_git_stub_degrades_to_absent(tmp_path):
    home = tmp_path / "profile"
    hostile = tmp_path / "hostile"
    home.mkdir()
    hostile.mkdir()
    git = hostile / "git"
    git.write_text("#!/bin/sh\nprintf 'not a usable git\\n'\n", encoding="utf-8")
    git.chmod(0o700)
    environment = {
        "HOME": str(home),
        "PATH": f"{hostile}:/usr/bin:/bin:/usr/sbin:/sbin",
        "BASH_ENV": "",
        "ENV": "",
        "LANG": "C",
        "LC_ALL": "C",
    }
    completed = subprocess.run(
        [
            "/bin/bash",
            str(MACOS_SCRIPT),
            "--dry-run",
            "--path",
            str(home / "Projects/Apparatus"),
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    git_line = next(line for line in completed.stdout.splitlines() if "Git:" in line)
    assert "missing" in git_line
    assert str(hostile) not in completed.stdout


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
    unc_root = "\\\\apparatus.invalid\\lexical-share\\"
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


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows path regression")
def test_windows_redirected_roots_match_equal_and_descendant_targets(tmp_path):
    pwsh = shutil.which("powershell") or shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell is unavailable")
    script = str(WINDOWS_SCRIPT).replace("'", "''")
    command = rf"""
$null = . '{script}' -DryRun -Path 'C:\Apparatus'
$cases = @(
    @('C:\', 'C:\', $true),
    @('C:\Child', 'C:\', $true),
    @('D:\Child', 'C:\', $false),
    @('\\server\share\', '\\server\share\', $true),
    @('\\server\share\Child', '\\server\share\', $true),
    @('\\server\other\Child', '\\server\share\', $false)
)
foreach ($case in $cases) {{
    if ((Test-PathWithin $case[0] $case[1]) -ne $case[2]) {{ exit 31 }}
}}
$values = @{{ Personal = 'C:\'; Desktop = '\\server\share\' }}
if (-not (Test-RedirectedTarget 'C:\Child' $values 'C:\Users\Example')) {{ exit 32 }}
if (-not (Test-RedirectedTarget '\\server\share\Child' $values 'C:\Users\Example')) {{ exit 33 }}
if (Test-RedirectedTarget 'D:\Child' $values 'C:\Users\Example') {{ exit 34 }}
"""
    completed = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows ETW regression")
def test_windows_dry_run_has_no_file_registry_or_network_syscalls():
    system_root = Path(os.environ["SystemRoot"])
    powershell = system_root / "System32/WindowsPowerShell/v1.0/powershell.exe"
    assert powershell.is_file(), "Windows PowerShell 5.1 is required"

    completed = subprocess.run(
        [
            str(powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(WINDOWS_TRACE_CONTROLLER),
            "-BootstrapScript",
            str(WINDOWS_SCRIPT),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Windows dry-run syscall proof passed" in completed.stdout


def test_macos_lexical_normalization_and_installer_child_path_are_hardened():
    macos = MACOS_SCRIPT.read_text(encoding="utf-8")
    assert "lexically_normalize_absolute" in macos
    assert "env -i HOME=\"$HOME\" PATH=/usr/bin:/bin:/usr/sbin:/sbin" in macos


@pytest.mark.skipif(sys.platform != "darwin", reason="native macOS path regression")
def test_macos_installer_child_uses_controlled_path(tmp_path):
    hostile = tmp_path / "hostile"
    hostile.mkdir()
    marker = tmp_path / "hostile-ran"
    command = hostile / "uname"
    command.write_text(f"#!/bin/sh\nprintf hostile > '{marker}'\n", encoding="utf-8")
    command.chmod(0o700)
    completed = subprocess.run(
        [
            "/usr/bin/env",
            "-i",
            f"HOME={tmp_path}",
            "PATH=/usr/bin:/bin:/usr/sbin:/sbin",
            "BASH_ENV=",
            "ENV=",
            "/bin/sh",
            "-c",
            "uname",
        ],
        env={"PATH": str(hostile)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert not marker.exists()


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
    files = ",".join(f"'{path}'" for path in (WINDOWS_SCRIPT, WINDOWS_TRACE_CONTROLLER))
    parser = (
        "$failed=$false; "
        f"foreach ($path in @({files})) {{ "
        "$e=$null; $t=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile($path,[ref]$t,[ref]$e) > $null; "
        "if ($e.Count) { $failed=$true; $e | ForEach-Object { Write-Error $_ } } }; "
        "if ($failed) { exit 1 }"
    )
    completed = subprocess.run(
        [pwsh, "-NoProfile", "-Command", parser],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
