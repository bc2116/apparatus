"""Bounded, fixed-path recognition of accepted module source versions."""

import hashlib
from importlib import resources
import json
import re

MAX_MANIFEST_BYTES = 65_536
MAX_RELEASES = 32


class ReleaseManifestError(ValueError):
    """The package's historical content inventory cannot be trusted."""


def _closed_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Non-JSON constant")


def _fingerprint(content):
    return {"length": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def _version(value):
    return (isinstance(value, str) and len(value) <= 32
            and re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", value))


def load_releases(sources, current_version, max_asset_bytes):
    """Validate the whole manifest before making current fingerprints available."""
    try:
        resource = resources.files("apparatus_mailbox_survey").joinpath("resources", "releases.json")
        with resource.open("rb") as stream:
            content = stream.read(MAX_MANIFEST_BYTES + 1)
        if len(content) > MAX_MANIFEST_BYTES:
            raise ValueError("Oversized manifest")
        manifest = json.loads(content.decode("utf-8"), object_pairs_hook=_closed_object,
                              parse_constant=_reject_constant)
        if (not isinstance(manifest, dict) or set(manifest) != {"schema", "releases"}
                or manifest["schema"] != "apparatus/mailbox-survey-releases@v1"
                or not isinstance(manifest["releases"], list)
                or not 1 <= len(manifest["releases"]) <= MAX_RELEASES
                or not _version(current_version)):
            raise ValueError("Invalid manifest")
        releases = {}
        for release in manifest["releases"]:
            if (not isinstance(release, dict) or set(release) != {"version", "source_commit", "assets"}
                    or not _version(release["version"])
                    or release["version"] == current_version
                    or release["version"] in releases
                    or not isinstance(release["source_commit"], str)
                    or not re.fullmatch(r"[0-9a-f]{40}", release["source_commit"])
                    or not isinstance(release["assets"], dict)
                    or set(release["assets"]) != set(sources)):
                raise ValueError("Invalid release")
            for asset in release["assets"].values():
                if (not isinstance(asset, dict) or set(asset) != {"length", "sha256"}
                        or type(asset["length"]) is not int
                        or not 1 <= asset["length"] <= max_asset_bytes
                        or not isinstance(asset["sha256"], str)
                        or not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"])):
                    raise ValueError("Invalid asset")
            releases[release["version"]] = release["assets"]
        releases[current_version] = {path: _fingerprint(content) for path, content in sources.items()}
        return releases
    except (OSError, ValueError, TypeError, RecursionError) as error:
        raise ReleaseManifestError("Packaged release manifest is invalid; reinstall the module package.") from error


def matching_releases(releases, path, content):
    """Use captured bytes only; this function never reads a deployed pathname."""
    expected = _fingerprint(content)
    return sorted((version for version, assets in releases.items() if assets[path] == expected),
                  key=lambda version: tuple(map(int, version.split("."))))
