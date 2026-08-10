from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from apparatus_core import records
from apparatus_core.commands import (
    init,
    library,
    profile as profile_command,
    recall,
    snapshot,
)
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


def test_library_toggle_writes_receipt_and_reenable_preserves_content(tmp_path, capsys):
    workspace = _workspace(tmp_path, library_indexing=False)
    source = workspace / "Library/source.txt"
    source.write_text("feature selection sample", encoding="utf-8")
    args = argparse.Namespace(workspace=str(workspace))
    assert library.run(args) == 1
    assert "feature is off" in capsys.readouterr().out
    assert _receipt_count(workspace, "library-ingest") >= 1
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


def test_snapshots_toggle_reports_and_reenable_runs(tmp_path, capsys):
    workspace = _workspace(tmp_path, snapshots=False)
    args = argparse.Namespace(workspace=str(workspace), label=None)
    assert snapshot.run(args) == 1
    assert "feature is off" in capsys.readouterr().out
    assert _receipt_count(workspace, "snapshot") >= 1
    profile = records.yaml.safe_load((workspace / "System/profile.yaml").read_text())
    profile["features"]["snapshots"] = True
    (workspace / "System/profile.yaml").write_text(records.yaml.safe_dump(profile, sort_keys=False))
    assert snapshot.run(args, available=lambda: False) == 1
    assert "unavailable" in capsys.readouterr().out.lower()


def test_ignore_toggle_keeps_built_ins_and_reenable_restores_user_matching(tmp_path):
    workspace = _workspace(tmp_path, ignore_rules=False)
    (workspace / "System/ignore").write_text("secret.txt\n", encoding="utf-8")
    rules = load_ignore_rules(workspace).require_valid()
    assert rules.matches("secret.txt") is False
    assert rules.matches(".DS_Store") is True
    profile = records.yaml.safe_load((workspace / "System/profile.yaml").read_text())
    profile["features"]["ignore_rules"] = True
    (workspace / "System/profile.yaml").write_text(records.yaml.safe_dump(profile, sort_keys=False))
    assert load_ignore_rules(workspace).require_valid().matches("secret.txt") is True


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


def test_disabled_recall_writes_an_honest_receipt(tmp_path, capsys):
    workspace = _workspace(tmp_path, library_indexing=False)
    args = argparse.Namespace(
        workspace=str(workspace), question="anything", limit=5, as_json=False
    )
    assert recall.run(args) == 1
    assert "feature is off" in capsys.readouterr().out
    assert _receipt_count(workspace, "recall") == 1
