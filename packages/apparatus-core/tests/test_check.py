from __future__ import annotations

import argparse
from pathlib import Path

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


def test_command_exit_codes_and_receipt_writing(tmp_path, capsys):
    workspace = _workspace(tmp_path)
    writes = []
    assert check.run(
        argparse.Namespace(workspace=str(workspace), no_receipt=False),
        write=lambda *args: writes.append(args) or Path("receipt.md"),
    ) == 0
    assert "check passed" in capsys.readouterr().out
    assert writes[0][1] == "check"
    assert "Finding codes: none. Ignore rules excluded 0 path(s)." == writes[0][2]["body"]

    missing = tmp_path / "missing"
    assert check.run(argparse.Namespace(workspace=str(missing), no_receipt=True)) == 2
    assert "workspace path does not exist" in capsys.readouterr().out

    file_path = tmp_path / "file"
    file_path.write_text("x", encoding="utf-8")
    assert check.run(argparse.Namespace(workspace=str(file_path), no_receipt=True)) == 2
    assert "workspace path is not a directory" in capsys.readouterr().out


def test_command_returns_two_when_receipt_write_fails(tmp_path, capsys):
    workspace = _workspace(tmp_path)
    assert check.run(
        argparse.Namespace(workspace=str(workspace), no_receipt=False),
        write=lambda *args: (_ for _ in ()).throw(OSError("read-only")),
    ) == 2
    assert "could not write receipt" in capsys.readouterr().out


def test_command_returns_one_for_findings_without_a_receipt(tmp_path, capsys):
    workspace = _workspace(tmp_path)
    _goal(workspace).write_text("---\nnot: yaml\n---\n", encoding="utf-8")
    assert check.run(argparse.Namespace(workspace=str(workspace), no_receipt=True)) == 1
    assert "record-schema-error" in capsys.readouterr().out


def test_command_receipt_summary_includes_outcome_count_and_codes(tmp_path):
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
    fields = writes[0][2]
    assert "1 finding(s)" in fields["summary"]
    assert fields["body"] == "Finding codes: missing-required-field. Ignore rules excluded 0 path(s)."


def test_check_skips_matched_records_but_reports_count_and_bad_patterns(tmp_path):
    workspace = _workspace(tmp_path)
    _goal(workspace)
    (workspace / "System/ignore").write_text("Goals/finish-sample.md\n!unsupported\n", encoding="utf-8")
    result = check_workspace(workspace)
    assert result.records_checked == 0
    assert result.ignored_paths == 1
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
