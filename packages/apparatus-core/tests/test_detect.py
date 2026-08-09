from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from apparatus_core import detect


def test_detect_tool_handles_missing_present_and_unreadable_version():
    assert detect.detect_tool("git", which=lambda command: None) == {
        "present": False,
        "version": None,
    }
    assert detect.detect_tool(
        "git",
        which=lambda command: "/fake/git",
        run=lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="git version 2.50\n"),
    ) == {"present": True, "version": "git version 2.50"}
    assert detect.detect_tool(
        "uv",
        which=lambda command: "/fake/uv",
        run=lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=""),
    ) == {"present": True, "version": None}


def test_detect_tool_handles_version_command_exception():
    def fail(*args, **kwargs):
        raise OSError("cannot execute")

    assert detect.detect_tool("git", which=lambda command: "/fake/git", run=fail) == {
        "present": True,
        "version": None,
    }


def test_detect_ai_apps_uses_data_table_and_injected_home(tmp_path):
    (tmp_path / "Library/Application Support/Cursor").mkdir(parents=True)
    found = detect.detect_ai_apps(
        "Darwin", home=lambda: tmp_path, root=tmp_path / "root", exists=Path.exists
    )
    assert found == ["Cursor"]


def test_detect_ai_apps_expands_root_and_non_darwin_locations(tmp_path):
    root = tmp_path / "root"
    darwin_home = tmp_path / "darwin-home"
    (root / "Applications/Claude.app").mkdir(parents=True)
    assert detect.detect_ai_apps(
        "Darwin", home=lambda: darwin_home, root=root, exists=Path.exists
    ) == ["Claude"]

    cases = [
        ("Windows", "AppData/Local/Programs/cursor", "Cursor"),
        ("Linux", ".config/github-copilot", "GitHub Copilot"),
    ]
    for os_name, relative_path, expected in cases:
        fake_home = tmp_path / os_name.casefold()
        (fake_home / relative_path).mkdir(parents=True)
        assert detect.detect_ai_apps(
            os_name, home=lambda fake_home=fake_home: fake_home, root=root, exists=Path.exists
        ) == [expected]


def test_sync_redirection_detects_each_common_engine_and_windows_separators():
    cases = [
        (r"C:\Users\Sam\OneDrive\Documents\Apparatus", "OneDrive"),
        (r"C:\Users\Sam\OneDrive - Contoso\Documents\Apparatus", "OneDrive"),
        ("/example/Library/CloudStorage/OneDrive-Contoso/Apparatus", "OneDrive"),
        ("/example/Dropbox/Apparatus", "Dropbox"),
        ("/example/Library/Mobile Documents/com~apple~CloudDocs/Apparatus", "iCloud Drive"),
        ("/example/Google Drive/Apparatus", "Google Drive"),
        ("/example/GoogleDrive/Apparatus", "Google Drive"),
        (
            "/example/Library/CloudStorage/GoogleDrive-account-label/My Drive/Apparatus",
            "Google Drive",
        ),
    ]
    for path, engine in cases:
        result = detect.detect_sync_redirection(path, env={})
        assert result["at_risk"] is True
        assert engine in result["reason"]
    assert detect.detect_sync_redirection("/Projects/Apparatus", env={}) == {
        "at_risk": False,
        "reason": "No common sync-redirection marker was found.",
    }


def test_sync_redirection_ignores_near_match_components():
    paths = [
        "/example/notonedrive/Apparatus",
        "/example/dropbox-notes/Apparatus",
        "/example/Google Drive Archive/Apparatus",
        "/example/Mobile Documents/archive/com~apple~CloudDocs/Apparatus",
        "/example/com~apple~CloudDocs-backup/Apparatus",
        "/example/OneDrive-Archive/Apparatus",
        "/example/GoogleDrive-Archive/Apparatus",
    ]
    for path in paths:
        assert detect.detect_sync_redirection(path, env={})["at_risk"] is False


def test_sync_redirection_uses_environment_markers():
    result = detect.detect_sync_redirection(
        r"C:\Users\Sam\Documents\Apparatus",
        env={"OneDriveCommercial": r"C:\Users\Sam\Documents"},
    )
    assert result["at_risk"] is True
    assert "OneDriveCommercial" in result["reason"]


def test_default_workspace_matches_documented_platform_locations(tmp_path):
    assert detect.default_workspace("Windows", home=lambda: tmp_path) == Path("C:/Projects/Apparatus")
    assert detect.default_workspace("Darwin", home=lambda: tmp_path) == tmp_path / "Projects/Apparatus"


def test_detect_machine_accepts_injected_collaborators(tmp_path):
    result = detect.detect_machine(
        workspace=tmp_path / "Apparatus",
        system=lambda: "Darwin",
        release=lambda: "15.0",
        version_info=(3, 12, 4, "final", 0),
        executable="/python",
        which=lambda command: f"/bin/{command}",
        run=lambda command, **kwargs: SimpleNamespace(returncode=0, stdout=f"{command[0]} version 1\n"),
        env={},
        home=lambda: tmp_path,
        exists=lambda path: False,
    )
    assert result["os"] == {"name": "Darwin", "version": "15.0"}
    assert result["python"] == {"version": "3.12.4", "executable": "/python"}
    assert result["git"]["version"] == "git version 1"
    assert result["uv"]["version"] == "uv version 1"
    assert result["ai_apps"] == []


def test_detect_machine_uses_default_workspace_when_none_is_given(tmp_path):
    result = detect.detect_machine(
        system=lambda: "Darwin",
        release=lambda: "15.0",
        version_info=(3, 12, 4),
        executable="/python",
        which=lambda command: None,
        run=lambda *args, **kwargs: None,
        env={},
        home=lambda: tmp_path,
        exists=lambda path: False,
    )
    assert result["workspace"] == str(tmp_path / "Projects/Apparatus")
    assert result["sync_redirection"]["at_risk"] is False
