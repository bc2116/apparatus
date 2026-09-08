"""Bounded native acceptance of an already-published, signed release.

Standard library only. Source metadata and artifacts are data, never commands.
No downloaded Python distribution is imported by this validator.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import urllib.request
import zipfile


REQUIRED_JOBS = {
    "Build release files", "Build Windows installer wrapper", "Build macOS installer wrapper",
    "Sign and notarize macOS installer", "Assemble release files and checksums",
    "Publish apparatus-core to PyPI",
}
WINDOWS_JOBS = {"Sign Windows installer", "Sign Windows installer with Azure Artifact Signing"}
MANAGED = ".agents/skills/apparatus-welcome/SKILL.md"
SENTINEL = b"Apparatus native installer acceptance: preserve this project file.\n"


class AcceptanceError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise AcceptanceError(message)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AcceptanceError("Authenticated GitHub metadata redirect refused")


def api(path):
    request = urllib.request.Request("https://api.github.com/" + path, headers={
        "Accept": "application/vnd.github+json", "Authorization": "Bearer " + os.environ["GH_TOKEN"],
        "X-GitHub-Api-Version": "2026-03-10",
    })
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
        return json.load(response)


def pages(path, field):
    result = []
    for page in range(1, 11):
        data = api(f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}")
        result.extend(data[field])
        if len(result) == data["total_count"]:
            return result
    raise AcceptanceError("Source metadata exceeds bounded pagination or changed during inspection")


def validate_source(run, jobs, repository, run_id, workflow_id, tag_sha):
    require(str(run.get("id")) == run_id, "Source run ID mismatch")
    require(run.get("repository", {}).get("full_name") == repository and
            run.get("head_repository", {}).get("full_name") == repository, "Source repository mismatch")
    require(run.get("workflow_id") == workflow_id and run.get("path") == ".github/workflows/release.yml",
            "Source must be the Release workflow")
    require(run.get("event") == "push", "Source must be a tagged push")
    tag = run.get("head_branch", "")
    require(re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag), "Source must use a stable version tag")
    require(re.fullmatch(r"[0-9a-f]{40}", run.get("head_sha", "")) and run["head_sha"] == tag_sha,
            "Version tag does not resolve to the source commit")
    counts = Counter(job.get("name") for job in jobs)
    for name in REQUIRED_JOBS | WINDOWS_JOBS:
        require(counts[name] == 1, "Missing or duplicate release job")
    by_name = {job["name"]: job for job in jobs}
    for name in REQUIRED_JOBS:
        require(by_name[name].get("conclusion") == "success", "Required release or publication job has not succeeded")
    conclusions = sorted(by_name[name].get("conclusion") or "pending" for name in WINDOWS_JOBS)
    require(conclusions == ["skipped", "success"], "Exactly one Windows signer must succeed and the other skip")
    return {"run_id": run_id, "run_attempt": run["run_attempt"], "tag": tag,
            "head_sha": tag_sha, "version": tag[1:], "repository": repository}


def acceptance_platforms(choice):
    choices = {"both": ["macos-15", "windows-2025"], "windows": ["windows-2025"], "macos": ["macos-15"]}
    require(choice in choices, "Acceptance platform must be both, windows or macos")
    return {"os": choices[choice]}


def resolve(run_id, repository, selected_platform="both"):
    matrix = acceptance_platforms(selected_platform)
    require(re.fullmatch(r"[1-9][0-9]{0,19}", run_id), "acceptance_run_id must be a positive numeric ID")
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository), "Invalid repository")
    root = f"repos/{repository}"
    run = api(f"{root}/actions/runs/{run_id}")
    tag = run.get("head_branch", "")
    require(re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag), "Source must use a stable version tag")
    obj = api(f"{root}/git/ref/tags/{tag}")["object"]
    for _ in range(5):
        if obj["type"] == "commit":
            break
        require(obj["type"] == "tag", "Unexpected tag object")
        obj = api(f"{root}/git/tags/{obj['sha']}")["object"]
    require(obj["type"] == "commit", "Tag nesting exceeds limit")
    workflow_id = api(f"{root}/actions/workflows/release.yml")["id"]
    jobs = pages(f"{root}/actions/runs/{run_id}/attempts/{run['run_attempt']}/jobs", "jobs")
    source = validate_source(run, jobs, repository, run_id, workflow_id, obj["sha"])
    artifacts = pages(f"{root}/actions/runs/{run_id}/artifacts", "artifacts")
    selected = [a for a in artifacts if a["name"] == "apparatus-release-" + source["version"]]
    require(len(selected) == 1 and not selected[0].get("expired"), "Expected one unexpired final release artifact")
    source["artifact_id"] = selected[0]["id"]
    source["artifact_digest"] = selected[0].get("digest")
    require(selected[0].get("workflow_run", {}).get("head_sha") == source["head_sha"], "Artifact commit mismatch")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
        stream.write(f"artifact_id={source['artifact_id']}\n")
        stream.write("source=" + json.dumps(source, separators=(",", ":")) + "\n")
        stream.write("matrix=" + json.dumps(matrix, separators=(",", ":")) + "\n")


def regular(path):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and not getattr(info, "st_file_attributes", 0) &
            getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0), "Expected an ordinary file")


def digest(path):
    regular(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_artifact(directory, version, pypi):
    require(directory.is_dir() and not directory.is_symlink(), "Artifact directory is unavailable")
    entries = list(directory.iterdir())
    for entry in entries:
        regular(entry)
    names = {entry.name for entry in entries}
    sdists = {n for n in names if n == f"apparatus_core-{version}.tar.gz"}
    wheels = {n for n in names if re.fullmatch(r"apparatus_core-" + re.escape(version) + r"-[A-Za-z0-9_.]+-[A-Za-z0-9_.]+-[A-Za-z0-9_.]+\.whl", n)}
    fixed = {f"apparatus-payload-{version}.zip", "bootstrap-apparatus.sh", "bootstrap-apparatus.ps1",
             "apparatus-installer.pkg", "apparatus-installer.exe"}
    require(len(sdists) == len(wheels) == 1 and names == fixed | sdists | wheels | {"release-notes.md", "SHA256SUMS"},
            "Release artifact must contain exactly seven distributables, notes and checksums")
    hashes = {}
    for line in (directory / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *]([^/\\]+)", line)
        require(match is not None, "Invalid checksum entry")
        checksum, name = match.groups()
        require(name not in hashes and name in fixed | sdists | wheels, "Unexpected or duplicate checksum entry")
        require(digest(directory / name) == checksum, "Release artifact checksum mismatch")
        hashes[name] = checksum
    require(set(hashes) == fixed | sdists | wheels, "Incomplete release checksums")
    require(pypi.get("info", {}).get("version") == version, "PyPI version mismatch")
    for name in sdists | wheels:
        records = [r for r in pypi.get("urls", []) if r.get("filename") == name]
        require(len(records) == 1 and not records[0].get("yanked") and
                records[0].get("digests", {}).get("sha256") == hashes[name], "PyPI distribution hash mismatch or unavailable package")
    return hashes


def child_environment():
    if platform.system() != "Windows":
        return None
    # PowerShell 7 -> Python -> Windows PowerShell otherwise retains incompatible
    # module paths. Clean only child environments, including installer descendants.
    return {key: value for key, value in os.environ.items() if key.casefold() != "psmodulepath"}


def command(args, receipt, stage, timeout=900):
    try:
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=timeout, check=False, env=child_environment())
    except subprocess.TimeoutExpired:
        receipt["commands"].append({"stage": stage, "result": "timeout"})
        raise AcceptanceError(stage + " exceeded its time limit") from None
    receipt["commands"].append({"stage": stage, "exit_code": result.returncode})
    require(result.returncode == 0, stage + " failed")
    return result.stdout.strip()


def clean_target(target):
    require(not target.is_symlink(), "Default target must not be a symlink")
    if target.exists():
        info = target.lstat()
        require(stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) &
                getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0) and not any(target.iterdir()),
                "Default target already contains work or is redirected; acceptance unavailable")


def require_installer_identity(signature_output):
    # pkgutil status prose varies by OS; native success plus the Installer
    # certificate identity is combined with Gatekeeper and stapler below.
    require(re.search(r"(?m)^\s*[0-9]+\.\s+Developer ID Installer: [^\r\n]+$", signature_output),
            "Package signature does not identify a Developer ID Installer certificate")


WINDOWS_SIGNATURE_PROBE = r"""
$ErrorActionPreference = 'Stop'
$result = [ordered]@{
    engine_version = [string]$PSVersionTable.PSVersion
    status = 'unavailable'
    signer_present = $false
    timestamp_present = $false
    failure_category = 'none'
}
try {
    $signature = Get-AuthenticodeSignature -LiteralPath $env:APPARATUS_ACCEPTANCE_INSTALLER -ErrorAction Stop
    $result.status = [string]$signature.Status
    $result.signer_present = $null -ne $signature.SignerCertificate
    $result.timestamp_present = $null -ne $signature.TimeStamperCertificate
} catch {
    $result.failure_category = 'verifier_exception'
}
$result | ConvertTo-Json -Compress
"""


def require_windows_signature(output, receipt):
    # Only this fixed schema reaches durable evidence. Reject extra output,
    # duplicate keys and unknown values without retaining any raw diagnostics.
    def unique_object(pairs):
        require(len(pairs) == len({key for key, _ in pairs}), "Malformed signature diagnostics")
        return dict(pairs)
    require(isinstance(output, str) and len(output) <= 2048, "Malformed signature diagnostics")
    try:
        data = json.loads(output, object_pairs_hook=unique_object)
    except (ValueError, TypeError):
        raise AcceptanceError("Malformed signature diagnostics") from None
    require(isinstance(data, dict) and set(data) == {
        "engine_version", "status", "signer_present", "timestamp_present", "failure_category"
    }, "Malformed signature diagnostics")
    require(isinstance(data["engine_version"], str) and
            re.fullmatch(r"[0-9]{1,5}(?:\.[0-9]{1,6}){1,3}", data["engine_version"]) and
            isinstance(data["status"], str) and data["status"] in {"Valid", "UnknownError", "NotSigned", "HashMismatch", "NotTrusted",
                                "NotSupportedFileFormat", "Incompatible", "unavailable"} and
            type(data["signer_present"]) is bool and type(data["timestamp_present"]) is bool and
            isinstance(data["failure_category"], str) and data["failure_category"] in {"none", "verifier_exception"}, "Malformed signature diagnostics")
    receipt["windows_signature"] = data
    require(data["failure_category"] == "none" and data["status"] == "Valid" and
            data["signer_present"] and data["timestamp_present"],
            "Windows signature verification did not establish a valid signer and timestamp")


def native(directory, source, receipt):
    system = platform.system()
    receipt.update(platform=system, architecture=platform.machine(), os_version=platform.platform())
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "Native acceptance is restricted to fresh GitHub-hosted runners")
    if system == "Darwin":
        import pwd
        name = command(["/usr/bin/stat", "-f", "%Su", "/dev/console"], receipt, "console lookup", 30)
        require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) and name not in {"root", "loginwindow", "nobody"},
                "No actual logged-in Mac console user; native acceptance unavailable")
        user = pwd.getpwnam(name)
        # Resolve the actual console account through the system user database;
        # never substitute the invoking process's HOME or a fabricated profile.
        home = Path(user.pw_dir)
        require(home.is_absolute() and home.is_dir() and not home.is_symlink() and
                home.stat().st_uid == user.pw_uid and user.pw_uid == os.getuid() and user.pw_uid > 0,
                "The fresh runner must be the real console owner with an owned home")
        command(["/bin/launchctl", "print", f"gui/{user.pw_uid}"], receipt, "real console session", 30)
        target = home / "Projects"
        installer = directory / "apparatus-installer.pkg"
        output = command(["/usr/sbin/pkgutil", "--check-signature", str(installer)], receipt, "package signature", 60)
        require_installer_identity(output)
        command(["/usr/sbin/spctl", "--assess", "--type", "install", str(installer)], receipt, "Gatekeeper assessment", 120)
        command(["/usr/bin/xcrun", "stapler", "validate", str(installer)], receipt, "notarization ticket", 120)
        install = ["/usr/bin/sudo", "-n", "/usr/sbin/installer", "-pkg", str(installer), "-target", "/"]
        app = home / ".local/bin/apparatus"
    elif system == "Windows":
        require(platform.machine().lower() in {"amd64", "x86_64"}, "Windows x64 is required")
        home = Path(os.environ["USERPROFILE"])
        require(home.is_absolute() and home.is_dir() and not home.is_symlink(), "Normal Windows user profile required")
        output = command(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                          "$id=[Security.Principal.WindowsIdentity]::GetCurrent(); if ($id.IsSystem -or $id.User.Value -in @('S-1-5-18','S-1-5-19','S-1-5-20')) { exit 1 }"], receipt, "Windows user context", 30)
        target = Path("C:/Projects")
        installer = directory / "apparatus-installer.exe"
        # The path comes from the fixed local artifact directory, never source metadata.
        env_path = str(installer)
        os.environ["APPARATUS_ACCEPTANCE_INSTALLER"] = env_path
        diagnostics = command(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                               WINDOWS_SIGNATURE_PROBE], receipt, "Authenticode and timestamp", 120)
        require_windows_signature(diagnostics, receipt)
        install = [str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
        app = home / ".local/bin/apparatus.exe"
    else:
        raise AcceptanceError("Unsupported native acceptance platform")
    clean_target(target)
    require(not app.exists(), "Runner already has Apparatus installed; clean install unavailable")
    command(install, receipt, "native install")
    version_output = command([str(app), "--version"], receipt, "installed version", 60)
    require(version_output.split()[-1] == source["version"], "Installed package is not the selected published version")
    receipt["installed_version"] = source["version"]
    command([str(app), "check", str(target)], receipt, "installed workspace check", 120)
    repair = target / MANAGED
    regular(repair)
    original = repair.read_bytes()
    with zipfile.ZipFile(directory / f"apparatus-payload-{source['version']}.zip") as archive:
        matches = [n for n in archive.namelist() if n == "payload/" + MANAGED]
        require(len(matches) == 1 and archive.read(matches[0]) == original, "Repair target is not unchanged shipped content")
    sentinel = target / "acceptance-project" / "preserve.txt"
    sentinel.parent.mkdir()
    sentinel.write_bytes(SENTINEL)
    repair.unlink()
    command(install, receipt, "native repair")
    require(repair.read_bytes() == original and sentinel.read_bytes() == SENTINEL, "Repair or project preservation failed")
    require(command([str(app), "--version"], receipt, "repaired version", 60).split()[-1] == source["version"], "Repair changed the selected package version")
    command([str(app), "check", str(target)], receipt, "repaired workspace check", 120)
    receipt.update(repaired_file=MANAGED, repaired_sha256=hashlib.sha256(original).hexdigest(),
                   sentinel_sha256=hashlib.sha256(SENTINEL).hexdigest(), result="passed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["resolve", "native"])
    args = parser.parse_args()
    if args.mode == "resolve":
        resolve(os.environ["ACCEPTANCE_RUN_ID"], os.environ["GITHUB_REPOSITORY"],
                os.environ.get("ACCEPTANCE_PLATFORM", "both"))
        return
    source = json.loads(os.environ["ACCEPTANCE_SOURCE"])
    receipt = {"source": source, "result": "failed", "commands": [], "limitations": [
        "Native command-line Installer/wrapper execution; interactive GUI presentation not tested.",
        "Fresh hosted runner includes preinstalled tools; this is not a bare operating-system image.",
    ]}
    try:
        version = source["version"]
        require(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version), "Invalid source version")
        directory = Path("acceptance-files").absolute()
        with urllib.request.urlopen(f"https://pypi.org/pypi/apparatus-core/{version}/json", timeout=30) as response:
            pypi = json.load(response)
        receipt["hashes"] = validate_artifact(directory, version, pypi)
        native(directory, source, receipt)
    except AcceptanceError as error:
        receipt["reason"] = str(error)  # Authored messages only, never command output.
        raise
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        receipt["reason"] = "Metadata, artifact or native verification unavailable"
        raise
    finally:
        Path("acceptance-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except AcceptanceError as error:
        print("Acceptance stopped: " + str(error), file=sys.stderr)
        sys.exit(1)
    except Exception:
        print("Acceptance stopped: metadata, artifact or native verification failed.", file=sys.stderr)
        sys.exit(1)
