from __future__ import annotations

import argparse
import importlib.metadata
import os
from io import StringIO
from pathlib import Path

import pytest

from apparatus_core import records
from apparatus_core.check import check_workspace
from apparatus_core.commands import check, init, memory, profile
from apparatus_core.receipts import write_receipt
from apparatus_core.render import render_workspace


def _init_workspace(path: Path) -> Path:
    assert init.run(
        argparse.Namespace(
            workspace=str(path), privacy_mode=None, work_types=None, payload=None
        ),
        available=lambda: False,
    ) == 0
    # Keep these profile tests independent of checkout line-ending conversion.
    render_workspace(path)
    return path


def _write_profile(workspace: Path, **answers: object) -> None:
    data = records.yaml.safe_load(
        (workspace / "System/profile.yaml").read_text(encoding="utf-8")
    )
    data.update({"status": "configured", **answers})
    (workspace / "System/profile.yaml").write_text(
        records.yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )


def _args(workspace: Path, *, candidate_stdin: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        profile_action="apply",
        workspace=str(workspace),
        payload=None,
        candidate_stdin=candidate_stdin,
    )


def _tree_without_receipts(root: Path) -> tuple[tuple[str, str, bytes | None], ...]:
    result: list[tuple[str, str, bytes | None]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if relative.parts[:2] == ("System", "receipts"):
            continue
        if path.is_symlink():
            result.append((relative.as_posix(), "symlink", os.readlink(path).encode()))
        elif path.is_file():
            result.append((relative.as_posix(), "file", path.read_bytes()))
        else:
            result.append((relative.as_posix(), "directory", None))
    return tuple(result)


def test_fresh_apply_seeds_records_and_writes_a_valid_receipt(tmp_path):
    workspace = _init_workspace(tmp_path / "workspace")
    _write_profile(
        workspace,
        key_people=[
            {
                "name": "Riley Sample",
                "role": "Reviewer; riley.sample@example.invalid",
                "organization": "Sample Group",
            }
        ],
        current_efforts=[
            {
                "title": "Finish sample report",
                "done_when": "The finished report is in Deliverables/.",
                "next_action": "Draft the outline.",
            }
        ],
        source_locations=["Library/"],
    )

    assert profile.run(_args(workspace)) == 0
    person = workspace / "Memory/People/riley-sample.md"
    goal = workspace / "Goals/finish-sample-report.md"
    assert person.is_file()
    assert goal.is_file()
    person_data, _ = records.parse_record(person.read_text(encoding="utf-8"))
    goal_data, _ = records.parse_record(goal.read_text(encoding="utf-8"))
    assert person_data["role"] == "Reviewer; riley.sample@example.invalid"
    assert person_data["organization"] == "Sample Group"
    assert person_data["labels"] == ["pii/email"]
    assert goal_data == {
        "schema": "apparatus/goal@v0",
        "title": "Finish sample report",
        "owner": "me",
        "status": "active",
        "done-when": "The finished report is in Deliverables/.",
        "next-action": "Draft the outline.",
    }
    receipts = list((workspace / "System/receipts").glob("*-profile-apply.md"))
    assert len(receipts) == 1
    receipt, _ = records.parse_record(receipts[0].read_text(encoding="utf-8"))
    assert receipt["event"] == "profile-apply"
    assert check_workspace(workspace).ok


def test_reapply_is_byte_identical_outside_receipts(tmp_path):
    workspace = _init_workspace(tmp_path / "workspace")
    _write_profile(
        workspace,
        key_people=[{"name": "Riley Sample"}],
        current_efforts=[{"title": "Finish sample report"}],
        source_locations=[],
    )
    assert profile.run(_args(workspace)) == 0
    before = _tree_without_receipts(workspace)
    assert profile.run(_args(workspace)) == 0
    assert _tree_without_receipts(workspace) == before
    assert len(list((workspace / "System/receipts").glob("*-profile-apply*.md"))) == 2


def test_reinterview_seeds_only_new_records_and_preserves_existing_edits(tmp_path):
    workspace = _init_workspace(tmp_path / "workspace")
    _write_profile(
        workspace,
        key_people=[{"name": "Riley Sample"}],
        current_efforts=[{"title": "Finish sample report"}],
        source_locations=[],
    )
    assert profile.run(_args(workspace)) == 0
    edited = workspace / "Goals/finish-sample-report.md"
    edited.write_text("user-edited record\n", encoding="utf-8")
    _write_profile(
        workspace,
        key_people=[{"name": "Riley Sample"}, {"name": "Alex Sample", "role": "Partner"}],
        current_efforts=[{"title": "Finish sample report"}, {"title": "Plan sample review"}],
        source_locations=["Shared drive"],
        review_day="monday",
    )
    assert profile.run(_args(workspace)) == 0
    assert edited.read_text(encoding="utf-8") == "user-edited record\n"
    assert (workspace / "Memory/People/alex-sample.md").is_file()
    assert (workspace / "Goals/plan-sample-review.md").is_file()


def test_invalid_interview_answers_fail_before_writing_records(tmp_path, capsys):
    workspace = _init_workspace(tmp_path / "workspace")
    _write_profile(
        workspace,
        key_people=[{"role": "Reviewer"}],
        current_efforts=[{"done_when": "Something happens."}],
        source_locations=[1],
    )
    before = _tree_without_receipts(workspace)
    findings = check_workspace(workspace).findings
    assert any("key_people[0].name" in finding.hint for finding in findings)
    assert profile.run(_args(workspace)) == 2
    output = capsys.readouterr().out
    assert "key_people[0].name" in output
    assert "current_efforts[0].title" in output
    assert "source_locations" in output
    assert _tree_without_receipts(workspace) == before


def test_stdin_candidate_is_redacted_before_profile_or_goal_becomes_durable(
    tmp_path, capsys
):
    workspace = _init_workspace(tmp_path / "workspace")
    current = records.yaml.safe_load(
        (workspace / "System/profile.yaml").read_text(encoding="utf-8")
    )
    current.update(
        {
            "status": "configured",
            "current_efforts": [
                {
                    "title": "Review api_key=sample-candidate-secret",
                    "done_when": "password=sample-done-secret is removed",
                    "next_action": "Replace token=sample-next-secret",
                }
            ],
            "source_locations": ["password=sample-source-secret"],
        }
    )
    candidate = records.yaml.safe_dump(current, sort_keys=False)

    assert profile.run(
        _args(workspace, candidate_stdin=True), input_stream=StringIO(candidate)
    ) == 0
    output = capsys.readouterr().out
    durable = "\n".join(
        path.read_text(encoding="utf-8")
        for path in workspace.rglob("*")
        if path.is_file() and ".git" not in path.parts
    )
    for secret in (
        "sample-candidate-secret",
        "sample-done-secret",
        "sample-next-secret",
        "sample-source-secret",
    ):
        assert secret not in output
        assert secret not in durable
    assert "[redacted-api-key]" in durable
    assert "[redacted-password]" in durable
    redaction_receipts = list(
        (workspace / "System/receipts").glob("*-redaction*.md")
    )
    assert len(redaction_receipts) == 1
    receipt_data, receipt_body = records.parse_record(
        redaction_receipts[0].read_text(encoding="utf-8")
    )
    assert receipt_data["counts"] == {"api-key": 2, "password": 2}
    assert "location" not in receipt_body.casefold()
    assert check_workspace(workspace).ok


def test_plain_apply_transactionally_sanitizes_a_legacy_configured_profile(tmp_path):
    workspace = _init_workspace(tmp_path / "workspace")
    _write_profile(
        workspace,
        source_locations=["password=sample-legacy-secret"],
        key_people=[],
        current_efforts=[],
    )
    assert "sample-legacy-secret" in (
        workspace / "System/profile.yaml"
    ).read_text(encoding="utf-8")

    assert profile.run(_args(workspace)) == 0
    durable = (workspace / "System/profile.yaml").read_text(encoding="utf-8")
    assert "sample-legacy-secret" not in durable
    assert "[redacted-password]" in durable
    assert len(list((workspace / "System/receipts").glob("*-redaction*.md"))) == 1


def test_receipt_writer_failure_leaves_profile_overlay_and_seeds_unchanged(
    tmp_path,
):
    workspace = _init_workspace(tmp_path / "workspace")
    _write_profile(
        workspace,
        key_people=[{"name": "Riley Sample"}],
        current_efforts=[{"title": "Finish sample report"}],
        source_locations=[],
    )
    before = _tree_without_receipts(workspace)

    def fail_writer(*_args, **_kwargs):
        raise OSError("injected receipt failure")

    assert profile.run(_args(workspace), write=fail_writer) == 2
    assert _tree_without_receipts(workspace) == before
    assert not list((workspace / "System/receipts").glob("*-profile-apply*.md"))


def test_partial_receipt_failure_removes_the_owned_redaction_receipt(tmp_path):
    workspace = _init_workspace(tmp_path / "workspace")
    current = records.yaml.safe_load(
        (workspace / "System/profile.yaml").read_text(encoding="utf-8")
    )
    current.update(
        {
            "status": "configured",
            "source_locations": ["password=sample-partial-secret"],
        }
    )
    candidate = records.yaml.safe_dump(current, sort_keys=False)
    before = _tree_without_receipts(workspace)
    calls = 0

    def partial_writer(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected second receipt failure")
        return write_receipt(*args, **kwargs)

    assert profile.run(
        _args(workspace, candidate_stdin=True),
        write=partial_writer,
        input_stream=StringIO(candidate),
    ) == 2
    assert calls == 2
    assert _tree_without_receipts(workspace) == before
    assert not list((workspace / "System/receipts").glob("*-redaction*.md"))
    assert "sample-partial-secret" not in (
        workspace / "System/profile.yaml"
    ).read_text(encoding="utf-8")


def test_mid_apply_failure_restores_profile_overlay_seed_and_receipts(
    tmp_path, monkeypatch
):
    workspace = _init_workspace(tmp_path / "workspace")
    welcome = workspace / "System/procedures/welcome.md"
    welcome.write_text("user-managed overlay edit\n", encoding="utf-8")
    candidate = records.yaml.safe_load(
        (workspace / "System/profile.yaml").read_text(encoding="utf-8")
    )
    candidate.update(
        {
            "status": "configured",
            "key_people": [{"name": "Riley Sample"}],
            "current_efforts": [{"title": "Finish sample report"}],
            "source_locations": [],
        }
    )
    candidate_text = records.yaml.safe_dump(candidate, sort_keys=False)
    before = _tree_without_receipts(workspace)
    original_create = memory._WorkspaceAnchor.create_file

    def fail_goal(self, relative, content, mode=0o600):
        if Path(relative).parts[:1] == ("Goals",):
            raise OSError("injected goal publication failure")
        return original_create(self, relative, content, mode)

    monkeypatch.setattr(memory._WorkspaceAnchor, "create_file", fail_goal)
    assert profile.run(
        _args(workspace, candidate_stdin=True),
        input_stream=StringIO(candidate_text),
    ) == 2
    assert _tree_without_receipts(workspace) == before
    assert not list((workspace / "System/receipts").glob("*-profile-apply*.md"))


def test_missing_done_when_preserves_supplied_next_action(tmp_path):
    workspace = _init_workspace(tmp_path / "workspace")
    _write_profile(
        workspace,
        key_people=[],
        current_efforts=[
            {"title": "Clarify sample outcome", "next_action": "Ask the owner Friday."}
        ],
        source_locations=[],
    )
    assert profile.run(_args(workspace)) == 0
    goal, _ = records.parse_record(
        (workspace / "Goals/clarify-sample-outcome.md").read_text(encoding="utf-8")
    )
    assert goal["status"] == "waiting"
    assert goal["next-action"] == "Ask the owner Friday."


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (["Library/"], None),
        ("Library/", "source_locations must be a list of strings"),
        (["   "], "source_locations[0] must be a non-empty string"),
        ([""], "source_locations[0] must be a non-empty string"),
    ],
)
def test_source_locations_validation_is_optional_typed_and_non_empty(value, expected):
    data = {
        "schema": "apparatus/profile@v0",
        "status": "configured",
        "privacy_mode": "standard",
        "work_types": [],
        "review_day": None,
    }
    if value is not None:
        data["source_locations"] = value
    problems = records.validate("profile", data, filename="profile.yaml")
    if expected is None:
        assert not problems
    else:
        assert expected in problems


def test_profile_diagnostics_never_echo_rejected_raw_values(tmp_path, capsys):
    workspace = _init_workspace(tmp_path / "workspace")
    raw_value = "password=sample-diagnostic-secret"
    _write_profile(workspace, privacy_mode=raw_value)

    assert check.run(
        argparse.Namespace(workspace=str(workspace), no_receipt=True)
    ) == 1
    assert raw_value not in capsys.readouterr().out
    assert profile.run(_args(workspace)) == 2
    assert raw_value not in capsys.readouterr().out


def test_invalid_stdin_candidate_never_becomes_durable_or_appears_in_output(
    tmp_path, capsys
):
    workspace = _init_workspace(tmp_path / "workspace")
    raw_value = "password=sample-rejected-candidate"
    candidate = {
        "schema": "apparatus/profile@v0",
        "status": "configured",
        "privacy_mode": raw_value,
        "work_types": [],
        "review_day": None,
    }
    before = _tree_without_receipts(workspace)
    assert profile.run(
        _args(workspace, candidate_stdin=True),
        input_stream=StringIO(records.yaml.safe_dump(candidate)),
    ) == 2
    assert raw_value not in capsys.readouterr().out
    assert _tree_without_receipts(workspace) == before
    assert raw_value not in "\n".join(
        path.read_text(encoding="utf-8")
        for path in workspace.rglob("*")
        if path.is_file() and ".git" not in path.parts
    )


def test_installed_profile_entry_point_exposes_stdin_without_value_arguments():
    entry = next(
        item
        for item in importlib.metadata.distribution("apparatus-core").entry_points
        if item.group == "apparatus.commands" and item.name == "profile"
    )
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="verb")
    entry.load()(subparsers)
    parsed = parser.parse_args(["profile", "apply", "--stdin"])
    assert parsed.workspace == "."
    assert parsed.candidate_stdin is True
    assert not hasattr(parsed, "candidate")
