import argparse
from pathlib import Path
import shutil

import pytest

from apparatus_core.check import _skill_findings, check_workspace
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.ignore import load_ignore_rules
from apparatus_core.payload import shipped_payload
from apparatus_core.render import render_workspace
from apparatus_core.skills import (
    BUILTIN_PATHS, BUILTIN_SKILLS, SKILL_INDEX, is_shipped_skill_orientation, legacy_pointer,
)
from apparatus_core.workspace_layout import new_layout_bytes


def _area(tmp_path, *, native=True):
    root = tmp_path / "area"
    shutil.copytree(shipped_payload(), root)
    (root / "System/workspace.yaml").write_bytes(new_layout_bytes())
    if not native:
        shutil.rmtree(root / ".agents")
        (root / "AGENTS.md").write_text("# Custom legacy instructions\n")
        (root / "Welcome.md").write_text("Welcome\n")
        (root / "System/README.md").write_text("# System\n")
        render_workspace(root)
    return root


def _check(root):
    return _skill_findings(root, load_ignore_rules(root, respect_feature=False))


def _bytes(root):
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_complete_native_set_validates_and_counts_each_body_once(tmp_path):
    root = _area(tmp_path)
    before = _bytes(root)
    assert _check(root) == ([], 5, 0, 0)
    result = check_workspace(root)
    assert result.ok
    assert result.records_checked == 6  # Five Skills and the profile.
    assert _bytes(root) == before


def test_external_ancestor_alias_keeps_canonical_workspace_boundary(tmp_path, monkeypatch):
    from apparatus_core import check as checks
    root = _area(tmp_path)
    alias = tmp_path / "external-alias"
    alias.symlink_to(tmp_path, target_is_directory=True)
    assert _check(alias / root.name) == ([], 5, 0, 0)
    read_rules = checks.load_ignore_rules
    observed = []

    def canonical_rules(workspace, **options):
        assert workspace == root.resolve(), "ignore reads used the unresolved external alias"
        observed.append(workspace)
        return read_rules(workspace, **options)

    monkeypatch.setattr(checks, "load_ignore_rules", canonical_rules)
    assert check_workspace(alias / root.name).ok
    assert observed == [root.resolve()]


def test_workspace_leaf_alias_remains_rejected_before_ignore_reads(tmp_path, monkeypatch):
    from apparatus_core import check as checks
    root = _area(tmp_path)
    before = _bytes(root)
    alias = tmp_path / "leaf-alias"
    alias.symlink_to(root, target_is_directory=True)
    monkeypatch.setattr(checks, "load_ignore_rules", lambda *_a, **_k: pytest.fail("followed a workspace leaf link"))
    result = check_workspace(alias)
    assert not result.ok
    assert [finding.code for finding in result.findings] == ["project-binding-invalid"]
    assert _bytes(root) == before


@pytest.mark.parametrize("damage", ["all-bodies", "all-directories", "one-body"])
def test_missing_native_bodies_remain_actionable(tmp_path, damage):
    root = _area(tmp_path)
    paths = list(BUILTIN_PATHS)
    missing = paths[:1] if damage == "one-body" else paths
    for relative in missing:
        (root / relative).unlink()
    if damage == "all-directories":
        shutil.rmtree(root / ".agents")
    before = _bytes(root)
    findings, count, _, _ = _check(root)
    assert {finding.path for finding in findings} == set(missing)
    assert all(finding.code == "skill-missing" and "apparatus init WORKSPACE" in finding.hint for finding in findings)
    assert count == 5 - len(missing)
    assert _bytes(root) == before


@pytest.mark.parametrize("evidence", ["directory", "stub", "canon", "orientation"])
def test_exact_installation_evidence_survives_missing_bodies(tmp_path, evidence):
    root = _area(tmp_path, native=False)
    if evidence == "directory":
        (root / next(iter(BUILTIN_PATHS))).parent.mkdir(parents=True)
    elif evidence == "stub":
        relative = next(iter(BUILTIN_SKILLS))
        (root / relative).parent.mkdir(parents=True)
        (root / relative).write_bytes(legacy_pointer(relative).replace(b"\n", b"\r\n"))
    else:
        path = "AGENTS.md" if evidence == "canon" else "System/README.md"
        (root / path).write_bytes(SKILL_INDEX.replace("\n", "\r\n").encode())
    findings, count, _, _ = _check(root)
    assert {finding.path for finding in findings if finding.code == "skill-missing"} == set(BUILTIN_PATHS)
    assert count == 0


@pytest.mark.parametrize("orientation", ["Welcome.md", "System/README.md"])
@pytest.mark.parametrize("other", ["absent", "custom"])
@pytest.mark.parametrize("crlf", [False, True])
def test_actual_shipped_orientation_detects_deleted_skills_with_preserved_custom_canon(tmp_path, orientation, other, crlf):
    from apparatus_core.commands import init
    root = tmp_path / "area"
    root.mkdir()
    canon = b"# Custom instructions\nPreserve the user's workflow.\n"
    (root / "AGENTS.md").write_bytes(canon)
    args = argparse.Namespace(workspace=str(root), payload=None, privacy_mode=None,
                              work_types=None, adopt=True)
    assert init.run(args, available=lambda: False) == 0
    assert (root / "AGENTS.md").read_bytes() == canon
    shutil.rmtree(root / ".agents")
    content = (shipped_payload() / orientation).read_bytes().replace(b"\r\n", b"\n")
    if crlf:
        content = content.replace(b"\n", b"\r\n")
    (root / orientation).write_bytes(content)
    other_path = "System/README.md" if orientation == "Welcome.md" else "Welcome.md"
    if other == "absent":
        (root / other_path).unlink()
    else:
        (root / other_path).write_bytes(b"# Custom orientation\n")
    assert is_shipped_skill_orientation(orientation, content)
    before = _bytes(root)
    result = check_workspace(root)
    assert {item.path for item in result.findings if item.code == "skill-missing"} == set(BUILTIN_PATHS)
    assert not result.ok
    assert _bytes(root) == before


@pytest.mark.parametrize("orientation", ["Welcome.md", "System/README.md"])
def test_edited_shipped_orientation_is_not_installation_or_ownership_evidence(tmp_path, orientation):
    root = _area(tmp_path, native=False)
    content = (shipped_payload() / orientation).read_bytes() + b"\nCustom changes.\n"
    (root / orientation).write_bytes(content)
    assert not is_shipped_skill_orientation(orientation, content)
    assert not is_shipped_skill_orientation("custom.md", (shipped_payload() / orientation).read_bytes())
    before = _bytes(root)
    assert _check(root) == ([], 0, 0, 0)
    assert check_workspace(root).ok
    assert _bytes(root) == before


def test_legacy_and_unrelated_native_skills_do_not_imply_installation(tmp_path, monkeypatch):
    root = _area(tmp_path, native=False)
    for relative in BUILTIN_SKILLS:
        path = root / relative
        path.parent.mkdir(exist_ok=True)
        path.write_text("---\nschema: apparatus/procedure@v0\ntitle: Legacy workflow\nintent: Keep this workflow.\n---\nOriginal steps.\n")
    foreign = root / ".agents/skills/third-party"
    foreign.mkdir(parents=True)
    (foreign / "SKILL.md").write_bytes(b"private third-party instructions")
    (root / "AGENTS.md").write_text("<!-- Apparatus Skill index: v1 -->\nA custom partial marker.\n")
    original = WorkspaceAnchor.read_file

    def bounded(self, relative):
        assert "third-party" not in str(relative)
        return original(self, relative)

    monkeypatch.setattr(WorkspaceAnchor, "read_file", bounded)
    original_iterdir = Path.iterdir

    def no_native_scan(path):
        assert ".agents" not in path.parts
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", no_native_scan)
    assert _check(root) == ([], 0, 0, 0)
    result = check_workspace(root)
    assert not any(item.code.startswith("skill-") for item in result.findings)
    assert result.records_checked == 6


@pytest.mark.parametrize("content", [b"invalid", b"\xff", b"---\nname: wrong-name\ndescription: Usable\n---\nSteps\n",
                                     b"---\nname: apparatus-welcome\ndescription: \n---\nSteps\n"])
def test_malformed_native_skill_is_reported_without_rewriting(tmp_path, content):
    root = _area(tmp_path)
    relative = ".agents/skills/apparatus-welcome/SKILL.md"
    (root / relative).write_bytes(content)
    findings, count, _, _ = _check(root)
    assert findings and all(finding.code == "skill-invalid" and finding.path == relative for finding in findings)
    assert count == 5
    assert (root / relative).read_bytes() == content


def test_mixed_historical_workflow_is_reported_and_stubs_are_healthy(tmp_path):
    root = _area(tmp_path)
    relative = next(iter(BUILTIN_SKILLS))
    old = root / relative
    old.parent.mkdir()
    body = b"---\nschema: apparatus/procedure@v0\ntitle: Original workflow\nintent: Keep it.\n---\nHistorical steps.\n"
    old.write_bytes(body)
    findings, count, _, _ = _check(root)
    assert [(item.code, item.path) for item in findings] == [("skill-mixed-state", relative)]
    assert "migrate" in findings[0].hint and count == 5
    assert old.read_bytes() == body
    old.write_bytes(legacy_pointer(relative))
    assert _check(root) == ([], 5, 0, 0)


def test_ignored_native_content_is_not_read_or_mistaken_for_legacy(tmp_path, monkeypatch):
    root = _area(tmp_path)
    (root / "System/ignore").write_text(".agents/\n")
    missing = next(iter(BUILTIN_PATHS))
    (root / missing).unlink()
    original = WorkspaceAnchor.read_file

    def no_hidden_body(self, relative):
        assert not str(relative).startswith(".agents/")
        return original(self, relative)

    monkeypatch.setattr(WorkspaceAnchor, "read_file", no_hidden_body)
    findings, count, built_in, user = _check(root)
    assert [(item.code, item.path) for item in findings if item.code == "skill-missing"] == [("skill-missing", missing)]
    assert len([item for item in findings if item.code == "skill-check-incomplete"]) == 4
    assert (count, built_in, user) == (0, 0, 4)
    result = check_workspace(root)
    assert result.records_checked == 1
    assert result.ignored_paths == 4


def test_ignored_orientation_reports_unknown_coverage_without_installation_claim(tmp_path, monkeypatch):
    root = _area(tmp_path, native=False)
    (root / "System/ignore").write_text("Welcome.md\n")
    original = WorkspaceAnchor.read_file

    def no_hidden_orientation(self, relative):
        assert str(relative) != "Welcome.md"
        return original(self, relative)

    monkeypatch.setattr(WorkspaceAnchor, "read_file", no_hidden_orientation)
    findings, count, _, _ = _check(root)
    assert [(item.code, item.path) for item in findings] == [("skill-check-incomplete", "Welcome.md")]
    assert count == 0


@pytest.mark.parametrize("endpoint", ["body", "directory", "ancestor"])
@pytest.mark.parametrize("ignored", [False, True])
def test_known_native_symlinks_are_reported_without_reading_their_target(tmp_path, monkeypatch, endpoint, ignored):
    root = _area(tmp_path)
    if ignored:
        (root / "System/ignore").write_text(".agents/\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "SKILL.md"
    sentinel.write_bytes(b"outside private bytes")
    relative = next(iter(BUILTIN_PATHS))
    target = root / relative
    if endpoint == "body":
        target.unlink()
        target.symlink_to(sentinel)
    else:
        target = target.parent if endpoint == "directory" else root / ".agents"
        shutil.rmtree(target)
        target.symlink_to(outside, target_is_directory=True)
    original = WorkspaceAnchor.read_file

    def no_unsafe_body(self, path):
        assert str(path) != relative
        assert self.workspace != outside
        return original(self, path)

    monkeypatch.setattr(WorkspaceAnchor, "read_file", no_unsafe_body)
    findings, _, _, _ = _check(root)
    assert any(item.code == "skill-path-unsafe" and item.path == relative for item in findings)
    assert any(item.code == "skill-path-unsafe" and item.path == relative for item in check_workspace(root).findings)
    assert sentinel.read_bytes() == b"outside private bytes"
