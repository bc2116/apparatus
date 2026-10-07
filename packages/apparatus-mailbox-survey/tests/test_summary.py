"""Bounded, value-limited summaries of supplied synthetic reports."""

import os
import socket
import subprocess
import sys

import pytest

import yaml

from apparatus_mailbox_survey.__main__ import main
from apparatus_mailbox_survey.report import MAX_BYTES
from apparatus_mailbox_survey.summary import summarize_report


def valid_report():
    return {
        "schema": "apparatus/mailbox-survey@v1",
        "action": "none",
        "scope": {"source": "sample", "description": "Synthetic supplied sample", "coverage": "sample"},
        "inventory": {"total": 2, "reviewed": 2, "unavailable": 0, "skipped": 0, "unassessed": 0},
        "items": [
            {"id": "private-id-a", "source": "private-locator-a", "summary": "private item summary a"},
            {"id": "private-id-b", "source": "private-locator-b", "summary": "private item summary b"},
        ],
        "categories": [
            {"id": "purchases", "name": "Purchases", "description": "private description", "examples": ["private-id-a"]},
            {"id": "deliveries", "name": "Deliveries", "description": "private description", "examples": ["private-id-a", "private-id-b"]},
        ],
        "uncategorized": [],
        "coverage_gaps": [],
        "next_steps": ["private next action"],
    }


def run_summary(tmp_path, content, capsys):
    path = tmp_path / "report.yaml"
    path.write_bytes(content)
    status = main(["summary", str(path)])
    return status, capsys.readouterr()


def test_summary_shows_scope_inventory_overlap_and_claim_limits(tmp_path, capsys):
    content = yaml.safe_dump(valid_report(), allow_unicode=True).encode()
    status, captured = run_summary(tmp_path, content, capsys)
    output = captured.out
    assert status == 0
    assert "Source: sample" in output
    assert "Scope: Synthetic supplied sample" in output
    assert "Coverage claim: sample" in output
    assert "total 2; reviewed 2; unavailable 0; skipped 0; unassessed 0" in output
    assert "Purchases: 1" in output
    assert "Deliveries: 2" in output
    assert "categories can overlap" in output
    assert "Uncategorized reviewed items: 0" in output
    assert "Coverage gaps:\n- None reported." in output
    assert "does not verify evidence, authority, or actual mailbox coverage" in output
    for hidden in ("private-id", "private-locator", "private item summary", "private description", "private next action"):
        assert hidden not in output


def test_unknown_total_partial_and_empty_complete_scope(tmp_path, capsys):
    value = valid_report()
    value["scope"].update(source="connected-mailbox", coverage="partial")
    value["inventory"].update(total=None, reviewed=1, unavailable=1)
    value["items"] = value["items"][:1]
    value["categories"] = []
    value["uncategorized"] = ["private-id-a"]
    value["coverage_gaps"] = ["Synthetic page was unavailable"]
    status, captured = run_summary(tmp_path, yaml.safe_dump(value).encode(), capsys)
    assert status == 0
    assert "total unknown; reviewed 1; unavailable 1; skipped 0; unassessed 0" in captured.out
    assert "- None reported." in captured.out
    assert "Uncategorized reviewed items: 1" in captured.out
    assert "- Synthetic page was unavailable" in captured.out

    empty = valid_report()
    empty["scope"].update(source="connected-mailbox", description="Synthetic empty scope", coverage="complete")
    empty["inventory"].update(total=0, reviewed=0)
    empty["items"] = []
    empty["categories"] = []
    empty["uncategorized"] = []
    status, captured = run_summary(tmp_path, yaml.safe_dump(empty).encode(), capsys)
    assert status == 0
    assert "Coverage claim: complete" in captured.out
    assert "total 0; reviewed 0" in captured.out
    assert "Coverage gaps:\n- None reported." in captured.out
    assert "does not verify" in captured.out  # Complete is only the report claim.


def test_invalid_yaml_never_emits_partial_summary(tmp_path, capsys):
    status, captured = run_summary(tmp_path, b"scope: [unterminated", capsys)
    assert status == 1
    assert captured.out == ""
    assert "report:" in captured.err
    status, captured = run_summary(tmp_path, yaml.safe_dump({**valid_report(), "extra": "DO_NOT_ECHO"}).encode(), capsys)
    assert status == 1
    assert captured.out == ""
    assert "DO_NOT_ECHO" not in captured.err


@pytest.mark.parametrize("count", [0, 1, 19, 20, 21])
def test_category_and_gap_omission_boundaries(count):
    value = valid_report()
    value["categories"] = [
        {"id": f"category-{index}", "name": f"Category {index}",
         "description": "not displayed", "examples": ["private-id-a"]}
        for index in range(count)
    ]
    value["uncategorized"] = ["private-id-a", "private-id-b"] if count == 0 else ["private-id-b"]
    value["coverage_gaps"] = [f"Gap {index}" for index in range(count)]
    output = summarize_report(value)
    if count <= 20:
        assert "additional category omitted" not in output
        assert "additional categories omitted" not in output
        assert "additional coverage gap omitted" not in output
        assert "additional coverage gaps omitted" not in output
    else:
        assert "1 additional category omitted." in output
        assert "1 additional coverage gap omitted." in output
    assert output.count("- Category ") == min(count, 20)
    assert output.count("- Gap ") == min(count, 20)
    assert "- -1 additional" not in output


def test_display_bounds_and_preserves_non_ascii():
    value = valid_report()
    value["scope"]["description"] = "s" * 241
    value["categories"][0]["name"] = "München — 東京"
    output = summarize_report(value)
    assert "s" * 240 + "… [truncated]" in output
    assert "München — 東京: 1" in output


def test_ascii_stdout_uses_safe_fallback(tmp_path):
    value = valid_report()
    value["scope"]["description"] = "München — 東京"
    path = tmp_path / "unicode-report.yaml"
    path.write_bytes(yaml.safe_dump(value, allow_unicode=True).encode())
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "ascii"
    completed = subprocess.run(
        [sys.executable, "-m", "apparatus_mailbox_survey", "summary", str(path)],
        capture_output=True, text=True, env=environment, timeout=10,
    )
    assert completed.returncode == 0
    assert "Traceback" not in completed.stderr
    assert "Scope: M\\xfc" in completed.stdout


def test_control_and_format_characters_cannot_add_lines_or_bidi(tmp_path, capsys):
    value = valid_report()
    value["scope"]["description"] = "first\nFAKE STATUS\x1b[31m\u202eoverride"
    value["categories"][0]["name"] = "name\u2066hidden"
    status, captured = run_summary(tmp_path, yaml.safe_dump(value, allow_unicode=True).encode(), capsys)
    assert status == 0
    output = captured.out
    assert "Scope: first\\u000AFAKE STATUS\\u001B[31m\\u202Eoverride" in output
    assert "name\\u2066hidden: 1" in output
    assert "FAKE STATUS\n" not in output
    assert "\x1b" not in output
    assert "\u202e" not in output
    assert "\u2066" not in output


def test_read_only_unchanged_bytes_and_no_network(tmp_path, monkeypatch, capsys):
    path = tmp_path / "report.yaml"
    original = yaml.safe_dump(valid_report()).encode()
    path.write_bytes(original)
    before = path.stat()
    real_open = os.open
    calls = []

    def read_only_open(file, flags, *args, **kwargs):
        calls.append(flags)
        assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        return real_open(file, flags, *args, **kwargs)

    def no_network(*args, **kwargs):
        raise AssertionError("summary attempted network access")

    monkeypatch.setattr(os, "open", read_only_open)
    monkeypatch.setattr(socket, "socket", no_network)
    assert main(["summary", str(path)]) == 0
    assert len(calls) == 1
    assert path.read_bytes() == original
    assert path.stat().st_mtime_ns == before.st_mtime_ns
    assert "Source: sample" in capsys.readouterr().out


def test_oversize_and_nonregular_input_fail_safely(tmp_path, capsys):
    path = tmp_path / "oversized.yaml"
    path.write_bytes(b"x" * (MAX_BYTES + 1))
    assert main(["summary", str(path)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "exceeds 1 MiB limit" in captured.err
    assert main(["summary", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "report: unable to read input\n"
