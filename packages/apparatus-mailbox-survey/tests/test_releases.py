"""Content recognition is additive, bounded and independent of write authority."""

import copy
import hashlib
from importlib import resources
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from apparatus_core.workspace_layout import new_layout_bytes
from apparatus_mailbox_survey import __version__, deployment as deploy, releases
from apparatus_mailbox_survey.__main__ import main

BODY, REFERENCE = deploy.ASSETS
HISTORICAL = ["0.1.0", "0.1.1", "0.1.2", "0.1.3"]


@pytest.fixture
def area(tmp_path):
    root = tmp_path / "area"
    (root / "System").mkdir(parents=True)
    (root / "System/workspace.yaml").write_bytes(new_layout_bytes())
    return root


def manifest():
    return json.loads(resources.files("apparatus_mailbox_survey").joinpath("resources", "releases.json").read_bytes())


def historical_sources():
    return {BODY: Path(__file__).with_name("fixtures").joinpath("skill-0.1.0.md").read_bytes(),
            REFERENCE: deploy._sources(deploy._core())[REFERENCE]}


def write_assets(area, sources):
    for relative, content in sources.items():
        path = area / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def snapshot(area):
    return {str(path.relative_to(area)): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in area.rglob("*") if path.is_file()}


def inject_manifest(monkeypatch, content):
    class Resource:
        def joinpath(self, *parts):
            assert parts == ("resources", "releases.json")
            return self

        def open(self, mode):
            assert mode == "rb"
            class BoundedStream(io.BytesIO):
                def read(self, limit=-1):
                    assert limit == releases.MAX_MANIFEST_BYTES + 1
                    return super().read(limit)
            return BoundedStream(content)

    monkeypatch.setattr(releases, "resources", SimpleNamespace(files=lambda package: Resource()))


def test_historical_fixture_and_manifest_fingerprints():
    historical = historical_sources()
    data = manifest()
    assert [release["version"] for release in data["releases"]] == HISTORICAL
    assert [release["source_commit"] for release in data["releases"]] == [
        "7c59aa765f334541b1a5153e6322693ac2c3049b", "df1aeb47a58d2ad8a37528c9f03ad3e7fdddb0f0",
        "ea84f5757c6ff1ac6e9206a6c93738f5f1f5842e", "dcc679c9bf907a25cb6bdfe480f2d529bf67f2cd"]
    for release in data["releases"]:
        assert release["assets"] == {path: {"length": len(content), "sha256": hashlib.sha256(content).hexdigest()}
                                     for path, content in historical.items()}


def test_current_install_status_and_repair_cli(area, capsys):
    for action in ("install", "status", "repair"):
        assert main([action, str(area)]) == 0
        result = json.loads(capsys.readouterr().out)
        assert result["state"] == "current"
        assert result["version"] == __version__
        assert result["release_matches"] == {BODY: [__version__], REFERENCE: HISTORICAL + [__version__]}
        assert result["complete_release_matches"] == [__version__]
    (area / REFERENCE).unlink()
    assert main(["repair", str(area)]) == 0
    assert json.loads(capsys.readouterr().out)["complete_release_matches"] == [__version__]


def test_old_complete_matches_do_not_claim_current_and_status_is_readonly(area, capsys):
    write_assets(area, historical_sources())
    before = snapshot(area)
    assert main(["status", str(area)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["assets"] == {BODY: "modified", REFERENCE: "current"}
    assert result["state"] == "conflict"
    assert result["complete_release_matches"] == HISTORICAL
    assert result["release_matches"][BODY] == HISTORICAL
    assert snapshot(area) == before


@pytest.mark.parametrize("action", ["install", "repair"])
@pytest.mark.parametrize("content", ["historical", "edited"])
def test_old_or_edited_asset_blocks_every_creation(area, action, content):
    body = historical_sources()[BODY] if content == "historical" else b"Edited content"
    write_assets(area, {BODY: body})
    before = snapshot(area)
    result = deploy.operate(area)
    assert result["release_matches"][BODY] == (HISTORICAL if content == "historical" else [])
    assert result["release_matches"][REFERENCE] == []
    assert result["complete_release_matches"] == []
    with pytest.raises(deploy.DeploymentError) as error:
        deploy.operate(area, action)
    assert error.value.code == 1
    assert snapshot(area) == before
    assert not (area / deploy.SKILL_ROOT / "references").exists()


def test_absent_unknown_and_partial_matches(area):
    result = deploy.operate(area)
    assert result["release_matches"] == {BODY: [], REFERENCE: []}
    assert result["complete_release_matches"] == []
    write_assets(area, {BODY: b"Unknown", REFERENCE: b"Also unknown"})
    assert deploy.operate(area)["release_matches"] == result["release_matches"]
    (area / BODY).unlink()
    write_assets(area, {REFERENCE: historical_sources()[REFERENCE]})
    result = deploy.operate(area)
    assert result["release_matches"][REFERENCE] == HISTORICAL + [__version__]
    assert result["complete_release_matches"] == []


def test_mixed_known_assets_cannot_form_a_complete_release(area, monkeypatch):
    data = manifest()
    # Model a future independently changed companion while preserving complete
    # per-release entries. No shipped historical release had that change.
    reference = b"Known alternate reference"
    data["releases"][0]["assets"][REFERENCE] = releases._fingerprint(reference)
    inject_manifest(monkeypatch, json.dumps(data).encode())
    write_assets(area, {BODY: deploy._sources(deploy._core())[BODY], REFERENCE: reference})
    result = deploy.operate(area)
    assert result["release_matches"] == {BODY: [__version__], REFERENCE: ["0.1.0"]}
    assert result["complete_release_matches"] == []


def bad_manifests():
    base = manifest()
    yield b'{"PRIVATE_MARKER":'
    yield b"x" * (releases.MAX_MANIFEST_BYTES + 1)
    yield b"[" * 2000 + b"]" * 2000
    yield b'{"schema":"a","schema":"b","releases":[]}'
    yield json.dumps(base).replace('"length": 3102', '"length": NaN').encode()
    for change in (
        lambda data: data.update(extra="PRIVATE_MARKER"),
        lambda data: data.update(schema="unknown"),
        lambda data: data.update(releases=[]),
        lambda data: data.update(releases=data["releases"] * 9),
        lambda data: data["releases"].append(copy.deepcopy(data["releases"][0])),
        lambda data: data["releases"][0].update(extra=True),
        lambda data: data["releases"][0].update(version="01.2.3"),
        lambda data: data["releases"][0].update(version=__version__),
        lambda data: data["releases"][0].update(source_commit="a" * 39),
        lambda data: data["releases"][0].update(source_commit="A" * 40),
        lambda data: data["releases"][0]["assets"].update({"../PRIVATE_MARKER": {"length": 1, "sha256": "a" * 64}}),
        lambda data: data["releases"][0]["assets"].pop(BODY),
        lambda data: data["releases"][0]["assets"][BODY].update(length=True),
        lambda data: data["releases"][0]["assets"][BODY].update(length=0),
        lambda data: data["releases"][0]["assets"][BODY].update(length=deploy.MAX_ASSET_BYTES + 1),
        lambda data: data["releases"][0]["assets"][BODY].update(sha256="A" * 64),
        lambda data: data["releases"][0]["assets"][BODY].update(sha256="abc"),
        lambda data: data["releases"][0]["assets"][BODY].update(extra=True),
    ):
        data = copy.deepcopy(base)
        change(data)
        yield json.dumps(data).encode()


@pytest.mark.parametrize("content", list(bad_manifests()), ids=[
    "malformed-json", "oversized-manifest", "excessive-nesting", "duplicate-key", "non-json-number",
    "unknown-root-key", "unknown-schema", "empty-releases", "too-many-releases", "duplicate-version",
    "unknown-release-key", "noncanonical-version", "current-version", "short-source-commit",
    "uppercase-source-commit", "unknown-asset-path", "missing-asset", "boolean-length", "zero-length",
    "oversized-asset-length", "uppercase-digest", "short-digest", "unknown-asset-key",
])
@pytest.mark.parametrize("action", ["status", "install", "repair"])
def test_invalid_manifest_is_bounded_content_free_and_prevents_writes(area, monkeypatch, capsys, content, action):
    inject_manifest(monkeypatch, content)
    before = snapshot(area)
    assert main([action, str(area)]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "module: Packaged release manifest is invalid; reinstall the module package.\n"
    assert snapshot(area) == before
    assert not (area / ".agents").exists()


def test_report_commands_ignore_manifest(area, monkeypatch, capsys):
    inject_manifest(monkeypatch, b"Invalid manifest")
    report = area / "report.yaml"
    report.write_bytes(resources.files("apparatus_mailbox_survey").joinpath("resources", "report-example.yaml").read_bytes())
    assert main(["validate", str(report)]) == 0
    assert main(["summary", str(report)]) == 0
    assert capsys.readouterr().err == ""
