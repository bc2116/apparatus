from __future__ import annotations

from dataclasses import dataclass, replace
import os
from pathlib import Path, PureWindowsPath
import re
import signal
import shutil
import stat
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
    "test_windows_optional_etw_witness_has_no_file_registry_or_network_syscalls"
)
WINDOWS_HOSTED_ETW_SKIP_REASON = (
    "operator ruling: WPR/ETW is platform-infeasible on hosted Windows runners; "
    "the scoped filesystem comparison is the primary persistent-object proof"
)
WINDOWS_INSTALL_DESTINATIONS = (
    ("uv executable", (".local", "bin", "uv.exe")),
    ("managed Python", (".local", "share", "uv", "python")),
    ("tool packages", (".local", "share", "uv", "tools")),
    ("tool commands", (".local", "bin")),
    ("uv cache", (".cache", "uv")),
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


@dataclass(frozen=True)
class _PersistentObjectState:
    kind: int
    size: int
    mtime_ns: int
    identity: tuple[int, int]
    permissions: int
    file_attributes: int | None


def _persistent_object_state(metadata: os.stat_result) -> _PersistentObjectState:
    return _PersistentObjectState(
        kind=stat.S_IFMT(metadata.st_mode),
        size=metadata.st_size,
        mtime_ns=metadata.st_mtime_ns,
        identity=(metadata.st_dev, metadata.st_ino),
        permissions=stat.S_IMODE(metadata.st_mode),
        file_attributes=getattr(metadata, "st_file_attributes", None),
    )


def _persistent_tree(root: Path) -> dict[str, _PersistentObjectState]:
    """Capture persistent-object metadata without following link-like objects."""

    try:
        root_metadata = root.stat(follow_symlinks=False)
    except FileNotFoundError:
        return {}

    state = {".": _persistent_object_state(root_metadata)}
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    root_is_reparse = bool(
        getattr(root_metadata, "st_file_attributes", 0) & reparse_flag
    )
    if not stat.S_ISDIR(root_metadata.st_mode) or root_is_reparse:
        return state

    pending = [(root, "")]
    while pending:
        current, prefix = pending.pop()
        with os.scandir(current) as entries:
            children = sorted(entries, key=lambda entry: entry.name.casefold())
        for entry in children:
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            # DirEntry.stat intentionally returns zero st_dev/st_ino on
            # Windows. os.stat performs the handle-backed identity query.
            metadata = os.stat(entry.path, follow_symlinks=False)
            state[relative] = _persistent_object_state(metadata)
            is_reparse = bool(
                getattr(metadata, "st_file_attributes", 0) & reparse_flag
            )
            if stat.S_ISDIR(metadata.st_mode) and not is_reparse:
                pending.append((Path(entry.path), relative))
    return state


def _windows_proof_locations(
    *,
    user_profile: Path,
    target: Path,
    temp: Path,
    working: Path,
) -> dict[str, Path]:
    locations = {"workspace target": target}
    locations.update(
        {
            f"install destination: {label}": user_profile.joinpath(*parts)
            for label, parts in WINDOWS_INSTALL_DESTINATIONS
        }
    )
    locations["TEMP"] = temp
    locations["working directory"] = working
    return locations


def _snapshot_locations(
    locations: dict[str, Path],
) -> dict[str, dict[str, _PersistentObjectState]]:
    return {label: _persistent_tree(path) for label, path in locations.items()}


def _snapshot_delta(
    before: dict[str, dict[str, _PersistentObjectState]],
    after: dict[str, dict[str, _PersistentObjectState]],
) -> str:
    """Return changes rejected by the Windows location-tiered proof.

    Workspace, install, and working-directory locations retain exact metadata
    maps. TEMP retains the exact entry-name set and full child metadata, while
    its container entry keeps every captured field except its own modification
    timestamp. A before/after comparison intentionally cannot attest transient
    create-then-delete churn inside TEMP.
    """

    changes: list[str] = []
    fields = tuple(_PersistentObjectState.__dataclass_fields__)
    for location in sorted(before.keys() - after.keys()):
        changes.append(f"removed location {location}")
    for location in sorted(after.keys() - before.keys()):
        changes.append(f"created location {location}")
    for location in sorted(before.keys() & after.keys()):
        old = before[location]
        new = after[location]
        for name in sorted(old.keys() - new.keys()):
            changes.append(f"{location}: removed {name}")
        for name in sorted(new.keys() - old.keys()):
            changes.append(f"{location}: created {name}")
        for name in sorted(old.keys() & new.keys()):
            compared_fields = fields
            if location == "TEMP" and name == ".":
                compared_fields = tuple(
                    field for field in fields if field != "mtime_ns"
                )
            changed_fields = [
                field
                for field in compared_fields
                if getattr(old[name], field) != getattr(new[name], field)
            ]
            if changed_fields:
                changes.append(
                    f"{location}: changed {name} ({', '.join(changed_fields)})"
                )
    return "; ".join(changes[:20])


def _is_github_hosted_runner() -> bool:
    return (
        os.environ.get("RUNNER_ENVIRONMENT", "").casefold() == "github-hosted"
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


def test_windows_hosted_jobs_use_scoped_filesystem_proof():
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
    assert bootstrap_windows.count(
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    ) == 2


def test_optional_etw_witness_skips_only_github_hosted_runners(monkeypatch):
    monkeypatch.delenv("RUNNER_ENVIRONMENT", raising=False)
    assert not _is_github_hosted_runner()
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "self-hosted")
    assert not _is_github_hosted_runner()
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "github-hosted")
    assert _is_github_hosted_runner()


def test_windows_filesystem_proof_pins_named_roots_and_compared_fields():
    windows = WINDOWS_SCRIPT.read_text(encoding="utf-8")
    declarations = {
        "uv executable": '$UvBin = Join-Path $UserProfile ".local\\bin\\uv.exe"',
        "managed Python": '$UvPythonDir = Join-Path $UserProfile ".local\\share\\uv\\python"',
        "tool packages": '$UvToolDir = Join-Path $UserProfile ".local\\share\\uv\\tools"',
        "tool commands": '$UvToolBin = Join-Path $UserProfile ".local\\bin"',
        "uv cache": '$UvCacheDir = Join-Path $UserProfile ".cache\\uv"',
    }
    assert {label for label, _parts in WINDOWS_INSTALL_DESTINATIONS} == set(
        declarations
    )
    assert all(declaration in windows for declaration in declarations.values())
    assert tuple(_PersistentObjectState.__dataclass_fields__) == (
        "kind",
        "size",
        "mtime_ns",
        "identity",
        "permissions",
        "file_attributes",
    )


def test_persistent_tree_detects_absence_name_size_mtime_identity_and_attributes(
    tmp_path,
):
    missing = tmp_path / "missing"
    assert _persistent_tree(missing) == {}
    missing.mkdir()
    assert set(_persistent_tree(missing)) == {"."}

    name_root = tmp_path / "name"
    name_root.mkdir()
    old_name = name_root / "old.txt"
    old_name.write_bytes(b"name")
    name_before = _persistent_tree(name_root)
    old_name.rename(name_root / "new.txt")
    name_after = _persistent_tree(name_root)
    assert "old.txt" in name_before and "old.txt" not in name_after
    assert "new.txt" not in name_before and "new.txt" in name_after

    size_root = tmp_path / "size"
    size_root.mkdir()
    size_file = size_root / "value.txt"
    size_file.write_bytes(b"a")
    size_before = _persistent_tree(size_root)["value.txt"]
    size_file.write_bytes(b"two")
    size_after = _persistent_tree(size_root)["value.txt"]
    assert size_before.size != size_after.size

    mtime_root = tmp_path / "mtime"
    mtime_root.mkdir()
    mtime_file = mtime_root / "value.txt"
    mtime_file.write_bytes(b"same")
    first_mtime = 1_700_000_000_000_000_000
    second_mtime = first_mtime + 10_000_000_000
    os.utime(mtime_file, ns=(first_mtime, first_mtime))
    mtime_before = _persistent_tree(mtime_root)["value.txt"]
    os.utime(mtime_file, ns=(second_mtime, second_mtime))
    mtime_after = _persistent_tree(mtime_root)["value.txt"]
    assert mtime_before.size == mtime_after.size
    assert mtime_before.identity == mtime_after.identity
    assert mtime_before.mtime_ns != mtime_after.mtime_ns

    identity_root = tmp_path / "identity"
    identity_root.mkdir()
    identity_file = identity_root / "value.txt"
    replacement = identity_root / "replacement.tmp"
    identity_file.write_bytes(b"same")
    os.utime(identity_file, ns=(first_mtime, first_mtime))
    identity_before = _persistent_tree(identity_root)["value.txt"]
    replacement.write_bytes(b"same")
    os.utime(replacement, ns=(first_mtime, first_mtime))
    replacement.replace(identity_file)
    identity_after = _persistent_tree(identity_root)["value.txt"]
    assert identity_before.size == identity_after.size
    assert identity_before.mtime_ns == identity_after.mtime_ns
    assert identity_before.identity != (0, 0)
    assert identity_after.identity != (0, 0)
    assert identity_before.identity != identity_after.identity

    attribute_file = identity_root / "attributes.txt"
    attribute_file.write_bytes(b"attributes")
    attribute_before = _persistent_tree(identity_root)["attributes.txt"]
    attribute_file.chmod(stat.S_IREAD)
    attribute_after = _persistent_tree(identity_root)["attributes.txt"]
    assert (
        attribute_before.permissions != attribute_after.permissions
        or attribute_before.file_attributes != attribute_after.file_attributes
    )
    attribute_file.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_windows_location_tiered_snapshot_comparison_is_non_vacuous():
    temp_root = _PersistentObjectState(
        kind=stat.S_IFDIR,
        size=0,
        mtime_ns=100,
        identity=(1, 1),
        permissions=0o700,
        file_attributes=16,
    )
    child = _PersistentObjectState(
        kind=stat.S_IFREG,
        size=7,
        mtime_ns=200,
        identity=(1, 2),
        permissions=0o600,
        file_attributes=32,
    )
    strict_root = _PersistentObjectState(
        kind=stat.S_IFDIR,
        size=0,
        mtime_ns=300,
        identity=(1, 3),
        permissions=0o700,
        file_attributes=16,
    )
    before = {
        "TEMP": {".": temp_root, "survivor.txt": child},
        "working directory": {".": strict_root},
    }

    allowed = {
        "TEMP": {
            ".": replace(temp_root, mtime_ns=temp_root.mtime_ns + 1),
            "survivor.txt": child,
        },
        "working directory": {".": strict_root},
    }
    assert _snapshot_delta(before, allowed) == ""

    non_timestamp_changes = {
        "kind": stat.S_IFREG,
        "size": 1,
        "identity": (1, 9),
        "permissions": 0o500,
        "file_attributes": 2,
    }
    for field, value in non_timestamp_changes.items():
        changed_root = replace(temp_root, **{field: value})
        after = {
            "TEMP": {".": changed_root, "survivor.txt": child},
            "working directory": {".": strict_root},
        }
        assert f"TEMP: changed . ({field})" in _snapshot_delta(before, after)

    changed_child = replace(child, mtime_ns=child.mtime_ns + 1)
    child_delta = _snapshot_delta(
        before,
        {
            "TEMP": {".": temp_root, "survivor.txt": changed_child},
            "working directory": {".": strict_root},
        },
    )
    assert "TEMP: changed survivor.txt (mtime_ns)" in child_delta

    removed_child_delta = _snapshot_delta(
        before,
        {
            "TEMP": {".": temp_root},
            "working directory": {".": strict_root},
        },
    )
    assert "TEMP: removed survivor.txt" in removed_child_delta

    created_child_delta = _snapshot_delta(
        before,
        {
            "TEMP": {
                ".": temp_root,
                "survivor.txt": child,
                "created.txt": child,
            },
            "working directory": {".": strict_root},
        },
    )
    assert "TEMP: created created.txt" in created_child_delta

    changed_strict_root = replace(
        strict_root, mtime_ns=strict_root.mtime_ns + 1
    )
    strict_delta = _snapshot_delta(
        before,
        {
            "TEMP": {".": temp_root, "survivor.txt": child},
            "working directory": {".": changed_strict_root},
        },
    )
    assert "working directory: changed . (mtime_ns)" in strict_delta


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


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows filesystem proof")
def test_windows_powershell_baseline_respects_location_tiered_proof(tmp_path):
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        pytest.skip("PowerShell is unavailable")

    temp = tmp_path / "temp"
    working = tmp_path / "working"
    temp.mkdir()
    working.mkdir()
    environment = os.environ.copy()
    environment.update({"TEMP": str(temp), "TMP": str(temp)})
    locations = {"TEMP": temp, "working directory": working}
    before = _snapshot_locations(locations)

    completed = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "exit",
        ],
        cwd=working,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    after = _snapshot_locations(locations)
    delta = _snapshot_delta(before, after)
    assert not delta, "PowerShell baseline: " + delta


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows filesystem proof")
@pytest.mark.parametrize(
    ("workspace_present", "git_on_path"),
    [(False, True), (True, True), (False, False)],
    ids=["absent-git", "present-git", "absent-no-git"],
)
def test_windows_dry_run_preserves_every_named_filesystem_location(
    tmp_path,
    workspace_present,
    git_on_path,
):
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        pytest.skip("PowerShell is unavailable")

    home = tmp_path / "profile"
    probe_temp = tmp_path / "profile-probe-temp"
    temp = tmp_path / "temp"
    working = tmp_path / "working"
    target = tmp_path / "workspace/Apparatus"
    for directory in (
        home,
        probe_temp,
        temp,
        working,
        home / "AppData/Local",
        home / "AppData/Roaming",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    if workspace_present:
        target.mkdir(parents=True)
        (target / "existing.txt").write_text("preserve me\n", encoding="utf-8")

    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "APPDATA": str(home / "AppData/Roaming"),
            "LOCALAPPDATA": str(home / "AppData/Local"),
            "TEMP": str(probe_temp),
            "TMP": str(probe_temp),
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "ALL_PROXY": "http://127.0.0.1:9",
            "NO_PROXY": "",
        }
    )
    # Bind the proof to the same .NET SpecialFolder root the bootstrap script
    # uses. Caller-provided HOME/USERPROFILE values are not evidence that this
    # API resolved the same install root.
    profile_probe = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "[Console]::Out.Write([Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile))",
        ],
        cwd=working,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert profile_probe.returncode == 0, profile_probe.stdout + profile_probe.stderr
    user_profile = Path(profile_probe.stdout)
    assert user_profile.is_absolute(), "the script's user profile root must be absolute"
    environment["TEMP"] = str(temp)
    environment["TMP"] = str(temp)
    if not git_on_path:
        system_root = Path(os.environ["SystemRoot"])
        environment["PATH"] = os.pathsep.join(
            (
                str(system_root / "System32"),
                str(system_root),
                str(system_root / "System32/WindowsPowerShell/v1.0"),
            )
        )

    locations = _windows_proof_locations(
        user_profile=user_profile,
        target=target,
        temp=temp,
        working=working,
    )
    assert set(locations) == {
        "workspace target",
        "install destination: uv executable",
        "install destination: managed Python",
        "install destination: tool packages",
        "install destination: tool commands",
        "install destination: uv cache",
        "TEMP",
        "working directory",
    }
    before = _snapshot_locations(locations)
    assert bool(before["workspace target"]) is workspace_present
    for label, objects in before.items():
        for name, object_state in objects.items():
            assert object_state.identity != (0, 0), (
                f"{label}: {name} did not expose a usable file identity"
            )

    completed = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(WINDOWS_SCRIPT),
            "-DryRun",
            "-Path",
            str(target),
        ],
        cwd=working,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "read-only detection; no install, network, or workspace commands" in (
        completed.stdout
    )
    after = _snapshot_locations(locations)
    delta = _snapshot_delta(before, after)
    assert not delta, delta


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows ETW regression")
@pytest.mark.skipif(
    _is_github_hosted_runner(),
    reason=WINDOWS_HOSTED_ETW_SKIP_REASON,
)
def test_windows_optional_etw_witness_has_no_file_registry_or_network_syscalls():
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
