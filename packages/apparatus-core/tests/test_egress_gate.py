from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess

import pytest
from apparatus_core import cli, egress, fs_transactions, receipts, records
from apparatus_core.check import check_workspace
from apparatus_core.commands import egress as egress_command
from apparatus_core.egress import (
    CREDENTIAL_REFUSAL_CODE,
    EgressError,
    REDACTION_UNAVAILABLE_CODE,
    check_egress,
)
from apparatus_core.render import render_workspace


FIXTURES = Path(__file__).parent / "fixtures/egress"


def _workspace(
    path: Path,
    mode: str = "standard",
    *,
    receipts_directory: bool = True,
) -> Path:
    path.mkdir()
    (path / "Welcome.md").write_text("Welcome\n", encoding="utf-8")
    directories = [
        "Goals",
        "Decisions",
        "Projects",
        "Library",
        "Deliverables",
        "Memory/People",
        "Memory/Facts",
    ]
    if receipts_directory:
        directories.append("System/receipts")
    else:
        directories.append("System")
    for relative in directories:
        (path / relative).mkdir(parents=True, exist_ok=True)
    (path / "System/profile.yaml").write_text(
        "schema: apparatus/profile@v0\n"
        "status: configured\n"
        f"privacy_mode: {mode}\n"
        "work_types: []\n"
        "review_day: null\n",
        encoding="utf-8",
    )
    (path / "AGENTS.md").write_text(
        "# Test workspace canon\n", encoding="utf-8"
    )
    render_workspace(path)
    return path


def _args(
    workspace: Path,
    *files: str,
    destination: str | None = None,
    decision: str | None = None,
) -> argparse.Namespace:
    return argparse.Namespace(
        egress_action="check",
        workspace=str(workspace),
        files=list(files),
        destination=destination,
        decision=decision,
    )


def _receipts(workspace: Path, event: str) -> list[Path]:
    return sorted((workspace / "System/receipts").glob(f"*-{event}*.md"))


def _receipt_data(path: Path) -> tuple[dict, str]:
    return records.parse_record(path.read_text(encoding="utf-8"))


def _copy_fixture(name: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((FIXTURES / name).read_bytes())


def _file_snapshot(root: Path) -> dict[Path, bytes]:
    snapshot: dict[Path, bytes] = {}
    for directory, _subdirectories, filenames in os.walk(root, followlinks=False):
        for filename in filenames:
            path = Path(directory) / filename
            if not path.is_symlink():
                snapshot[path.relative_to(root)] = path.read_bytes()
    return snapshot


def _directory_link(link: Path, target: Path) -> None:
    if os.name == "nt":
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode:
            pytest.skip("this Windows worker could not create a test junction")
    else:
        link.symlink_to(target, target_is_directory=True)


def _remove_directory_link(link: Path) -> None:
    if os.name == "nt":
        os.rmdir(link)
    else:
        link.unlink()


def test_clean_pass_writes_one_schema_valid_inspection_receipt(tmp_path, capsys):
    workspace = _workspace(tmp_path / "workspace", receipts_directory=False)
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
    assert data["destination"] == "not provided"
    assert data["pre_share_authorized"] is False
    assert data["anything_left_workspace"] is False
    assert "- none" in body
    assert check_workspace(workspace).ok


def test_initial_inspection_enumerates_and_offers_without_publishing(tmp_path, capsys):
    workspace = _workspace(tmp_path / "workspace")
    outbound = workspace / "Projects/handoff.txt"
    _copy_fixture("free-form-sensitive.txt", outbound)

    assert (
        egress_command.run(
            _args(
                workspace,
                "Projects/handoff.txt",
                destination="fictional review inbox",
            )
        )
        == 1
    )

    output = capsys.readouterr().out
    assert "Projects/handoff.txt:1: label/pii/email" in output
    assert "Projects/handoff.txt:1: label/pii/phone" in output
    assert "redacted-copy offer: Projects/handoff.redacted.txt" in output
    assert "redacted-copy offer" in output
    assert not (workspace / "Projects/handoff.redacted.txt").exists()
    data, _body = _receipt_data(_receipts(workspace, "egress")[0])
    assert data["redacted_offers"] == ["Projects/handoff.redacted.txt"]
    assert data["redacted_copies"] == []
    assert data["destination"] == "fictional review inbox"
    assert data["outcome"] == "decision-required"
    assert data["pre_share_authorized"] is False


@pytest.mark.parametrize("decision", ["use-redacted", "send-original"])
def test_successful_decision_publishes_copy_and_records_authorization(
    tmp_path, decision
):
    workspace = _workspace(tmp_path / "workspace")
    outbound = workspace / "Projects/handoff.txt"
    original = (FIXTURES / "free-form-sensitive.txt").read_text(encoding="utf-8")
    outbound.write_text(original, encoding="utf-8")

    result = check_egress(
        workspace,
        ["Projects/handoff.txt"],
        destination="fictional shared folder",
        decision=decision,
    )

    assert result.exit_code == 0
    assert result.outcome == decision
    assert result.redacted_offers == ("Projects/handoff.redacted.txt",)
    assert result.redacted_copies == ("Projects/handoff.redacted.txt",)
    redacted = (workspace / result.redacted_copies[0]).read_text(encoding="utf-8")
    assert "[redacted-email]" in redacted
    assert "[redacted-phone]" in redacted
    assert outbound.read_text(encoding="utf-8") == original
    data, body = _receipt_data(result.receipt)
    assert data["decision"] == decision
    assert data["pre_share_authorized"] is True
    assert data["anything_left_workspace"] is False
    assert "Anything left the workspace: no" in body


def test_declared_labels_are_independent_and_record_copy_keeps_check_green(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    source = workspace / "Memory/Facts/contact-note.md"
    source.write_text(
        "---\n"
        "schema: apparatus/fact@v0\n"
        "title: Fictional contact note\n"
        "labels:\n"
        "- pii/email\n"
        "---\n"
        "Contact sample.person@example.invalid for the fictional review.\n",
        encoding="utf-8",
    )

    result = check_egress(
        workspace,
        ["Memory/Facts/contact-note.md"],
        decision="use-redacted",
    )

    assert [(item.source, item.kind, item.line) for item in result.findings] == [
        ("declared-label", "pii/email", 1),
        ("label", "pii/email", 7),
    ]
    assert result.redacted_copies == ("Memory/Facts/contact-note-redacted.md",)
    copy = workspace / result.redacted_copies[0]
    assert "[redacted-email]" in copy.read_text(encoding="utf-8")
    assert not (workspace / "Memory/Facts/contact-note.redacted.md").exists()
    assert check_workspace(workspace).ok


def test_label_only_content_fails_closed_in_redacted_generation(tmp_path, capsys):
    workspace = _workspace(tmp_path / "workspace")
    outbound = workspace / "Projects/opaque.md"
    _copy_fixture("label-only.md", outbound)

    assert (
        egress_command.run(
            _args(workspace, "Projects/opaque.md", decision="use-redacted")
        )
        == 1
    )

    output = capsys.readouterr().out
    assert "Projects/opaque.md:1: declared-label/confidential/project" in output
    assert "redaction unavailable: Projects/opaque.md" in output
    assert f"refusal-code: {REDACTION_UNAVAILABLE_CODE}" in output
    assert not (workspace / "Projects/opaque.redacted.md").exists()
    data, _body = _receipt_data(_receipts(workspace, "egress")[0])
    assert data["redaction_unavailable"] == ["Projects/opaque.md"]
    assert data["pre_share_authorized"] is False

    original_choice = check_egress(
        workspace, ["Projects/opaque.md"], decision="send-original"
    )
    original_data, _body = _receipt_data(original_choice.receipt)
    assert original_choice.outcome == "send-original"
    assert original_choice.redacted_copies == ()
    assert original_data["pre_share_authorized"] is True


def test_outbound_people_record_is_always_structurally_labeled(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    person = workspace / "Memory/People/riley-example.md"
    _copy_fixture("person-riley-example.md", person)

    result = check_egress(
        workspace,
        ["Memory/People/riley-example.md"],
        decision="use-redacted",
    )

    assert ("structural", "person-data", 1) in [
        (item.source, item.kind, item.line) for item in result.findings
    ]
    assert result.outcome == "redaction-unavailable-refused"
    assert result.redaction_unavailable == ("Memory/People/riley-example.md",)
    assert result.redacted_copies == ()
    assert not (workspace / "Memory/People/riley-example-redacted.md").exists()


def test_people_matches_are_case_sensitive_boundary_aware_and_not_fuzzy(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    (workspace / "Memory/People/al.md").write_text(
        "---\n"
        "schema: apparatus/person@v0\n"
        "name: Al\n"
        "---\n"
        "Email: al@example.invalid\n",
        encoding="utf-8",
    )
    outbound = workspace / "Projects/names.txt"
    outbound.write_text(
        "Also, AL, al, ÉAl, and Alé do not count; Al does.\n"
        "xal@example.invalid al@example.invalidx "
        "al@example.invalid@other.invalid al@example.invalid\n",
        encoding="utf-8",
    )

    result = check_egress(
        workspace, ["Projects/names.txt"], decision="use-redacted"
    )

    people = [item for item in result.findings if item.source == "people"]
    assert [(item.kind, item.line) for item in people] == [
        ("person-name", 1),
        ("person-email", 2),
    ]
    text = (workspace / "Projects/names.redacted.txt").read_text(encoding="utf-8")
    assert "Also, AL, al, ÉAl, and Alé do not count" in text
    assert "[redacted-person-name] does." in text


def test_name_from_no_people_record_passes_unflagged(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    outbound = workspace / "Projects/unknown-name.txt"
    outbound.write_text(
        "Morgan Unlisted approved the fictional sample.\n", encoding="utf-8"
    )

    result = check_egress(workspace, ["Projects/unknown-name.txt"])

    assert result.exit_code == 0
    assert result.findings == ()


def test_hidden_people_record_is_traversed_and_supplies_exact_matches(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    hidden = workspace / "Memory/People/.contacts/riley-example.md"
    _copy_fixture("person-riley-example.md", hidden)
    outbound = workspace / "Projects/handoff.txt"
    outbound.write_text("Riley Example owns the fictional handoff.\n", encoding="utf-8")

    result = check_egress(workspace, ["Projects/handoff.txt"])

    assert [(item.source, item.kind) for item in result.findings] == [
        ("people", "person-name")
    ]


def test_hidden_invalid_people_record_fails_closed_before_writes(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    hidden = workspace / "Memory/People/.contacts/not-a-record.md"
    hidden.parent.mkdir()
    hidden.write_text("not frontmatter\n", encoding="utf-8")
    outbound = workspace / "Projects/ordinary.txt"
    outbound.write_text("Ordinary fictional text.\n", encoding="utf-8")

    before = _file_snapshot(workspace)
    with pytest.raises(EgressError, match="Memory/People"):
        check_egress(workspace, ["Projects/ordinary.txt"])
    assert _file_snapshot(workspace) == before


@pytest.mark.skipif(os.name == "nt", reason="POSIX unreadable-mode regression")
def test_unreadable_people_record_fails_closed_before_writes(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    unreadable = workspace / "Memory/People/unreadable.md"
    _copy_fixture("person-riley-example.md", unreadable)
    outbound = workspace / "Projects/ordinary.txt"
    outbound.write_text("Ordinary fictional text.\n", encoding="utf-8")
    before = _file_snapshot(workspace)
    unreadable.chmod(0)
    try:
        try:
            unreadable.read_bytes()
        except PermissionError:
            pass
        else:
            pytest.skip("the test user can read mode-000 files")
        with pytest.raises(EgressError, match="Memory/People"):
            check_egress(workspace, ["Projects/ordinary.txt"])
    finally:
        unreadable.chmod(0o600)
    assert _file_snapshot(workspace) == before


def test_people_symlink_or_reparse_subtree_is_rejected_without_outside_read(
    tmp_path,
):
    workspace = _workspace(tmp_path / "workspace")
    outside = tmp_path / "outside-people"
    outside.mkdir()
    _copy_fixture("person-riley-example.md", outside / "riley-example.md")
    link = workspace / "Memory/People/linked"
    _directory_link(link, outside)
    outbound = workspace / "Projects/ordinary.txt"
    outbound.write_text("Ordinary fictional text.\n", encoding="utf-8")
    before_outside = _file_snapshot(outside)
    try:
        with pytest.raises(EgressError, match="Memory/People"):
            check_egress(workspace, ["Projects/ordinary.txt"])
        assert _receipts(workspace, "egress") == []
        assert _file_snapshot(outside) == before_outside
    finally:
        _remove_directory_link(link)


def test_people_root_symlink_or_reparse_is_rejected_without_outside_read(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    people = workspace / "Memory/People"
    retained = workspace / "Memory/People-retained"
    people.rename(retained)
    outside = tmp_path / "outside-people-root"
    outside.mkdir()
    _copy_fixture("person-riley-example.md", outside / "riley-example.md")
    _directory_link(people, outside)
    outbound = workspace / "Projects/ordinary.txt"
    outbound.write_text("Ordinary fictional text.\n", encoding="utf-8")
    before_outside = _file_snapshot(outside)
    try:
        with pytest.raises(EgressError, match="Memory/People"):
            check_egress(workspace, ["Projects/ordinary.txt"])
        assert _receipts(workspace, "egress") == []
        assert _file_snapshot(outside) == before_outside
    finally:
        _remove_directory_link(people)
        retained.rename(people)


def test_symlink_or_reparse_workspace_ancestor_is_rejected(tmp_path):
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    workspace = _workspace(real_parent / "workspace")
    alias = tmp_path / "alias"
    _directory_link(alias, real_parent)
    try:
        with pytest.raises(EgressError, match="containment-safe"):
            check_egress(alias / workspace.name, ["Projects/ordinary.txt"])
        assert _receipts(workspace, "egress") == []
    finally:
        _remove_directory_link(alias)


@pytest.mark.skipif(os.name != "posix", reason="POSIX descriptor race regression")
def test_path_substitution_rolls_back_exact_owned_artifacts_and_writes_nothing_outside(
    tmp_path,
):
    workspace = _workspace(tmp_path / "workspace")
    outbound = workspace / "Projects/sensitive.txt"
    outbound.write_text("Call 202-555-0142 for the fictional sample.\n", encoding="utf-8")
    detached = tmp_path / "detached-projects"
    outside = tmp_path / "outside"
    outside.mkdir()

    class SwapAfterFirstArtifact(fs_transactions.WorkspaceAnchor):
        calls = 0

        def create_file(
            self,
            relative,
            content,
            mode=0o600,
            *,
            owned_parent=None,
        ):
            owned = super().create_file(
                relative,
                content,
                mode,
                owned_parent=owned_parent,
            )
            self.calls += 1
            if self.calls == 1:
                (workspace / "Projects").rename(detached)
                (workspace / "Projects").symlink_to(
                    outside, target_is_directory=True
                )
            return owned

    with pytest.raises(EgressError, match="safely"):
        check_egress(
            workspace,
            ["Projects/sensitive.txt"],
            decision="use-redacted",
            anchor_factory=SwapAfterFirstArtifact,
        )

    assert _file_snapshot(outside) == {}
    assert not (detached / "sensitive.redacted.txt").exists()
    assert _receipts(workspace, "egress") == []


@pytest.mark.skipif(os.name != "nt", reason="native Win32 containment regression")
def test_windows_retained_source_parent_blocks_path_substitution(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    source = workspace / "Projects/source.txt"
    source.write_text("Fictional source.\n", encoding="utf-8")
    anchor = fs_transactions.WorkspaceAnchor(workspace)
    owned = anchor.capture_file("Projects/source.txt")
    try:
        with pytest.raises(OSError):
            (workspace / "Projects").rename(tmp_path / "detached-projects")
    finally:
        owned.close()
        anchor.close()


def test_existing_redacted_output_is_never_overwritten(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    source = workspace / "Projects/note.md"
    source.write_text("Contact sample.person@example.invalid.\n", encoding="utf-8")
    output = workspace / "Projects/note.redacted.md"
    output.write_text("Concurrent sentinel.\n", encoding="utf-8")
    before = _file_snapshot(workspace)

    with pytest.raises(EgressError, match="already exists"):
        check_egress(workspace, ["Projects/note.md"], decision="use-redacted")

    assert _file_snapshot(workspace) == before


def test_output_input_collision_is_rejected_before_writes(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    (workspace / "Projects/note.txt").write_text(
        "Call 202-555-0142 for the fictional sample.\n", encoding="utf-8"
    )
    (workspace / "Projects/note.redacted.txt").write_text(
        "Ordinary fictional text.\n", encoding="utf-8"
    )
    before = _file_snapshot(workspace)

    with pytest.raises(EgressError, match="collides with an input"):
        check_egress(
            workspace,
            ["Projects/note.txt", "Projects/note.redacted.txt"],
            decision="use-redacted",
        )

    assert _file_snapshot(workspace) == before


def test_duplicate_output_is_rejected_before_writes(tmp_path, monkeypatch):
    workspace = _workspace(tmp_path / "workspace")
    for name in ("one.txt", "two.txt"):
        (workspace / "Projects" / name).write_text(
            "Call 202-555-0142 for the fictional sample.\n", encoding="utf-8"
        )
    monkeypatch.setattr(
        egress,
        "_redacted_relative",
        lambda _relative: Path("Projects/shared.redacted.txt"),
    )
    before = _file_snapshot(workspace)

    with pytest.raises(EgressError, match="duplicate redacted output"):
        check_egress(
            workspace,
            ["Projects/one.txt", "Projects/two.txt"],
            decision="use-redacted",
        )

    assert _file_snapshot(workspace) == before


@pytest.mark.parametrize("duplicate_kind", ["path", "identity"])
def test_duplicate_inputs_are_rejected_before_writes(tmp_path, duplicate_kind):
    workspace = _workspace(tmp_path / "workspace")
    source = workspace / "Projects/note.txt"
    source.write_text("Call 202-555-0142 for the fictional sample.\n", encoding="utf-8")
    if duplicate_kind == "path":
        files = ["Projects/note.txt", "Projects/note.txt"]
    else:
        alias = workspace / "Projects/alias.txt"
        try:
            os.link(source, alias)
        except OSError:
            pytest.skip("this filesystem cannot create a hard-link fixture")
        files = ["Projects/note.txt", "Projects/alias.txt"]
    before = _file_snapshot(workspace)

    with pytest.raises(EgressError, match="duplicate input"):
        check_egress(workspace, files, decision="use-redacted")

    assert _file_snapshot(workspace) == before


def test_multi_file_receipt_failure_rolls_back_all_copies_and_receipts(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    first = workspace / "Projects/credential.txt"
    second = workspace / "Projects/phone.txt"
    first.write_text("password=sample-only\n", encoding="utf-8")
    second.write_text("Call 202-555-0142 for the fictional sample.\n", encoding="utf-8")
    originals = _file_snapshot(workspace)

    class FailFinalReceipt(fs_transactions.WorkspaceAnchor):
        calls = 0

        def create_file(
            self,
            relative,
            content,
            mode=0o600,
            *,
            owned_parent=None,
        ):
            self.calls += 1
            if self.calls == 4:
                raise OSError("injected final receipt failure")
            return super().create_file(
                relative,
                content,
                mode,
                owned_parent=owned_parent,
            )

    with pytest.raises(EgressError, match="safely"):
        check_egress(
            workspace,
            ["Projects/credential.txt", "Projects/phone.txt"],
            decision="use-redacted",
            anchor_factory=FailFinalReceipt,
        )

    assert _file_snapshot(workspace) == originals
    assert not list((workspace / "Projects").glob("*.redacted.txt"))
    assert _receipts(workspace, "redaction") == []
    assert _receipts(workspace, "egress") == []


def test_receipt_directory_creation_rolls_back_when_publication_fails(tmp_path):
    workspace = _workspace(tmp_path / "workspace", receipts_directory=False)
    source = workspace / "Projects/phone.txt"
    source.write_text("Call 202-555-0142 for the fictional sample.\n", encoding="utf-8")

    class FailReceipt(fs_transactions.WorkspaceAnchor):
        calls = 0

        def create_file(
            self,
            relative,
            content,
            mode=0o600,
            *,
            owned_parent=None,
        ):
            self.calls += 1
            if self.calls == 2:
                raise OSError("injected receipt failure")
            return super().create_file(
                relative,
                content,
                mode,
                owned_parent=owned_parent,
            )

    with pytest.raises(EgressError, match="safely"):
        check_egress(
            workspace,
            ["Projects/phone.txt"],
            decision="use-redacted",
            anchor_factory=FailReceipt,
        )

    assert not (workspace / "Projects/phone.redacted.txt").exists()
    assert not (workspace / "System/receipts").exists()


def test_credential_refusal_requires_fresh_explicit_use_redacted_choice(
    tmp_path, capsys
):
    workspace = _workspace(tmp_path / "workspace")
    source = workspace / "Projects/credential.txt"
    original = "Temporary password=sample-only for the fictional fixture.\n"
    source.write_text(original, encoding="utf-8")

    initial = check_egress(workspace, ["Projects/credential.txt"])
    assert initial.exit_code == 1
    assert initial.redacted_copies == ()
    assert not (workspace / "Projects/credential.redacted.txt").exists()

    assert (
        egress_command.run(
            _args(
                workspace,
                "Projects/credential.txt",
                decision="send-original",
            )
        )
        == 1
    )
    assert f"refusal-code: {CREDENTIAL_REFUSAL_CODE}" in capsys.readouterr().out
    assert not (workspace / "Projects/credential.redacted.txt").exists()

    authorized = check_egress(
        workspace,
        ["Projects/credential.txt"],
        decision="use-redacted",
    )
    assert authorized.exit_code == 0
    authorized_data, _body = _receipt_data(authorized.receipt)
    assert authorized_data["pre_share_authorized"] is True
    assert (workspace / "Projects/credential.redacted.txt").read_text(
        encoding="utf-8"
    ) == "Temporary password=[redacted-password] for the fictional fixture.\n"
    assert source.read_text(encoding="utf-8") == original
    for receipt in (workspace / "System/receipts").glob("*.md"):
        text = receipt.read_text(encoding="utf-8")
        assert "sample-only" not in text
        data, _body = records.parse_record(text)
        assert records.validate("receipt", data, filename=receipt.name) == []


def test_destination_and_stop_are_honestly_recorded_without_authorization(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    source = workspace / "Projects/contact.txt"
    source.write_text("Call 202-555-0142 for the fictional sample.\n", encoding="utf-8")

    result = check_egress(
        workspace,
        ["Projects/contact.txt"],
        destination="fictional customer portal",
        decision="stop",
    )

    assert result.exit_code == 0
    assert result.outcome == "stopped"
    assert result.redacted_copies == ()
    data, body = _receipt_data(result.receipt)
    assert data["destination"] == "fictional customer portal"
    assert data["decision"] == "stop"
    assert data["pre_share_authorized"] is False
    assert data["anything_left_workspace"] is False
    assert "Anything left the workspace: no" in body


@pytest.mark.parametrize(
    "destination", ["", "two\nlines", "password=sample-only"]
)
def test_unsafe_destination_metadata_is_rejected_before_writes(
    tmp_path, destination
):
    workspace = _workspace(tmp_path / "workspace")
    source = workspace / "Projects/ordinary.txt"
    source.write_text("Ordinary fictional text.\n", encoding="utf-8")
    before = _file_snapshot(workspace)

    with pytest.raises(EgressError, match="destination"):
        check_egress(
            workspace,
            ["Projects/ordinary.txt"],
            destination=destination,
        )

    assert _file_snapshot(workspace) == before


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
        result = check_egress(
            workspace,
            ["Projects/contact.txt"],
            destination="fictional review inbox",
            decision="use-redacted",
        )
        receipt_text = result.receipt.read_text(encoding="utf-8")
        copy_text = (workspace / result.redacted_copies[0]).read_text(
            encoding="utf-8"
        )
        results.append((result.exit_code, result.findings, copy_text, receipt_text))
    assert results[0] == results[1]


def test_ignore_file_never_weakens_egress_scan(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    (workspace / "System/ignore").write_text(
        "Projects/ignored.txt\n", encoding="utf-8"
    )
    (workspace / "Projects/ignored.txt").write_text(
        "Contact sample.person@example.invalid.\n", encoding="utf-8"
    )

    result = check_egress(workspace, ["Projects/ignored.txt"])

    assert [(item.source, item.kind) for item in result.findings] == [
        ("label", "pii/email")
    ]


def test_one_decision_covers_complete_list_and_only_flagged_files_get_copies(
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


def test_every_share_step_has_initial_ask_and_fresh_decision_check():
    procedures = Path(__file__).parents[3] / "starter/payload/System/procedures"
    share_gates = []
    for path in sorted(procedures.glob("*.md")):
        _data, body = records.parse_record(path.read_text(encoding="utf-8"))
        steps = {
            int(match.group(1)): match.group(2)
            for match in re.finditer(r"(?ms)^(\d+)\. (.*?)(?=^\d+\. |\Z)", body)
        }
        for number, step in steps.items():
            if not step.startswith("[share] "):
                continue
            gate = steps[number - 1]
            share_gates.append((path.name, number, gate))
            normalized = " ".join(gate.split())
            assert (
                "apparatus egress check WORKSPACE DRAFT-FILE "
                "--destination TARGET" in normalized
            )
            assert (
                "Do not pass `--decision` on this initial inspection" in normalized
            )
            assert "Show the user every finding" in normalized
            assert (
                "use the redacted copy, send the original, or stop" in normalized
            )
            assert "Rerun the same check with the same destination" in normalized
            assert "`--decision use-redacted`" in normalized
            assert "`--decision send-original`" in normalized
            assert "`--decision stop`" in normalized
            assert "records pre-share authorization" in normalized
            assert "After a credential refusal, ask again" in normalized
            assert "new explicit `use-redacted` choice" in normalized
    assert [(name, number) for name, number, _gate in share_gates] == [
        ("produce-deliverable.md", 7),
        ("produce-deliverable.md", 9),
        ("research-and-summarize.md", 7),
        ("review-against-checklist.md", 7),
        ("weekly-review.md", 7),
        ("welcome.md", 8),
    ]


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
    before = _file_snapshot(tmp_path)

    assert egress_command.run(args) == 2
    assert "egress:" in capsys.readouterr().out
    assert _file_snapshot(tmp_path) == before


def test_late_invalid_file_and_source_symlink_write_nothing(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    (workspace / "Projects/sensitive.txt").write_text(
        "Contact sample.person@example.invalid.\n", encoding="utf-8"
    )
    outside = tmp_path / "outside.txt"
    outside.write_text("Outside sentinel.\n", encoding="utf-8")
    link = workspace / "Projects/link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("this worker cannot create a file-link fixture")
    before = _file_snapshot(tmp_path)

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
    assert _file_snapshot(tmp_path) == before


def test_cli_parser_requires_workspace_and_file_and_uses_only_entry_point(capsys):
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    assert 'egress = "apparatus_core.commands.egress:register"' in text
    assert cli.main(["egress", "check"]) == 2
    assert "required" in capsys.readouterr().err
