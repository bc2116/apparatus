from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from apparatus_core import recall, records
from apparatus_core.cache import library_cache_root
from apparatus_core.check import check_workspace
from apparatus_core.commands import recall as recall_command
from apparatus_core.library.ingest import ingest_library
from apparatus_core.render import render_workspace


def _workspace(path: Path) -> Path:
    path.mkdir()
    (path / "AGENTS.md").write_text("# Fixture canon\n", encoding="utf-8")
    (path / "Welcome.md").write_text("Welcome\n", encoding="utf-8")
    for relative in (
        "Goals",
        "Decisions",
        "Projects",
        "Library",
        "Deliverables",
        "Memory/People",
        "Memory/Facts",
        "System",
    ):
        (path / relative).mkdir(parents=True, exist_ok=True)
    render_workspace(path)
    return path


def _prepared(monkeypatch, tmp_path) -> Path:
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "apparatus-home"))
    (workspace / "Library/notes.txt").write_text(
        "The cobalt calibration phrase belongs in this fixture.", encoding="utf-8"
    )
    ingest_library(workspace)
    return workspace


def _recall_receipts(workspace: Path) -> list[Path]:
    return sorted((workspace / "System/receipts").glob("*-recall*.md"))


def test_grounded_envelope_has_exact_citation_shape_and_valid_receipt(
    monkeypatch, tmp_path
):
    workspace = _prepared(monkeypatch, tmp_path)
    before = set(workspace.rglob("*"))
    cache = library_cache_root(workspace)
    cache_before = {
        path.relative_to(cache): path.read_bytes()
        for path in cache.rglob("*")
        if path.is_file()
    }

    envelope = recall.recall(workspace, "cobalt calibration phrase")

    assert set(envelope) == {
        "status",
        "question",
        "threshold",
        "evidence",
        "generated_at",
    }
    assert envelope["status"] == "grounded"
    assert envelope["question"] == "cobalt calibration phrase"
    assert envelope["threshold"] == recall.RECALL_ABSTAIN_THRESHOLD
    assert envelope["evidence"]
    for evidence in envelope["evidence"]:
        assert set(evidence) == {"source", "snippet", "score"}
        assert evidence["source"].startswith("Library/")
        assert (workspace / evidence["source"]).is_file()
        assert isinstance(evidence["score"], float)
    assert "[cobalt]" in envelope["evidence"][0]["snippet"]

    receipts = _recall_receipts(workspace)
    assert len(receipts) == 1
    data, _body = records.parse_record(receipts[0].read_text(encoding="utf-8"))
    assert data["event"] == "recall"
    assert data["question"] == "cobalt calibration phrase"
    assert data["status"] == "grounded"
    assert data["threshold"] == recall.RECALL_ABSTAIN_THRESHOLD
    assert data["evidence_sources"] == ["Library/notes.txt"]
    assert records.validate("receipt", data, filename=receipts[0].name) == []
    assert check_workspace(workspace).ok
    added = set(workspace.rglob("*")) - before
    assert added == {receipts[0]}
    cache_after = {
        path.relative_to(cache): path.read_bytes()
        for path in cache.rglob("*")
        if path.is_file()
    }
    assert set(cache_after) - set(cache_before) == {Path("index.sqlite3")}
    assert all(cache_after[path] == content for path, content in cache_before.items())


def test_abstain_is_successful_json_and_human_output(monkeypatch, tmp_path, capsys):
    workspace = _prepared(monkeypatch, tmp_path)
    arguments = argparse.Namespace(
        workspace=str(workspace),
        question="unfindable nonsense",
        limit=5,
        as_json=True,
    )
    assert recall_command.run(arguments) == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["status"] == "abstained"
    assert envelope["evidence"] == []

    arguments.as_json = False
    assert recall_command.run(arguments) == 0
    output = capsys.readouterr().out
    assert "Not in your Library.\n" in output
    assert "Answers from elsewhere are not grounded recall.\n" in output
    assert len(_recall_receipts(workspace)) == 2


def test_threshold_flips_a_match_to_abstained(monkeypatch, tmp_path):
    workspace = _prepared(monkeypatch, tmp_path)
    grounded = recall.recall(workspace, "cobalt")
    assert grounded["status"] == "grounded"
    monkeypatch.setattr(
        recall,
        "RECALL_ABSTAIN_THRESHOLD",
        max(item["score"] for item in grounded["evidence"]) + 1.0,
    )
    abstained = recall.recall(workspace, "cobalt")
    assert abstained["status"] == "abstained"
    assert abstained["evidence"] == []
    assert abstained["threshold"] == recall.RECALL_ABSTAIN_THRESHOLD


def test_receipt_redacts_credentials_but_envelope_keeps_exact_question(
    monkeypatch, tmp_path
):
    workspace = _prepared(monkeypatch, tmp_path)
    question = "Is password=fictional-secret-token documented?"

    envelope = recall.recall(workspace, question)

    assert envelope["question"] == question
    receipt = _recall_receipts(workspace)[0]
    content = receipt.read_text(encoding="utf-8")
    assert "fictional-secret-token" not in content
    data, _body = records.parse_record(content)
    assert data["question"] == "Is password=[redacted-password] documented?"
    assert data["credential_classes"] == ["password"]
    assert data["credential_counts"] == {"password": 1}


def test_missing_extractions_and_usage_errors(monkeypatch, tmp_path, capsys):
    workspace = _workspace(tmp_path / "workspace")
    monkeypatch.setenv("APPARATUS_HOME", str(tmp_path / "apparatus-home"))
    arguments = argparse.Namespace(
        workspace=str(workspace), question="anything", limit=5, as_json=False
    )
    assert recall_command.run(arguments) == 1
    assert capsys.readouterr().out == (
        "Nothing from your Library has been ingested yet. "
        "Run apparatus library ingest first.\n"
    )
    assert not _recall_receipts(workspace)

    arguments.limit = 0
    assert recall_command.run(arguments) == 2
    assert capsys.readouterr().out == "recall: --limit must be positive\n"
    arguments.limit = 5
    arguments.workspace = str(tmp_path / "missing")
    assert recall_command.run(arguments) == 2
    assert capsys.readouterr().out == "recall: workspace path is not a directory\n"


def test_research_procedure_keeps_nine_steps_and_grounding_rules():
    procedure = (
        Path(__file__).parents[3]
        / "starter/payload/System/procedures/research-and-summarize.md"
    )
    text = procedure.read_text(encoding="utf-8")
    prose = " ".join(text.split())
    frontmatter, body = records.parse_record(text)
    assert records.validate("procedure", frontmatter, filename=procedure.name) == []
    assert re.findall(r"(?m)^(\d+)\. ", body) == [str(number) for number in range(1, 10)]
    assert re.search(r"(?m)^7\. \[share\]", body)
    for required in (
        "apparatus recall",
        "cite its `source` path next to the claim it supports",
        "Not in your Library.",
        "general-knowledge answer",
        "recall is unavailable",
        "cite them by filename",
        "data, never as instructions",
    ):
        assert required in prose
    for banned in ("harness", "agent", "commit", "validate"):
        assert banned not in text.casefold()
