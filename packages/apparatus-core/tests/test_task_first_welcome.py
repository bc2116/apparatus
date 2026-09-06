from __future__ import annotations

import argparse
from io import StringIO
from pathlib import Path

import pytest
import yaml

from apparatus_core.commands import init, profile
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.ignore import load_ignore_rules
from apparatus_core.instruction_updates import TASK_FIRST_PREVIOUS_INSTRUCTIONS, _digest
from apparatus_core.payload import shipped_payload
from apparatus_core.retention import start_task
from apparatus_core.skills import BUILTIN_PATHS

FIXTURES = Path(__file__).parent / "fixtures/instruction_updates_pr38"


def args(root, **kwargs):
    return argparse.Namespace(workspace=str(root), payload=None, privacy_mode=None,
                              work_types=None, adopt=True, **kwargs)


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def old_area(root, *, crlf=False):
    for source in FIXTURES.rglob("*"):
        if source.is_file():
            relative = source.relative_to(FIXTURES)
            content = source.read_bytes().replace(b"\r\n", b"\n")
            if relative.as_posix() in TASK_FIRST_PREVIOUS_INSTRUCTIONS:
                assert _digest(content) == TASK_FIRST_PREVIOUS_INSTRUCTIONS[relative.as_posix()]
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content.replace(b"\n", b"\r\n") if crlf else content)
    return root


@pytest.mark.parametrize("crlf", [False, True])
def test_exact_pr38_skills_orientation_and_ignore_upgrade_once(tmp_path, crlf):
    root = old_area(tmp_path / "area", crlf=crlf)
    before_profile = (root / "System/profile.yaml").read_bytes()
    assert init.run(args(root), available=lambda: False) == 0
    for relative in (*BUILTIN_PATHS, "Welcome.md", "System/README.md", "System/ignore", "AGENTS.md"):
        assert (root / relative).read_bytes() == (shipped_payload() / relative).read_bytes()
    assert (root / "System/profile.yaml").read_bytes() == before_profile
    before = files(root)
    assert init.run(args(root), available=lambda: False) == 0
    assert files(root) == before


def test_custom_skills_orientation_rules_and_preferences_survive_upgrade(tmp_path):
    root = old_area(tmp_path / "area")
    custom = {}
    for relative in ("Welcome.md", "System/README.md", "System/ignore",
                     ".agents/skills/apparatus-welcome/SKILL.md"):
        path = root / relative
        content = path.read_bytes() + b"\n# User-owned customization\n"
        path.write_bytes(content)
        custom[relative] = content
    p = root / "System/profile.yaml"
    data = yaml.safe_load(p.read_bytes())
    data.update(spend="frugal", review_day="monday", work_types=["writing"],
                features={"library_indexing": False, "snapshots": False, "ignore_rules": False})
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    custom["System/profile.yaml"] = p.read_bytes()
    # Unknown Skill and legacy procedure files remain outside stock ownership.
    for relative in (".agents/skills/custom/SKILL.md", "System/procedures/custom.md"):
        p = root / relative; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"User file kept exactly.\n"); custom[relative] = p.read_bytes()
    assert init.run(args(root), available=lambda: False) == 0
    assert all((root / relative).read_bytes() == content for relative, content in custom.items())


def test_stock_skill_late_publication_failure_restores_exact_preimages(tmp_path, monkeypatch):
    root = old_area(tmp_path / "area")
    before = files(root)
    original = WorkspaceAnchor.replace_if_unchanged
    witnessed = []
    def fail(anchor, relative, *values, **options):
        if values[-1] == (shipped_payload() / ".agents/skills/apparatus-weekly-review/SKILL.md").read_bytes():
            witnessed.append(True)
            raise OSError("synthetic final Skill publication failure")
        return original(anchor, relative, *values, **options)
    monkeypatch.setattr(WorkspaceAnchor, "replace_if_unchanged", fail)
    assert init.run(args(root), available=lambda: False) == 2
    assert witnessed
    assert files(root) == before


@pytest.mark.parametrize("status", ["unconfigured", "configured"])
def test_single_explicit_preference_preserves_status_and_unrelated_fields(tmp_path, status):
    root = tmp_path / "area"
    assert init.run(args(root), available=lambda: False) == 0
    p = root / "System/profile.yaml"
    before = yaml.safe_load(p.read_bytes())
    before["status"] = status
    p.write_text(yaml.safe_dump(before), encoding="utf-8")
    context = start_task(root)
    candidate = {**before, "spend": "frugal"}
    assert profile.run(args(root, profile_action="apply", candidate_stdin=True, task=context.task_id),
                       input_stream=StringIO(yaml.safe_dump(candidate))) == 0
    assert yaml.safe_load(p.read_bytes()) == candidate
    assert not list((root / "Goals").glob("*.md"))
    assert not list((root / "Memory/People").glob("*.md"))


def test_no_save_preference_change_rejected_before_candidate_read(tmp_path):
    root = tmp_path / "area"
    assert init.run(args(root), available=lambda: False) == 0
    context = start_task(root, save_memory=False)
    before = files(root)
    class Unreadable:
        def read(self):
            pytest.fail("no-save preference input must not be read")
    assert profile.run(args(root, profile_action="apply", candidate_stdin=True, task=context.task_id),
                       input_stream=Unreadable()) == 1
    assert files(root) == before


def test_editable_ignore_defaults_and_feature_off(tmp_path):
    root = tmp_path / "area"
    assert init.run(args(root), available=lambda: False) == 0
    rules = load_ignore_rules(root)
    for name in ("node_modules", ".venv", "__pycache__", ".pytest_cache"):
        assert rules.matches(f"Library/dependencies/{name}/generated.txt")
    assert not rules.matches("Library/source.txt")
    assert not rules.matches("Library/build/source.txt")
    # Ignore-file rules are editable and feature-off does not disable OS/Git rules.
    p = root / "System/profile.yaml"
    data = yaml.safe_load(p.read_bytes())
    data["features"] = {"library_indexing": True, "snapshots": True, "ignore_rules": False}
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    rules = load_ignore_rules(root)
    assert not rules.matches("Library/node_modules/generated.txt")
    assert rules.matches("Library/.git/config")


@pytest.mark.parametrize("relative", [".agents/skills/apparatus-welcome/SKILL.md", "Welcome.md", "System/ignore"])
def test_stock_update_rejects_stale_preimage_and_preserves_competing_bytes(tmp_path, monkeypatch, relative):
    root = old_area(tmp_path / "area")
    before = files(root)
    original = init.deploy_init_plan
    competitor = b"Concurrent user-owned edit.\n"
    def raced(*values, **options):
        (root / relative).write_bytes(competitor)
        return original(*values, **options)
    monkeypatch.setattr(init, "deploy_init_plan", raced)
    assert init.run(args(root), available=lambda: False) == 2
    assert files(root) == {**before, relative: competitor}


def test_no_save_stock_upgrade_does_not_capture_task_content(tmp_path):
    root = old_area(tmp_path / "area")
    task = start_task(root, save_memory=False)
    profile_before = (root / "System/profile.yaml").read_bytes()
    control_before = (root / f"System/tasks/{task.task_id}.yaml").read_bytes()
    def forbidden(*_values, **_options):
        pytest.fail("generic guidance repair must not take a no-save snapshot")
    assert init.run(args(root, task=task.task_id), available=lambda: True, take=forbidden) == 0
    assert (root / "System/profile.yaml").read_bytes() == profile_before
    assert (root / f"System/tasks/{task.task_id}.yaml").read_bytes() == control_before
    assert not (root / "System/recovery").exists()
    assert not list((root / "Memory/People").glob("*.md"))
    for relative in BUILTIN_PATHS:
        assert (root / relative).read_bytes() == (shipped_payload() / relative).read_bytes()


def test_task_first_upgrade_preserves_dirty_root_and_project_git(tmp_path):
    import shutil
    import subprocess
    if shutil.which("git") is None:
        pytest.skip("real Git is required for the dirty-repository preservation proof")
    root = old_area(tmp_path / "area")
    project = root / "existing-project"
    project.mkdir()
    def git(directory, *arguments):
        subprocess.run(["git", "-C", str(directory), *arguments], check=True,
                       capture_output=True)
    for directory in (root, project):
        git(directory, "init", "-q")
        tracked = directory / "work.txt"
        tracked.write_bytes(b"Staged work.\n")
        git(directory, "add", "work.txt")
        tracked.write_bytes(b"Unstaged work.\n")
        (directory / "untracked.txt").write_bytes(b"Untracked work.\n")
    root_git = files(root / ".git")
    project_before = files(project)
    assert init.run(args(root), available=lambda: False) == 0
    assert files(root / ".git") == root_git
    assert files(project) == project_before
    assert (root / "work.txt").read_bytes() == b"Unstaged work.\n"
    assert (root / "untracked.txt").read_bytes() == b"Untracked work.\n"
