from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re

import pytest
from apparatus_core import cli, receipts, records
from apparatus_core.check import check_workspace
from apparatus_core.commands import egress as egress_command
from apparatus_core.egress import CREDENTIAL_REFUSAL_CODE, check_egress
from apparatus_core.render import render_workspace


def _workspace(path: Path, mode: str = "standard") -> Path:
    path.mkdir()
    (path / "Welcome.md").write_text("Welcome\n", encoding="utf-8")
    for relative in (
        "Goals",
        "Decisions",
        "Projects",
        "Library",
        "Deliverables",
        "Memory/People",
        "Memory/Facts",
        "System/receipts",
    ):
        (path / relative).mkdir(parents=True, exist_ok=True)
    (path / "System/profile.yaml").write_text(
        "schema: apparatus/profile@v0\n"
        "status: configured\n"
        f"privacy_mode: {mode}\n"
        "work_types: []\n"
        "review_day: null\n",
        encoding="utf-8",
    )
    (path / "AGENTS.md").write_text("# Test workspace canon\n", encoding="utf-8")
    render_workspace(path)
    return path


def _args(workspace: Path, *files: str, decision: str | None = None):
    return argparse.Namespace(
        egress_action="check",
        workspace=str(workspace),
        files=list(files),
        decision=decision,
    )


def _receipts(workspace: Path, event: str) -> list[Path]:
    return sorted((workspace / "System/receipts").glob(f"*-{event}*.md"))


def _receipt_data(path: Path) -> tuple[dict, str]:
    return records.parse_record(path.read_text(encoding="utf-8"))


def test_clean_pass_writes_one_schema_valid_egress_receipt(tmp_path, capsys):
    workspace = _workspace(tmp_path / "workspace")
    outbound = workspace / "Projects/ordinary.md"
    outbound.write_text("An ordinary fictional project update.\n", encoding="utf-8")

    assert egress_command.run(_args(workspace, "Projects/ordinary.md")) == 0
    assert "no sensitive items found" in capsys.readouterr().out
    assert list(workspace.glob("Projects/*.redacted.md")) == []
    receipt = _receipts(workspace, "egress")
    assert len(receipt) == 1
    data, body = _receipt_data(receipt[0])
    assert data["outcome"] == "clean"
    assert data["finding_counts"] == {}
    assert data["decision"] is None
    assert "- none" in body
    assert check_workspace(workspace).ok


@pytest.mark.parametrize("decision", [None, "use-redacted", "send-original"])
def test_labeled_items_are_enumerated_redacted_and_decided(
    tmp_path, capsys, decision
):
    workspace = _workspace(tmp_path / "workspace")
    outbound = workspace / "Projects/contact-note.md"
    original = (
        "---\n"
        "schema: apparatus/fact@v0\n"
        "title: Contact note\n"
        "labels:\n"
        "- pii/email\n"
        "---\n"
        "Contact sample.person@example.invalid about the fictional review.\n"
    )
    outbound.write_text(original, encoding="utf-8")

    expected = 1 if decision is None else 0
    assert (
        egress_command.run(
            _args(workspace, "Projects/contact-note.md", decision=decision)
        )
        == expected
    )
    output = capsys.readouterr().out
    assert "Projects/contact-note.md:7: label/pii/email" in output
    redacted = workspace / "Projects/contact-note.redacted.md"
    assert "[redacted-email]" in redacted.read_text(encoding="utf-8")
    assert outbound.read_text(encoding="utf-8") == original
    data, body = _receipt_data(_receipts(workspace, "egress")[0])
    assert data["decision"] == decision
    assert data["finding_counts"] == {"label/pii/email": 1}
    assert data["redacted_copies"] == ["Projects/contact-note.redacted.md"]
    assert "sample.person" not in body


def test_people_name_and_email_are_exact_matched_but_unknown_name_is_not(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    (workspace / "Memory/People/riley-example.md").write_text(
        "---\n"
        "schema: apparatus/person@v0\n"
        "name: Riley Example\n"
        "labels:\n"
        "- pii/email\n"
        "---\n"
        "Email: riley.example@example.invalid\n",
        encoding="utf-8",
    )
    outbound = workspace / "Projects/handoff.txt"
    outbound.write_text(
        "Riley Example owns this. Morgan Unlisted may observe.\n"
        "Use riley.example@example.invalid for the fictional handoff.\n",
        encoding="utf-8",
    )

    result = check_egress(workspace, ["Projects/handoff.txt"])
    kinds = [(item.source, item.kind, item.line) for item in result.findings]
    assert ("people", "person-name", 1) in kinds
    assert ("people", "person-email", 2) in kinds
    assert all("Morgan" not in repr(item) for item in result.findings)
    redacted = workspace / "Projects/handoff.redacted.txt"
    text = redacted.read_text(encoding="utf-8")
    assert "[redacted-person-name] owns this. Morgan Unlisted may observe." in text
    assert "[redacted-email]" in text


def test_name_from_no_people_record_passes_unflagged(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    outbound = workspace / "Projects/unknown-name.txt"
    outbound.write_text("Morgan Unlisted approved the fictional sample.\n", encoding="utf-8")
    result = check_egress(workspace, ["Projects/unknown-name.txt"])
    assert result.exit_code == 0
    assert result.findings == ()


def test_credential_is_redacted_refuses_original_and_receipts_never_store_value(
    tmp_path, capsys
):
    workspace = _workspace(tmp_path / "workspace")
    outbound = workspace / "Projects/credential.txt"
    original = "Temporary password=sample-only for the fictional fixture.\n"
    outbound.write_text(original, encoding="utf-8")

    assert (
        egress_command.run(
            _args(workspace, "Projects/credential.txt", decision="send-original")
        )
        == 1
    )
    output = capsys.readouterr().out
    assert f"refusal-code: {CREDENTIAL_REFUSAL_CODE}" in output
    assert "credential/password" in output
    assert outbound.read_text(encoding="utf-8") == original
    assert (workspace / "Projects/credential.redacted.txt").read_text(
        encoding="utf-8"
    ) == "Temporary password=[redacted-password] for the fictional fixture.\n"
    assert len(_receipts(workspace, "redaction")) == 1
    assert len(_receipts(workspace, "egress")) == 1
    for receipt in (workspace / "System/receipts").glob("*.md"):
        text = receipt.read_text(encoding="utf-8")
        assert "sample-only" not in text
        data, _body = records.parse_record(text)
        assert records.validate("receipt", data, filename=receipt.name) == []
    egress_data, _body = _receipt_data(_receipts(workspace, "egress")[0])
    assert egress_data["outcome"] == "credential-original-refused"
    assert egress_data["decision"] == "send-original"


def test_credential_can_leave_only_through_use_redacted(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    outbound = workspace / "Projects/credential.txt"
    outbound.write_text("token=sample-only\n", encoding="utf-8")
    result = check_egress(
        workspace, ["Projects/credential.txt"], decision="use-redacted"
    )
    assert result.exit_code == 0
    assert result.outcome == "use-redacted"


def test_standard_and_private_modes_have_identical_egress_behavior(
    tmp_path, monkeypatch
):
    fixed = datetime(2026, 8, 10, 12, 30, 45, tzinfo=timezone.utc)
    monkeypatch.setattr(receipts, "_utcnow", lambda: fixed)
    results = []
    for mode in ("standard", "private"):
        workspace = _workspace(tmp_path / mode, mode)
        (workspace / "Projects/contact.txt").write_text(
            "Call 202-555-0142 about the fictional sample.\n", encoding="utf-8"
        )
        result = check_egress(workspace, ["Projects/contact.txt"])
        receipt_text = result.receipt.read_text(encoding="utf-8")
        copy_text = (workspace / result.redacted_copies[0]).read_text(encoding="utf-8")
        results.append((result.exit_code, result.findings, copy_text, receipt_text))
    assert results[0] == results[1]


def test_ignore_file_never_weakens_egress_scan(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    (workspace / "System/ignore").write_text("Projects/ignored.txt\n", encoding="utf-8")
    (workspace / "Projects/ignored.txt").write_text(
        "Contact sample.person@example.invalid.\n", encoding="utf-8"
    )
    result = check_egress(workspace, ["Projects/ignored.txt"])
    assert [(item.source, item.kind) for item in result.findings] == [
        ("label", "pii/email")
    ]


def test_one_decision_covers_the_complete_file_list_and_only_flagged_files_get_copies(
    tmp_path,
):
    workspace = _workspace(tmp_path / "workspace")
    (workspace / "Projects/clean.txt").write_text(
        "Ordinary fictional text.\n", encoding="utf-8"
    )
    (workspace / "Projects/labeled.txt").write_text(
        "Call 202-555-0142 about the fictional sample.\n", encoding="utf-8"
    )
    result = check_egress(
        workspace,
        ["Projects/clean.txt", "Projects/labeled.txt"],
        decision="use-redacted",
    )
    data, _body = _receipt_data(result.receipt)
    assert data["files"] == ["Projects/clean.txt", "Projects/labeled.txt"]
    assert data["decision"] == "use-redacted"
    assert result.redacted_copies == ("Projects/labeled.redacted.txt",)
    assert not (workspace / "Projects/clean.redacted.txt").exists()


def test_every_shipped_share_step_has_an_explicit_human_gated_check_before_it():
    procedures = (
        Path(__file__).parents[3] / "starter/payload/System/procedures"
    )
    for path in sorted(procedures.glob("*.md")):
        _data, body = records.parse_record(path.read_text(encoding="utf-8"))
        steps = {
            int(match.group(1)): match.group(2)
            for match in re.finditer(
                r"(?ms)^(\d+)\. (.*?)(?=^\d+\. |\Z)", body
            )
        }
        for number, step in steps.items():
            if not step.startswith("[share] "):
                continue
            gate = steps[number - 1]
            assert "apparatus egress check WORKSPACE DRAFT-FILE" in gate
            assert "`--decision`" in gate
            assert "user" in gate
            assert "stop" in gate.casefold()


@pytest.mark.parametrize("case", ["missing-workspace", "missing-file", "outside-file"])
def test_usage_errors_write_nothing(tmp_path, capsys, case):
    workspace = _workspace(tmp_path / "workspace")
    outside = tmp_path / "outside.txt"
    outside.write_text("Ordinary fictional text.\n", encoding="utf-8")
    if case == "missing-workspace":
        args = _args(tmp_path / "absent", "Projects/file.txt")
    elif case == "missing-file":
        args = _args(workspace, "Projects/absent.txt")
    else:
        args = _args(workspace, str(outside))
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert egress_command.run(args) == 2
    assert "egress:" in capsys.readouterr().out
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert after == before


def test_late_invalid_file_and_symlink_escape_write_nothing(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    (workspace / "Projects/sensitive.txt").write_text(
        "Contact sample.person@example.invalid.\n", encoding="utf-8"
    )
    outside = tmp_path / "outside.txt"
    outside.write_text("Outside sentinel.\n", encoding="utf-8")
    link = workspace / "Projects/link.txt"
    link.symlink_to(outside)
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    assert (
        egress_command.run(
            _args(
                workspace,
                "Projects/sensitive.txt",
                "Projects/absent.txt",
            )
        )
        == 2
    )
    assert egress_command.run(_args(workspace, "Projects/link.txt")) == 2
    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    assert after == before


def test_cli_parser_requires_workspace_and_file_and_uses_only_entry_point(capsys):
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    assert 'egress = "apparatus_core.commands.egress:register"' in text
    assert cli.main(["egress", "check"]) == 2
    assert "required" in capsys.readouterr().err
