from __future__ import annotations

from pathlib import Path

from apparatus_core.check import check_workspace


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACES = REPO_ROOT / "conformance" / "workspaces"


def test_golden_workspace_has_no_findings():
    result = check_workspace(WORKSPACES / "golden")
    assert result.ok
    assert result.findings == ()


def test_invalid_workspaces_each_pin_one_finding_code():
    expected = {
        "invalid-bad-frontmatter": "frontmatter-parse-error",
        "invalid-missing-required-field": "missing-required-field",
        "invalid-unknown-kind": "unknown-record-kind",
    }
    for fixture, code in expected.items():
        result = check_workspace(WORKSPACES / fixture)
        assert [finding.code for finding in result.findings] == [code]
