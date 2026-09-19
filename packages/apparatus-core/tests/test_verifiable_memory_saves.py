from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from apparatus_core import cli, project_binding
from apparatus_core.commands import memory
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.labeler import render_record, split_record_exact
from apparatus_core.memory import recall
from apparatus_core.receipts import write_receipt
from apparatus_core.retention import start_task
from apparatus_core.workspace_layout import new_layout_bytes


def area(path: Path) -> Path:
    for folder in (
        "System/receipts",
        "Memory/People",
        "Memory/Facts",
        "Memory/Decisions",
        "Decisions",
        "Library",
    ):
        (path / folder).mkdir(parents=True, exist_ok=True)
    (path / "System/profile.yaml").write_text(
        "schema: apparatus/profile@v0\n"
        "status: configured\n"
        "privacy_mode: standard\n"
        "work_types: []\n"
        "review_day: null\n",
        encoding="utf-8",
    )
    return path


def add_args(root: Path, action: str, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "workspace": str(root),
        "memory_action": action,
        "body": "A durable synthetic statement with its reason.",
        "from_file": None,
    }
    if action == "add-person":
        values.update(name="Synthetic Person", role="Review lead")
    else:
        values["title"] = "Synthetic choice"
    if action == "add-decision":
        values["date"] = "2026-09-18"
    values.update(overrides)
    return argparse.Namespace(**values)


@pytest.mark.parametrize(
    ("action", "folder", "leaf"),
    [
        ("add-fact", "Memory/Facts", "synthetic-choice.md"),
        ("add-person", "Memory/People", "synthetic-person.md"),
        ("add-decision", "Memory/Decisions", "synthetic-choice.md"),
    ],
)
def test_success_reports_the_exact_safe_record_path(
    tmp_path, capsys, action, folder, leaf
):
    root = area(tmp_path / "area")
    assert memory.run(add_args(root, action)) == 0
    relative = f"{folder}/{leaf}"
    assert capsys.readouterr().out.splitlines()[:2] == [
        "Memory record saved.",
        f"Record: {relative}",
    ]
    assert (root / relative).is_file()


def test_decision_add_uses_schema_collision_redaction_recall_and_lifecycle(
    tmp_path, capsys
):
    root = area(tmp_path / "area")
    legacy = root / "Decisions/synthetic-choice.md"
    legacy_content = render_record(
        {
            "schema": "apparatus/decision@v0",
            "title": "Legacy choice",
            "date": "2026-09-17",
        },
        "Use the amber legacy option.",
    )
    legacy.write_text(legacy_content, encoding="utf-8")
    first = add_args(
        root,
        "add-decision",
        body="Use cobalt because password=synthetic-secret was retired.",
    )
    assert memory.run(first) == 0
    output = capsys.readouterr().out
    assert "Record: Memory/Decisions/synthetic-choice.md" in output
    assert "synthetic-secret" not in output
    saved = root / "Memory/Decisions/synthetic-choice.md"
    data, body = split_record_exact(saved.read_text(encoding="utf-8"))
    assert data == {
        "schema": "apparatus/decision@v0",
        "title": "Synthetic choice",
        "date": "2026-09-18",
    }
    assert body == "Use cobalt because password=[redacted-password] was retired."
    assert legacy.read_text(encoding="utf-8") == legacy_content
    assert len(list((root / "System/receipts").glob("*-redaction.md"))) == 1
    with WorkspaceAnchor(root) as anchor:
        result = recall(anchor, "cobalt")
    assert [item["source"] for item in result["results"]] == [
        "Memory/Decisions/synthetic-choice.md"
    ]

    assert memory.run(add_args(root, "add-decision")) == 0
    assert "Record: Memory/Decisions/synthetic-choice-2.md" in capsys.readouterr().out
    assert memory.run(
        argparse.Namespace(
            workspace=str(root),
            memory_action="outdated",
            record="Memory/Decisions/synthetic-choice.md",
        )
    ) == 0
    with WorkspaceAnchor(root) as anchor:
        assert recall(anchor, "cobalt")["results"] == []


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"title": " \t"}, "--title must not be empty"),
        ({"date": "2026-02-29"}, "--date must be a valid YYYY-MM-DD date"),
        ({"date": "2026-2-03"}, "--date must be a valid YYYY-MM-DD date"),
        ({"body": "\r\n\t"}, "Decision body must not be empty"),
        ({"body": None, "from_file": None}, "provide exactly one"),
        ({"body": "x", "from_file": "unused"}, "provide exactly one"),
    ],
)
def test_invalid_decision_input_creates_nothing_and_reports_no_locator(
    tmp_path, capsys, overrides, message
):
    root = area(tmp_path / "area")
    assert memory.run(add_args(root, "add-decision", **overrides)) == 2
    output = capsys.readouterr().out
    assert message in output
    assert "Record:" not in output
    assert list((root / "Memory/Decisions").iterdir()) == []


def test_missing_decision_directory_is_actionable_and_never_repaired(tmp_path, capsys):
    root = area(tmp_path / "area")
    (root / "Memory/Decisions").rmdir()
    legacy = root / "Decisions/keep-me.md"
    legacy.write_text("legacy sentinel", encoding="utf-8")
    assert memory.run(add_args(root, "add-decision")) == 2
    output = capsys.readouterr().out
    assert "Memory/Decisions is missing or unsafe" in output
    assert "Record:" not in output
    assert not (root / "Memory/Decisions").exists()
    assert legacy.read_text(encoding="utf-8") == "legacy sentinel"


def test_no_save_refuses_decision_before_reading_input(tmp_path, capsys):
    root = area(tmp_path / "area")
    task = start_task(root, save_memory=False)
    before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
    args = add_args(
        root,
        "add-decision",
        body=None,
        from_file=str(tmp_path / "private-input-that-must-not-be-read.md"),
    )
    assert memory.run(args, task_id=task.task_id) == 1
    assert "Record:" not in capsys.readouterr().out
    assert sorted(path.relative_to(root).as_posix() for path in root.rglob("*")) == before


@pytest.mark.parametrize("action", ["add-fact", "add-person", "add-decision"])
@pytest.mark.parametrize("boundary", ["leaf", "parent"])
def test_from_file_rejects_symlink_or_reparse_boundaries_without_saving(
    tmp_path, capsys, action, boundary
):
    root = area(tmp_path / "area")
    outside = tmp_path / "outside"
    outside.mkdir()
    source = outside / "body.txt"
    source.write_text("outside body must not be retained", encoding="utf-8")
    if boundary == "leaf":
        linked = tmp_path / "linked-body.txt"
        try:
            linked.symlink_to(source)
        except OSError as error:
            pytest.fail(f"platform safety coverage requires a file reparse endpoint: {error}")
        candidate = linked
    else:
        linked = tmp_path / "linked-parent"
        try:
            linked.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            pytest.fail(f"platform safety coverage requires a directory reparse endpoint: {error}")
        candidate = linked / source.name

    args = add_args(root, action, body=None, from_file=str(candidate))
    assert memory.run(args) == 2
    output = capsys.readouterr().out
    assert "Record:" not in output
    assert "outside body" not in output
    assert list((root / "Memory/Facts").iterdir()) == []
    assert list((root / "Memory/People").iterdir()) == []
    assert list((root / "Memory/Decisions").iterdir()) == []
    assert list((root / "System/receipts").iterdir()) == []


def test_failed_required_receipt_rolls_back_only_the_new_decision(tmp_path, capsys):
    root = area(tmp_path / "area")
    competing = root / "Memory/Decisions/competing.md"
    competing.write_bytes(b"concurrent sentinel")

    def fail(*_args, **_kwargs):
        raise OSError("synthetic-secret receipt failure")

    args = add_args(
        root,
        "add-decision",
        body="Use cobalt because password=synthetic-secret must rotate.",
    )
    assert memory.run(args, write=fail) == 2
    output = capsys.readouterr().out
    assert "Record:" not in output
    assert "synthetic-secret" not in output
    assert competing.read_bytes() == b"concurrent sentinel"
    assert sorted(path.name for path in (root / "Memory/Decisions").iterdir()) == [
        "competing.md"
    ]
    assert list((root / "System/receipts").iterdir()) == []


def test_decision_collision_race_preserves_competing_file(tmp_path, monkeypatch, capsys):
    root = area(tmp_path / "area")
    original = memory._WorkspaceAnchor.create_file
    raced = False

    def race(anchor, relative, content, mode=0o600):
        nonlocal raced
        if not raced and relative == Path("Memory/Decisions/synthetic-choice.md"):
            raced = True
            competing = original(anchor, relative, b"competing bytes", mode)
            competing.close()
            raise FileExistsError("simulated exclusive-open race")
        return original(anchor, relative, content, mode)

    monkeypatch.setattr(memory._WorkspaceAnchor, "create_file", race)
    assert memory.run(add_args(root, "add-decision")) == 0
    assert "Record: Memory/Decisions/synthetic-choice-2.md" in capsys.readouterr().out
    assert (root / "Memory/Decisions/synthetic-choice.md").read_bytes() == b"competing bytes"


@pytest.mark.parametrize(
    ("action", "relative"),
    [
        ("add-fact", Path("Memory/Facts/synthetic-choice.md")),
        ("add-person", Path("Memory/People/synthetic-person.md")),
        ("add-decision", Path("Memory/Decisions/synthetic-choice.md")),
    ],
)
def test_final_publication_check_rejects_a_substituted_record(
    tmp_path, monkeypatch, capsys, action, relative
):
    root = area(tmp_path / "area")
    original = memory._WorkspaceAnchor.create_file

    def substitute(anchor, candidate, content, mode=0o600):
        owned = original(anchor, candidate, content, mode)
        if candidate == relative:
            anchor.unlink_owned(owned)
            competing = original(anchor, candidate, b"competing bytes", mode)
            competing.close()
        return owned

    monkeypatch.setattr(memory._WorkspaceAnchor, "create_file", substitute)
    assert memory.run(add_args(root, action)) == 2
    assert "Record:" not in capsys.readouterr().out
    assert (root / relative).read_bytes() == b"competing bytes"
    assert list((root / "System/receipts").iterdir()) == []


def test_final_check_rolls_back_owned_redaction_receipt_after_substitution(
    tmp_path, monkeypatch, capsys
):
    root = area(tmp_path / "area")
    relative = Path("Memory/Decisions/synthetic-choice.md")
    original = memory._WorkspaceAnchor.create_file
    publication = {}

    def remember(anchor, candidate, content, mode=0o600):
        owned = original(anchor, candidate, content, mode)
        if candidate == relative:
            publication.update(anchor=anchor, owned=owned, mode=mode)
        return owned

    def substitute_then_write(workspace, event, fields, **kwargs):
        anchor = publication["anchor"]
        anchor.unlink_owned(publication["owned"])
        competing = original(anchor, relative, b"competing redaction bytes", publication["mode"])
        competing.close()
        return write_receipt(workspace, event, fields, **kwargs)

    monkeypatch.setattr(memory._WorkspaceAnchor, "create_file", remember)
    args = add_args(
        root,
        "add-decision",
        body="Use cobalt because password=synthetic-secret must rotate.",
    )
    assert memory.run(args, write=substitute_then_write) == 2
    output = capsys.readouterr().out
    assert "Record:" not in output
    assert "synthetic-secret" not in output
    assert (root / relative).read_bytes() == b"competing redaction bytes"
    assert list((root / "System/receipts").iterdir()) == []


def test_bound_project_reports_a_work_area_relative_decision_path(tmp_path, capsys):
    root = area(tmp_path / "area")
    (root / "System/workspace.yaml").write_bytes(new_layout_bytes())
    project = root / "project"
    project.mkdir()
    project_binding.bind_project(project, root)

    assert cli.main(
        [
            "memory",
            "add-decision",
            str(project),
            "--title",
            "Bound choice",
            "--date",
            "2026-09-18",
            "--body",
            "Use the selected work area because the project is explicitly bound.",
        ]
    ) == 0
    output = capsys.readouterr().out
    assert output.splitlines()[-2:] == [
        "Memory record saved.",
        "Record: Memory/Decisions/bound-choice.md",
    ]
    assert (root / "Memory/Decisions/bound-choice.md").is_file()
    assert not (project / "Memory").exists()


def test_cli_requires_exactly_one_decision_body_source(tmp_path, capsys):
    root = area(tmp_path / "area")
    assert cli.main(
        [
            "memory",
            "add-decision",
            str(root),
            "--title",
            "Synthetic choice",
            "--date",
            "2026-09-18",
        ]
    ) == 2
    assert "Record:" not in capsys.readouterr().out
