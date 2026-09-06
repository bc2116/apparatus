"""Normal installer control flow with a built wheel and isolated tool collaborators.

No download or user installation is performed. Enrollment, migration, receipts,
layout proofs and doctor report publication execute from the real wheel.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def wheel_site(tmp_path_factory):
    root = tmp_path_factory.mktemp("bootstrap-wheel").resolve()
    subprocess.run(["uv", "build", "--wheel", str(REPO / "packages/apparatus-core"),
                    "--out-dir", str(root / "dist")], check=True, capture_output=True)
    wheel, = (root / "dist").glob("*.whl")
    site = root / "site"
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(site)
    assert (site / "apparatus_core/commands/init.py").is_file()
    assert '--adopt' in (site / "apparatus_core/commands/init.py").read_text()
    return site


def replace_once(text, before, after):
    assert text.count(before) == 1, before
    return text.replace(before, after)


class Setup:
    def __init__(self, root, site, *, missing_git=False, failure=None, initial_git_absent=False, report_fault=None):
        self.root = root.resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.log = self.root / "calls.jsonl"
        self.target = self.home / "Projects"
        self.site = site
        self.windows = sys.platform == "win32"
        self.bin = self.home / ".local/bin"
        self.bin.mkdir(parents=True)
        (self.home / ".local/share/uv/python/cpython-3.12-test").mkdir(parents=True)
        self.helper = self.root / "collaborator.py"
        # The only core override is optional dependency detection. No enrollment,
        # write, restore or ownership behavior is replaced.
        self.helper.write_text(f'''import json, os, pathlib, shutil, sys
site = pathlib.Path({str(site)!r})
sys.path.insert(0, str(site))
log = pathlib.Path({str(self.log)!r})
kind, *args = sys.argv[1:]
with log.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps([kind, *args]) + "\\n")
if kind == "uv":
    assert os.environ["UV_TOOL_DIR"] == {str(self.home / '.local/share/uv/tools')!r}
    assert os.environ["UV_DEFAULT_INDEX"] == "https://pypi.org/simple"
    assert "PIP_INDEX_URL" not in os.environ
    if args == ["--version"]:
        print("uv 0.0.0-test")
    elif args[:2] == ["tool", "install"]:
        shutil.copy2({str(self.bin / 'apparatus-template')!r}, {str(self.bin / ('apparatus.cmd' if self.windows else 'apparatus'))!r})
    elif args[:2] not in (["tool", "upgrade"], ["python", "find"], ["python", "install"]):
        raise SystemExit("unexpected uv operation")
    raise SystemExit(0)
import apparatus_core
assert pathlib.Path(apparatus_core.__file__).is_relative_to(site)
with log.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(["wheel", apparatus_core.__version__, str(apparatus_core.__file__)]) + "\\n")
if {missing_git!r}:
    import apparatus_core.snapshots as snapshots
    snapshots.git_available = lambda: False
    import apparatus_core.detect as detection
    real_detect = detection.detect_machine
    def detect(**kwargs):
        result = real_detect(**kwargs)
        result["git"] = {{"present": False, "version": None}}
        return result
    detection.detect_machine = detect
if args and args[0] == {failure!r}:
    print("synthetic required step failed")
    raise SystemExit(2)
from apparatus_core.cli import main
code = main(args)
if args and args[0] == "doctor" and {report_fault!r}:
    report = pathlib.Path(args[1]) / "System/machine-report.md"
    text = report.read_text()
    assert 'snapshots:' in text and 'git:' in text
    fault = {report_fault!r}
    if fault == "missing":
        text = "\\n".join(line for line in text.split("\\n") if not line.startswith("git:"))
    elif fault == "inconsistent":
        text = text.replace('snapshots: "available"', 'snapshots: "unavailable"')
    elif fault == "duplicate":
        text = text.replace('\\n---\\n', '\\ngit: null\\n---\\n', 1)
    elif fault == "duplicate-risk":
        text = text.replace('\\n---\\n', '\\n  at_risk: true\\n---\\n', 1)
    elif fault == "bad-status":
        code = 1
    report.write_text(text)
    with log.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(["report-fault", fault]) + "\\n")
raise SystemExit(code)
''', encoding="utf-8")
        for kind in ("uv", "apparatus"):
            self.launcher(self.bin / (kind + (".cmd" if self.windows else "")), kind)
        shutil.copy2(self.bin / ("apparatus.cmd" if self.windows else "apparatus"), self.bin / "apparatus-template")
        # Start with the tool absent so the normal install collaborator is used.
        (self.bin / ("apparatus.cmd" if self.windows else "apparatus")).unlink()
        if self.windows:
            self.script = self.root / "bootstrap.ps1"
            source = (REPO / "installer/windows/bootstrap-apparatus.ps1").read_text()
            source = replace_once(source,
                '$UserProfile = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)',
                "$UserProfile = '" + str(self.home).replace("'", "''") + "'")
            source = source.replace('".local\\bin\\uv.exe"', '".local\\bin\\uv.cmd"')
            source = source.replace('"apparatus.exe"', '"apparatus.cmd"')
            source = replace_once(source, '$UvInstallUrl =',
                'function Invoke-RestMethod { throw "network is forbidden in this isolated test" }\n$UvInstallUrl =')
            if missing_git or initial_git_absent:
                source = replace_once(source, '$GitPath = Find-Git', '$GitPath = $null')
            self.script.write_text(source, encoding="utf-8")
            self.interpreter = shutil.which("powershell") or shutil.which("pwsh")
            assert self.interpreter, "normal-flow Windows coverage requires PowerShell"
        else:
            self.script = self.root / "bootstrap.sh"
            source = (REPO / "installer/macos/bootstrap-apparatus.sh").read_text()
            # A failing tool collaborator must never fall through to a download.
            deny_download = self.root / "deny-download"
            deny_download.write_text("#!/bin/sh\necho 'network is forbidden in this isolated test' >&2\nexit 1\n")
            deny_download.chmod(0o700)
            import shlex
            source = replace_once(source, 'if ! /usr/bin/curl', 'if ! ' + shlex.quote(str(deny_download)))
            if sys.platform != "darwin":
                # Linux exercises the shell flow; it does not certify macOS.
                source = replace_once(source, '== "Darwin"', '== "Linux"')
            if missing_git or initial_git_absent:
                source = replace_once(source, 'git_path=$(find_git || true)', 'git_path=""')
            self.script.write_text(source, encoding="utf-8")
            self.interpreter = "/bin/bash"

    def launcher(self, path, kind):
        if self.windows:
            text = f'@echo off\r\n"{sys.executable}" "{self.helper}" {kind} %*\r\nexit /b %errorlevel%\r\n'
        else:
            import shlex
            text = f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(self.helper))} {kind} "$@"\n'
        path.write_text(text, encoding="utf-8")
        path.chmod(0o700)

    def run(self, *, target=None, adopt=False, dry=False):
        if self.windows:
            command = [self.interpreter, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(self.script)]
            # Native Windows default is deliberately not redirected to a live drive.
            command += ["-Path", str(target or self.target)]
            if adopt:
                command += ["-Adopt"]
            if dry:
                command += ["-DryRun"]
        else:
            command = [self.interpreter, str(self.script)]
            if target is not None:
                command += ["--path", str(target)]
            if adopt:
                command += ["--adopt"]
            if dry:
                command += ["--dry-run"]
        environment = {**os.environ, "HOME": str(self.home), "UV_OFFLINE": "1",
                       "UV_TOOL_DIR": "synthetic-poison", "UV_CACHE_DIR": "synthetic-poison",
                       "PIP_INDEX_URL": "https://invalid.example", "UV_INSTALL_URL": "synthetic-poison"}
        if not self.windows:
            environment["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
        for name in ("BASH_ENV", "ENV", "PYTHONPATH"):
            environment.pop(name, None)
        return subprocess.run(command, cwd=self.root, env=environment, capture_output=True,
                              text=True, timeout=90)

    def calls(self, kind="apparatus"):
        if not self.log.exists():
            return []
        return [entry[1:] for line in self.log.read_text().splitlines()
                if (entry := json.loads(line))[0] == kind]

    def core(self, *args):
        result = subprocess.run([sys.executable, str(self.helper), "apparatus", *map(str, args)],
                                cwd=self.root, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("empty", [False, True])
def test_fresh_and_empty_setup_use_direct_root_and_real_wheel(tmp_path, wheel_site, empty):
    setup = Setup(tmp_path, wheel_site)
    if empty:
        setup.target.mkdir()
    result = setup.run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ask for your actual task" in result.stdout
    assert setup.calls()[0] == ["init", str(setup.target)]
    assert not (setup.target / "Apparatus").exists()
    assert (setup.target / "System/workspace.yaml").is_file()
    assert (setup.target / "Memory/Decisions").is_dir()
    assert (setup.target / ".agents/skills/apparatus-economizer/SKILL.md").is_file()
    assert len(setup.calls("wheel")) >= 2
    assert any(call[:2] == ["tool", "install"] for call in setup.calls("uv"))


@pytest.mark.parametrize("kind", ["ordinary", "partial_legacy", "complete_legacy"])
def test_existing_unmarked_requires_explicit_adoption_then_preserves_files(tmp_path, wheel_site, kind):
    setup = Setup(tmp_path, wheel_site)
    root = setup.target
    root.mkdir()
    if kind == "complete_legacy":
        shutil.copytree(REPO / "starter/payload", root, dirs_exist_ok=True)
        old_procedures = REPO / "packages/apparatus-core/tests/fixtures/instruction_updates_pr36/System/procedures"
        shutil.copytree(old_procedures, root / "System/procedures", dirs_exist_ok=True)
    if kind != "ordinary":
        fixtures = REPO / "packages/apparatus-core/tests/fixtures/instruction_updates_pr40"
        for path in fixtures.rglob("*"):
            if path.is_file():
                target = root / path.relative_to(fixtures)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
    if kind == "complete_legacy":
        # This exact old shape previously short-circuited installer migration.
        for name in ("Goals", "Decisions", "Projects", "Library", "Deliverables", "Memory/People", "Memory/Facts", "System/receipts"):
            (root / name).mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    project = root / "existing project"
    project.mkdir()
    (project / "report.md").write_text("Synthetic selected original.\n")
    subprocess.run(["git", "init", "--quiet", str(project)], check=True)
    before = tree(root)
    refusal = setup.run()
    assert refusal.returncode != 0
    assert "requires --adopt" in refusal.stdout
    assert "released script" in refusal.stderr
    assert ("-Path" if setup.windows else "--path") in refusal.stderr
    assert "Apparatus is ready" not in refusal.stdout
    assert tree(root) == before
    assert len([call for call in setup.calls() if call[0] == "init"]) == 1
    result = setup.run(adopt=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert ["init", str(root), "--adopt"] in setup.calls()
    assert tree(project) == {name[len("existing project/"):]: value for name, value in before.items() if name.startswith("existing project/")}
    assert tree(root / ".git") == {name[len(".git/"):]: value for name, value in before.items() if name.startswith(".git/")}
    assert (root / "System/workspace.yaml").is_file()
    assert (root / ".agents/skills/apparatus-humanizer/SKILL.md").is_file()
    if kind != "ordinary":
        assert before["AGENTS.md"] != (root / "AGENTS.md").read_bytes()
        assert (root / "AGENTS.md").read_bytes() == (REPO / "starter/payload/AGENTS.md").read_bytes()


def test_rerun_reaches_core_and_preserves_custom_choices_and_original(tmp_path, wheel_site):
    setup = Setup(tmp_path, wheel_site)
    assert setup.run().returncode == 0
    root = setup.target
    original = root / "research/report.md"
    original.parent.mkdir()
    original.write_text("Synthetic source remains in its project.\n")
    setup.core("library", "add", root, "research/report.md")
    canon = root / "AGENTS.md"
    canon.write_text(canon.read_text() + "\nPreserve this local instruction.\n")
    setup.core("render", root)
    setup.core("task", "start", root, "--no-memory")
    custom = root / ".agents/skills/apparatus-humanizer/SKILL.md"
    custom.write_text(custom.read_text() + "\nPreserve this local refinement.\n")
    before = tree(root)
    result = setup.run()
    assert result.returncode == 0, result.stdout + result.stderr
    init_calls = [call for call in setup.calls() if call[0] == "init"]
    assert init_calls == [["init", str(root)], ["init", str(root)]]
    after = tree(root)
    for name, content in before.items():
        if name != "System/machine-report.md":
            assert after[name] == content, name
    assert original.read_text() == "Synthetic source remains in its project.\n"


@pytest.mark.parametrize("failure", ["init", "doctor"])
def test_required_step_failure_never_reports_ready_or_retries_adoption(tmp_path, wheel_site, failure):
    setup = Setup(tmp_path, wheel_site, failure=failure)
    result = setup.run()
    assert result.returncode != 0
    assert "Apparatus is ready" not in result.stdout
    assert setup.calls().count(["init", str(setup.target)]) == 1
    assert all("--adopt" not in call for call in setup.calls())
    if failure == "doctor":
        assert (setup.target / "System/workspace.yaml").is_file()


def test_missing_git_still_enrolls_with_explicit_degraded_report(tmp_path, wheel_site):
    setup = Setup(tmp_path, wheel_site, missing_git=True)
    result = setup.run()
    assert result.returncode == 0, result.stdout + result.stderr
    report = (setup.target / "System/machine-report.md").read_text()
    assert 'git: null' in report and 'snapshots: "unavailable"' in report
    assert "Git was not confirmed by the initial probe" in result.stdout


def test_invalid_marker_and_bound_project_reject_without_changing_target(tmp_path, wheel_site):
    setup = Setup(tmp_path, wheel_site)
    assert setup.run().returncode == 0
    project = setup.target / "project"
    project.mkdir()
    setup.core("project", "bind", project, "--workspace", setup.target)
    before = tree(project)
    result = setup.run(target=project, adopt=True)
    assert result.returncode != 0 and "bound project" in result.stdout
    assert tree(project) == before
    marker = setup.target / "System/workspace.yaml"
    marker.write_text("schema: invalid\n")
    before = tree(setup.target)
    result = setup.run(adopt=True)
    assert result.returncode != 0 and "Apparatus is ready" not in result.stdout
    assert tree(setup.target) == before


@pytest.mark.parametrize("adopt", [False, True])
def test_dry_run_nonempty_root_never_calls_core_or_changes_files(tmp_path, wheel_site, adopt):
    setup = Setup(tmp_path, wheel_site)
    setup.target.mkdir()
    (setup.target / "existing.md").write_text("Synthetic work.\n")
    before = tree(setup.root)
    result = setup.run(dry=True, adopt=adopt)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "core validation and repair" in result.stdout
    assert "init skip" not in result.stdout
    assert setup.calls() == [] and setup.calls("uv") == []
    assert tree(setup.root) == before
    assert ("explicitly requested" in result.stdout) is adopt


def test_bootstrap_defaults_and_core_delegation_are_not_legacy_inventory():
    mac = (REPO / "installer/macos/bootstrap-apparatus.sh").read_text()
    windows = (REPO / "installer/windows/bootstrap-apparatus.ps1").read_text()
    assert 'target="$HOME/Projects"' in mac
    assert '"C:\\Projects"' in windows
    assert 'workspace_present' not in mac and 'Test-WorkspacePresent' not in windows
    assert 'init_options=("$target")' in mac  # nonempty under Bash 3 nounset
    assert 'if ($Adopt) { $InitOptions += "--adopt" }' in windows


def test_final_doctor_can_confirm_git_missed_by_initial_probe(tmp_path, wheel_site):
    setup = Setup(tmp_path, wheel_site, initial_git_absent=True)
    result = setup.run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Git was not confirmed by the initial probe" in result.stdout
    report = (setup.target / "System/machine-report.md").read_text()
    assert 'snapshots: "available"' in report and 'git: "git version' in report
    assert "Apparatus is ready" in result.stdout


@pytest.mark.parametrize("fault", ["missing", "inconsistent", "duplicate", "duplicate-risk", "bad-status"])
def test_final_doctor_report_must_have_consistent_fields_and_exit_status(tmp_path, wheel_site, fault):
    setup = Setup(tmp_path, wheel_site, report_fault=fault)
    result = setup.run()
    assert setup.calls("report-fault") == [[fault]], result.stdout + result.stderr
    assert result.returncode != 0
    assert "Apparatus is ready" not in result.stdout
    assert (setup.target / "System/workspace.yaml").is_file()
