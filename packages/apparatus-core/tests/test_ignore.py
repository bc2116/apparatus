from __future__ import annotations

import os
from pathlib import Path

import pytest

from apparatus_core.ignore import IgnoreRulesError, load_ignore_rules
import apparatus_core.ignore as ignore_module


def _rules(tmp_path: Path, text: str):
    (tmp_path / "System").mkdir()
    (tmp_path / "System/ignore").write_text(text, encoding="utf-8")
    return load_ignore_rules(tmp_path)


def test_supported_workspace_relative_patterns_and_builtin_defaults(tmp_path):
    rules = _rules(
        tmp_path,
        "# a comment\nLibrary/private/\nProjects/**/scratch?.md\n*.dump\n/root.txt\n",
    )
    assert rules.matches("Library/private/source.txt")
    assert rules.matches("Projects/a/b/scratch1.md")
    assert rules.matches("Library/vendor.dump")
    assert rules.matches("root.txt")
    assert not rules.matches("Library/root.txt")
    assert rules.matches("Library/.DS_Store")
    assert rules.matches("Projects/.git/config")
    assert not rules.matches("Library/visible.txt")


@pytest.mark.parametrize(
    "pattern", ["Library/private", "/Library/private", "Library/*"]
)
def test_any_pattern_matching_a_directory_hides_its_descendants(
    tmp_path, pattern
):
    rules = _rules(tmp_path, f"{pattern}\n")

    assert rules.matches("Library/private", is_directory=True)
    assert rules.matches("Library/private/secret.txt")


def test_trailing_slash_is_directory_only_but_still_hides_descendants(tmp_path):
    rules = _rules(tmp_path, "Library/private/\n")

    assert not rules.matches("Library/private")
    assert rules.matches("Library/private", is_directory=True)
    assert rules.matches("Library/private/secret.txt")


def test_unsupported_syntax_is_reported_not_reinterpreted(tmp_path):
    rules = _rules(tmp_path, "!Library/keep.txt\nfolder/[ab].txt\nfolder\\name.txt\n")
    assert [issue.line for issue in rules.issues] == [1, 2, 3]
    assert not rules.valid
    with pytest.raises(IgnoreRulesError):
        rules.require_valid()
    assert not rules.matches("Library/keep.txt")


def test_missing_file_is_valid_builtins_only_provenance(tmp_path):
    (tmp_path / "System").mkdir()
    rules = load_ignore_rules(tmp_path).require_valid()
    report = rules.report(built_in_paths=1)
    assert not report.file_present
    assert report.skipped_paths == 1
    assert "System/ignore is missing" in report.provenance


def test_non_utf8_unreadable_and_symlink_files_are_invalid(monkeypatch, tmp_path):
    system = tmp_path / "System"
    system.mkdir()
    ignore = system / "ignore"
    ignore.write_bytes(b"\xff")
    rules = load_ignore_rules(tmp_path)
    assert not rules.valid
    assert rules.issues[0].code == "ignore-file-encoding-error"

    ignore.write_text("Library/private/\n", encoding="utf-8")
    monkeypatch.setattr(
        ignore_module,
        "_read_regular_file",
        lambda *_args: (_ for _ in ()).throw(PermissionError()),
    )
    rules = load_ignore_rules(tmp_path)
    assert not rules.valid
    assert rules.issues[0].code == "ignore-file-read-error"

    monkeypatch.undo()
    target = tmp_path / "outside-ignore"
    target.write_text("Library/private/\n", encoding="utf-8")
    ignore.unlink()
    ignore.symlink_to(target)
    rules = load_ignore_rules(tmp_path)
    assert not rules.valid
    assert rules.issues[0].code == "ignore-file-unsafe"


def test_reparse_system_directory_is_not_mistaken_for_missing_ignore(tmp_path):
    outside = tmp_path / "outside-system"
    outside.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "System").symlink_to(outside, target_is_directory=True)

    rules = load_ignore_rules(workspace)

    assert rules.file_present
    assert not rules.valid
    assert rules.issues[0].code == "ignore-file-unsafe"


@pytest.mark.skipif(os.name != "posix", reason="descriptor endpoint regression")
def test_ignore_name_replacement_during_read_fails_closed(monkeypatch, tmp_path):
    system = tmp_path / "System"
    system.mkdir()
    ignore = system / "ignore"
    ignore.write_text("Library/private/\n", encoding="utf-8")
    replacement = system / "replacement"
    replacement.write_text("# replacement\n", encoding="utf-8")
    original_read = ignore_module.os.read
    replaced = [False]

    def replace_after_read(descriptor, size):
        content = original_read(descriptor, size)
        if content and not replaced[0]:
            replaced[0] = True
            ignore.unlink()
            replacement.rename(ignore)
        return content

    monkeypatch.setattr(ignore_module.os, "read", replace_after_read)
    rules = load_ignore_rules(tmp_path)

    assert not rules.valid
    assert rules.issues[0].code == "ignore-file-read-error"
