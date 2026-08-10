from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import shutil
import stat
import zipfile

import pytest
from apparatus_core.render import rendered_shims


REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_MANIFEST = REPO_ROOT / "conformance" / "golden" / "payload-manifest.txt"
BUILDER_PATH = REPO_ROOT / "tools" / "build_payload.py"

spec = importlib.util.spec_from_file_location("apparatus_build_payload", BUILDER_PATH)
assert spec is not None and spec.loader is not None
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def _golden_payload_paths() -> set[str]:
    return {
        line
        for line in GOLDEN_MANIFEST.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }


def _build(out: Path, *, version: str = "archive-test") -> Path:
    archive, drift = builder.build_payload(out, version=version)
    assert drift == ()
    return archive


def test_payload_archive_is_complete_freshly_rendered_hashed_and_reproducible(tmp_path):
    first = _build(tmp_path / "first")
    second = _build(tmp_path / "second")
    assert first.read_bytes() == second.read_bytes()

    with zipfile.ZipFile(first) as archive:
        names = archive.namelist()
        assert names == sorted(names)
        assert {name.removeprefix("payload/") for name in names if name.startswith("payload/")} == (
            _golden_payload_paths()
        )
        assert {name.removeprefix("profiles/") for name in names if name.startswith("profiles/")} == {
            "README.md",
            "profiles.yaml",
        }

        for shim in rendered_shims(REPO_ROOT / "starter" / "payload"):
            assert archive.read(f"payload/{shim.target}") == shim.content

        manifest_lines = archive.read("manifest.txt").decode("utf-8").splitlines()
        assert manifest_lines[0] == "version: archive-test"
        listed: dict[str, str] = {}
        for line in manifest_lines[1:]:
            digest, path = line.split("  ", 1)
            listed[path] = digest
        assert set(listed) == set(names) - {"manifest.txt"}
        assert list(listed) == sorted(listed)
        for path, digest in listed.items():
            assert hashlib.sha256(archive.read(path)).hexdigest() == digest

        for info in archive.infolist():
            assert info.date_time == (1980, 1, 1, 0, 0, 0)
            assert stat.S_IMODE(info.external_attr >> 16) == 0o644
            assert info.compress_type == zipfile.ZIP_STORED


def test_builder_uses_source_date_epoch_and_retains_gitkeep(tmp_path):
    archive, _drift = builder.build_payload(
        tmp_path, version="epoch-test", environ={"SOURCE_DATE_EPOCH": "315532802"}
    )
    with zipfile.ZipFile(archive) as built:
        assert all(info.date_time == (1980, 1, 1, 0, 0, 2) for info in built.infolist())
        assert "payload/Goals/.gitkeep" in built.namelist()


def test_builder_repairs_committed_shim_drift_and_reports_the_path(tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / "starter", repo / "starter")
    stale = repo / "starter" / "payload" / "CLAUDE.md"
    stale.write_text("stale shim\n", encoding="utf-8")

    archive, drift = builder.build_payload(tmp_path / "out", version="drift-test", repo_root=repo)

    assert drift == ("payload/CLAUDE.md",)
    with zipfile.ZipFile(archive) as built:
        expected = {shim.target: shim.content for shim in rendered_shims(repo / "starter" / "payload")}
        assert built.read("payload/CLAUDE.md") == expected["CLAUDE.md"]


def test_command_prints_each_drift_warning(monkeypatch, tmp_path, capsys):
    output = tmp_path / "apparatus-payload-test.zip"
    monkeypatch.setattr(
        builder,
        "build_payload",
        lambda _out, version=None: (output, ("payload/CLAUDE.md",)),
    )

    assert builder.main(["--out", str(tmp_path), "--version", "test"]) == 0
    captured = capsys.readouterr()
    assert captured.out == f"{output}\n"
    assert captured.err == (
        "warning: committed shim differs from fresh render: payload/CLAUDE.md\n"
    )


@pytest.mark.parametrize(
    "path",
    (
        "payload/../escape.md",
        "payload\\escape.md",
        "C:/escape.md",
        "payload/CON.txt",
        "payload/trailing.",
        "payload/name:stream",
        "payload/bad?.md",
        "payload/control\x01.md",
    ),
)
def test_archive_paths_reject_cross_platform_unsafe_names(path):
    with pytest.raises(builder.PayloadBuildError):
        builder.validate_archive_path(path)


def test_archive_paths_reject_portable_name_collisions():
    with pytest.raises(builder.PayloadBuildError, match="conflict on a supported platform"):
        builder.reject_portable_collisions(("payload/Name.md", "payload/name.md"))


def test_source_tree_filters_os_metadata_and_python_caches(tmp_path):
    source = tmp_path / "payload"
    source.mkdir()
    (source / "keep.md").write_text("keep", encoding="utf-8")
    (source / ".DS_Store").write_text("metadata", encoding="utf-8")
    cache = source / "__pycache__"
    cache.mkdir()
    (cache / "cached.pyc").write_bytes(b"cache")

    assert builder._source_files(source, "payload") == ((source / "keep.md", "payload/keep.md"),)


def test_source_tree_rejects_links_without_reading_their_targets(tmp_path):
    source = tmp_path / "payload"
    source.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside sentinel", encoding="utf-8")
    link = source / "linked.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are unavailable on this host")

    with pytest.raises(builder.PayloadBuildError, match="must not be a symbolic link"):
        builder._source_files(source, "payload")
    assert outside.read_text(encoding="utf-8") == "outside sentinel"


def test_missing_starter_tree_and_invalid_version_fail_clearly(tmp_path):
    with pytest.raises(builder.PayloadBuildError, match="starter payload tree is missing"):
        builder.build_payload(tmp_path / "out", version="test", repo_root=tmp_path)
    with pytest.raises(builder.PayloadBuildError, match="version must contain"):
        builder.validate_version("../unsafe")


def test_render_failure_and_unwritable_output_fail_clearly(tmp_path):
    repo = tmp_path / "repo"
    payload = repo / "starter" / "payload"
    profiles = repo / "starter" / "profiles"
    payload.mkdir(parents=True)
    profiles.mkdir(parents=True)
    (payload / "Welcome.md").write_text("welcome", encoding="utf-8")
    (profiles / "profiles.yaml").write_text("profiles", encoding="utf-8")
    with pytest.raises(builder.PayloadBuildError, match="could not render staged payload shims"):
        builder.build_payload(tmp_path / "out", version="test", repo_root=repo)

    blocked = tmp_path / "not-a-directory"
    blocked.write_text("blocked", encoding="utf-8")
    with pytest.raises(builder.PayloadBuildError, match="could not write payload archive"):
        builder.build_payload(blocked, version="test")
