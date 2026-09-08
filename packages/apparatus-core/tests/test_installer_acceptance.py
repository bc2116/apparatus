"""Acceptance-source and byte validation without executing real installers."""
import copy
import hashlib
import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("installer_acceptance", ROOT / "tools/installer_acceptance/acceptance.py")
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)


def source():
    run = {"id": 12, "repository": {"full_name": "owner/product"}, "head_repository": {"full_name": "owner/product"},
           "workflow_id": 3, "path": ".github/workflows/release.yml", "event": "push", "head_branch": "v1.2.3",
           "head_sha": "a" * 40, "run_attempt": 1}
    jobs = [{"name": name, "conclusion": "success"} for name in a.REQUIRED_JOBS]
    jobs.extend([{"name": "Sign Windows installer", "conclusion": "skipped"},
                 {"name": "Sign Windows installer with Azure Artifact Signing", "conclusion": "success"}])
    return run, jobs


def test_source_allows_public_release_gate_to_remain_waiting():
    run, jobs = source()
    jobs.append({"name": "Create GitHub Release", "conclusion": None})
    result = a.validate_source(run, jobs, "owner/product", "12", 3, "a" * 40)
    assert result["version"] == "1.2.3"


@pytest.mark.parametrize("field,value", [
    ("event", "workflow_dispatch"), ("head_branch", "main"), ("head_branch", "v1.2.3\nmalicious"),
    ("head_branch", "v1.2.3/other"), ("head_sha", "b" * 40), ("workflow_id", 4),
    ("path", ".github/workflows/other.yml"), ("repository", {"full_name": "other/product"}),
    ("head_repository", {"full_name": "fork/product"}), ("id", 13),
])
def test_wrong_source_is_rejected(field, value):
    run, jobs = source()
    run[field] = value
    with pytest.raises(a.AcceptanceError):
        a.validate_source(run, jobs, "owner/product", "12", 3, "a" * 40)


@pytest.mark.parametrize("problem", ["both_signers", "failed_signer", "missing_signer", "duplicate_signer", "skipped_publish", "failed_build"])
def test_incomplete_or_ambiguous_release_jobs_rejected(problem):
    run, jobs = source()
    if problem == "both_signers":
        jobs[-2]["conclusion"] = "success"
    elif problem == "failed_signer":
        jobs[-2]["conclusion"] = "failure"
    elif problem == "missing_signer":
        jobs.pop()
    elif problem == "duplicate_signer":
        jobs.append(copy.deepcopy(jobs[-1]))
    else:
        wanted = "Publish apparatus-core to PyPI" if problem == "skipped_publish" else "Build release files"
        next(j for j in jobs if j["name"] == wanted)["conclusion"] = "skipped" if problem == "skipped_publish" else "failure"
    with pytest.raises(a.AcceptanceError):
        a.validate_source(run, jobs, "owner/product", "12", 3, "a" * 40)


@pytest.mark.parametrize("run_id", ["", "0", "-1", "12\n", "12/other", "abc", "1" * 21])
def test_bad_run_id_fails_before_api(run_id, monkeypatch):
    monkeypatch.setattr(a, "api", lambda *_: pytest.fail("Invalid ID reached API"))
    with pytest.raises(a.AcceptanceError):
        a.resolve(run_id, "owner/product")


def artifact(tmp_path):
    version = "1.2.3"
    names = ["apparatus-payload-1.2.3.zip", "apparatus_core-1.2.3.tar.gz", "apparatus_core-1.2.3-py3-none-any.whl",
             "bootstrap-apparatus.sh", "bootstrap-apparatus.ps1", "apparatus-installer.exe", "apparatus-installer.pkg"]
    hashes = {}
    for name in names:
        (tmp_path / name).write_bytes(("synthetic " + name).encode())
        hashes[name] = hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
    (tmp_path / "release-notes.md").write_text("Synthetic notes\n")
    (tmp_path / "SHA256SUMS").write_text("".join(f"{value}  {name}\n" for name, value in hashes.items()))
    pypi = {"info": {"version": version}, "urls": [{"filename": name, "digests": {"sha256": value}, "yanked": False}
            for name, value in hashes.items() if name.endswith((".whl", ".tar.gz"))]}
    return pypi, hashes


def test_exact_artifact_matches_published_distribution_hashes(tmp_path):
    pypi, hashes = artifact(tmp_path)
    assert a.validate_artifact(tmp_path, "1.2.3", pypi) == hashes


@pytest.mark.parametrize("problem", ["extra", "missing", "tampered", "duplicate_checksum", "missing_checksum", "path_checksum", "pypi_hash", "pypi_version", "yanked", "duplicate_pypi", "directory"])
def test_artifact_rejects_unsafe_or_unpublished_bytes(tmp_path, problem):
    pypi, _ = artifact(tmp_path)
    sums = tmp_path / "SHA256SUMS"
    if problem == "extra":
        (tmp_path / "extra.exe").write_bytes(b"extra")
    elif problem == "missing":
        (tmp_path / "apparatus-installer.pkg").unlink()
    elif problem == "tampered":
        (tmp_path / "apparatus-installer.pkg").write_bytes(b"tampered")
    elif problem == "duplicate_checksum":
        sums.write_text(sums.read_text() + sums.read_text().splitlines()[0] + "\n")
    elif problem == "missing_checksum":
        sums.write_text("\n".join(sums.read_text().splitlines()[1:]))
    elif problem == "path_checksum":
        sums.write_text(sums.read_text().replace("  apparatus-", "  ../apparatus-", 1))
    elif problem == "pypi_hash":
        pypi["urls"][0]["digests"]["sha256"] = "0" * 64
    elif problem == "pypi_version":
        pypi["info"]["version"] = "9.9.9"
    elif problem == "yanked":
        pypi["urls"][0]["yanked"] = True
    elif problem == "duplicate_pypi":
        pypi["urls"].append(copy.deepcopy(pypi["urls"][0]))
    else:
        path = tmp_path / "apparatus-installer.pkg"
        path.unlink()
        path.mkdir()
    with pytest.raises(a.AcceptanceError):
        a.validate_artifact(tmp_path, "1.2.3", pypi)


def test_symlink_artifact_rejected(tmp_path):
    pypi, _ = artifact(tmp_path)
    target = tmp_path / "apparatus-installer.pkg"
    target.unlink()
    try:
        target.symlink_to(tmp_path / "apparatus-installer.exe")
    except OSError:
        pytest.skip("Symlinks unavailable")
    with pytest.raises(a.AcceptanceError):
        a.validate_artifact(tmp_path, "1.2.3", pypi)


def test_existing_target_not_adopted_or_removed(tmp_path):
    sentinel = tmp_path / "existing.txt"
    sentinel.write_text("Preserve")
    with pytest.raises(a.AcceptanceError):
        a.clean_target(tmp_path)
    assert sentinel.read_text() == "Preserve"


def test_unavailable_console_stops_before_native_install(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "github-hosted")
    monkeypatch.setattr(a.platform, "system", lambda: "Darwin")
    calls = []
    def command(args, *rest):
        calls.append(args)
        return "root"
    monkeypatch.setattr(a, "command", command)
    with pytest.raises(a.AcceptanceError, match="No actual logged-in"):
        a.native(tmp_path, {"version": "1.2.3"}, {"commands": []})
    assert len(calls) == 1
    assert calls[0][-1] == "/dev/console"


def test_acceptance_mode_has_no_release_credentials_or_write_permissions():
    workflow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    jobs = workflow["jobs"]
    assert "inputs.acceptance_run_id == ''" in jobs["build"]["if"]
    assert "inputs.acceptance_run_id != ''" in jobs["acceptance-source"]["if"]
    assert "github.event_name == 'workflow_dispatch'" in jobs["acceptance-source"]["if"]
    assert jobs["acceptance-native"]["needs"] == "acceptance-source"
    assert jobs["acceptance-native"]["strategy"]["matrix"]["os"] == ["macos-15", "windows-2025"]
    for name in ["acceptance-source", "acceptance-native"]:
        job = jobs[name]
        assert job["permissions"] == {"contents": "read", "actions": "read"}
        assert "environment" not in job
        assert "secrets." not in str(job)
        assert job["steps"][0]["with"]["persist-credentials"] is False
    download = jobs["acceptance-native"]["steps"][1]
    assert download["with"]["artifact-ids"] == "${{ needs.acceptance-source.outputs.artifact_id }}"
    assert download["with"]["run-id"] == "${{ inputs.acceptance_run_id }}"


@pytest.mark.parametrize("status", [
    "signed by a certificate trusted by macOS",
    "signed by a developer certificate issued by Apple for distribution",
])
def test_supported_pkgutil_status_prose_with_installer_identity(status):
    a.require_installer_identity(f"Status: {status}\nCertificate Chain:\n  1. Developer ID Installer: Example Publisher (SYNTHETIC1)\n")


@pytest.mark.parametrize("output", ["Status: no signature", "1. Developer ID Application: Example Publisher", "Not a certificate line Developer ID Installer: Example"])
def test_unsigned_or_wrong_mac_certificate_kind_rejected(output):
    with pytest.raises(a.AcceptanceError):
        a.require_installer_identity(output)


def test_authenticated_metadata_redirect_is_refused():
    from urllib.request import Request
    request = Request("https://api.github.com/repos/example/product", headers={"Authorization": "Bearer synthetic"})
    with pytest.raises(a.AcceptanceError, match="redirect refused"):
        a.NoRedirect().redirect_request(request, None, 302, "redirect", {}, "https://elsewhere.example/")


@pytest.fixture
def synthetic_native_boundary(tmp_path, monkeypatch):
    """Map the fixed Windows OS target into disposable files; mock commands only."""
    import zipfile
    home = tmp_path / "synthetic-profile"
    home.mkdir()
    target = tmp_path / "synthetic-projects"
    artifact_directory = tmp_path / "artifact"
    artifact_directory.mkdir()
    original = b"Synthetic unchanged shipped managed file\n"
    with zipfile.ZipFile(artifact_directory / "apparatus-payload-1.2.3.zip", "w") as archive:
        archive.writestr("payload/" + a.MANAGED, original)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "github-hosted")
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("APPARATUS_ACCEPTANCE_INSTALLER", "")
    monkeypatch.setattr(a.platform, "system", lambda: "Windows")
    monkeypatch.setattr(a.platform, "machine", lambda: "AMD64")
    # Keep real filesystem checks and mutations; replace only the unavailable
    # Windows drive-root namespace on the test host.
    monkeypatch.setattr(a, "Path", lambda value: target if value == "C:/Projects" else Path(value))
    return home, target, artifact_directory, original


def test_installed_version_mismatch_stops_before_managed_file_removal(synthetic_native_boundary, monkeypatch):
    home, target, artifact_directory, original = synthetic_native_boundary
    managed = target / a.MANAGED
    stages = []
    def external_command(args, receipt, stage, timeout=900):
        stages.append(stage)
        if stage == "native install":
            managed.parent.mkdir(parents=True)
            managed.write_bytes(original)
        if stage == "installed version":
            return "9.9.9"
        return ""
    monkeypatch.setattr(a, "command", external_command)
    receipt = {"commands": [], "result": "failed"}
    with pytest.raises(a.AcceptanceError, match="not the selected published version"):
        a.native(artifact_directory, {"version": "1.2.3"}, receipt)
    assert managed.read_bytes() == original
    assert not (target / "acceptance-project").exists()
    assert "native repair" not in stages
    assert receipt["result"] != "passed"


@pytest.mark.parametrize("repair_result", ["command_failure", "different_bytes"])
def test_failed_or_mismatched_repair_preserves_sentinel_without_success(synthetic_native_boundary, monkeypatch, repair_result):
    home, target, artifact_directory, original = synthetic_native_boundary
    managed = target / a.MANAGED
    stages = []
    def external_command(args, receipt, stage, timeout=900):
        stages.append(stage)
        if stage == "native install":
            managed.parent.mkdir(parents=True)
            managed.write_bytes(original)
        elif stage == "native repair":
            assert not managed.exists(), "The bounded repair must remove its selected file first"
            if repair_result == "command_failure":
                raise a.AcceptanceError("Synthetic native repair failure")
            managed.write_bytes(b"Different synthetic repair bytes\n")
        if stage == "installed version":
            return "1.2.3"
        return ""
    monkeypatch.setattr(a, "command", external_command)
    receipt = {"commands": [], "result": "failed"}
    with pytest.raises(a.AcceptanceError, match="repair failure|Repair or project preservation failed"):
        a.native(artifact_directory, {"version": "1.2.3"}, receipt)
    assert (target / "acceptance-project/preserve.txt").read_bytes() == a.SENTINEL
    assert stages.count("native repair") == 1
    assert "repaired workspace check" not in stages
    assert receipt["result"] != "passed"
