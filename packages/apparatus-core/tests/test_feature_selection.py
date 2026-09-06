from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil

import pytest

from apparatus_core import features, fs_transactions, records
from apparatus_core.commands import (
    init,
    library,
    profile as profile_command,
    recall,
    snapshot,
    restore,
)
from apparatus_core import ignore
from apparatus_core.ignore import load_ignore_rules


def _workspace(tmp_path: Path, **features: bool) -> Path:
    workspace = tmp_path / "workspace"
    assert init.run(
        argparse.Namespace(workspace=str(workspace), privacy_mode=None, work_types=None, payload=None),
        available=lambda: False,
    ) == 0
    profile = records.yaml.safe_load((workspace / "System/profile.yaml").read_text())
    if features:
        profile["features"] = {
            "library_indexing": features.get("library_indexing", True),
            "snapshots": features.get("snapshots", True),
            "ignore_rules": features.get("ignore_rules", True),
        }
    (workspace / "System/profile.yaml").write_text(
        records.yaml.safe_dump(profile, sort_keys=False), encoding="utf-8"
    )
    return workspace


def _receipt_count(workspace: Path, event: str) -> int:
    return len(list((workspace / "System/receipts").glob(f"*-{event}*.md")))


def _receipt(workspace: Path, event: str) -> tuple[dict, str]:
    path = sorted((workspace / "System/receipts").glob(f"*-{event}*.md"))[-1]
    return records.parse_record(path.read_text(encoding="utf-8"))


def _workspace_bytes(workspace: Path) -> dict[str, bytes]:
    return {
        path.relative_to(workspace).as_posix(): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def _assert_profile_failure_has_no_effects(tmp_path, workspace: Path, capsys) -> None:
    before = _workspace_bytes(workspace)
    home = tmp_path / "feature-home"
    assert not home.exists()
    prior_home = os.environ.get("APPARATUS_HOME")
    os.environ["APPARATUS_HOME"] = str(home)
    try:
        assert library.run(argparse.Namespace(workspace=str(workspace))) == 2
        assert "profile" in capsys.readouterr().out
        assert snapshot.run(argparse.Namespace(workspace=str(workspace), label=None)) == 2
        assert "profile" in capsys.readouterr().out
    finally:
        if prior_home is None:
            os.environ.pop("APPARATUS_HOME", None)
        else:
            os.environ["APPARATUS_HOME"] = prior_home
    assert _workspace_bytes(workspace) == before
    assert not home.exists()


def test_features_mapping_is_closed_and_absence_keeps_defaults(tmp_path):
    workspace = _workspace(tmp_path)
    profile = records.yaml.safe_load((workspace / "System/profile.yaml").read_text())
    assert records.validate("profile", profile, "profile.yaml") == []
    profile["features"] = {
        "library_indexing": True,
        "snapshots": True,
        "ignore_rules": True,
    }
    assert records.validate("profile", profile, "profile.yaml") == []
    profile["features"] = {
        "library_indexing": True,
        "snapshots": True,
        "ignore_rules": True,
        "other": False,
    }
    problems = records.validate("profile", profile, "profile.yaml")
    assert any("unexpected key" in problem for problem in problems)
    profile["features"] = {"library_indexing": True}
    assert any(
        "must include" in problem
        for problem in records.validate("profile", profile, "profile.yaml")
    )


def test_library_toggle_is_quiet_and_reenable_preserves_content(tmp_path, capsys):
    workspace = _workspace(tmp_path, library_indexing=False)
    source = workspace / "Library/source.txt"
    source.write_text("feature selection sample", encoding="utf-8")
    args = argparse.Namespace(workspace=str(workspace))
    assert library.run(args) == 1
    assert "feature is off" in capsys.readouterr().out
    assert _receipt_count(workspace, "library-ingest") == 0
    profile = records.yaml.safe_load((workspace / "System/profile.yaml").read_text())
    profile["features"]["library_indexing"] = True
    (workspace / "System/profile.yaml").write_text(records.yaml.safe_dump(profile, sort_keys=False))
    assert library.run(args) == 0
    assert source.read_text(encoding="utf-8") == "feature selection sample"
    assert library.run_search(
        argparse.Namespace(
            workspace=str(workspace),
            query="sample",
            limit=5,
            as_json=False,
            rebuild=False,
        )
    ) == 0
    assert recall.run(
        argparse.Namespace(
            workspace=str(workspace), question="sample", limit=5, as_json=False
        )
    ) == 0


def test_disabled_library_search_prints_the_control_outcome_without_history(tmp_path, capsys):
    workspace = _workspace(tmp_path, library_indexing=False)
    capsys.readouterr()
    assert library.run_search(
        argparse.Namespace(
            workspace=str(workspace), query="sample", limit=5, as_json=False, rebuild=True
        )
    ) == 1
    assert capsys.readouterr().out == "This feature is off; say the word and I'll enable it.\n"
    receipts = list((workspace / "System/receipts").glob("*.md"))
    assert len(receipts) == 1  # actual init only
    assert _receipt_count(workspace, "library-ingest") == 0


def test_snapshots_toggle_reports_and_reenable_runs(tmp_path, capsys):
    workspace = _workspace(tmp_path, snapshots=False)
    args = argparse.Namespace(workspace=str(workspace), label=None)
    assert snapshot.run(args) == 1
    assert "feature is off" in capsys.readouterr().out
    assert _receipt_count(workspace, "snapshot") == 0
    profile = records.yaml.safe_load((workspace / "System/profile.yaml").read_text())
    profile["features"]["snapshots"] = True
    (workspace / "System/profile.yaml").write_text(records.yaml.safe_dump(profile, sort_keys=False))
    assert snapshot.run(args, available=lambda: False) == 1
    assert "unavailable" in capsys.readouterr().out.lower()


def test_disabled_restore_and_list_do_not_touch_snapshot_history(tmp_path, capsys):
    workspace = _workspace(tmp_path, snapshots=False)
    args = argparse.Namespace(workspace=str(workspace), snapshot_id=None, list=True)
    assert restore.run(args) == 1
    assert "feature is off" in capsys.readouterr().out
    assert _receipt_count(workspace, "restore") == 0


def test_ignore_toggle_keeps_built_ins_and_reenable_restores_user_matching(tmp_path):
    workspace = _workspace(tmp_path, ignore_rules=False)
    (workspace / "System/ignore").write_text("secret.txt\n", encoding="utf-8")
    rules = load_ignore_rules(workspace).require_valid()
    assert rules.matches("secret.txt") is False
    assert rules.matches(".DS_Store") is True
    assert rules.report().provenance == "built-in defaults; user rules are off"
    profile = records.yaml.safe_load((workspace / "System/profile.yaml").read_text())
    profile["features"]["ignore_rules"] = True
    (workspace / "System/profile.yaml").write_text(records.yaml.safe_dump(profile, sort_keys=False))
    assert load_ignore_rules(workspace).require_valid().matches("secret.txt") is True


@pytest.mark.parametrize("content", [b"!unsupported\n", b"\xff\n"])
def test_disabled_ignore_rules_do_not_open_or_parse_the_user_file(tmp_path, monkeypatch, content):
    workspace = _workspace(tmp_path, ignore_rules=False)
    (workspace / "System/ignore").write_bytes(content)

    def must_not_open(*_args, **_kwargs):
        raise AssertionError("disabled user rules must not be opened")

    monkeypatch.setattr(ignore, "_read_regular_file", must_not_open)
    rules = load_ignore_rules(workspace).require_valid()
    assert rules.matches("secret.txt") is False
    assert rules.matches(".DS_Store") is True
    assert rules.report().provenance == "built-in defaults; user rules are off"


def test_profile_apply_keeps_feature_choices_idempotently(tmp_path):
    workspace = _workspace(tmp_path, library_indexing=False, snapshots=False, ignore_rules=False)
    profile = records.yaml.safe_load((workspace / "System/profile.yaml").read_text())
    profile["status"] = "configured"
    (workspace / "System/profile.yaml").write_text(records.yaml.safe_dump(profile, sort_keys=False))
    args = argparse.Namespace(
        profile_action="apply",
        workspace=str(workspace),
        payload=None,
        candidate_stdin=False,
    )
    assert profile_command.run(args) == 0
    before = (workspace / "System/profile.yaml").read_bytes()
    assert profile_command.run(args) == 0
    assert (workspace / "System/profile.yaml").read_bytes() == before


def test_disabled_recall_is_quiet(tmp_path, capsys):
    workspace = _workspace(tmp_path, library_indexing=False)
    args = argparse.Namespace(
        workspace=str(workspace), question="anything", limit=5, as_json=False
    )
    assert recall.run(args) == 1
    assert "feature is off" in capsys.readouterr().out
    assert _receipt_count(workspace, "recall") == 0


@pytest.mark.parametrize("profile_content", ["not: [valid", "[]\n", "features: false\n"])
def test_invalid_profile_fails_closed_before_feature_machinery_mutates(
    tmp_path, capsys, profile_content
):
    workspace = _workspace(tmp_path)
    profile = workspace / "System/profile.yaml"
    profile.write_text(profile_content, encoding="utf-8")
    receipts_before = sorted((workspace / "System/receipts").glob("*.md"))
    assert library.run(argparse.Namespace(workspace=str(workspace))) == 2
    assert "profile" in capsys.readouterr().out
    assert snapshot.run(argparse.Namespace(workspace=str(workspace), label=None)) == 2
    assert "profile" in capsys.readouterr().out
    assert sorted((workspace / "System/receipts").glob("*.md")) == receipts_before
    with pytest.raises(ValueError, match="profile"):
        load_ignore_rules(workspace).require_valid()


@pytest.mark.skipif(os.name != "posix", reason="FIFOs are a POSIX endpoint")
def test_fifo_profile_is_rejected_without_blocking_or_any_feature_effects(tmp_path, capsys):
    workspace = _workspace(tmp_path)
    profile = workspace / "System/profile.yaml"
    profile.unlink()
    os.mkfifo(profile)
    _assert_profile_failure_has_no_effects(tmp_path, workspace, capsys)


@pytest.mark.parametrize("replacement", ["directory", "non_utf8"])
def test_unsafe_profile_endpoint_has_no_feature_effects(tmp_path, capsys, replacement):
    workspace = _workspace(tmp_path)
    profile = workspace / "System/profile.yaml"
    profile.unlink()
    if replacement == "directory":
        profile.mkdir()
    else:
        profile.write_bytes(b"\xff")
    _assert_profile_failure_has_no_effects(tmp_path, workspace, capsys)


@pytest.mark.skipif(os.name != "posix", reason="descriptor-currentness probe is POSIX-specific")
@pytest.mark.parametrize("replacement", ["profile", "system", "workspace"])
def test_profile_path_replacement_fails_closed_before_selections_return(
    tmp_path, monkeypatch, replacement
):
    workspace = _workspace(tmp_path)
    original_reader = features._read_posix_regular
    calls = 0

    def replace_after_retained_read(parent, name):
        nonlocal calls
        value = original_reader(parent, name)
        calls += 1
        if calls != 1:
            return value
        if replacement == "profile":
            candidate = tmp_path / "replacement-profile.yaml"
            candidate.write_bytes((workspace / "System/profile.yaml").read_bytes())
            candidate.replace(workspace / "System/profile.yaml")
        elif replacement == "system":
            candidate = tmp_path / "replacement-system"
            shutil.copytree(workspace / "System", candidate)
            (workspace / "System").rename(tmp_path / "prior-system")
            candidate.rename(workspace / "System")
        else:
            candidate = tmp_path / "replacement-workspace"
            shutil.copytree(workspace, candidate)
            workspace.rename(tmp_path / "prior-workspace")
            candidate.rename(workspace)
        return value

    monkeypatch.setattr(features, "_read_posix_regular", replace_after_retained_read)
    with pytest.raises(features.FeatureProfileError, match="read safely"):
        features.selections(workspace)


@pytest.mark.skipif(os.name != "nt", reason="native Windows endpoint coverage")
def test_windows_nonregular_profile_has_no_feature_effects(tmp_path, capsys):
    workspace = _workspace(tmp_path)
    profile = workspace / "System/profile.yaml"
    profile.unlink()
    profile.mkdir()
    _assert_profile_failure_has_no_effects(tmp_path, workspace, capsys)


@pytest.mark.skipif(os.name != "nt", reason="native Windows reparse coverage")
def test_windows_reparse_profile_has_no_feature_effects(tmp_path, capsys):
    workspace = _workspace(tmp_path)
    profile = workspace / "System/profile.yaml"
    outside = tmp_path / "outside-profile.yaml"
    outside.write_bytes(profile.read_bytes())
    profile.unlink()
    try:
        profile.symlink_to(outside)
    except OSError as error:  # GitHub's Windows runner enables this primitive.
        pytest.fail(f"Windows safety coverage requires a reparse endpoint: {error}")
    _assert_profile_failure_has_no_effects(tmp_path, workspace, capsys)


@pytest.mark.skipif(os.name != "nt", reason="native Windows pathname-currentness coverage")
def test_windows_profile_replacement_has_no_feature_effects(tmp_path, monkeypatch, capsys):
    workspace = _workspace(tmp_path)
    profile = workspace / "System/profile.yaml"
    candidate = tmp_path / "replacement-profile.yaml"
    candidate.write_bytes(profile.read_bytes())
    original_matches = features.WindowsWorkspaceAnchor.matches_owned

    def replace_then_verify(anchor, owned):
        candidate.replace(profile)
        return original_matches(anchor, owned)

    monkeypatch.setattr(
        features.WindowsWorkspaceAnchor, "matches_owned", replace_then_verify
    )
    _assert_profile_failure_has_no_effects(tmp_path, workspace, capsys)


def _windows_identity(
    path: Path, *, directory: bool
) -> fs_transactions.WindowsIdentity:
    handle = fs_transactions._win_open(path, directory=directory)
    try:
        return fs_transactions._win_identity(handle)
    finally:
        fs_transactions._win_close(handle)


def _replace_windows_profile_container(
    workspace: Path, tmp_path: Path, replacement: str
) -> None:
    root_before = _windows_identity(workspace, directory=True)
    system = workspace / "System"
    system_before = _windows_identity(system, directory=True)
    profile_before = _windows_identity(system / "profile.yaml", directory=False)

    if replacement == "system":
        candidate = tmp_path / "replacement-system"
        shutil.copytree(
            system,
            candidate,
            ignore=shutil.ignore_patterns("profile.yaml"),
        )
        (system / "profile.yaml").replace(candidate / "profile.yaml")
        system.rename(tmp_path / "prior-system")
        candidate.rename(system)
    else:
        candidate = tmp_path / "replacement-workspace"
        shutil.copytree(
            workspace,
            candidate,
            ignore=shutil.ignore_patterns("System"),
        )
        system.replace(candidate / "System")
        workspace.rename(tmp_path / "prior-workspace")
        candidate.rename(workspace)

    root_after = _windows_identity(workspace, directory=True)
    system_after = _windows_identity(workspace / "System", directory=True)
    profile_after = _windows_identity(
        workspace / "System/profile.yaml", directory=False
    )
    assert profile_after == profile_before
    if replacement == "system":
        assert fs_transactions._same_windows_object(root_after, root_before)
        assert not fs_transactions._same_windows_object(system_after, system_before)
    else:
        assert not fs_transactions._same_windows_object(root_after, root_before)
        assert fs_transactions._same_windows_object(system_after, system_before)


@pytest.mark.skipif(os.name != "nt", reason="native Windows parent-currentness coverage")
@pytest.mark.parametrize("replacement", ["system", "workspace"])
@pytest.mark.parametrize("operation", ["library", "snapshot"])
def test_windows_parent_replacement_with_original_profile_has_no_effects(
    tmp_path, monkeypatch, capsys, replacement, operation
):
    workspace = _workspace(tmp_path)
    before = _workspace_bytes(workspace)
    home = tmp_path / "feature-home"
    monkeypatch.setenv("APPARATUS_HOME", str(home))
    original_validate = features.records.validate
    replaced = False

    def replace_after_validation(*args, **kwargs):
        nonlocal replaced
        problems = original_validate(*args, **kwargs)
        if not replaced:
            replaced = True
            _replace_windows_profile_container(workspace, tmp_path, replacement)
        return problems

    monkeypatch.setattr(features.records, "validate", replace_after_validation)
    if operation == "library":
        result = library.run(argparse.Namespace(workspace=str(workspace)))
    else:
        result = snapshot.run(
            argparse.Namespace(workspace=str(workspace), label=None)
        )

    assert replaced
    assert result == 2
    assert "profile" in capsys.readouterr().out
    assert _workspace_bytes(workspace) == before
    assert not home.exists()


@pytest.mark.skipif(os.name == "nt", reason="Windows link privilege is runner-dependent")
def test_symlinked_profile_fails_closed_without_following_outside_control(tmp_path, capsys):
    workspace = _workspace(tmp_path)
    outside = tmp_path / "outside-profile.yaml"
    outside.write_text(
        "schema: apparatus/profile@v0\nstatus: unconfigured\nprivacy_mode: standard\n"
        "work_types: []\nreview_day: null\nfeatures:\n  library_indexing: false\n"
        "  snapshots: false\n  ignore_rules: false\n",
        encoding="utf-8",
    )
    profile = workspace / "System/profile.yaml"
    profile.unlink()
    profile.symlink_to(outside)
    receipts_before = sorted((workspace / "System/receipts").glob("*.md"))
    assert library.run(argparse.Namespace(workspace=str(workspace))) == 2
    assert "read safely" in capsys.readouterr().out
    assert sorted((workspace / "System/receipts").glob("*.md")) == receipts_before
