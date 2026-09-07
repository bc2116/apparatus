from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.metadata
import os
from io import StringIO
from pathlib import Path

import pytest

from apparatus_core import records
from apparatus_core.check import check_workspace
from apparatus_core.commands import check, init, memory, profile
from apparatus_core.receipts import prepare_receipt_invocation, write_receipt
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


def _whole_tree(root: Path) -> tuple[tuple[str, str, bytes | None], ...]:
    result: list[tuple[str, str, bytes | None]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_symlink():
            result.append((relative.as_posix(), "symlink", os.readlink(path).encode()))
        elif path.is_file():
            result.append((relative.as_posix(), "file", path.read_bytes()))
        else:
            result.append((relative.as_posix(), "directory", None))
    return tuple(result)


def _receipt_names(root: Path) -> tuple[str, ...]:
    return tuple(sorted(path.name for path in (root / "System/receipts").iterdir()))


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


def test_reapply_is_byte_identical_including_receipts(tmp_path):
    workspace = _init_workspace(tmp_path / "workspace")
    _write_profile(
        workspace,
        key_people=[{"name": "Riley Sample"}],
        current_efforts=[{"title": "Finish sample report"}],
        source_locations=[],
    )
    assert profile.run(_args(workspace)) == 0
    before = _whole_tree(workspace)
    assert profile.run(_args(workspace)) == 0
    assert _whole_tree(workspace) == before
    assert len(list((workspace / "System/receipts").glob("*-profile-apply*.md"))) == 1


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


def test_preexisting_receipt_path_is_never_treated_as_publication_ownership(tmp_path):
    workspace = _init_workspace(tmp_path / "workspace")
    _write_profile(
        workspace,
        source_locations=["password=sample-existing-path-secret"],
    )
    sentinel = workspace / "System/receipts/user-owned.md"
    sentinel.write_bytes(b"user-owned receipt sentinel\n")
    before = _whole_tree(workspace)

    def preexisting_writer(*_args, **_kwargs):
        return sentinel

    assert profile.run(_args(workspace), write=preexisting_writer) == 2
    assert _whole_tree(workspace) == before


def test_outside_receipt_path_is_never_treated_as_publication_ownership(tmp_path):
    workspace = _init_workspace(tmp_path / "workspace")
    _write_profile(workspace, current_efforts=[{"title": "Required receipt mutation"}])
    outside = tmp_path / "outside-user-owned.md"
    outside.write_bytes(b"outside user-owned sentinel\n")
    before_workspace = _whole_tree(workspace)
    before_outside = outside.read_bytes()

    def outside_writer(*_args, **_kwargs):
        return outside

    assert profile.run(_args(workspace), write=outside_writer) == 2
    assert _whole_tree(workspace) == before_workspace
    assert outside.read_bytes() == before_outside


def test_stale_publication_proof_is_never_reclaimed(tmp_path):
    workspace = _init_workspace(tmp_path / "workspace")
    _write_profile(workspace, current_efforts=[{"title": "Required receipt mutation"}])
    stale = write_receipt(
        workspace,
        "profile-apply",
        {"summary": "Pre-existing receipt sentinel."},
    )
    before = _whole_tree(workspace)

    def stale_writer(*_args, **_kwargs):
        return stale

    assert profile.run(_args(workspace), write=stale_writer) == 2
    assert _whole_tree(workspace) == before


def test_live_same_workspace_event_and_content_substitution_is_not_reclaimed(
    tmp_path,
):
    workspace = _init_workspace(tmp_path / "workspace")
    _write_profile(workspace, current_efforts=[{"title": "Required receipt mutation"}])
    observed: dict[str, object] = {}

    def unrelated_live_writer(target, event, fields, *, invocation):
        del invocation
        unrelated = prepare_receipt_invocation(target, event, fields)
        publication = write_receipt(
            target,
            event,
            fields,
            invocation=unrelated,
        )
        observed.update(
            invocation=unrelated,
            publication=publication,
            digest=publication.content_digest,
            receipts=_receipt_names(workspace),
            tree=_tree_without_receipts(workspace),
        )
        return publication

    assert profile.run(_args(workspace), write=unrelated_live_writer) == 2
    publication = observed["publication"]
    invocation = observed["invocation"]
    assert _tree_without_receipts(workspace) == observed["tree"]
    assert _receipt_names(workspace) == observed["receipts"]
    assert publication.content_digest == observed["digest"]
    publication.validate()
    publication.claim(invocation)
    publication.commit()
    publication.close()
    assert sha256(publication.path.read_bytes()).hexdigest() == observed["digest"]


@pytest.mark.parametrize(
    "substitution",
    ("wrong-event", "wrong-content", "other-workspace"),
)
def test_live_foreign_capabilities_are_rejected_without_modification(
    tmp_path,
    substitution,
):
    workspace = _init_workspace(tmp_path / "workspace")
    _write_profile(workspace, current_efforts=[{"title": "Required receipt mutation"}])
    other = _init_workspace(tmp_path / "other-workspace")
    target = other if substitution == "other-workspace" else workspace
    event = "redaction" if substitution == "wrong-event" else "profile-apply"
    fields = {
        "summary": (
            "Wrong rendered content."
            if substitution == "wrong-content"
            else "Unrelated live receipt."
        )
    }
    invocation = prepare_receipt_invocation(target, event, fields)
    publication = write_receipt(
        target,
        event,
        fields,
        invocation=invocation,
    )
    before_workspace = _tree_without_receipts(workspace)
    before_other = _tree_without_receipts(other)
    workspace_receipts = _receipt_names(workspace)
    other_receipts = _receipt_names(other)
    receipt_digest = publication.content_digest

    def foreign_writer(*_args, **_kwargs):
        return publication

    assert profile.run(_args(workspace), write=foreign_writer) == 2
    assert _tree_without_receipts(workspace) == before_workspace
    assert _tree_without_receipts(other) == before_other
    assert _receipt_names(workspace) == workspace_receipts
    assert _receipt_names(other) == other_receipts
    assert publication.content_digest == receipt_digest
    publication.validate()
    publication.claim(invocation)
    publication.commit()
    publication.close()
    assert sha256(publication.path.read_bytes()).hexdigest() == receipt_digest


def test_reused_current_invocation_is_rejected_and_rolled_back(tmp_path):
    workspace = _init_workspace(tmp_path / "workspace")
    _write_profile(workspace, current_efforts=[{"title": "Required receipt mutation"}])
    before = _whole_tree(workspace)

    def reused_writer(target, event, fields, *, invocation):
        publication = write_receipt(
            target,
            event,
            fields,
            invocation=invocation,
        )
        publication.claim(invocation)
        return publication

    assert profile.run(_args(workspace), write=reused_writer) == 2
    assert _whole_tree(workspace) == before


@pytest.mark.skipif(os.name != "posix", reason="POSIX name-substitution probe")
def test_receipt_substitution_after_return_restores_exact_prior_tree(tmp_path):
    workspace = _init_workspace(tmp_path / "workspace")
    _write_profile(workspace, current_efforts=[{"title": "Required receipt mutation"}])
    sentinel = workspace / "System/receipts/user-owned.md"
    sentinel.write_bytes(b"user-owned receipt sentinel\n")
    before = _whole_tree(workspace)

    def substituted_writer(*args, **kwargs):
        publication = write_receipt(*args, **kwargs)
        held = publication.path.with_name("temporary-name-swap")
        publication.path.rename(held)
        sentinel.rename(publication.path)
        held.rename(sentinel)
        return publication

    assert profile.run(_args(workspace), write=substituted_writer) == 2
    assert _whole_tree(workspace) == before


def test_first_owned_receipt_is_removed_when_second_publication_fails(tmp_path):
    workspace = _init_workspace(tmp_path / "workspace")
    current = records.yaml.safe_load(
        (workspace / "System/profile.yaml").read_text(encoding="utf-8")
    )
    current.update(
        {
            "status": "configured",
            "source_locations": ["password=sample-second-failure-secret"],
        }
    )
    candidate = records.yaml.safe_dump(current, sort_keys=False)
    before = _whole_tree(workspace)
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected second publication failure")
        return write_receipt(*args, **kwargs)

    assert profile.run(
        _args(workspace, candidate_stdin=True),
        write=fail_second,
        input_stream=StringIO(candidate),
    ) == 2
    assert calls == 2
    assert _whole_tree(workspace) == before


def test_normal_two_receipt_apply_commits_without_ownership_artifacts(tmp_path):
    workspace = _init_workspace(tmp_path / "workspace")
    current = records.yaml.safe_load(
        (workspace / "System/profile.yaml").read_text(encoding="utf-8")
    )
    current.update(
        {
            "status": "configured",
            "source_locations": ["password=sample-two-receipt-secret"],
        }
    )
    candidate = records.yaml.safe_dump(current, sort_keys=False)
    existing = {path.name for path in (workspace / "System/receipts").iterdir()}

    assert profile.run(
        _args(workspace, candidate_stdin=True),
        input_stream=StringIO(candidate),
    ) == 0
    receipt_files = sorted(
        path
        for path in (workspace / "System/receipts").iterdir()
        if path.name not in existing
    )
    assert len(receipt_files) == 2
    assert {
        records.parse_record(path.read_text(encoding="utf-8"))[0]["event"]
        for path in receipt_files
    } == {
        "profile-apply",
        "redaction",
    }
    assert not list((workspace / "System/receipts").glob(".apparatus-receipt-*"))


def test_mid_apply_failure_restores_profile_overlay_seed_and_receipts(
    tmp_path, monkeypatch
):
    workspace = _init_workspace(tmp_path / "workspace")
    welcome = workspace / ".agents/skills/apparatus-welcome/SKILL.md"
    welcome.write_bytes(welcome.read_bytes() + b"\nUser-owned custom Skill edit.\n")
    (workspace / "System/policy/standard.md").write_bytes(b"Policy preimage before overlay.\n")
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
    injected = []

    def fail_goal(self, relative, content, mode=0o600):
        if Path(relative).parts[:1] == ("Goals",):
            injected.append(relative)
            raise OSError("injected goal publication failure")
        return original_create(self, relative, content, mode)

    monkeypatch.setattr(memory._WorkspaceAnchor, "create_file", fail_goal)
    assert profile.run(
        _args(workspace, candidate_stdin=True),
        input_stream=StringIO(candidate_text),
    ) == 2
    assert injected, "profile must reach the injected failure after overlay publication"
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


@pytest.mark.parametrize("target", ["System/profile.yaml", "System/policy/standard.md"])
@pytest.mark.parametrize("same_bytes", [False, True])
@pytest.mark.parametrize("real_change", [False, True])
def test_frozen_noop_preimages_reject_competitors_before_apply(
    tmp_path, monkeypatch, target, same_bytes, real_change
):
    workspace = _init_workspace(tmp_path / "workspace")
    _write_profile(workspace)
    assert profile.run(_args(workspace)) == 0
    current = (workspace / "System/profile.yaml").read_bytes()
    candidate = records.yaml.safe_load(current)
    candidate["spend"] = "thorough"
    candidate_text = records.yaml.safe_dump(candidate, sort_keys=False)
    path = workspace / target
    original = path.read_bytes()
    competitor = original if same_bytes else original + b"\n# competing edit\n"
    before_receipts = {p.name: p.read_bytes() for p in (workspace / "System/receipts").glob("*.md")}
    original_receipts = profile._write_required_receipts
    attempted = []

    def interfere(*args, **kwargs):
        publications = original_receipts(*args, **kwargs)
        replacement = workspace / "competitor.tmp"
        replacement.write_bytes(competitor)
        try:
            os.replace(replacement, path)
            attempted.append("replaced")
        except PermissionError as error:
            assert os.name == "nt" and getattr(error, "winerror", None) in {5, 32}
            replacement.unlink()
            attempted.append("native-denial")
        return publications

    monkeypatch.setattr(profile, "_write_required_receipts", interfere)
    result = profile.run(_args(workspace, candidate_stdin=real_change),
                         input_stream=StringIO(candidate_text))
    assert attempted in (["replaced"], ["native-denial"])
    if attempted == ["replaced"]:
        assert result == 2
        assert path.read_bytes() == competitor
        if target != "System/profile.yaml":
            assert (workspace / "System/profile.yaml").read_bytes() == current
        assert {p.name: p.read_bytes() for p in (workspace / "System/receipts").glob("*.md")} == before_receipts
    else:
        assert result == 0
        if not real_change or target != "System/profile.yaml":
            assert path.read_bytes() == original


def test_equal_sanitized_candidate_keeps_only_required_redaction(tmp_path):
    workspace = _init_workspace(tmp_path / "workspace")
    _write_profile(workspace, source_locations=["password=synthetic-quiet-secret"])
    assert profile.run(_args(workspace)) == 0
    before = _tree_without_receipts(workspace)
    before_apply = len(list((workspace / "System/receipts").glob("*-profile-apply*.md")))
    before_redaction = len(list((workspace / "System/receipts").glob("*-redaction*.md")))
    candidate = (workspace / "System/profile.yaml").read_text().replace(
        "[redacted-password]", "synthetic-quiet-secret")
    assert profile.run(_args(workspace, candidate_stdin=True), input_stream=StringIO(candidate)) == 0
    assert _tree_without_receipts(workspace) == before
    assert len(list((workspace / "System/receipts").glob("*-profile-apply*.md"))) == before_apply
    assert len(list((workspace / "System/receipts").glob("*-redaction*.md"))) == before_redaction + 1


def _select_fixture_subset(workspace, monkeypatch):
    # The universal manifest currently selects all seven Skills for every work
    # type. Exercise its supported declarative subset/removal path explicitly.
    from dataclasses import replace
    original = profile.load_manifest
    def subset(*args, **kwargs):
        manifest = original(*args, **kwargs)
        paths = manifest.managed_workflow_paths
        return replace(manifest, work_types={"analysis": paths[1:], "writing": paths[:1]})
    monkeypatch.setattr(profile, "load_manifest", subset)
    _write_profile(workspace, work_types=["analysis"])


def test_overlay_removal_reopens_read_only_proof_and_requires_presence(tmp_path, monkeypatch):
    workspace = _init_workspace(tmp_path / "workspace")
    _select_fixture_subset(workspace, monkeypatch)
    original_unlink = memory._WorkspaceAnchor.unlink_owned
    original_if_present = memory._WorkspaceAnchor.unlink_owned_if_present
    reopening = []
    witnessed = []

    def read_only_handle(self, owned):
        if not reopening and Path(owned.relative).as_posix().startswith(".agents/"):
            raise OSError("simulated Windows read-only publication proof lacks DELETE access")
        return original_unlink(self, owned)

    def exact_reopen(self, owned):
        reopening.append(True)
        try:
            result = original_if_present(self, owned)
            witnessed.append(Path(owned.relative).as_posix())
            return result
        finally:
            reopening.pop()

    monkeypatch.setattr(memory._WorkspaceAnchor, "unlink_owned", read_only_handle)
    monkeypatch.setattr(memory._WorkspaceAnchor, "unlink_owned_if_present", exact_reopen)
    assert profile.run(_args(workspace)) == 0
    assert any(name.startswith(".agents/") for name in witnessed)
    assert not (workspace / ".agents/skills/apparatus-welcome/SKILL.md").exists()
    assert len(list((workspace / ".agents/skills").glob("*/SKILL.md"))) == 6
    assert len(list((workspace / "System/receipts").glob("*-profile-apply*.md"))) == 1


def test_overlay_removal_does_not_adopt_custom_body_after_planning(tmp_path, monkeypatch):
    workspace = _init_workspace(tmp_path / "workspace")
    _select_fixture_subset(workspace, monkeypatch)
    original_plan = profile.plan_overlay
    observed = []
    target = workspace / ".agents/skills/apparatus-welcome/SKILL.md"
    original = target.read_bytes()
    custom = original + b"\nPreserve this independently edited instruction.\n"

    def plan_then_compete(*args, **kwargs):
        plan = original_plan(*args, **kwargs)
        assert target.relative_to(workspace).as_posix() in plan.removals
        replacement = workspace / "competitor.tmp"
        replacement.write_bytes(custom)
        try:
            os.replace(replacement, target)
            observed.append("replaced")
        except PermissionError as error:
            assert os.name == "nt" and getattr(error, "winerror", None) in {5, 32}
            replacement.unlink()
            observed.append("native-denial")
        return plan

    monkeypatch.setattr(profile, "plan_overlay", plan_then_compete)
    result = profile.run(_args(workspace))
    assert observed in (["replaced"], ["native-denial"])
    if observed == ["replaced"]:
        assert result == 2
        assert target.read_bytes() == custom
        assert not list((workspace / "System/receipts").glob("*-profile-apply*.md"))
    else:
        assert result == 0
        assert not target.exists()


def test_unchanged_overlay_competing_after_receipt_commit_rolls_back_real_profile_change(tmp_path, monkeypatch):
    workspace = _init_workspace(tmp_path / "workspace")
    current = (workspace / "System/profile.yaml").read_bytes()
    candidate = records.yaml.safe_load(current)
    candidate["spend"] = "thorough"
    target = workspace / "System/policy/standard.md"
    original = target.read_bytes()
    original_commit = profile.ReceiptPublication.commit
    observed = []

    def commit_then_compete(self):
        original_commit(self)
        replacement = workspace / "competitor.tmp"
        replacement.write_bytes(original)
        try:
            os.replace(replacement, target)
            observed.append("replaced")
        except PermissionError as error:
            assert os.name == "nt" and getattr(error, "winerror", None) in {5, 32}
            replacement.unlink()
            observed.append("native-denial")

    monkeypatch.setattr(profile.ReceiptPublication, "commit", commit_then_compete)
    result = profile.run(_args(workspace, candidate_stdin=True), input_stream=StringIO(
        records.yaml.safe_dump(candidate, sort_keys=False)))
    assert observed in (["replaced"], ["native-denial"])
    assert target.read_bytes() == original
    if observed == ["replaced"]:
        assert result == 2
        assert (workspace / "System/profile.yaml").read_bytes() == current
        assert not list((workspace / "System/receipts").glob("*-profile-apply*.md"))
    else:
        assert result == 0
