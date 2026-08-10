from __future__ import annotations

import argparse
import os
from pathlib import Path

from apparatus_core import records
from apparatus_core.check import check_workspace
from apparatus_core.commands import init, profile


def _init_workspace(path: Path) -> Path:
    assert init.run(
        argparse.Namespace(
            workspace=str(path), privacy_mode=None, work_types=None, payload=None
        ),
        available=lambda: False,
    ) == 0
    return path


def _write_profile(workspace: Path, **answers: object) -> None:
    data = records.yaml.safe_load(
        (workspace / "System/profile.yaml").read_text(encoding="utf-8")
    )
    data.update({"status": "configured", **answers})
    (workspace / "System/profile.yaml").write_text(
        records.yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )


def _args(workspace: Path) -> argparse.Namespace:
    return argparse.Namespace(profile_action="apply", workspace=str(workspace), payload=None)


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
