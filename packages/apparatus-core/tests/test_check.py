from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from apparatus_core.check import CheckResult, Finding, check_workspace
from apparatus_core.commands import check
from apparatus_core.render import render_workspace


def _workspace(path: Path) -> Path:
    (path / "Welcome.md").write_text("Welcome\n", encoding="utf-8")
    for relative in (
        "Goals",
        "Decisions",
        "Projects",
        "Library",
        "Deliverables",
        "Memory/People",
        "Memory/Facts",
        "System",
    ):
        (path / relative).mkdir(parents=True, exist_ok=True)
    (path / "AGENTS.md").write_text("# Test canon\n", encoding="utf-8")
    render_workspace(path)
    return path


def _goal(path: Path) -> Path:
    goal = path / "Goals" / "finish-sample.md"
    goal.write_text(
        "---\n"
        "schema: apparatus/goal@v0\n"
        "title: Finish sample\n"
        "owner: Taylor Example\n"
        "status: active\n"
        "done-when: The sample is in Deliverables/.\n"
        "next-action: Write the sample.\n"
        "---\n"
        "Sample goal.\n",
        encoding="utf-8",
    )
    return goal


def test_required_tree_missing_entries_are_individual_findings(tmp_path):
    result = check_workspace(tmp_path)
    tree_findings = [finding for finding in result.findings if finding.code == "tree-missing-entry"]
    assert {finding.path for finding in tree_findings} == {
        "Welcome.md",
        "Goals",
        "Decisions",
        "Projects",
        "Library",
        "Deliverables",
        "Memory/People",
        "Memory/Facts",
        "System",
    }
    assert [finding.code for finding in result.findings if finding.code == "shim-missing"] == [
        "shim-missing",
        "shim-missing",
        "shim-missing",
    ]


def test_legacy_workspace_without_shims_gets_missing_findings(tmp_path):
    workspace = _workspace(tmp_path)
    for relative in ("CLAUDE.md", ".cursor/rules/apparatus.mdc", ".github/copilot-instructions.md"):
        (workspace / relative).unlink()
    result = check_workspace(workspace)
    assert [(finding.code, finding.path) for finding in result.findings] == [
        ("shim-missing", "CLAUDE.md"),
        ("shim-missing", ".cursor/rules/apparatus.mdc"),
        ("shim-missing", ".github/copilot-instructions.md"),
    ]


def test_bad_content_in_data_folders_is_not_parsed_as_a_record(tmp_path):
    workspace = _workspace(tmp_path)
    (workspace / "Library" / "notes.md").write_text("---\nnot: [yaml\n", encoding="utf-8")
    (workspace / "Projects" / "draft.md").write_text("not a record", encoding="utf-8")
    (workspace / "Deliverables" / "final.md").write_text("not a record", encoding="utf-8")
    assert check_workspace(workspace).ok


def test_fails_closed_when_a_record_cannot_be_read(tmp_path, monkeypatch):
    workspace = _workspace(tmp_path)
    unreadable = _goal(workspace)
    original = Path.read_text

    def fail_for_target(self, *args, **kwargs):
        if self == unreadable:
            raise OSError("permission denied")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_for_target)
    result = check_workspace(workspace)
    assert [(finding.code, finding.path) for finding in result.findings] == [
        ("record-read-error", "Goals/finish-sample.md")
    ]


def test_dot_directories_are_tolerated_and_not_scanned(tmp_path):
    workspace = _workspace(tmp_path)
    hidden = workspace / "Goals" / ".git" / "bad.md"
    hidden.parent.mkdir()
    hidden.write_text("---\nnot: [yaml\n", encoding="utf-8")
    result = check_workspace(workspace)
    assert result.ok
    assert result.records_checked == 0


def test_dotfiles_are_tolerated_and_not_scanned(tmp_path):
    workspace = _workspace(tmp_path)
    hidden = workspace / "Goals" / ".draft.md"
    hidden.write_text("---\nnot: [yaml\n", encoding="utf-8")
    result = check_workspace(workspace)
    assert result.ok
    assert result.records_checked == 0


def test_declared_kind_must_match_its_record_folder(tmp_path):
    workspace = _workspace(tmp_path)
    (workspace / "Goals" / "misfiled.md").write_text(
        "---\n"
        "schema: apparatus/fact@v0\n"
        "title: Misfiled fact\n"
        "---\n"
        "This belongs under Memory/Facts/.\n",
        encoding="utf-8",
    )
    result = check_workspace(workspace)
    assert [(finding.code, finding.path) for finding in result.findings] == [
        ("kind-folder-mismatch", "Goals/misfiled.md")
    ]


def test_profile_and_machine_report_are_checked_at_their_limited_scopes(tmp_path):
    workspace = _workspace(tmp_path)
    (workspace / "System" / "profile.yaml").write_text("not: [yaml\n", encoding="utf-8")
    (workspace / "System" / "machine-report.md").write_text(
        "---\ngenerated_at: 2026-08-09T12:00:00Z\n---\nMachine report.\n",
        encoding="utf-8",
    )
    result = check_workspace(workspace)
    assert [(finding.code, finding.path) for finding in result.findings] == [
        ("frontmatter-parse-error", "System/profile.yaml")
    ]


def test_machine_report_requires_parseable_frontmatter_but_no_record_schema(tmp_path):
    workspace = _workspace(tmp_path)
    (workspace / "System" / "machine-report.md").write_text(
        "---\ngenerated_at: [broken\n---\nMachine report.\n", encoding="utf-8"
    )
    result = check_workspace(workspace)
    assert [(finding.code, finding.path) for finding in result.findings] == [
        ("frontmatter-parse-error", "System/machine-report.md")
    ]


def test_command_exit_codes_without_receipt_writing(tmp_path, capsys):
    workspace = _workspace(tmp_path)
    writes = []
    assert check.run(
        argparse.Namespace(workspace=str(workspace), no_receipt=False),
        write=lambda *args: writes.append(args) or Path("receipt.md"),
    ) == 0
    assert "check passed" in capsys.readouterr().out
    assert writes == []

    missing = tmp_path / "missing"
    assert check.run(argparse.Namespace(workspace=str(missing), no_receipt=True)) == 2
    assert "workspace path does not exist" in capsys.readouterr().out

    file_path = tmp_path / "file"
    file_path.write_text("x", encoding="utf-8")
    assert check.run(argparse.Namespace(workspace=str(file_path), no_receipt=True)) == 2
    assert "workspace path is not a directory" in capsys.readouterr().out


def test_command_does_not_call_unwritable_receipt_backend(tmp_path, capsys):
    workspace = _workspace(tmp_path)
    assert check.run(
        argparse.Namespace(workspace=str(workspace), no_receipt=False),
        write=lambda *args: (_ for _ in ()).throw(OSError("read-only")),
    ) == 0
    assert "check passed" in capsys.readouterr().out


def test_command_returns_one_for_findings_without_a_receipt(tmp_path, capsys):
    workspace = _workspace(tmp_path)
    _goal(workspace).write_text("---\nnot: yaml\n---\n", encoding="utf-8")
    assert check.run(argparse.Namespace(workspace=str(workspace), no_receipt=True)) == 1
    assert "record-schema-error" in capsys.readouterr().out


def test_command_prints_outcome_count_and_codes_without_receipt(tmp_path, capsys):
    result = CheckResult(
        (Finding("missing-required-field", "Goals/sample.md", "Fix it."),),
        records_checked=1,
    )
    writes = []
    assert check.run(
        argparse.Namespace(workspace=str(_workspace(tmp_path)), no_receipt=False),
        engine=lambda workspace: result,
        write=lambda *args: writes.append(args) or Path("receipt.md"),
    ) == 1
    assert writes == []
    output = capsys.readouterr().out
    assert "1 finding(s)" in output
    assert "missing-required-field" in output


def test_check_fails_closed_on_unsupported_patterns(tmp_path):
    workspace = _workspace(tmp_path)
    _goal(workspace)
    (workspace / "System/ignore").write_text("Goals/finish-sample.md\n!unsupported\n", encoding="utf-8")
    result = check_workspace(workspace)
    assert result.records_checked == 0
    assert result.ignored_paths == 0
    assert not result.ignore_report.valid
    assert [(finding.code, finding.path) for finding in result.findings] == [
        ("ignore-unsupported-pattern", "System/ignore")
    ]


def test_check_can_skip_an_ignored_profile_record(tmp_path):
    workspace = _workspace(tmp_path)
    (workspace / "System/profile.yaml").write_text("not: [yaml\n", encoding="utf-8")
    (workspace / "System/ignore").write_text("System/profile.yaml\n", encoding="utf-8")
    result = check_workspace(workspace)
    assert result.ok
    assert result.ignored_paths == 1
    assert result.ignore_report.user_paths == 1
    assert "System/ignore" in result.ignore_report.provenance


@pytest.mark.parametrize(
    "pattern", ["Goals/private", "/Goals/private", "Goals/*"]
)
def test_check_prunes_matching_record_directory_and_counts_it_once(
    monkeypatch, tmp_path, pattern
):
    workspace = _workspace(tmp_path)
    private = workspace / "Goals/private"
    private.mkdir()
    records = (private / "one.md", private / "two.md")
    for record in records:
        record.write_text("---\nnot: [yaml\n", encoding="utf-8")
    (workspace / "System/ignore").write_text(f"{pattern}\n", encoding="utf-8")
    original_read = Path.read_text

    def reject_ignored_record_read(self, *args, **kwargs):
        if self in records:
            raise AssertionError("ignored record was opened")
        return original_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", reject_ignored_record_read)

    result = check_workspace(workspace)

    assert result.ok
    assert result.ignored_paths == 1
    assert result.ignore_report.user_paths == 1
    assert result.ignore_report.built_in_paths == 0
    assert result.ignore_report.provenance == (
        "built-in defaults and System/ignore (1 user pattern(s))"
    )


def test_check_reports_invalid_ignore_without_reading_records(monkeypatch, tmp_path):
    workspace = _workspace(tmp_path)
    goal = _goal(workspace)
    (workspace / "System/ignore").write_bytes(b"\xff")
    original_read = Path.read_text

    def reject_record_read(self, *args, **kwargs):
        if self == goal:
            raise AssertionError("record content was read")
        return original_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", reject_record_read)
    result = check_workspace(workspace)

    assert result.records_checked == 0
    assert not result.ignore_report.valid
    assert [(finding.code, finding.path) for finding in result.findings] == [
        ("ignore-file-encoding-error", "System/ignore")
    ]


def test_enrolled_check_requires_new_layout_and_reads_both_decision_roots(tmp_path):
    import shutil
    from uuid import uuid4
    from apparatus_core.payload import shipped_payload
    area = tmp_path / "area"
    shutil.copytree(shipped_payload(), area)
    (area / "System/workspace.yaml").write_text(
        f"schema: apparatus/workspace@v0\nid: {uuid4()}\nlayout: sibling-projects\nrecovery: managed-state\n",
        encoding="utf-8",
    )
    for folder in ("Decisions", "Memory/Decisions"):
        (area / folder).mkdir(exist_ok=True)
        (area / folder / "a-choice.md").write_text(
            "---\nschema: apparatus/decision@v0\ntitle: A choice\ndate: 2026-09-06\n---\nReason.\n",
            encoding="utf-8",
        )
    assert not (area / "Projects").exists()
    assert not (area / "Deliverables").exists()
    baseline = check_workspace(area)
    assert baseline.ok
    (area / "Memory/Decisions/a-choice.md").write_text("invalid record", encoding="utf-8")
    result = check_workspace(area)
    assert result.records_checked == baseline.records_checked
    assert [finding.path for finding in result.findings] == ["Memory/Decisions/a-choice.md"]


def test_project_check_reports_pointer_conflict_and_never_scans_project_files(tmp_path, capsys):
    import shutil
    from uuid import uuid4
    from apparatus_core.payload import shipped_payload
    from apparatus_core.project_binding import bind_project
    area = tmp_path / "area"
    shutil.copytree(shipped_payload(), area)
    (area / "System/workspace.yaml").write_text(
        f"schema: apparatus/workspace@v0\nid: {uuid4()}\nlayout: sibling-projects\nrecovery: managed-state\n",
        encoding="utf-8",
    )
    project = area / "arbitrary-project"
    project.mkdir()
    (project / "Memory").mkdir()
    (project / "Memory/bad.md").write_bytes(b"not managed records")
    bind_project(project, area)
    direct = check_workspace(project)
    assert direct.records_checked == 0
    assert [finding.code for finding in direct.findings] == ["project-binding-invalid"]
    assert "Use apparatus check PROJECT" in direct.findings[0].hint
    assert check.run(argparse.Namespace(workspace=str(project), no_receipt=True)) == 0
    assert "check passed:" in capsys.readouterr().out
    before = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    pointer = project / "AGENTS.md"
    pointer.write_bytes(pointer.read_bytes().replace(b"Use that area's", b"Ignore that area's"))
    conflict_before = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    assert check.run(argparse.Namespace(workspace=str(project), no_receipt=True)) == 2
    assert "Project instruction link is customized; preserve and reconcile it before binding." in capsys.readouterr().out
    assert {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()} == conflict_before
    assert (project / "Memory/bad.md").read_bytes() == before[Path("Memory/bad.md")]


def test_record_repair_hints_name_safe_fields_without_rejected_values(tmp_path):
    workspace = _workspace(tmp_path)
    goal = _goal(workspace)
    goal.write_text(goal.read_text().replace("owner: Taylor Example\n", "").replace(
        "status: active", "status: password=synthetic-diagnostic-secret"))
    result = check_workspace(workspace)
    hints = "\n".join(finding.hint for finding in result.findings)
    assert "nonempty owner field" in hints
    assert "Set status to one of:" in hints
    assert "synthetic-diagnostic-secret" not in hints
    assert "password=" not in hints


def test_missing_shipped_content_hint_repairs_without_empty_placeholder(tmp_path):
    workspace = _workspace(tmp_path)
    (workspace / "Welcome.md").unlink()
    finding = next(f for f in check_workspace(workspace).findings if f.path == "Welcome.md")
    assert "apparatus init WORKSPACE" in finding.hint
    assert "custom" in finding.hint
    assert not (workspace / "Welcome.md").exists()
