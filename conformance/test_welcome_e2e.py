"""Subprocess-only proof of the day-1 welcome-to-deliverable story."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest
import yaml


FIXTURES = Path(__file__).parent / "fixtures" / "welcome-e2e"
HAS_GIT = shutil.which("git") is not None
APPARATUS = shutil.which("apparatus")
UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
RECEIPT_EVENTS = {
    "backup-export",
    "check",
    "egress",
    "init",
    "library-ingest",
    "profile-apply",
    "recall",
    "redaction",
    "restore",
    "snapshot",
}


def _run(
    *arguments: str | Path,
    env: dict[str, str],
    expected: int = 0,
) -> subprocess.CompletedProcess[str]:
    assert APPARATUS is not None, "the installed apparatus console script is required"
    result = subprocess.run(
        [APPARATUS, *(str(argument) for argument in arguments)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )
    assert result.returncode == expected, (
        f"apparatus {' '.join(str(item) for item in arguments)} returned "
        f"{result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return result


def _frontmatter(path: Path) -> tuple[dict[str, object], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines and lines[0] == "---"
    closing = lines.index("---", 1)
    data = yaml.safe_load("\n".join(lines[1:closing]))
    assert isinstance(data, dict)
    return data, "\n".join(lines[closing + 1 :])


def _write_record(path: Path, data: dict[str, object], body: str) -> None:
    rendered = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    path.write_text(f"---\n{rendered}---\n{body.rstrip()}\n", encoding="utf-8")


def _receipts(workspace: Path, event: str | None = None) -> list[tuple[Path, dict[str, object], str]]:
    found: list[tuple[Path, dict[str, object], str]] = []
    for path in sorted((workspace / "System" / "receipts").glob("*.md")):
        data, body = _frontmatter(path)
        if event is None or data.get("event") == event:
            found.append((path, data, body))
    return found


def _receipt_paths(workspace: Path, event: str) -> set[Path]:
    return {path for path, _data, _body in _receipts(workspace, event)}


def _new_receipt(
    workspace: Path, event: str, before: set[Path]
) -> tuple[Path, dict[str, object], str]:
    created = _receipt_paths(workspace, event) - before
    assert len(created) == 1
    path = created.pop()
    data, body = _frontmatter(path)
    return path, data, body


def _assert_receipts_are_bound_and_well_formed(workspace: Path) -> None:
    receipts = _receipts(workspace)
    assert receipts
    for path, data, _body in receipts:
        assert data["schema"] == "apparatus/receipt@v0"
        event = data["event"]
        timestamp = data["timestamp"]
        assert event in RECEIPT_EVENTS
        assert isinstance(timestamp, str) and UTC_TIMESTAMP.fullmatch(timestamp)
        assert isinstance(data["summary"], str) and data["summary"].strip()
        labels = data.get("labels")
        assert labels is None or (
            isinstance(labels, list)
            and all(isinstance(label, str) for label in labels)
        )
        filename_time = timestamp.replace("T", "-").replace(":", "").removesuffix("Z")
        assert re.fullmatch(
            rf"{re.escape(filename_time)}-{re.escape(event)}(?:-[2-9]|-[1-9]\d+)?\.md",
            path.name,
        )


@pytest.mark.parametrize(
    ("event", "labels"),
    [
        ("not-an-event", None),
        ("check", "pii/email"),
    ],
)
def test_receipt_schema_proof_rejects_parseable_invalid_common_fields(
    tmp_path, event, labels
):
    workspace = tmp_path / "workspace"
    receipts = workspace / "System" / "receipts"
    receipts.mkdir(parents=True)
    data = {
        "schema": "apparatus/receipt@v0",
        "event": event,
        "timestamp": "2026-08-10T20:00:00Z",
        "summary": "Parseable but intentionally invalid receipt fixture.",
    }
    if labels is not None:
        data["labels"] = labels
    receipt = receipts / f"2026-08-10-200000-{event}.md"
    receipt.write_text(
        "---\n"
        + yaml.safe_dump(data, sort_keys=False)
        + "---\nIntentional negative fixture.\n",
        encoding="utf-8",
    )

    with pytest.raises(AssertionError):
        _assert_receipts_are_bound_and_well_formed(workspace)


@pytest.mark.skipif(
    not HAS_GIT,
    reason="git is required for the welcome end-to-end snapshot story",
)
def test_welcome_to_deliverable_story_uses_only_files_and_subprocesses(tmp_path):
    workspace = tmp_path / "workspace"
    environment = {
        **os.environ,
        "APPARATUS_HOME": str(tmp_path / "apparatus-home"),
    }

    # Fresh workspace and fresh-workspace check.
    _run("init", workspace, env=environment)
    fresh_check = _run("check", workspace, env=environment)
    assert "check passed" in fresh_check.stdout

    # Configured interview answers apply into valid People and Goal records.
    shutil.copyfile(
        FIXTURES / "profile-configured.yaml",
        workspace / "System" / "profile.yaml",
    )
    apply_before = len(_receipts(workspace, "profile-apply"))
    _run("profile", "apply", workspace, env=environment)
    assert len(_receipts(workspace, "profile-apply")) == apply_before + 1
    people = {
        "Memory/People/riley-sample.md",
        "Memory/People/northstar-quality-council.md",
    }
    goal_relative = "Goals/prepare-orion-readiness-brief.md"
    assert all((workspace / relative).is_file() for relative in people)
    assert (workspace / goal_relative).is_file()
    apply_path, apply_data, apply_body = _receipts(workspace, "profile-apply")[-1]
    assert apply_data["event"] == "profile-apply"
    for relative in (*sorted(people), goal_relative):
        assert relative in apply_body
    applied_check = _run("check", workspace, env=environment)
    assert "check passed" in applied_check.stdout

    # Library ingest and grounded/abstaining recall each bind a valid receipt.
    library_source = workspace / "Library" / "reference-note.md"
    shutil.copyfile(FIXTURES / "library" / "reference-note.md", library_source)
    ingest_before = len(_receipts(workspace, "library-ingest"))
    ingest = _run("library", "ingest", workspace, env=environment)
    assert "extracted=1" in ingest.stdout
    assert len(_receipts(workspace, "library-ingest")) == ingest_before + 1

    grounded_before = _receipt_paths(workspace, "recall")
    grounded = json.loads(
        _run(
            "recall",
            workspace,
            "cobalt readiness marker",
            "--json",
            env=environment,
        ).stdout
    )
    assert grounded["status"] == "grounded"
    assert grounded["evidence"]
    citation = grounded["evidence"][0]
    assert set(citation) == {"source", "snippet", "score"}
    assert citation["source"] == "Library/reference-note.md"
    assert (workspace / citation["source"]).is_file()
    assert "cobalt" in citation["snippet"].casefold()
    _grounded_path, grounded_receipt, _grounded_body = _new_receipt(
        workspace, "recall", grounded_before
    )
    assert grounded_receipt["status"] == "grounded"
    assert grounded_receipt["question"] == "cobalt readiness marker"
    assert grounded_receipt["evidence_sources"] == ["Library/reference-note.md"]

    missed_before = _receipt_paths(workspace, "recall")
    missed = json.loads(
        _run(
            "recall",
            workspace,
            "zephyr quantum orchard",
            "--json",
            env=environment,
        ).stdout
    )
    assert missed["status"] == "abstained"
    assert missed["evidence"] == []
    _missed_path, missed_receipt, _missed_body = _new_receipt(
        workspace, "recall", missed_before
    )
    assert missed_receipt["status"] == "abstained"
    assert missed_receipt["evidence_sources"] == []

    # The assistant writes a cited draft, then the gate finds both People data
    # and the credential floor before any copy is published.
    project = workspace / "Projects" / "orion-readiness"
    project.mkdir()
    draft = project / "orion-readiness-brief.md"
    draft.write_text(
        "# Orion readiness brief\n\n"
        "The Orion readiness brief must include the cobalt readiness marker "
        "before the Thursday review with Riley Sample "
        "(`Library/reference-note.md`).\n\n"
        "Temporary password=sample-only for this clearly fake fixture.\n",
        encoding="utf-8",
    )
    offered = draft.with_name("orion-readiness-brief.redacted.md")
    inspected_egress_before = _receipt_paths(workspace, "egress")
    inspected_redaction_before = _receipt_paths(workspace, "redaction")
    inspection = _run(
        "egress",
        "check",
        workspace,
        draft,
        "--destination",
        "the readiness review team",
        env=environment,
        expected=1,
    )
    assert "people/person-name" in inspection.stdout
    assert "credential/password" in inspection.stdout
    assert "redacted-copy offer" in inspection.stdout
    assert not offered.exists()
    _inspection_path, inspected_egress, _inspection_body = _new_receipt(
        workspace, "egress", inspected_egress_before
    )
    _new_receipt(workspace, "redaction", inspected_redaction_before)
    assert inspected_egress["decision"] is None
    assert inspected_egress["outcome"] == "decision-required"
    assert inspected_egress["anything_left_workspace"] is False
    assert inspected_egress["finding_counts"]["people/person-name"] == 1
    assert inspected_egress["finding_counts"]["credential/password"] == 1

    decided_egress_before = _receipt_paths(workspace, "egress")
    decided_redaction_before = _receipt_paths(workspace, "redaction")
    decision = _run(
        "egress",
        "check",
        workspace,
        draft,
        "--destination",
        "the readiness review team",
        "--decision",
        "use-redacted",
        env=environment,
    )
    assert "egress decision recorded: use-redacted" in decision.stdout
    assert offered.is_file()
    redacted = offered.read_text(encoding="utf-8")
    assert "Riley Sample" not in redacted
    assert "sample-only" not in redacted
    assert "[redacted-person-name]" in redacted
    assert "password=[redacted-password]" in redacted
    _decision_path, decided_egress, _decision_body = _new_receipt(
        workspace, "egress", decided_egress_before
    )
    assert decided_egress["decision"] == "use-redacted"
    assert decided_egress["outcome"] == "use-redacted"
    assert decided_egress["pre_share_authorized"] is True
    assert decided_egress["anything_left_workspace"] is False
    assert decided_egress["redacted_copies"] == [
        "Projects/orion-readiness/orion-readiness-brief.redacted.md"
    ]
    redaction_path, redaction_data, _redaction_body = _new_receipt(
        workspace, "redaction", decided_redaction_before
    )
    assert redaction_data["counts"] == {"password": 1}
    assert redaction_data["copies_published"] is True
    assert "sample-only" not in redaction_path.read_text(encoding="utf-8")

    # Filing remains inside the workspace. The related goal names the filed
    # deliverable before the final snapshot and whole-workspace check.
    deliverable = workspace / "Deliverables" / "orion-readiness-brief.md"
    offered.replace(deliverable)
    goal = workspace / goal_relative
    goal_data, goal_body = _frontmatter(goal)
    goal_data["status"] = "done"
    goal_data["next-action"] = (
        "Review Deliverables/orion-readiness-brief.md with the readiness team."
    )
    _write_record(goal, goal_data, goal_body)
    assert _frontmatter(goal)[0]["status"] == "done"
    assert "Deliverables/orion-readiness-brief.md" in str(
        _frontmatter(goal)[0]["next-action"]
    )

    snapshot_before = _receipt_paths(workspace, "snapshot")
    snapshot = _run(
        "snapshot",
        workspace,
        "--label",
        "Welcome end-to-end",
        env=environment,
    )
    assert "Snapshot saved" in snapshot.stdout
    _snapshot_path, snapshot_data, _snapshot_body = _new_receipt(
        workspace, "snapshot", snapshot_before
    )
    assert snapshot_data["label"] == "Welcome end-to-end"
    assert snapshot_data["snapshot_id"] == "self"

    final_check = _run("check", workspace, env=environment)
    assert "check passed" in final_check.stdout
    assert deliverable.is_file()
    _assert_receipts_are_bound_and_well_formed(workspace)

    expected_events = {
        "init",
        "check",
        "profile-apply",
        "library-ingest",
        "recall",
        "egress",
        "redaction",
        "snapshot",
    }
    assert expected_events <= {data["event"] for _path, data, _body in _receipts(workspace)}
