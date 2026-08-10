from __future__ import annotations

from pathlib import Path

from apparatus_core.egress import check_egress, findings_summary
from apparatus_core.render import render_workspace

ROOT = Path(__file__).parent
GOLDEN = ROOT / "golden/egress"


def _workspace(path: Path) -> Path:
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
        "privacy_mode: standard\n"
        "work_types: []\n"
        "review_day: null\n",
        encoding="utf-8",
    )
    (path / "AGENTS.md").write_text("# Conformance workspace canon\n", encoding="utf-8")
    render_workspace(path)
    return path


def test_egress_redaction_and_findings_match_the_golden_trio(tmp_path):
    workspace = _workspace(tmp_path / "workspace")
    outbound = workspace / "Projects/input.md"
    outbound.write_bytes((GOLDEN / "input.md").read_bytes())

    result = check_egress(
        workspace, ["Projects/input.md"], decision="use-redacted"
    )

    assert (workspace / "Projects/input.redacted.md").read_bytes() == (
        GOLDEN / "expected.redacted.md"
    ).read_bytes()
    assert findings_summary(result.findings).encode("utf-8") == (
        GOLDEN / "expected-findings.txt"
    ).read_bytes()
