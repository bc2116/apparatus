from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest
from apparatus_core import records
from apparatus_core.check import check_workspace
from apparatus_core.commands import init, memory, profile
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.labeler import render_record, split_record_exact
from apparatus_core.memory import recall
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


def record(workspace, *, folder="Facts", name="sample.md", **metadata):
    kind = "fact" if folder == "Facts" else "person"
    data = {"schema": f"apparatus/{kind}@v0",
            "title" if kind == "fact" else "name": "Fictional context", **metadata}
    relative = Path("Memory") / folder / name
    (workspace / relative).write_text(render_record(data, "Original cobalt context.\n"))
    return relative


def run(workspace, action, target=None, **kwargs):
    return memory.run(argparse.Namespace(workspace=str(workspace), memory_action=action,
                                        record=target.as_posix() if target else None, **kwargs))


def replacement(tmp_path, *, kind="fact", body="Corrected amber context.\n", **metadata):
    path = tmp_path / "replacement.md"
    data = {"schema": f"apparatus/{kind}@v0",
            "title" if kind == "fact" else "name": "Replacement", **metadata}
    path.write_text(render_record(data, body))
    return str(path)


def test_legacy_correct_outdated_forget_and_explicit_recreation(tmp_path, capsys):
    workspace = _workspace(tmp_path / "workspace")
    target = record(workspace, source="old-source", obsolete="old metadata")
    with WorkspaceAnchor(workspace) as anchor:
        assert len(recall(anchor, "COBALT context")["results"]) == 1
    source = replacement(tmp_path, source="Library/new.md", custom={"owner": "team"})
    assert run(workspace, "correct", target, from_file=source) == 0
    data, body = split_record_exact((workspace / target).read_text())
    assert data["status"] == "current" and data["source"] == "Library/new.md"
    assert data["custom"] == {"owner": "team"} and "obsolete" not in data
    assert body == "Corrected amber context.\n"
    assert run(workspace, "recall", query="amber", limit=5) == 0
    assert "Library/new.md" in capsys.readouterr().out
    assert run(workspace, "outdated", target) == 0
    with WorkspaceAnchor(workspace) as anchor:
        assert recall(anchor, "amber")["results"] == []
    assert run(workspace, "forget", target) == 0
    before = (workspace / target).read_bytes()
    assert split_record_exact(before.decode()) == (
        {"schema": "apparatus/fact@v0", "status": "forgotten"}, ""
    )
    assert run(workspace, "forget", target) == 0
    assert run(workspace, "outdated", target) == 2
    assert (workspace / target).read_bytes() == before
    assert "sample.md" not in capsys.readouterr().out
    assert check_workspace(workspace).ok
    assert run(workspace, "label") == 0
    assert (workspace / target).read_bytes() == before
    assert run(workspace, "correct", target, from_file=source) == 0
    assert not list((workspace / "System/receipts").glob("*.md"))


def test_recall_ignores_before_content_and_validates_past_limit(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    for number in range(4):
        record(workspace, name=f"sample-{number}.md")
    hidden = workspace / "Memory/Facts/hidden.md"
    hidden.write_bytes(b"\xff")
    (workspace / "System/ignore").write_text("Memory/Facts/hidden.md\n")
    with WorkspaceAnchor(workspace) as anchor:
        result = recall(anchor, "cobalt", limit=2)
        assert result["truncated"] is True
        assert [r["source"] for r in result["results"]] == [
            "Memory/Facts/sample-0.md", "Memory/Facts/sample-1.md"]
        (workspace / "Memory/People/invalid.md").write_text("not a record")
        with pytest.raises(ValueError, match="invalid record"):
            recall(anchor, "cobalt", limit=1)
        for query, limit in ((" ", 5), ("cobalt", 0), ("cobalt", 21)):
            with pytest.raises(ValueError):
                recall(anchor, query, limit=limit)


def test_correct_credentials_and_private_restrictions(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    target = record(workspace)
    (workspace / "System/ignore").write_text("Memory/\n")
    source = replacement(tmp_path, body="password=synthetic-change contact sample@example.invalid\n")
    assert run(workspace, "correct", target, from_file=source) == 0
    text = (workspace / target).read_text()
    assert "synthetic-change" not in text and "[redacted-password]" in text
    assert "pii/email" in text
    receipt = next((workspace / "System/receipts").glob("*-redaction.md"))
    assert "synthetic-change" not in receipt.read_text()
    profile_path = workspace / "System/profile.yaml"
    profile_path.write_text(profile_path.read_text().replace("standard", "private"))
    before = (workspace / target).read_bytes()
    assert run(workspace, "correct", target, from_file=source) == 1
    assert (workspace / target).read_bytes() == before
    person = record(workspace, folder="People")
    assert run(workspace, "correct", person, from_file=replacement(tmp_path, kind="person")) == 1
    assert run(workspace, "forget", person) == 0


def test_lifecycle_requires_existing_safe_same_kind_record(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    target = record(workspace)
    original = (workspace / target).read_bytes()
    assert run(workspace, "correct", target, from_file=replacement(tmp_path, kind="person")) == 2
    assert run(workspace, "forget", Path("Memory/Facts/missing.md")) == 2
    assert run(workspace, "forget", Path("Memory/Facts/../../escape.md")) == 2
    (workspace / "Memory/Facts/link.md").symlink_to(workspace / target)
    assert run(workspace, "forget", Path("Memory/Facts/link.md")) == 2
    assert run(workspace, "recall", query="cobalt", limit=5) == 2
    source = Path(replacement(tmp_path))
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(tmp_path, target_is_directory=True)
    assert run(workspace, "correct", target, from_file=str(linked_parent / source.name)) == 2
    assert (workspace / target).read_bytes() == original


@pytest.mark.parametrize("concurrent", [False, True])
def test_correct_receipt_failure_rolls_back_only_owned_write(tmp_path, concurrent):
    workspace = _workspace(tmp_path / "workspace")
    target = record(workspace)
    original = (workspace / target).read_bytes()
    source = replacement(tmp_path, body="password=synthetic-receipt\n")
    write_attempts = []
    def fail(*args, **kwargs):
        if concurrent:
            try:
                (workspace / target).write_bytes(b"Concurrent replacement\n")
            except PermissionError as error:
                write_attempts.append(error.winerror)
            else:
                write_attempts.append(None)
        raise OSError("publication failed")
    args = argparse.Namespace(workspace=str(workspace), memory_action="correct",
                              record=target.as_posix(), from_file=source)
    assert memory.run(args, write=fail) == 2
    # Windows retains a target handle denying FILE_SHARE_WRITE; POSIX permits
    # the injected writer, whose replacement must then survive rollback.
    assert write_attempts == ([32 if os.name == "nt" else None] if concurrent else [])
    assert (workspace / target).read_bytes() == (
        b"Concurrent replacement\n" if concurrent and os.name != "nt" else original)
    assert not list((workspace / "System/receipts").glob("*.md"))
    assert not list((workspace / "Memory/Facts").glob(".apparatus*"))


def test_stale_record_is_never_overwritten(tmp_path, monkeypatch):
    workspace = _workspace(tmp_path / "workspace")
    target = record(workspace)
    original = WorkspaceAnchor.replace_if_unchanged
    def replace(self, *args, **kwargs):
        (workspace / target).write_text("Concurrent edit\n")
        return original(self, *args, **kwargs)
    monkeypatch.setattr(WorkspaceAnchor, "replace_if_unchanged", replace)
    assert run(workspace, "forget", target) == 2
    assert (workspace / target).read_text() == "Concurrent edit\n"


def test_tombstone_prevents_profile_reseeding(tmp_path):
    workspace = tmp_path / "workspace"
    assert init.run(argparse.Namespace(workspace=str(workspace), payload=None,
                                      privacy_mode=None, work_types=None),
                    available=lambda: False) == 0
    profile_path = workspace / "System/profile.yaml"
    data = records.yaml.safe_load(profile_path.read_text())
    data["status"] = "configured"
    data["key_people"] = [{"name": "Fictional Person", "role": "Lead"}]
    profile_path.write_text(records.yaml.safe_dump(data))
    args = argparse.Namespace(workspace=str(workspace), candidate_stdin=False,
                              profile_action="apply", payload=None)
    assert profile.run(args) == 0
    target = Path("Memory/People/fictional-person.md")
    assert run(workspace, "forget", target) == 0
    before = (workspace / target).read_bytes()
    assert profile.run(args) == 0
    assert (workspace / target).read_bytes() == before
    assert len(list((workspace / "Memory/People").glob("*.md"))) == 1


@pytest.mark.parametrize("kind", ["fact", "person"])
def test_lifecycle_schema_and_body_validation(kind):
    base = {"schema": f"apparatus/{kind}@v0", "status": "forgotten"}
    assert records.validate(kind, base, body="") == []
    assert records.validate(kind, {**base, "title": "retained"}, body="")
    assert records.validate(kind, base, body="retained body")
    assert records.validate(kind, {**base, "status": "unknown"})


def test_correct_rolls_back_published_receipt_after_concurrent_write_attempt(tmp_path, monkeypatch):
    from apparatus_core.receipts import write_receipt
    workspace = _workspace(tmp_path / "workspace")
    target = record(workspace)
    original = (workspace / target).read_bytes()
    source = replacement(tmp_path, body="password=synthetic-proof\n")
    write_attempts = []
    validation_attempts = []
    validate_commit = memory._ReplacementTransaction.validate_commit

    def reject_commit(transaction):
        validation_attempts.append(True)
        validate_commit(transaction)
        # On Windows the concurrent writer is blocked, so explicitly fail at
        # the post-publication validation boundary to exercise receipt rollback.
        if os.name == "nt":
            raise OSError("injected final validation failure")

    monkeypatch.setattr(memory._ReplacementTransaction, "validate_commit", reject_commit)

    def publish(*args, **kwargs):
        proof = write_receipt(*args, **kwargs)
        try:
            (workspace / target).write_bytes(b"Concurrent content\n")
        except PermissionError as error:
            write_attempts.append(error.winerror)
        else:
            write_attempts.append(None)
        # Return ownership even when Windows refuses the competing writer.
        return proof

    args = argparse.Namespace(workspace=str(workspace), memory_action="correct",
                              record=target.as_posix(), from_file=source)
    assert memory.run(args, write=publish) == 2
    assert write_attempts == [32 if os.name == "nt" else None]
    assert validation_attempts == [True]
    assert (workspace / target).read_bytes() == (
        original if os.name == "nt" else b"Concurrent content\n")
    assert not list((workspace / "System/receipts").glob("*.md"))
    assert not list((workspace / "Memory/Facts").glob(".apparatus*"))


def test_check_and_recall_reject_content_bearing_forgotten_record(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    target = workspace / "Memory/Facts/sample.md"
    target.write_text(render_record({"schema": "apparatus/fact@v0",
                                     "status": "forgotten"}, "Retained content\n"))
    assert not check_workspace(workspace).ok
    assert run(workspace, "recall", query="content", limit=5) == 2


def test_installed_cli_executes_lifecycle_and_json_recall(tmp_path):
    import json
    import shutil
    import subprocess
    workspace = _workspace(tmp_path / "workspace")
    target = record(workspace)
    executable = shutil.which("apparatus")
    assert executable
    for action in ("outdated", "forget"):
        result = subprocess.run([executable, "memory", action, str(workspace),
                                 target.as_posix()], capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
    source = replacement(tmp_path)
    result = subprocess.run([executable, "memory", "correct", str(workspace),
                             target.as_posix(), "--from-file", source],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run([executable, "memory", "recall", str(workspace), "amber"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["results"][0]["source"] == target.as_posix()


@pytest.mark.parametrize("phase", ["before-apply", "after-initial-proof"])
@pytest.mark.parametrize("same_content", [False, True])
def test_repeat_forget_rejects_a_stale_noop(tmp_path, monkeypatch, capsys, phase, same_content):
    workspace = _workspace(tmp_path / "workspace")
    target = record(workspace)
    assert run(workspace, "forget", target) == 0
    capsys.readouterr()
    tombstone = (workspace / target).read_bytes()
    concurrent = tombstone if same_content else render_record(
        {"schema": "apparatus/fact@v0", "title": "Concurrent current record"},
        "Newly saved context.\n",
    ).encode()

    def substitute():
        other = workspace / "Memory/Facts/replacement.md"
        other.write_bytes(concurrent)
        other.replace(workspace / target)

    if phase == "before-apply":
        original_apply = memory._apply_changes
        def apply(*args, **kwargs):
            substitute()
            return original_apply(*args, **kwargs)
        monkeypatch.setattr(memory, "_apply_changes", apply)
    else:
        original_read = WorkspaceAnchor.read_file
        reads = 0
        def read(self, relative):
            nonlocal reads
            result = original_read(self, relative)
            if Path(relative) == target:
                reads += 1
                if reads == 2:  # Planning read, then the initial no-op proof.
                    substitute()
            return result
        monkeypatch.setattr(WorkspaceAnchor, "read_file", read)

    assert run(workspace, "forget", target) == 2
    assert (workspace / target).read_bytes() == concurrent
    assert "Memory record forgotten." not in capsys.readouterr().out
    assert not list((workspace / "Memory/Facts").glob(".apparatus*"))
