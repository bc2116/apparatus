from __future__ import annotations

import argparse
import errno
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

import pytest

from apparatus_core import learned_skills as learned, managed_state_recovery as recovery
from apparatus_core.check import check_workspace
from apparatus_core.commands import init, skill
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.receipts import ReceiptPublication
from apparatus_core.retention import operation, start_task

NAME = "learned-report-review"


def body(name=NAME, text="Compare the report with its evidence and save findings."):
    return f"---\nname: {name}\ndescription: Review a recurring report with evidence.\n---\n{text}\n".encode()


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def area(tmp_path, monkeypatch):
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "home"))
    root = tmp_path / "area"
    assert init.run(argparse.Namespace(workspace=str(root), payload=None, privacy_mode=None,
                                      work_types=None), available=lambda: False) == 0
    return root, start_task(root).task_id


def args(area, action, name=NAME, digest=None):
    root, task = area
    return argparse.Namespace(workspace=str(root), task=task, skill_action=action,
                              name=name, digest=digest, stdin=True)


def draft(area, name=NAME, content=None):
    content = body(name) if content is None else content
    assert skill.run(args(area, "draft", name), input_stream=StringIO(content.decode())) == 0
    stored = (area[0] / learned.draft_path(name)).read_bytes()
    return hashlib.sha256(stored).hexdigest()


def adopt(area, name=NAME):
    digest = draft(area, name)
    assert skill.run(args(area, "adopt", name, digest)) == 0
    return digest


def test_draft_is_inactive_adoption_is_exact_repeatable_and_user_editable(area):
    root, task = area
    before = files(root)
    digest = draft(area)
    assert not (root / learned.body_path(NAME)).exists()
    with WorkspaceAnchor(root) as anchor:
        assert learned.registered_files(anchor) == {}
    assert skill.run(args(area, "adopt", digest=digest)) == 0
    assert (root / learned.body_path(NAME)).read_bytes() == body()
    assert learned.parse_marker(learned.marker_path(NAME), (root / learned.marker_path(NAME)).read_bytes()) == NAME
    published = files(root)
    assert skill.run(args(area, "adopt", digest=digest)) == 0
    assert files(root) == published
    assert (root / "AGENTS.md").read_bytes() == before["AGENTS.md"]
    assert {k: v for k, v in published.items() if k.startswith("System/receipts/")} == {
        k: v for k, v in before.items() if k.startswith("System/receipts/")}
    changed = body(text="Use the user's edited evidence comparison.")
    (root / learned.body_path(NAME)).write_bytes(changed)
    with WorkspaceAnchor(root) as anchor:
        assert learned.registered_files(anchor)[learned.body_path(NAME)] == changed
    assert not any(f.code.startswith("learned-skill") for f in check_workspace(root).findings)
    assert skill.run(args(area, "adopt", digest=digest)) == 2
    assert (root / learned.body_path(NAME)).read_bytes() == changed


@pytest.mark.parametrize("action", ["draft", "adopt"])
def test_no_save_stops_before_candidate_read_and_leaves_no_changes(area, monkeypatch, action):
    root, _ = area
    task = start_task(root, save_memory=False)
    before = files(root)
    class Unreadable:
        def read(self):
            pytest.fail("no-save read candidate")
    original = WorkspaceAnchor.capture_file
    def guard(anchor, relative, **options):
        assert str(relative) != learned.draft_path(NAME), "no-save read draft"
        return original(anchor, relative, **options)
    monkeypatch.setattr(WorkspaceAnchor, "capture_file", guard)
    with operation(root, task_id=task.task_id, requested=("snapshot", "library")):
        assert skill.run(args((root, task.task_id), action, digest="0" * 64), input_stream=Unreadable()) == 1
    assert files(root) == before


def test_missing_task_does_not_infer_retention_or_read_text(area):
    class Unreadable:
        def read(self):
            pytest.fail("missing task read candidate")
    root, _ = area
    before = files(root)
    assert skill.run(args((root, None), "draft"), input_stream=Unreadable()) == 2
    assert files(root) == before


def test_draft_redacts_before_storage_and_returns_digest_of_sanitized_bytes(area, capsys):
    root, _ = area
    capsys.readouterr()
    original = body(text="Use password=synthetic-password for this synthetic example.")
    digest = draft(area, content=original)
    output = json.loads(capsys.readouterr().out)
    assert output["sha256"] == digest
    assert "synthetic-password" not in output.values()
    saved = (root / learned.draft_path(NAME)).read_bytes()
    assert b"synthetic-password" not in saved and b"[redacted-password]" in saved
    assert len(list((root / "System/receipts").glob("*-redaction.md"))) == 1
    assert skill.run(args(area, "adopt", digest=digest)) == 0
    assert (root / learned.body_path(NAME)).read_bytes() == saved


@pytest.mark.parametrize("stale", [True, False])
def test_adoption_never_sanitizes_or_accepts_unreviewed_bytes(area, stale):
    root, _ = area
    old_digest = draft(area)
    changed = body(text="Use password=unreviewed-password for the synthetic test.")
    (root / learned.draft_path(NAME)).write_bytes(changed)
    before = files(root)
    digest = old_digest if stale else hashlib.sha256(changed).hexdigest()
    assert skill.run(args(area, "adopt", digest=digest)) == 2
    assert files(root) == before


@pytest.mark.parametrize("occupant", ["body", "marker", "directory"])
def test_partial_or_foreign_destinations_are_preserved(area, occupant):
    root, _ = area
    digest = draft(area)
    relative = learned.marker_path(NAME) if occupant == "marker" else learned.body_path(NAME)
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if occupant != "directory":
        path.write_bytes(b"User-owned occupant\n")
    before = files(root)
    assert skill.run(args(area, "adopt", digest=digest)) == 2
    assert files(root) == before


@pytest.mark.parametrize("with_resource", [False, True])
def test_native_leaf_created_after_preflight_is_not_claimed(area, monkeypatch, with_resource):
    root, _ = area
    digest = draft(area)
    before = files(root)
    leaf = root / Path(learned.body_path(NAME)).parent
    resource = leaf / "user-resource.txt"
    competitor = b"Concurrent native Skill resource.\n"
    original = skill._publish
    reached = []
    def race(*values, **options):
        assert not leaf.exists()
        leaf.mkdir()
        if with_resource:
            resource.write_bytes(competitor)
        reached.append(True)
        return original(*values, **options)
    monkeypatch.setattr(skill, "_publish", race)
    assert skill.run(args(area, "adopt", digest=digest)) == 2
    assert reached == [True]
    expected = {**before, resource.relative_to(root).as_posix(): competitor} if with_resource else before
    assert files(root) == expected
    assert leaf.is_dir()
    assert not (root / learned.body_path(NAME)).exists()
    assert not (root / learned.marker_path(NAME)).exists()


@pytest.mark.parametrize("content", [
    b"schema: apparatus/learned-skill@v0\nname: learned-other\n",
    b"schema: apparatus/learned-skill@v0\nname: learned-report-review\nname: learned-report-review\n",
    b"schema: apparatus/learned-skill@v0\nname: &name learned-report-review\n",
    b"schema: apparatus/learned-skill@v0\nname: learned-report-review\npath: ../../outside\n",
    b"schema: apparatus/learned-skill@v0\nname: [learned-report-review]\n",
])
def test_control_is_closed_unique_plain_and_name_bound(content):
    with pytest.raises(learned.LearnedSkillError):
        learned.parse_marker(learned.marker_path(NAME), content)


@pytest.mark.parametrize("name", ["apparatus-welcome", "../escape", "learned-", "learned-" + "a" * 60])
def test_name_does_not_claim_builtins_or_unsafe_paths(area, name):
    before = files(area[0])
    assert skill.run(args(area, "draft", name), input_stream=StringIO(body().decode())) == 2
    assert files(area[0]) == before


def test_late_adoption_failure_rolls_back_only_owned_body_and_allows_retry(area, monkeypatch):
    root, _ = area
    digest = draft(area)
    before = files(root)
    original = WorkspaceAnchor.create_file
    reached = []
    def fail(anchor, relative, content, **options):
        if str(relative) == f"{NAME}.yaml":
            reached.append(True)
            raise OSError("synthetic ownership publication failure")
        return original(anchor, relative, content, **options)
    monkeypatch.setattr(WorkspaceAnchor, "create_file", fail)
    assert skill.run(args(area, "adopt", digest=digest)) == 2
    assert reached and files(root) == before
    assert not (root / Path(learned.body_path(NAME)).parent).exists()
    monkeypatch.setattr(WorkspaceAnchor, "create_file", original)
    assert skill.run(args(area, "adopt", digest=digest)) == 0


def test_late_redaction_receipt_close_compensates_draft_and_receipt(area, monkeypatch):
    root, _ = area
    before = files(root)
    original = ReceiptPublication.close
    reached = []
    def fail(publication):
        original(publication)
        if "-redaction" in publication.path.name and not reached:
            reached.append(True)
            raise OSError("synthetic late redaction close")
    monkeypatch.setattr(ReceiptPublication, "close", fail)
    assert skill.run(args(area, "draft"), input_stream=StringIO(body(text="password=synthetic-secret").decode())) == 2
    assert reached and files(root) == before
    assert not (root / learned.DRAFTS).exists()


def test_stale_review_during_publication_preserves_actual_competitor_or_denial(area, monkeypatch):
    root, _ = area
    digest = draft(area)
    original = skill._validate
    outcomes = []
    changed = body(text="Concurrent edited workflow.")
    def race(anchor, reads, writes, parents):
        if writes and not outcomes:
            try:
                count = (root / learned.draft_path(NAME)).write_bytes(changed)
            except PermissionError as error:
                assert os.name == "nt" and error.errno == errno.EACCES
                outcomes.append(("blocked", error.errno, getattr(error, "winerror", None)))
            else:
                outcomes.append(("written", count))
                assert count == len(changed)
        original(anchor, reads, writes, parents)
        if outcomes and outcomes[0][0] == "blocked":
            raise OSError("synthetic failure after observed native mutation denial")
    monkeypatch.setattr(skill, "_validate", race)
    assert skill.run(args(area, "adopt", digest=digest)) == 2
    assert len(outcomes) == 1
    assert (root / learned.draft_path(NAME)).read_bytes() == (changed if outcomes[0][0] == "written" else body()), outcomes
    assert not (root / learned.body_path(NAME)).exists()
    assert not (root / learned.marker_path(NAME)).exists()


def test_missing_registered_body_is_check_and_recovery_failure_unknown_files_unclaimed(area):
    root, task = area
    adopt(area)
    unknown = root / ".agents/skills/learned-unregistered/SKILL.md"
    unknown.parent.mkdir()
    unknown.write_bytes(b"An unowned third-party file, not a valid Skill.")
    with recovery.capture_state(root) as captured:
        assert str(unknown.relative_to(root)) not in captured.files
        assert learned.draft_path(NAME) not in captured.files
    (root / learned.body_path(NAME)).unlink()
    assert any(f.code == "learned-skill-check-incomplete" for f in check_workspace(root).findings)
    with pytest.raises(recovery.SnapshotError, match="Adopted Skill"):
        recovery.capture_state(root)


def test_ignored_adopted_body_reports_incomplete_without_reading(area, monkeypatch):
    root, _ = area
    adopt(area)
    (root / "System/ignore").write_text(learned.body_path(NAME) + "\n")
    original = WorkspaceAnchor.capture_file
    def guard(anchor, relative, **options):
        assert str(relative) != learned.body_path(NAME)
        return original(anchor, relative, **options)
    monkeypatch.setattr(WorkspaceAnchor, "capture_file", guard)
    assert any(f.code == "learned-skill-check-incomplete" for f in check_workspace(root).findings)


@pytest.mark.skipif(shutil.which("git") is None, reason="real Git recovery/export proof")
def test_history_export_restore_pairs_preserve_later_adoptions(area, tmp_path):
    from apparatus_core.managed_state_backup import export_backup
    from apparatus_core.instruction_updates import LEARNED_PREVIOUS_INSTRUCTIONS
    from apparatus_core.skills import BUILTIN_PATHS
    root, task = area
    fixtures = Path(__file__).parent / "fixtures/instruction_updates_pr40"
    for relative in LEARNED_PREVIOUS_INSTRUCTIONS:
        (root / relative).write_bytes((fixtures / relative).read_bytes())
    historical = recovery.take_snapshot(root, task_id=task).snapshot
    options = argparse.Namespace(workspace=str(root), payload=None, privacy_mode=None,
                                 work_types=None, adopt=True, task=task)
    assert init.run(options, available=lambda: False) == 0
    adopt(area)
    first = recovery.take_snapshot(root, task_id=task).snapshot
    later = "learned-later-review"
    adopt(area, later)
    (root / learned.body_path(NAME)).write_bytes(body(text="Edited adopted workflow."))
    with operation(root, task_id=task):
        recovery.restore_snapshot(root, first.identifier)
    assert (root / learned.body_path(NAME)).read_bytes() == body()
    assert (root / learned.body_path(later)).read_bytes() == body(later)
    assert (root / learned.marker_path(later)).is_file()
    with operation(root, task_id=task):
        recovery.restore_snapshot(root, historical.identifier)
    assert b"System/skills/adopted/" not in (root / "AGENTS.md").read_bytes()
    assert all((root / learned.body_path(name)).is_file() and (root / learned.marker_path(name)).is_file()
               for name in (NAME, later))
    assert init.run(options, available=lambda: False) == 0
    assert b"System/skills/adopted/" in (root / "AGENTS.md").read_bytes()
    destination = tmp_path / "exports"; destination.mkdir()
    with operation(root, task_id=task):
        result = export_backup(root, destination)
    with zipfile.ZipFile(result.archive) as archive:
        names = archive.namelist()
        assert set(BUILTIN_PATHS) <= set(names)
        for name in (NAME, later):
            assert learned.body_path(name) in names and learned.marker_path(name) in names
            assert learned.draft_path(name) not in names
        extracted = tmp_path / "restored"
        archive.extractall(extracted)
    assert recovery.list_snapshots(extracted)
    with recovery.capture_state(extracted) as captured:
        assert learned.body_path(later) in captured.files
    orphan = {learned.body_path(NAME): body()}
    with pytest.raises(learned.LearnedSkillError):
        learned.validate_pairs(orphan)


def test_missing_enrollment_fails_before_input_and_preserves_legacy_files(area, capsys):
    root, _ = area
    (root / "System/workspace.yaml").unlink()
    before = files(root)
    class Unreadable:
        def read(self):
            pytest.fail("unenrolled command read candidate")
    assert skill.run(args(area, "draft"), input_stream=Unreadable()) == 2
    assert "apparatus init WORKSPACE --adopt" in capsys.readouterr().out
    assert files(root) == before


@pytest.mark.parametrize("missing", ["marker", "body"])
def test_historical_manifest_cannot_claim_an_unpaired_learned_file(area, missing):
    from apparatus_core.workspace_layout import read_layout
    root, _ = area
    included = {learned.body_path(NAME): body(), learned.marker_path(NAME): learned.marker_bytes(NAME)}
    del included[learned.marker_path(NAME) if missing == "marker" else learned.body_path(NAME)]
    identifier = read_layout(root).workspace_id
    tree = {**included, recovery.MANIFEST: recovery._manifest(identifier, included)}
    with pytest.raises(recovery.SnapshotError, match="manifest or coverage"):
        recovery._validated_manifest(identifier, tree)


def test_bound_project_cli_uses_one_adopted_body_and_no_task_text_arguments(area, tmp_path):
    from apparatus_core.project_binding import bind_project
    root, task = area
    project = root / "project"; project.mkdir()
    bind_project(project, root)
    env = {**os.environ, "APPARATUS_HOME": str(tmp_path / "cli-home")}
    result = subprocess.run([shutil.which("apparatus"), "--task", task, "skill", "draft", str(project), NAME, "--stdin"],
                            input=body(), capture_output=True, env=env)
    assert result.returncode == 0, result.stderr + result.stdout
    digest = json.loads(result.stdout)["sha256"]
    result = subprocess.run([shutil.which("apparatus"), "--task", task, "skill", "adopt", str(project), NAME, "--digest", digest],
                            capture_output=True, env=env)
    assert result.returncode == 0, result.stderr + result.stdout
    assert (root / learned.body_path(NAME)).is_file()
    assert not (project / ".agents").exists()


@pytest.mark.parametrize("target", ["draft", "parent"])
def test_symlink_candidate_or_destination_cannot_escape_work_area(area, tmp_path, target):
    root, _ = area
    outside = tmp_path / "outside"; outside.mkdir()
    (outside / "sentinel").write_bytes(b"Preserve outside files.")
    if target == "draft":
        path = root / learned.draft_path(NAME)
        path.parent.mkdir(parents=True)
        source = outside / "draft.md"; source.write_bytes(body())
    else:
        path = root / learned.DRAFTS
        source = outside
    try:
        path.symlink_to(source, target_is_directory=target == "parent")
    except OSError as error:
        if os.name == "nt" and getattr(error, "winerror", None) == 1314:
            pytest.skip("native symlink creation privilege unavailable")
        raise
    before = files(outside)
    if target == "draft":
        assert skill.run(args(area, "adopt", digest=hashlib.sha256(body()).hexdigest())) == 2
    else:
        assert skill.run(args(area, "draft"), input_stream=StringIO(body().decode())) == 2
    assert files(outside) == before
    assert path.is_symlink()
    assert not (root / learned.body_path(NAME)).exists()


def test_exact_pr39_orientation_migrates_without_changing_custom_canon(area):
    root, task = area
    fixtures = Path(__file__).parent / "fixtures/instruction_updates_pr39"
    for source in fixtures.rglob("*"):
        if source.is_file():
            (root / source.relative_to(fixtures)).write_bytes(source.read_bytes())
    assert init.run(argparse.Namespace(workspace=str(root),payload=None,privacy_mode=None,
                                      work_types=None,adopt=True,task=task),available=lambda:False)==0
    assert "System/skills/adopted/" in (root / "AGENTS.md").read_text()
    custom = (root / "AGENTS.md").read_bytes() + b"\nUser-owned instruction.\n"
    (root / "AGENTS.md").write_bytes(custom)
    assert init.run(argparse.Namespace(workspace=str(root),payload=None,privacy_mode=None,
                                      work_types=None,adopt=True,task=task),available=lambda:False)==0
    assert (root / "AGENTS.md").read_bytes() == custom


@pytest.mark.parametrize("crlf", [False, True])
@pytest.mark.parametrize("custom", [False, True])
@pytest.mark.parametrize("no_save", [False, True])
def test_actual_pr40_stock_migration_preserves_seven_skills_and_task_controls(area, crlf, custom, no_save):
    from apparatus_core.instruction_updates import LEARNED_PREVIOUS_INSTRUCTIONS, _digest
    from apparatus_core.payload import shipped_payload
    from apparatus_core.skills import BUILTIN_PATHS, SKILL_INDEX
    root, task = area
    if no_save:
        task = start_task(root, save_memory=False).task_id
    fixtures = Path(__file__).parent / "fixtures/instruction_updates_pr40"
    for relative, expected in LEARNED_PREVIOUS_INSTRUCTIONS.items():
        content = (fixtures / relative).read_bytes().replace(b"\r\n", b"\n")
        assert _digest(content) == expected
        (root / relative).write_bytes(content.replace(b"\n", b"\r\n") if crlf else content)
    preserved = [*BUILTIN_PATHS, "System/profile.yaml", "System/guidance/model-guidance.md"]
    if custom:
        for relative in (*BUILTIN_PATHS, "AGENTS.md", "Welcome.md", "System/README.md",
                         "System/guidance/model-guidance.md"):
            path = root / relative
            path.write_bytes(path.read_bytes() + b"\nUser-owned customization.\n")
        preserved.extend(("AGENTS.md", "Welcome.md", "System/README.md"))
    preserved.extend(p.relative_to(root).as_posix() for p in (root / "System/tasks").rglob("*") if p.is_file())
    assert f"System/tasks/{task}.yaml" in preserved
    before = {relative: (root / relative).read_bytes() for relative in preserved}
    options = argparse.Namespace(workspace=str(root), payload=None, privacy_mode=None,
                                 work_types=None, adopt=True, task=task)
    assert init.run(options, available=lambda: False) == 0
    assert all((root / relative).read_bytes() == content for relative, content in before.items())
    assert SKILL_INDEX.encode() in (root / "AGENTS.md").read_bytes().replace(b"\r\n", b"\n")
    if not custom:
        for relative in LEARNED_PREVIOUS_INSTRUCTIONS:
            assert (root / relative).read_bytes() == (shipped_payload() / relative).read_bytes()
        assert b"System/skills/adopted/" in (root / "AGENTS.md").read_bytes()
    assert check_workspace(root).ok
    assert not (root / learned.DRAFTS).exists()
    after = files(root)
    assert init.run(options, available=lambda: False) == 0
    assert files(root) == after


@pytest.mark.parametrize("version", ["pr40", "current"])
@pytest.mark.parametrize("orientation", ["Welcome.md", "System/README.md"])
@pytest.mark.parametrize("crlf", [False, True])
def test_old_and_new_seven_skill_orientation_rejects_partial_source(tmp_path, version, orientation, crlf):
    from apparatus_core.payload import shipped_payload
    from apparatus_core.skills import NEW_SKILL_PATHS, read_skill_payload
    payload = tmp_path / "payload"
    shutil.copytree(shipped_payload(), payload)
    source = (Path(__file__).parent / "fixtures/instruction_updates_pr40" if version == "pr40"
              else shipped_payload())
    content = (source / orientation).read_bytes().replace(b"\r\n", b"\n")
    for relative in ("AGENTS.md", "Welcome.md", "System/README.md"):
        (payload / relative).write_bytes(b"Custom orientation.\n")
    (payload / orientation).write_bytes(content.replace(b"\n", b"\r\n") if crlf else content)
    for relative in NEW_SKILL_PATHS:
        shutil.rmtree((payload / relative).parent)
    before = files(payload)
    with WorkspaceAnchor(payload) as anchor:
        with pytest.raises(ValueError, match="complete portable Skill payload"):
            read_skill_payload(anchor)
    assert files(payload) == before
