from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest
from apparatus_core import fs_transactions, records
from apparatus_core.check import check_workspace
from apparatus_core.commands import memory
from apparatus_core.labeler import split_record_exact
from apparatus_core.receipts import write_receipt
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


def _fact_args(workspace: Path, **overrides) -> argparse.Namespace:
    values = {
        "workspace": str(workspace),
        "memory_action": "add-fact",
        "title": "Fictional sample",
        "body": "Ordinary fictional context.",
        "from_file": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _person_args(workspace: Path, **overrides) -> argparse.Namespace:
    values = {
        "workspace": str(workspace),
        "memory_action": "add-person",
        "name": "Fictional Person",
        "role": None,
        "body": "Ordinary fictional context.",
        "from_file": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _tree_bytes(root: Path) -> list[tuple[str, str, bytes | None]]:
    entries = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries.append((relative, "symlink", os.readlink(path).encode()))
        elif path.is_file():
            entries.append((relative, "file", path.read_bytes()))
        else:
            entries.append((relative, "directory", None))
    return entries


def _records(workspace: Path, folder: str) -> list[Path]:
    return sorted((workspace / folder).glob("*.md"))


def test_standard_fact_scans_title_and_body_writes_labels_redaction_receipt_and_checks_clean(
    tmp_path, capsys
):
    workspace = _workspace(tmp_path / "workspace")
    args = _fact_args(
        workspace,
        title="api_key=sample-only",
        body="Contact sample.person@example.invalid.\r\nNo final newline",
    )
    assert memory.run(args) == 0
    output = capsys.readouterr().out
    assert "Credential floor replaced 1 value(s): api-key." in output
    fact = _records(workspace, "Memory/Facts")[0]
    assert fact.name == "api-key-redacted-api-key.md"
    data, body = split_record_exact(fact.read_bytes().decode("utf-8"))
    assert data["title"] == "api_key=[redacted-api-key]"
    assert data["labels"] == ["pii/email"]
    assert body == "Contact sample.person@example.invalid.\r\nNo final newline"
    receipt = _records(workspace, "System/receipts")[0]
    receipt_text = receipt.read_text(encoding="utf-8")
    assert "sample-only" not in receipt_text
    assert "sample.person" not in receipt_text
    receipt_data, _ = records.parse_record(receipt_text)
    assert receipt_data["classes"] == ["api-key"]
    assert receipt_data["counts"] == {"api-key": 1}
    assert check_workspace(workspace).ok


def test_standard_person_scans_name_role_and_body_but_stores_no_structural_fifth_label(
    tmp_path,
):
    workspace = _workspace(tmp_path / "workspace")
    args = _person_args(
        workspace,
        name="Fictional Person",
        role="Call 202-555-0142",
        body="Customer ID: SAMPLE-1042",
    )
    assert memory.run(args) == 0
    person = _records(workspace, "Memory/People")[0]
    data, _body = split_record_exact(person.read_text(encoding="utf-8"))
    assert data["labels"] == ["pii/phone", "pii/id"]
    assert set(data["labels"]) == {"pii/phone", "pii/id"}
    assert check_workspace(workspace).ok


def test_every_private_add_person_blocks_structurally_with_zero_effects(
    tmp_path, capsys
):
    workspace = _workspace(tmp_path / "workspace", "private")
    before = _tree_bytes(workspace)
    assert memory.run(_person_args(workspace)) == 1
    assert "person data" in capsys.readouterr().out
    assert _tree_bytes(workspace) == before


def test_private_fact_blocks_after_floor_and_labels_without_record_receipt_temp_or_directory_effects(
    tmp_path, capsys
):
    workspace = _workspace(tmp_path / "workspace", "private")
    (workspace / "System/receipts").rmdir()
    before = _tree_bytes(workspace)
    args = _fact_args(
        workspace,
        title="Private sample",
        body="password=sample-only and sample.person@example.invalid",
    )
    assert memory.run(args) == 1
    output = capsys.readouterr().out
    assert "pii/email" in output
    assert "sample.person" not in output
    assert "sample-only" not in output
    assert _tree_bytes(workspace) == before


def test_collision_suffix_is_safe_bounded_and_never_overwrites_or_follows_symlink(
    tmp_path,
):
    workspace = _workspace(tmp_path / "workspace")
    outside = tmp_path / "outside.md"
    outside.write_text("outside sentinel", encoding="utf-8")
    collision = workspace / "Memory/Facts/fictional-sample.md"
    collision.symlink_to(outside)
    assert memory.run(_fact_args(workspace, title="Fictional sample")) == 0
    created = next(
        path for path in _records(workspace, "Memory/Facts") if not path.is_symlink()
    )
    assert created.name == "fictional-sample-2.md"
    assert len(created.stem) <= 80
    assert created.name.isascii()
    assert outside.read_text(encoding="utf-8") == "outside sentinel"

    assert memory.run(_fact_args(workspace, title="é" * 500 + " Long title")) == 0
    long_named = max(
        _records(workspace, "Memory/Facts"), key=lambda path: len(path.name)
    )
    assert len(long_named.stem) <= 80
    assert long_named.name.isascii()


def test_from_file_is_strict_utf8_and_preserves_crlf_and_missing_final_newline(
    tmp_path,
):
    workspace = _workspace(tmp_path / "workspace")
    source = tmp_path / "body.txt"
    source.write_bytes(b"First\r\nSecond")
    assert memory.run(_fact_args(workspace, body=None, from_file=str(source))) == 0
    _data, body = split_record_exact(
        _records(workspace, "Memory/Facts")[0].read_bytes().decode("utf-8")
    )
    assert body.encode("utf-8") == b"First\r\nSecond"

    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"\xff")
    before = _tree_bytes(workspace)
    assert memory.run(_fact_args(workspace, body=None, from_file=str(bad))) == 2
    assert _tree_bytes(workspace) == before


def test_invalid_profile_and_workspace_symlink_escape_fail_closed_without_writes(
    tmp_path,
):
    workspace = _workspace(tmp_path / "workspace")
    profile = workspace / "System/profile.yaml"
    profile.write_text("schema: wrong\n", encoding="utf-8")
    before = _tree_bytes(workspace)
    assert memory.run(_fact_args(workspace)) == 2
    assert _tree_bytes(workspace) == before

    profile.write_text(
        "schema: apparatus/profile@v0\nstatus: configured\nprivacy_mode: standard\n"
        "work_types: []\nreview_day: null\n",
        encoding="utf-8",
    )
    facts = workspace / "Memory/Facts"
    facts.rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    facts.symlink_to(outside, target_is_directory=True)
    assert memory.run(_fact_args(workspace)) == 2
    assert list(outside.iterdir()) == []


def test_receipt_failure_rolls_back_new_record_and_partial_receipt(tmp_path, capsys):
    workspace = _workspace(tmp_path / "workspace")

    def fail_atomically(target, event, fields, **_kwargs):
        raise OSError("SAMPLE_SECRET_FAILURE")

    before = _tree_bytes(workspace)
    args = _fact_args(workspace, body="password=sample-only")
    assert memory.run(args, write=fail_atomically) == 2
    assert "SAMPLE_SECRET_FAILURE" not in capsys.readouterr().out
    assert _tree_bytes(workspace) == before


def test_private_sweep_redacts_refreshes_stale_managed_labels_keeps_unrelated_and_is_idempotent(
    tmp_path,
):
    workspace = _workspace(tmp_path / "workspace", "private")
    fact = workspace / "Memory/Facts/hand-written.md"
    body = "Email sample.person@example.invalid\r\npassword=sample-only"
    fact.write_bytes(
        (
            "---\r\nschema: apparatus/fact@v0\r\ntitle: Hand written\r\n"
            "labels:\r\n- custom/review\r\n- pii/phone\r\n---\r\n" + body
        ).encode("utf-8")
    )
    args = argparse.Namespace(workspace=str(workspace), memory_action="label")
    assert memory.run(args) == 0
    first = fact.read_bytes()
    data, refreshed_body = split_record_exact(first.decode("utf-8"))
    assert data["labels"] == ["custom/review", "pii/email"]
    assert (
        refreshed_body
        == "Email sample.person@example.invalid\r\npassword=[redacted-password]"
    )
    receipts = _records(workspace, "System/receipts")
    assert len(receipts) == 1
    assert memory.run(args) == 0
    assert fact.read_bytes() == first
    assert _records(workspace, "System/receipts") == receipts
    assert check_workspace(workspace).ok


def test_sweep_preplans_all_records_and_invalid_or_symlink_record_leaves_everything_old(
    tmp_path,
):
    workspace = _workspace(tmp_path / "workspace")
    good = workspace / "Memory/Facts/good.md"
    good.write_text(
        "---\nschema: apparatus/fact@v0\ntitle: Good\n---\npassword=sample-only",
        encoding="utf-8",
    )
    bad = workspace / "Memory/People/bad.md"
    bad.write_text("not a record", encoding="utf-8")
    before = _tree_bytes(workspace)
    args = argparse.Namespace(workspace=str(workspace), memory_action="label")
    assert memory.run(args) == 2
    assert _tree_bytes(workspace) == before

    bad.unlink()
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    bad.symlink_to(outside)
    before = _tree_bytes(workspace)
    assert memory.run(args) == 2
    assert _tree_bytes(workspace) == before
    assert outside.read_text(encoding="utf-8") == "outside"


def test_sweep_receipt_failure_rolls_back_every_record_and_new_receipt(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    for index in (1, 2):
        (workspace / f"Memory/Facts/sample-{index}.md").write_text(
            f"---\nschema: apparatus/fact@v0\ntitle: Sample {index}\n---\npassword=sample-{index}",
            encoding="utf-8",
        )
    before = _tree_bytes(workspace)
    calls = 0

    def fail_second(target, event, fields, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return write_receipt(target, event, fields, **kwargs)
        concurrent = Path(target) / "System/receipts/concurrent.md"
        concurrent.write_text("concurrent receipt", encoding="utf-8")
        raise OSError("second receipt failed")

    args = argparse.Namespace(workspace=str(workspace), memory_action="label")
    assert memory.run(args, write=fail_second) == 2
    for index in (1, 2):
        path = workspace / f"Memory/Facts/sample-{index}.md"
        before_content = next(
            content
            for relative, kind, content in before
            if relative == path.relative_to(workspace).as_posix()
        )
        assert path.read_bytes() == before_content
    assert _records(workspace, "System/receipts") == [
        workspace / "System/receipts/concurrent.md"
    ]


def test_sweep_scans_safe_yaml_sets_binary_labels_and_nested_containers(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    fact = workspace / "Memory/Facts/container-types.md"
    fact.write_text(
        "---\n"
        "schema: apparatus/fact@v0\n"
        "title: Container types\n"
        "labels:\n"
        "- custom/review\n"
        "- password=label-only\n"
        "sample_set: !!set\n"
        "  ? token=set-only\n"
        "sample_binary: !!binary |\n"
        "  dG9rZW49YmluYXJ5LW9ubHk=\n"
        "nested:\n"
        "- query:\n"
        "  - password=nested-only\n"
        "when: 2026-08-09\n"
        "---\n"
        "Ordinary body.",
        encoding="utf-8",
    )
    args = argparse.Namespace(workspace=str(workspace), memory_action="label")
    assert memory.run(args) == 0
    data, _body = records.parse_record(fact.read_text(encoding="utf-8"))
    assert data["labels"] == ["custom/review", "password=[redacted-password]"]
    assert data["sample_set"] == {"token=[redacted-api-key]"}
    assert data["sample_binary"] == b"token=[redacted-api-key]"
    assert data["nested"] == [{"query": ["password=[redacted-password]"]}]
    assert str(data["when"]) == "2026-08-09"


def test_sweep_fails_closed_on_unscannable_binary_during_full_preplanning(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    good = workspace / "Memory/Facts/a-good.md"
    good.write_text(
        "---\nschema: apparatus/fact@v0\ntitle: Good\n---\npassword=sample-only",
        encoding="utf-8",
    )
    bad = workspace / "Memory/Facts/z-binary.md"
    bad.write_text(
        "---\nschema: apparatus/fact@v0\ntitle: Binary\nsample: !!binary /w==\n---\nBody",
        encoding="utf-8",
    )
    before = _tree_bytes(workspace)
    args = argparse.Namespace(workspace=str(workspace), memory_action="label")
    assert memory.run(args) == 2
    assert _tree_bytes(workspace) == before


def test_sweep_ignores_hidden_memory_files_and_directories_like_workspace_check(
    tmp_path,
):
    workspace = _workspace(tmp_path / "workspace")
    hidden = workspace / "Memory/Facts/.hidden.md"
    nested = workspace / "Memory/Facts/.hidden-folder/nested.md"
    nested.parent.mkdir()
    for path, title in ((hidden, "Hidden"), (nested, "Nested")):
        path.write_text(
            f"---\nschema: apparatus/fact@v0\ntitle: {title}\n---\npassword=sample-only",
            encoding="utf-8",
        )
    before_hidden = hidden.read_bytes()
    before_nested = nested.read_bytes()
    args = argparse.Namespace(workspace=str(workspace), memory_action="label")
    assert memory.run(args) == 0
    assert hidden.read_bytes() == before_hidden
    assert nested.read_bytes() == before_nested


def test_sweep_aborts_without_overwriting_a_concurrent_record_edit(
    tmp_path, monkeypatch
):
    workspace = _workspace(tmp_path / "workspace")
    fact = workspace / "Memory/Facts/concurrent.md"
    fact.write_text(
        "---\nschema: apparatus/fact@v0\ntitle: Concurrent\n---\npassword=sample-only",
        encoding="utf-8",
    )
    concurrent = (
        "---\nschema: apparatus/fact@v0\ntitle: Concurrent\n---\n"
        "A concurrent editor changed this record."
    )
    original = memory._WorkspaceAnchor.replace_if_unchanged
    changed = False

    def edit_then_replace(self, relative, identity, expected, replacement):
        nonlocal changed
        if not changed:
            changed = True
            fact.write_text(concurrent, encoding="utf-8")
        return original(self, relative, identity, expected, replacement)

    monkeypatch.setattr(
        memory._WorkspaceAnchor, "replace_if_unchanged", edit_then_replace
    )
    args = argparse.Namespace(workspace=str(workspace), memory_action="label")
    assert memory.run(args) == 2
    assert fact.read_text(encoding="utf-8") == concurrent
    assert _records(workspace, "System/receipts") == []


def test_sweep_atomic_exchange_restores_an_edit_injected_at_publication(
    tmp_path, monkeypatch
):
    workspace = _workspace(tmp_path / "workspace")
    fact = workspace / "Memory/Facts/publication-race.md"
    fact.write_text(
        "---\nschema: apparatus/fact@v0\ntitle: Publication race\n---\n"
        "password=sample-only",
        encoding="utf-8",
    )
    concurrent = (
        b"---\nschema: apparatus/fact@v0\ntitle: Publication race\n---\n"
        b"Concurrent publication edit."
    )
    original = fs_transactions.exchange_names
    injected = False

    def edit_at_exchange(parent, first, second):
        nonlocal injected
        if not injected:
            injected = True
            descriptor = os.open(second, os.O_WRONLY | os.O_TRUNC, dir_fd=parent)
            try:
                os.write(descriptor, concurrent)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        original(parent, first, second)

    monkeypatch.setattr(fs_transactions, "exchange_names", edit_at_exchange)
    args = argparse.Namespace(workspace=str(workspace), memory_action="label")
    assert memory.run(args) == 2
    assert fact.read_bytes() == concurrent
    assert _records(workspace, "System/receipts") == []


def test_post_exchange_failure_restores_original_before_returning_two(
    tmp_path, monkeypatch
):
    workspace = _workspace(tmp_path / "workspace")
    fact = workspace / "Memory/Facts/post-exchange.md"
    original_content = (
        b"---\nschema: apparatus/fact@v0\ntitle: Post exchange\n---\n"
        b"password=sample-only"
    )
    fact.write_bytes(original_content)
    original = fs_transactions.exchange_names
    failed = False

    def exchange_then_fail(parent, first, second):
        nonlocal failed
        original(parent, first, second)
        if not failed:
            failed = True
            raise OSError("fictional post-exchange verification failure")

    monkeypatch.setattr(fs_transactions, "exchange_names", exchange_then_fail)
    args = argparse.Namespace(workspace=str(workspace), memory_action="label")
    assert memory.run(args) == 2
    assert fact.read_bytes() == original_content
    assert _records(workspace, "System/receipts") == []


def test_new_record_does_not_follow_a_swapped_memory_ancestor(tmp_path, monkeypatch):
    workspace = _workspace(tmp_path / "workspace")
    facts = workspace / "Memory/Facts"
    held = workspace / "Memory/held-facts"
    outside = tmp_path / "outside"
    outside.mkdir()
    original = memory._WorkspaceAnchor.create_file
    swapped = False

    def swap_then_create(self, relative, content, mode=0o600):
        nonlocal swapped
        if not swapped:
            swapped = True
            facts.rename(held)
            facts.symlink_to(outside, target_is_directory=True)
        return original(self, relative, content, mode)

    monkeypatch.setattr(memory._WorkspaceAnchor, "create_file", swap_then_create)
    assert memory.run(_fact_args(workspace)) == 2
    assert list(outside.iterdir()) == []
    assert list(held.iterdir()) == []


def test_new_record_rollback_uses_its_owned_directory_after_an_ancestor_swap(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    facts = workspace / "Memory/Facts"
    held = workspace / "Memory/held-facts"
    outside = tmp_path / "outside"
    outside.mkdir()

    def swap_then_fail(_target, _event, _fields, **_kwargs):
        facts.rename(held)
        facts.symlink_to(outside, target_is_directory=True)
        raise OSError("fictional receipt failure")

    assert (
        memory.run(
            _fact_args(workspace, body="password=sample-only"), write=swap_then_fail
        )
        == 2
    )
    assert list(outside.iterdir()) == []
    assert list(held.iterdir()) == []


def test_sweep_replace_does_not_follow_a_swapped_memory_ancestor(tmp_path, monkeypatch):
    workspace = _workspace(tmp_path / "workspace")
    facts = workspace / "Memory/Facts"
    fact = facts / "sample.md"
    fact.write_text(
        "---\nschema: apparatus/fact@v0\ntitle: Sample\n---\npassword=sample-only",
        encoding="utf-8",
    )
    held = workspace / "Memory/held-facts"
    outside = tmp_path / "outside"
    outside.mkdir()
    original = memory._WorkspaceAnchor.replace_if_unchanged
    swapped = False

    def swap_then_replace(self, relative, identity, expected, replacement):
        nonlocal swapped
        if not swapped:
            swapped = True
            facts.rename(held)
            facts.symlink_to(outside, target_is_directory=True)
        return original(self, relative, identity, expected, replacement)

    monkeypatch.setattr(
        memory._WorkspaceAnchor, "replace_if_unchanged", swap_then_replace
    )
    args = argparse.Namespace(workspace=str(workspace), memory_action="label")
    assert memory.run(args) == 2
    assert list(outside.iterdir()) == []
    assert (
        (held / "sample.md")
        .read_text(encoding="utf-8")
        .endswith("password=sample-only")
    )


def test_new_record_retries_suffix_when_exclusive_open_loses_a_race(
    tmp_path, monkeypatch
):
    workspace = _workspace(tmp_path / "workspace")
    original = memory._WorkspaceAnchor.create_file
    raced = False

    def race_at_open(self, relative, content, mode=0o600):
        nonlocal raced
        if not raced and relative.name == "fictional-sample.md":
            raced = True
            concurrent = original(self, relative, b"concurrent file", mode)
            concurrent.close()
            raise FileExistsError("simulated exclusive-open race")
        return original(self, relative, content, mode)

    monkeypatch.setattr(memory._WorkspaceAnchor, "create_file", race_at_open)
    assert memory.run(_fact_args(workspace)) == 0
    assert (
        workspace / "Memory/Facts/fictional-sample.md"
    ).read_bytes() == b"concurrent file"
    assert (workspace / "Memory/Facts/fictional-sample-2.md").is_file()


@pytest.mark.skipif(os.name != "posix", reason="POSIX descriptor cleanup probe")
def test_failed_new_record_write_preserves_a_substituted_entry(tmp_path, monkeypatch):
    workspace = _workspace(tmp_path / "workspace")
    target = workspace / "Memory/Facts/fictional-sample.md"
    original_write = memory.os.write
    substituted = False

    def substitute_then_fail(descriptor, content):
        nonlocal substituted
        if not substituted:
            substituted = True
            target.unlink()
            target.write_bytes(b"unrelated concurrent content")
            raise OSError("fictional record write failure")
        return original_write(descriptor, content)

    monkeypatch.setattr(memory.os, "write", substitute_then_fail)
    assert memory.run(_fact_args(workspace)) == 2
    assert target.read_bytes() == b"unrelated concurrent content"


def test_multi_record_validation_failure_rolls_back_every_record_and_receipt(
    tmp_path, monkeypatch
):
    workspace = _workspace(tmp_path / "workspace")
    facts = []
    originals = []
    for index in (1, 2):
        fact = workspace / f"Memory/Facts/validation-{index}.md"
        content = (
            f"---\nschema: apparatus/fact@v0\ntitle: Validation {index}\n---\n"
            f"password=sample-{index}"
        ).encode()
        fact.write_bytes(content)
        facts.append(fact)
        originals.append(content)

    original_validate = memory._ReplacementTransaction.validate_commit
    validations = 0

    def fail_second_validation(self):
        nonlocal validations
        validations += 1
        if validations == 2:
            raise OSError("fictional validation failure")
        return original_validate(self)

    monkeypatch.setattr(
        memory._ReplacementTransaction, "validate_commit", fail_second_validation
    )
    args = argparse.Namespace(workspace=str(workspace), memory_action="label")
    assert memory.run(args) == 2
    assert [fact.read_bytes() for fact in facts] == originals
    assert _records(workspace, "System/receipts") == []


def test_multi_record_cleanup_failure_keeps_all_redactions_receipted(
    tmp_path, monkeypatch
):
    workspace = _workspace(tmp_path / "workspace")
    facts = []
    for index in (1, 2):
        fact = workspace / f"Memory/Facts/cleanup-{index}.md"
        fact.write_text(
            f"---\nschema: apparatus/fact@v0\ntitle: Cleanup {index}\n---\n"
            f"password=sample-{index}",
            encoding="utf-8",
        )
        facts.append(fact)

    original_commit = memory._ReplacementTransaction.commit
    commits = 0

    def fail_second_commit(self):
        nonlocal commits
        commits += 1
        if commits == 2:
            raise OSError("fictional cleanup failure")
        return original_commit(self)

    monkeypatch.setattr(memory._ReplacementTransaction, "commit", fail_second_commit)
    args = argparse.Namespace(workspace=str(workspace), memory_action="label")
    assert memory.run(args) == 2
    assert all(b"[redacted-password]" in fact.read_bytes() for fact in facts)
    assert len(_records(workspace, "System/receipts")) == 2
    assert list(workspace.rglob(".apparatus-memory-*.tmp")) == []


def test_cli_registration_and_argument_contract_are_available_from_installed_entry_point():
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    assert 'memory = "apparatus_core.commands.memory:register"' in pyproject.read_text(
        encoding="utf-8"
    )
