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
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    assert APPARATUS is not None, "the installed apparatus console script is required"
    result = subprocess.run(
        [APPARATUS, *(str(argument) for argument in arguments)],
        capture_output=True,
        input=input_text,
        text=True,
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
    skill_names = {"apparatus-welcome", "apparatus-produce-deliverable",
                   "apparatus-research-and-summarize", "apparatus-review-against-checklist",
                   "apparatus-weekly-review", "apparatus-economizer", "apparatus-humanizer"}
    skill_root = workspace / ".agents/skills"
    assert {path.name for path in skill_root.iterdir()} == skill_names
    for name in skill_names:
        skill = skill_root / name / "SKILL.md"
        metadata, body = _frontmatter(skill)
        assert metadata["name"] == name
        assert metadata["description"] and body.strip()
        assert set(metadata) == {"name", "description"}
        assert not skill.is_symlink()
    assert not (workspace / "System/procedures").exists()
    fresh_check = _run("check", workspace, env=environment)
    assert "check passed" in fresh_check.stdout

    profile_before_work = (workspace / "System/profile.yaml").read_bytes()
    assert yaml.safe_load(profile_before_work)["status"] == "unconfigured"
    task_id = json.loads(_run("task", "start", workspace, env=environment).stdout)["task_id"]
    def run(*args, **kwargs):
        return _run("--task", task_id, *args, **kwargs)

    # Library ingest and grounded/abstaining recall return evidence without activity logs.
    library_source = workspace / "Library" / "reference-note.md"
    shutil.copyfile(FIXTURES / "library" / "reference-note.md", library_source)
    for generated in ("node_modules", ".venv", "__pycache__", ".pytest_cache"):
        excluded = workspace / "Library" / generated / "generated.txt"
        excluded.parent.mkdir()
        excluded.write_text("Generated cache content must not enter recall.\n", encoding="utf-8")
    ingest_before = len(_receipts(workspace, "library-ingest"))
    ingest = run("library", "ingest", workspace, env=environment)
    assert "extracted=1" in ingest.stdout
    assert len(_receipts(workspace, "library-ingest")) == ingest_before

    grounded_before = _receipt_paths(workspace, "recall")
    grounded = json.loads(
        run(
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
    assert _receipt_paths(workspace, "recall") == grounded_before

    missed_before = _receipt_paths(workspace, "recall")
    missed = json.loads(
        run(
            "recall",
            workspace,
            "zephyr quantum orchard",
            "--json",
            env=environment,
        ).stdout
    )
    assert missed["status"] == "abstained"
    assert missed["evidence"] == []
    assert _receipt_paths(workspace, "recall") == missed_before

    # The assistant saves an ordinary cited draft containing useful People
    # context. There is no sharing-gate inspection or decision to request.
    project = workspace / "orion-readiness"
    project.mkdir()
    draft = project / "orion-readiness-brief.md"
    draft.write_text(
        "# Orion readiness brief\n\n"
        "The Orion readiness brief must include the cobalt readiness marker "
        "before the Thursday review with Riley Sample "
        "(`Library/reference-note.md`).\n",
        encoding="utf-8",
    )
    draft_text = draft.read_text(encoding="utf-8")
    assert "Riley Sample" in draft_text
    assert "Library/reference-note.md" in draft_text
    assert not _receipts(workspace, "egress")

    assert (workspace / "System/profile.yaml").read_bytes() == profile_before_work
    assert not _receipts(workspace, "profile-apply")
    assert not list((workspace / "Goals").glob("*.md"))
    assert not list((workspace / "Memory/People").glob("*.md"))

    # Completion preserves the file in its project; managed snapshots do not
    # claim recovery of this project original.
    deliverable = draft
    run("project", "bind", project, "--workspace", workspace, env=environment)
    assert (project / ".apparatus/workspace.yaml").is_file()
    # Only after the requested deliverable is saved, an explicit legacy profile
    # import passes through stdin so the retained credential
    # floor runs before any profile or Memory record reaches durable storage.
    candidate = yaml.safe_load(
        (FIXTURES / "profile-configured.yaml").read_text(encoding="utf-8")
    )
    candidate["key_people"][0]["role"] = (
        "Review lead; temporary password=profile-fixture-only for this fake fixture."
    )
    apply_before = len(_receipts(workspace, "profile-apply"))
    redaction_before = _receipt_paths(workspace, "redaction")
    applied = run(
        "profile", "apply", workspace, "--stdin",
        input_text=yaml.safe_dump(candidate, sort_keys=False),
        env=environment,
    )
    assert "profile-fixture-only" not in applied.stdout + applied.stderr
    assert len(_receipts(workspace, "profile-apply")) == apply_before + 1
    redaction_path, redaction_data, _redaction_body = _new_receipt(
        workspace, "redaction", redaction_before
    )
    assert redaction_data["counts"] == {"password": 1}
    assert "profile-fixture-only" not in redaction_path.read_text(encoding="utf-8")
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
    applied_check = run("check", workspace, env=environment)
    assert "check passed" in applied_check.stdout

    goal = workspace / goal_relative
    goal_data, goal_body = _frontmatter(goal)
    goal_data["status"] = "done"
    goal_data["next-action"] = (
        "Review orion-readiness/orion-readiness-brief.md with the readiness team."
    )
    _write_record(goal, goal_data, goal_body)
    assert _frontmatter(goal)[0]["status"] == "done"
    assert "orion-readiness/orion-readiness-brief.md" in str(
        _frontmatter(goal)[0]["next-action"]
    )

    snapshot_before = _receipt_paths(workspace, "snapshot")
    snapshot = run(
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
    actual_head = subprocess.run(
        ["git", "--git-dir", str(workspace / "System/recovery/store"),
         "rev-parse", "refs/heads/managed"],
        capture_output=True, text=True, check=True, env=environment,
    ).stdout.strip()
    assert snapshot_data["snapshot_id"] == actual_head
    assert re.fullmatch(r"[0-9a-f]{40}", actual_head)
    assert not (workspace / ".git").exists()

    final_check = run("check", workspace, env=environment)
    assert "check passed" in final_check.stdout
    assert deliverable.is_file()
    assert deliverable.read_text(encoding="utf-8") == draft_text
    durable_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in workspace.rglob("*")
        if path.is_file() and ".git" not in path.parts and path.suffix in {".md", ".yaml"}
    )
    assert "profile-fixture-only" not in durable_text
    assert "password=[redacted-password]" in durable_text
    # Imported source files remain intact; the managed-write redaction floor
    # does not promise to sanitize original files or historical content.
    assert library_source.read_bytes() == (
        FIXTURES / "library" / "reference-note.md"
    ).read_bytes()
    assert "sample-only" not in draft_text
    assert "Riley Sample" in (workspace / "Memory/People/riley-sample.md").read_text(
        encoding="utf-8"
    )
    assert not _receipts(workspace, "egress")
    _assert_receipts_are_bound_and_well_formed(workspace)

    expected_events = {
        "init",
        "profile-apply",
        "redaction",
        "snapshot",
    }
    assert expected_events <= {data["event"] for _path, data, _body in _receipts(workspace)}

    assert not {"check", "library-ingest", "recall"}.intersection(
        data["event"] for _path, data, _body in _receipts(workspace))


def test_no_save_task_finishes_cited_work_without_setup_or_automatic_retention(tmp_path):
    workspace = tmp_path / "area"
    environment = {**os.environ, "APPARATUS_HOME": str(tmp_path / "app-home")}
    _run("init", workspace, env=environment)
    source = workspace / "Library/reference-note.md"
    shutil.copyfile(FIXTURES / "library/reference-note.md", source)
    _run("library", "ingest", workspace, env=environment)
    task = json.loads(_run("task", "start", workspace, "--no-memory", env=environment).stdout)
    task_id = task["task_id"]
    assert task["memory"] == "no-save"
    project = workspace / "project"
    project.mkdir()
    _run("--task", task_id, "project", "bind", project, "--workspace", workspace, env=environment)
    def managed_files():
        return {str(p.relative_to(workspace)): p.read_bytes()
                for folder in ("System", "Memory", "Goals", "Library")
                for p in (workspace / folder).rglob("*") if p.is_file()}
    before = managed_files()
    result = json.loads(_run("--task", task_id, "recall", workspace,
                             "cobalt readiness marker", "--json", env=environment).stdout)
    assert result["status"] == "grounded"
    assert result["evidence"][0]["source"] == "Library/reference-note.md"
    output = project / "readiness-summary.md"
    output.write_text("The brief needs a cobalt readiness marker before the Thursday review "
                      "(Library/reference-note.md).\n", encoding="utf-8")
    assert "cobalt readiness marker" in output.read_text(encoding="utf-8")
    assert managed_files() == before
    candidate = yaml.safe_load((workspace / "System/profile.yaml").read_bytes())
    assert candidate["status"] == "unconfigured"
    candidate["spend"] = "frugal"
    rejected = _run("--task", task_id, "profile", "apply", workspace, "--stdin",
                    input_text=yaml.safe_dump(candidate), expected=1, env=environment)
    assert "does not save answers" in rejected.stdout
    assert managed_files() == before
    assert output.is_file()
    assert not _receipts(workspace, "profile-apply")
