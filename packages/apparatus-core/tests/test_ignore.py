from __future__ import annotations

from pathlib import Path

from apparatus_core.ignore import load_ignore_rules


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


def test_unsupported_syntax_is_reported_not_reinterpreted(tmp_path):
    rules = _rules(tmp_path, "!Library/keep.txt\nfolder/[ab].txt\nfolder\\name.txt\n")
    assert [issue.line for issue in rules.issues] == [1, 2, 3]
    assert not rules.matches("Library/keep.txt")
