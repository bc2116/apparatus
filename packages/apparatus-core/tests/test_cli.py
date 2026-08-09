from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib.metadata
from pathlib import Path

from apparatus_core import __version__
from apparatus_core import cli
from apparatus_core.commands import doctor


@dataclass
class FakeEntryPoint:
    name: str
    value: str
    register: object
    group: str = cli.ENTRY_POINT_GROUP

    def load(self):
        return self.register


def test_version_prints_the_core_version(capsys):
    assert cli.main(["--version"]) == 0
    assert capsys.readouterr().out == f"{__version__}\n"


def test_no_verb_prints_help_and_returns_usage_error(capsys):
    assert cli.main([]) == 2
    output = capsys.readouterr().out
    assert "usage: apparatus" in output
    assert "doctor" in output
    assert "\nap " not in output


def test_unknown_verb_returns_usage_error(capsys):
    assert cli.main(["unknown"]) == 2
    assert "invalid choice" in capsys.readouterr().err


def test_console_script_metadata_has_two_names_with_one_main():
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    assert 'apparatus = "apparatus_core.cli:main"' in text
    assert 'ap = "apparatus_core.cli:main"' in text


def test_console_script_aliases_resolve_to_one_callable_and_match_version_output(capsys):
    scripts = {
        entry.name: entry
        for entry in importlib.metadata.distribution("apparatus-core").entry_points
        if entry.group == "console_scripts" and entry.name in {"apparatus", "ap"}
    }
    assert set(scripts) == {"apparatus", "ap"}
    assert scripts["apparatus"].load() is scripts["ap"].load() is cli.main
    for name in ("apparatus", "ap"):
        assert scripts[name].load()(["--version"]) == 0
        assert capsys.readouterr().out == f"{__version__}\n"


def test_fake_entry_point_command_is_dispatched():
    calls: list[str] = []

    def run(args):
        calls.append(args.verb)
        return 0

    def register(subparsers):
        parser = subparsers.add_parser("example")
        parser.set_defaults(func=run)

    entry_point = FakeEntryPoint("example", "pack:register", register)
    parser = cli.build_parser(lambda: {cli.ENTRY_POINT_GROUP: [entry_point]})
    args = parser.parse_args(["example"])
    assert args.func(args) == 0
    assert calls == ["example"]


def test_duplicate_verb_uses_first_sorted_entry_point_and_warns(capsys):
    called: list[str] = []

    def first(subparsers):
        called.append("first")
        subparsers.add_parser("sample").set_defaults(func=lambda args: 0)

    def loser(subparsers):
        called.append("loser")
        subparsers.add_parser("sample").set_defaults(func=lambda args: 0)

    entries = [
        FakeEntryPoint("sample", "z_pack:register", loser),
        FakeEntryPoint("sample", "a_pack:register", first),
    ]
    parser = cli.build_parser(lambda: {cli.ENTRY_POINT_GROUP: entries})
    parser.parse_args(["sample"])
    assert called == ["first"]
    assert "skipping duplicate command verb 'sample'" in capsys.readouterr().err


def test_entry_point_api_variants_are_normalized():
    entry = FakeEntryPoint("sample", "pack:register", lambda subparsers: None)

    class Selectable:
        def select(self, *, group):
            assert group == cli.ENTRY_POINT_GROUP
            return [entry]

    assert cli.command_entry_points(lambda: Selectable()) == [entry]
    assert cli.command_entry_points(lambda: {cli.ENTRY_POINT_GROUP: [entry]}) == [entry]
    assert cli.command_entry_points(lambda: [entry]) == [entry]


def test_doctor_prints_and_writes_only_for_an_explicit_workspace(capsys, tmp_path):
    detections = {
        "python": {"version": "3.12.4", "executable": "/python"},
        "git": {"present": True, "version": "git version 2.50"},
        "uv": {"present": True, "version": "uv 0.9"},
        "sync_redirection": {"at_risk": False, "reason": "No risk."},
    }
    writes: list[Path] = []

    def write(workspace, report):
        writes.append(Path(workspace))
        return Path(workspace) / "System/machine-report.md"

    assert doctor.run(
        argparse.Namespace(workspace=str(tmp_path)),
        detect=lambda **kwargs: detections,
        render=lambda report: "machine report\n",
        write=write,
    ) == 0
    assert capsys.readouterr().out == "machine report\n"
    assert writes == [tmp_path]


def test_doctor_without_workspace_does_not_write(capsys):
    detections = {
        "python": {"version": "3.12.4", "executable": "/python"},
        "git": {"present": True, "version": "git version 2.50"},
        "uv": {"present": True, "version": "uv 0.9"},
        "sync_redirection": {"at_risk": False, "reason": "No risk."},
    }
    writes: list[Path] = []
    assert doctor.run(
        argparse.Namespace(workspace=None),
        detect=lambda **kwargs: detections,
        render=lambda report: "machine report\n",
        write=lambda workspace, report: writes.append(Path(workspace)),
    ) == 0
    assert capsys.readouterr().out == "machine report\n"
    assert writes == []


def test_doctor_returns_degraded_for_missing_tools_or_sync_risk(capsys):
    healthy = {
        "python": {"version": "3.12.4", "executable": "/python"},
        "git": {"present": True, "version": "git version 2.50"},
        "uv": {"present": True, "version": "uv 0.9"},
        "sync_redirection": {"at_risk": False, "reason": "No risk."},
    }
    degraded = [
        {**healthy, "git": {"present": False, "version": None}},
        {**healthy, "uv": {"present": False, "version": None}},
        {
            **healthy,
            "sync_redirection": {"at_risk": True, "reason": "OneDrive location."},
        },
    ]
    for detections in degraded:
        assert doctor.run(
            argparse.Namespace(workspace=None),
            detect=lambda **kwargs: detections,
            render=lambda report: "",
            write=lambda workspace, report: None,
        ) == 1
    assert capsys.readouterr().out == ""
