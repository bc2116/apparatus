"""Read-only command and independent resource packaging checks."""

import importlib.metadata
import importlib.resources
import os
import socket
import stat
import subprocess
import sys
from types import SimpleNamespace
import pytest
import yaml

from apparatus_mailbox_survey import __version__, validate_report
from apparatus_mailbox_survey.__main__ import main
from apparatus_mailbox_survey.report import MAX_BYTES


def resources():
    return importlib.resources.files("apparatus_mailbox_survey").joinpath("resources")


def test_metadata_and_independent_dependencies():
    metadata = importlib.metadata.metadata("apparatus-mailbox-survey")
    assert metadata["Version"] == __version__ == "0.1.0"
    assert metadata["Requires-Python"] == ">=3.10"
    assert importlib.metadata.requires("apparatus-mailbox-survey") == ["pyyaml>=6.0"]


def test_resources_are_available_and_example_valid():
    root = resources()
    assert root.joinpath("skills", "apparatus-mailbox-survey", "SKILL.md").is_file()
    assert root.joinpath("sample-mailbox.yaml").is_file()
    assert root.joinpath("report-example.yaml").is_file()
    assert root.joinpath("skills", "apparatus-mailbox-survey", "references", "report-format.md").is_file()
    assert validate_report(root.joinpath("report-example.yaml").read_bytes()) == []


def test_sample_parses_and_example_references_supplied_messages():
    root = resources()
    sample = yaml.safe_load(root.joinpath("sample-mailbox.yaml").read_bytes())
    example = yaml.safe_load(root.joinpath("report-example.yaml").read_bytes())
    messages = sample["messages"]
    identities = {message["id"] for message in messages}
    assert len(messages) == len(identities) == 8
    assert sample["inventory"]["total"] == 8
    assert sample["inventory"]["supplied"] == 8
    assert sample["inventory"]["reviewed"] == 8
    assert example["inventory"]["reviewed"] == len(messages)
    assert {item["id"] for item in example["items"]} == identities
    known_locators = {f"sample-mailbox.yaml#{identity}" for identity in identities}
    assert {item["source"] for item in example["items"]} == known_locators
    assert all(item["source"] == f"sample-mailbox.yaml#{item['id']}" for item in example["items"])
    referenced = set(example["uncategorized"])
    for category in example["categories"]:
        referenced.update(category["examples"])
    assert referenced == identities


@pytest.mark.parametrize("args", [[], ["validate"], ["repair", "PRIVATE_MARKER"], ["validate", "a", "b"]])
def test_usage_is_safe(args, capsys):
    assert main(args) == 2
    assert "PRIVATE_MARKER" not in capsys.readouterr().err


def test_read_failure_is_safe(tmp_path, capsys):
    assert main(["validate", str(tmp_path / "PRIVATE_MARKER")]) == 2
    assert "PRIVATE_MARKER" not in capsys.readouterr().err
    assert main(["validate", str(tmp_path)]) == 2


def test_input_unchanged_and_no_network(tmp_path, monkeypatch, capsys):
    path = tmp_path / "report.yaml"
    original = resources().joinpath("report-example.yaml").read_bytes()
    path.write_bytes(original)
    before = path.stat()
    real_open = os.open
    calls = []

    def only_read(file, flags, *args, **kwargs):
        calls.append(flags)
        assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        return real_open(file, flags, *args, **kwargs)

    def no_network(*args, **kwargs):
        raise AssertionError("Unexpected network access")

    monkeypatch.setattr(os, "open", only_read)
    monkeypatch.setattr(socket, "socket", no_network)
    assert main(["validate", str(path)]) == 0
    assert len(calls) == 1
    assert path.read_bytes() == original
    assert path.stat().st_mtime_ns == before.st_mtime_ns
    assert "unverified" in capsys.readouterr().out


def test_invalid_command_preserves_input(tmp_path, capsys):
    path = tmp_path / "invalid.yaml"
    original = b"secret-value: [unfinished"
    path.write_bytes(original)
    before = path.stat().st_mtime_ns
    assert main(["validate", str(path)]) == 1
    assert "secret-value" not in capsys.readouterr().err
    assert path.read_bytes() == original
    assert path.stat().st_mtime_ns == before


def test_command_bounds_read(monkeypatch):
    class Input:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, limit):
            assert limit == MAX_BYTES + 1
            return b"x" * limit
    monkeypatch.setattr(os, "open", lambda *args: 123)
    monkeypatch.setattr(os, "fstat", lambda descriptor: SimpleNamespace(st_mode=stat.S_IFREG))
    monkeypatch.setattr(os, "fdopen", lambda *args: Input())
    assert main(["validate", "report.yaml"]) == 1


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="Named pipes are POSIX-specific")
def test_fifo_read_is_nonblocking(tmp_path):
    path = tmp_path / "input-pipe"
    os.mkfifo(path)
    completed = subprocess.run(
        [sys.executable, "-m", "apparatus_mailbox_survey", "validate", str(path)],
        capture_output=True, text=True, timeout=5,
    )
    assert completed.returncode == 2
    assert completed.stderr == "report: unable to read input\n"


def test_nonregular_descriptor_closed(monkeypatch):
    closed = []
    monkeypatch.setattr(os, "open", lambda *args: 123)
    monkeypatch.setattr(os, "fstat", lambda descriptor: SimpleNamespace(st_mode=stat.S_IFDIR))
    monkeypatch.setattr(os, "close", closed.append)
    assert main(["validate", "report.yaml"]) == 2
    assert closed == [123]
