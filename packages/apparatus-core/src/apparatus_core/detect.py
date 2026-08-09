"""Pure, local-only environment detection for the doctor command."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any


# Keep this table small and data-only: adding an AI app is a location change,
# not a new detector. ``<home>`` and ``<root>`` are expanded by the scanner.
AI_APP_LOCATIONS: dict[str, dict[str, tuple[str, ...]]] = {
    "darwin": {
        "Claude": ("<root>/Applications/Claude.app", "<home>/Library/Application Support/Claude"),
        "Cursor": ("<root>/Applications/Cursor.app", "<home>/Library/Application Support/Cursor"),
        "GitHub Copilot": ("<home>/.config/github-copilot",),
    },
    "windows": {
        "Claude": ("<home>/AppData/Local/AnthropicClaude",),
        "Cursor": ("<home>/AppData/Local/Programs/cursor",),
        "GitHub Copilot": ("<home>/.config/github-copilot",),
    },
    "linux": {
        "Claude": ("<home>/.config/Claude",),
        "Cursor": ("<home>/.config/Cursor",),
        "GitHub Copilot": ("<home>/.config/github-copilot",),
    },
}

SYNC_ENVIRONMENT_MARKERS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("OneDrive", ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"), "OneDrive"),
    ("Dropbox", ("DROPBOX_HOME", "Dropbox"), "Dropbox"),
    ("iCloud Drive", ("ICLOUD_DRIVE",), "iCloud Drive"),
    ("Google Drive", ("GOOGLE_DRIVE", "GoogleDrive"), "Google Drive"),
)

def _platform_key(name: str) -> str:
    return {"darwin": "darwin", "windows": "windows", "linux": "linux"}.get(
        name.casefold(), name.casefold()
    )


def detect_os(
    system: Callable[[], str] = platform.system,
    release: Callable[[], str] = platform.release,
) -> dict[str, str]:
    """Return the local operating system identity without probing the network."""
    return {"name": system(), "version": release()}


def detect_python(
    version_info: Any = sys.version_info,
    executable: str = sys.executable,
) -> dict[str, str]:
    """Return Python identity; arguments make it deterministic in tests."""
    return {
        "version": ".".join(str(part) for part in version_info[:3]),
        "executable": executable,
    }


def detect_tool(
    command: str,
    *,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., Any] = subprocess.run,
) -> dict[str, str | bool | None]:
    """Detect a local executable and ask it for a version, if available."""
    executable = which(command)
    if not executable:
        return {"present": False, "version": None}
    try:
        result = run([command, "--version"], capture_output=True, text=True, check=False)
    except (OSError, subprocess.SubprocessError):
        return {"present": True, "version": None}
    if getattr(result, "returncode", 1) != 0:
        return {"present": True, "version": None}
    version = (getattr(result, "stdout", "") or "").strip().splitlines()
    return {"present": True, "version": version[0] if version else None}


def _expand_location(location: str, home: Path, root: Path) -> Path:
    if location.startswith("<home>/"):
        return home / location.removeprefix("<home>/")
    if location.startswith("<root>/"):
        return root / location.removeprefix("<root>/")
    return Path(location)


def detect_ai_apps(
    os_name: str,
    *,
    home: Callable[[], Path] = Path.home,
    root: Path = Path("/"),
    exists: Callable[[Path], bool] = Path.exists,
) -> list[str]:
    """Return installed AI app families from known local paths only."""
    home_path = home()
    locations = AI_APP_LOCATIONS.get(_platform_key(os_name), {})
    return [
        name
        for name, candidates in locations.items()
        if any(exists(_expand_location(candidate, home_path, root)) for candidate in candidates)
    ]


def _normal_path(path: str | Path) -> str:
    return str(path).replace("\\", "/").rstrip("/").casefold()


def _path_components(path: str | Path) -> tuple[str, ...]:
    """Return case-normalized components for either POSIX or Windows paths."""
    return tuple(component for component in _normal_path(path).split("/") if component)


def _is_within(path: str, parent: str) -> bool:
    return path == parent or path.startswith(parent + "/")


def _sync_engine_from_components(components: tuple[str, ...]) -> str | None:
    """Match only known provider folder components, never partial names."""
    for index, component in enumerate(components):
        previous = components[index - 1] if index else None

        # Windows uses ``OneDrive - Tenant``; macOS CloudStorage uses
        # ``OneDrive-Tenant``. The latter form is provider-specific only under
        # the CloudStorage parent, which avoids broad hyphen-prefix matches.
        if component == "onedrive" or (
            component.startswith("onedrive - ") and component.removeprefix("onedrive - ").strip()
        ):
            return "OneDrive"
        if (
            previous == "cloudstorage"
            and component.startswith("onedrive-")
            and component.removeprefix("onedrive-").strip()
        ):
            return "OneDrive"

        if component == "dropbox":
            return "Dropbox"

        if component == "icloud drive":
            return "iCloud Drive"
        if previous == "mobile documents" and component == "com~apple~clouddocs":
            return "iCloud Drive"

        # Older mounted folders use either spaced or joined names. Current
        # macOS CloudStorage folders add an account suffix to ``GoogleDrive``.
        if component in {"google drive", "googledrive"}:
            return "Google Drive"
        if (
            previous == "cloudstorage"
            and component.startswith("googledrive-")
            and component.removeprefix("googledrive-").strip()
        ):
            return "Google Drive"
    return None


def detect_sync_redirection(
    path: str | Path,
    *,
    env: Mapping[str, str] | None = None,
    home: Callable[[], Path] = Path.home,
) -> dict[str, bool | str]:
    """Identify common sync-engine locations from paths and environment markers."""
    del home  # Kept injectable for a uniform detection collaborator contract.
    normalized = _normal_path(path)
    environment = env if env is not None else __import__("os").environ
    for _, variables, engine in SYNC_ENVIRONMENT_MARKERS:
        for variable in variables:
            marker = environment.get(variable)
            if marker and _is_within(normalized, _normal_path(marker)):
                return {
                    "at_risk": True,
                    "reason": f"The path is inside the {engine} location from {variable}.",
                }
    engine = _sync_engine_from_components(_path_components(path))
    if engine is not None:
        return {
            "at_risk": True,
            "reason": f"The path contains a {engine} sync-location marker.",
        }
    return {"at_risk": False, "reason": "No common sync-redirection marker was found."}


def default_workspace(os_name: str, *, home: Callable[[], Path] = Path.home) -> Path:
    """Return the documented default workspace location for this operating system."""
    if _platform_key(os_name) == "windows":
        return Path("C:/Projects/Apparatus")
    return home() / "Projects" / "Apparatus"


def detect_machine(
    workspace: str | Path | None = None,
    *,
    system: Callable[[], str] = platform.system,
    release: Callable[[], str] = platform.release,
    version_info: Any = sys.version_info,
    executable: str = sys.executable,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., Any] = subprocess.run,
    env: Mapping[str, str] | None = None,
    home: Callable[[], Path] = Path.home,
    exists: Callable[[Path], bool] = Path.exists,
) -> dict[str, Any]:
    """Collect all doctor detections through injectable, local-only collaborators."""
    operating_system = detect_os(system=system, release=release)
    inspected_workspace = Path(workspace) if workspace is not None else default_workspace(
        operating_system["name"], home=home
    )
    return {
        "os": operating_system,
        "python": detect_python(version_info=version_info, executable=executable),
        "git": detect_tool("git", which=which, run=run),
        "uv": detect_tool("uv", which=which, run=run),
        "ai_apps": detect_ai_apps(operating_system["name"], home=home, exists=exists),
        "sync_redirection": detect_sync_redirection(inspected_workspace, env=env, home=home),
        "workspace": str(inspected_workspace),
    }
