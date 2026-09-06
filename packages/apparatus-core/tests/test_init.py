from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest

from apparatus_core import records
from apparatus_core import init_deploy
from apparatus_core import payload as payload_module
from apparatus_core.check import check_workspace
from apparatus_core.commands import init
from apparatus_core.overlays import (
    OverlayPlan,
    OverlayWrite,
    apply_overlay_plan,
    load_manifest,
    plan_overlay,
)
from apparatus_core.payload import (
    PayloadError,
    PayloadFile,
    PayloadPlan,
    deploy_missing_payload_files,
    plan_payload_deployment,
    shipped_payload,
)
from apparatus_core.receipts import write_receipt
from apparatus_core.fs_transactions import (
    ReplacementTransaction,
    WorkspaceAnchor,
)
from apparatus_core.snapshots import SnapshotError, list_snapshots


HAS_GIT = shutil.which("git") is not None


def _args(workspace: Path, **kwargs) -> argparse.Namespace:
    return argparse.Namespace(
        workspace=str(workspace),
        privacy_mode=kwargs.get("privacy_mode"),
        work_types=kwargs.get("work_types"),
        payload=kwargs.get("payload"),
        adopt=kwargs.get("adopt", True),
        task=kwargs.get("task"),
    )


def _profile(workspace: Path) -> dict:
    return records.yaml.safe_load((workspace / "System/profile.yaml").read_text(encoding="utf-8"))


def _receipt_events(workspace: Path) -> list[str]:
    return [
        records.parse_record(path.read_text(encoding="utf-8"))[0]["event"]
        for path in sorted((workspace / "System/receipts").glob("*.md"))
    ]


def _tree_state(root: Path) -> tuple[tuple[str, str, bytes | str], ...]:
    if not root.exists() and not root.is_symlink():
        return ((".", "missing", b""),)
    entries: list[tuple[str, str, bytes | str]] = [(".", "directory", b"")]
    for directory, directory_names, file_names in os.walk(root, topdown=True, followlinks=False):
        directory_names.sort()
        file_names.sort()
        parent = Path(directory)
        for name in (*directory_names, *file_names):
            path = parent / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                entries.append((relative, "symlink", os.readlink(path)))
            elif path.is_dir():
                entries.append((relative, "directory", b""))
            else:
                entries.append((relative, "file", path.read_bytes()))
    return tuple(entries)


def _custom_payload(root: Path) -> Path:
    payload = root / "payload"
    shutil.copytree(shipped_payload(), payload)
    return payload


def _rollback_deployment_plan() -> tuple[PayloadPlan, OverlayPlan, bytes]:
    payload_plan = PayloadPlan(
        directories=(Path("System/policy"), Path("Scratch/Nested")),
        files=(
            PayloadFile(Path("payload-one.md"), b"payload one\n"),
            PayloadFile(Path("Scratch/Nested/payload-two.md"), b"payload two\n"),
        ),
        placeholders=(Path("System/policy/payload-placeholder.md"),),
    )
    overlay_plan = OverlayPlan(
        writes=(
            OverlayWrite("System/policy/managed-one.md", b"managed one new\n"),
            OverlayWrite("System/policy/managed-two.md", b"managed two new\n"),
        ),
        removals=(
            "System/policy/obsolete-one.md",
            "System/policy/obsolete-two.md",
        ),
    )
    return payload_plan, overlay_plan, b"profile new\n"


def _seed_rollback_workspace(workspace: Path) -> None:
    policy = workspace / "System/policy"
    policy.mkdir(parents=True)
    (workspace / "foreign.md").write_bytes(b"foreign\n")
    (workspace / "System/profile.yaml").write_bytes(b"profile original\n")
    (policy / "managed-one.md").write_bytes(b"managed one original\n")
    (policy / "managed-two.md").write_bytes(b"managed two original\n")
    (policy / "payload-placeholder.md").write_bytes(b"placeholder original\n")
    (policy / "obsolete-one.md").write_bytes(b"obsolete one original\n")
    (policy / "obsolete-two.md").write_bytes(b"obsolete two original\n")


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_fresh_init_deploys_check_clean_workspace_and_initial_snapshot(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    assert init.run(_args(workspace)) == 0
    assert "Workspace created." in capsys.readouterr().out
    assert _profile(workspace) == {
        "schema": "apparatus/profile@v0",
        "status": "unconfigured",
        "privacy_mode": "standard",
        "work_types": ["analysis", "quality", "project-management", "support", "writing"],
        "review_day": None,
        "spend": "balanced",
    }
    assert not list(workspace.rglob(".gitkeep"))
    assert check_workspace(workspace).ok
    assert _receipt_events(workspace).count("init") == 1
    assert _receipt_events(workspace).count("snapshot") == 1
    snapshots = list_snapshots(workspace)
    assert len(snapshots) == 1
    assert snapshots[0].label == "Workspace created"
    before = list((workspace / "System/receipts").glob("*.md"))
    assert check_workspace(workspace).ok
    assert list((workspace / "System/receipts").glob("*.md")) == before


@pytest.mark.skipif(not HAS_GIT, reason="git is unavailable")
def test_repeat_preserves_unmanaged_bytes_repairs_tree_and_updates_profile(tmp_path):
    workspace = tmp_path / "workspace"
    assert init.run(_args(workspace)) == 0
    user_file = workspace / "Projects/user.bin"
    user_file.parent.mkdir()
    user_file.write_bytes(b"keep\x00all\xffbytes")
    welcome = workspace / "Welcome.md"
    welcome.write_bytes(b"my welcome\x00edit")
    user_procedure = workspace / "System/procedures/user-added.md"
    user_procedure_bytes = (
        b"---\nschema: apparatus/procedure@v0\ntitle: User added\n"
        b"intent: Preserve this procedure.\n---\nUser procedure bytes.\n"
    )
    user_procedure.write_bytes(user_procedure_bytes)
    shutil.rmtree(workspace / "Goals")
    assert init.run(_args(workspace, privacy_mode="private")) == 0
    assert user_file.read_bytes() == b"keep\x00all\xffbytes"
    assert welcome.read_bytes() == b"my welcome\x00edit"
    assert user_procedure.read_bytes() == user_procedure_bytes
    assert (workspace / "Goals").is_dir()
    assert _profile(workspace)["privacy_mode"] == "private"
    assert (workspace / "System/policy/standard.md").is_file()
    assert (workspace / "System/policy/private.md").is_file()
    assert check_workspace(workspace).ok


def test_redirected_path_warns_and_records_sync_note_with_unavailable_snapshots(tmp_path, capsys):
    workspace = tmp_path / "OneDrive" / "workspace"
    assert init.run(_args(workspace), available=lambda: False) == 0
    output = capsys.readouterr().out
    assert "Warning:" in output
    assert "Snapshots are unavailable" in output
    receipt = next((workspace / "System/receipts").glob("*-init.md"))
    assert "OneDrive" in receipt.read_text(encoding="utf-8")
    assert _receipt_events(workspace).count("snapshot") == 1
    assert check_workspace(workspace).ok


def test_invalid_existing_profile_exits_before_mutating_workspace(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    (workspace / "System").mkdir(parents=True)
    profile = workspace / "System/profile.yaml"
    profile.write_text("schema: wrong\n", encoding="utf-8")
    before = profile.read_bytes()
    assert init.run(_args(workspace), available=lambda: False) == 2
    assert "existing System/profile.yaml is invalid" in capsys.readouterr().out
    assert profile.read_bytes() == before
    assert not (workspace / "Welcome.md").exists()


def test_empty_existing_work_types_keep_all_managed_starter_procedures(tmp_path):
    workspace = tmp_path / "workspace"
    assert init.run(_args(workspace), available=lambda: False) == 0
    profile = _profile(workspace)
    profile["work_types"] = []
    (workspace / "System/profile.yaml").write_text(
        records.yaml.safe_dump(profile, sort_keys=False), encoding="utf-8"
    )
    for path in (workspace / "System/procedures").glob("*.md"):
        path.unlink()
    assert init.run(_args(workspace), available=lambda: False) == 0
    assert _profile(workspace)["work_types"] == []
    assert len(list((workspace / "System/procedures").glob("*.md"))) == 5


def test_work_type_flags_are_trimmed_validated_and_canonicalized_before_deployment(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    assert init.run(_args(workspace, work_types=" writing,analysis "), available=lambda: False) == 0
    assert _profile(workspace)["work_types"] == ["analysis", "writing"]
    bad = tmp_path / "bad"
    assert init.run(_args(bad, work_types="analysis,,writing"), available=lambda: False) == 2
    assert "no empty names" in capsys.readouterr().out
    assert not bad.exists()


def test_custom_payload_prefers_its_sibling_profiles_manifest(tmp_path):
    payload = tmp_path / "payload"
    shutil.copytree(shipped_payload(), payload)
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "profiles.yaml").write_text(
        """privacy_modes:\n  standard: System/policy/standard.md\n  private: System/policy/private.md\nwork_types:\n  analysis:\n    - System/procedures/welcome.md\ndefault:\n  privacy_mode: private\n  work_types: [analysis]\n""",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    assert init.run(_args(workspace, payload=str(payload)), available=lambda: False) == 0
    assert _profile(workspace)["privacy_mode"] == "private"
    assert _profile(workspace)["work_types"] == ["analysis"]


def test_availability_is_probed_before_target_mutation_and_unavailable_failures_remain_errors(tmp_path):
    workspace = tmp_path / "workspace"

    def unavailable():
        assert not workspace.exists()
        return False

    calls: list[str] = []

    def write(_workspace, event, _fields):
        calls.append(event)
        if event == "snapshot":
            raise RuntimeError("receipt backend failed")
        return Path("receipt.md")

    assert init.run(_args(workspace), available=unavailable, write=write) == 2
    assert calls == ["init", "snapshot"]


def test_only_explicit_unavailable_result_enters_degraded_path(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    assert init.run(_args(workspace), available=lambda: None) == 2
    assert "could not inspect workspace capabilities" in capsys.readouterr().out
    assert not workspace.exists()


def test_unexpected_initial_snapshot_failure_is_not_reported_as_success(tmp_path):
    workspace = tmp_path / "workspace"

    def fail_snapshot(*_args, **_kwargs):
        raise SnapshotError("git failed")

    assert init.run(_args(workspace), available=lambda: True, take=fail_snapshot) == 2


@pytest.mark.parametrize(
    ("collision", "kind"),
    (
        ("Welcome.md", "directory"),
        ("Goals", "file"),
        ("System/policy/standard.md", "directory"),
        ("System/receipts", "file"),
    ),
)
def test_complete_plan_rejects_generic_managed_and_receipt_collisions_atomically(
    tmp_path, collision, kind
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / collision
    target.parent.mkdir(parents=True, exist_ok=True)
    if kind == "directory":
        target.mkdir()
        (target / "sentinel.bin").write_bytes(b"collision sentinel")
    else:
        target.write_bytes(b"collision sentinel")
    before = _tree_state(workspace)

    assert init.run(_args(workspace), available=lambda: True) == 2
    assert _tree_state(workspace) == before


def test_full_init_rejects_target_symlink_without_touching_outside(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    target = workspace / "System/policy/standard.md"
    target.parent.mkdir(parents=True)
    outside = tmp_path / "outside-target.txt"
    outside.write_bytes(b"outside target sentinel")
    target.symlink_to(outside)
    before = _tree_state(workspace)

    assert init.run(_args(workspace), available=lambda: False) == 2
    output = capsys.readouterr().out
    assert "System/policy/standard.md" in output
    assert "symbolic link" in output
    assert outside.read_bytes() == b"outside target sentinel"
    assert _tree_state(workspace) == before


def test_full_init_rejects_workspace_ancestor_symlink_without_touching_outside(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    outside_system = tmp_path / "outside-system"
    outside_system.mkdir()
    sentinel = outside_system / "sentinel.bin"
    sentinel.write_bytes(b"workspace ancestor sentinel")
    workspace.mkdir()
    (workspace / "System").symlink_to(outside_system, target_is_directory=True)
    before = _tree_state(workspace)

    assert init.run(_args(workspace), available=lambda: False) == 2
    output = capsys.readouterr().out
    assert "workspace path 'System'" in output
    assert "symbolic link" in output
    assert sentinel.read_bytes() == b"workspace ancestor sentinel"
    assert _tree_state(workspace) == before


@pytest.mark.parametrize(
    ("relative", "snapshots_available", "directory_link"),
    (
        ("System/receipts", False, True),
        ("System/machine-report.md", False, False),
        ("System/workspace.yaml", True, False),
    ),
)
def test_full_init_preflights_receipts_report_and_snapshot_store_symlinks(
    tmp_path, capsys, relative, snapshots_available, directory_link
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    if directory_link:
        outside.mkdir()
        sentinel = outside / "sentinel.bin"
        sentinel.write_bytes(b"support path sentinel")
    else:
        outside.write_bytes(b"support path sentinel")
        sentinel = outside
    target = workspace / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(outside, target_is_directory=directory_link)
    before = _tree_state(workspace)

    assert init.run(
        _args(workspace), available=lambda: snapshots_available
    ) == 2
    output = capsys.readouterr().out
    assert relative in output
    assert "symbolic link" in output
    assert sentinel.read_bytes() == b"support path sentinel"
    assert _tree_state(workspace) == before


def test_full_init_rejects_source_entry_symlink_without_touching_outside(tmp_path, capsys):
    source_root = tmp_path / "source"
    payload = _custom_payload(source_root)
    outside = tmp_path / "outside-source.txt"
    outside.write_bytes(b"outside source sentinel")
    welcome = payload / "Welcome.md"
    welcome.unlink()
    welcome.symlink_to(outside)
    workspace = tmp_path / "workspace"

    assert init.run(_args(workspace, payload=str(payload)), available=lambda: False) == 2
    output = capsys.readouterr().out
    assert "Welcome.md" in output
    assert "symbolic link" in output
    assert outside.read_bytes() == b"outside source sentinel"
    assert not workspace.exists()


def test_full_init_rejects_payload_root_and_manifest_symlinks(tmp_path, capsys):
    source_root = tmp_path / "source"
    real_payload = _custom_payload(source_root)
    payload_link = tmp_path / "payload-link"
    payload_link.symlink_to(real_payload, target_is_directory=True)
    first_workspace = tmp_path / "first-workspace"
    assert init.run(_args(first_workspace, payload=str(payload_link)), available=lambda: False) == 2
    assert "payload source path" in capsys.readouterr().out
    assert not first_workspace.exists()

    profiles = source_root / "profiles"
    profiles.mkdir()
    outside_manifest = tmp_path / "outside-manifest.yaml"
    outside_manifest.write_bytes(b"manifest sentinel\n")
    (profiles / "profiles.yaml").symlink_to(outside_manifest)
    second_workspace = tmp_path / "second-workspace"
    assert init.run(_args(second_workspace, payload=str(real_payload)), available=lambda: False) == 2
    assert "profiles manifest" in capsys.readouterr().out
    assert outside_manifest.read_bytes() == b"manifest sentinel\n"
    assert not second_workspace.exists()


@pytest.mark.parametrize("relationship", ("equal", "target-under-payload", "payload-under-target"))
def test_payload_workspace_overlap_is_rejected_before_mutation(tmp_path, relationship, capsys):
    if relationship == "payload-under-target":
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        payload = _custom_payload(workspace / "source")
    else:
        payload = _custom_payload(tmp_path / "source")
        workspace = payload if relationship == "equal" else payload / "new-workspace"
    before = _tree_state(tmp_path)

    assert init.run(_args(workspace, payload=str(payload)), available=lambda: False) == 2
    assert "must not overlap" in capsys.readouterr().out
    assert _tree_state(tmp_path) == before


def test_unavailable_snapshot_attempts_receipt_and_report_independently(tmp_path):
    workspace = tmp_path / "workspace"
    report = workspace / "System/machine-report.md"
    report.parent.mkdir(parents=True)
    report.write_text("original report\n", encoding="utf-8")
    calls: list[str] = []

    def write(_workspace, event, _fields):
        calls.append(f"write:{event}")
        if event == "snapshot":
            raise RuntimeError("snapshot receipt failed")
        return Path("receipt.md")

    def update(_workspace):
        calls.append("update:report")
        report.write_text("report update attempted\n", encoding="utf-8")
        return True

    assert init.run(
        _args(workspace), available=lambda: False, write=write, update_report=update
    ) == 2
    assert calls == ["write:init", "write:snapshot", "update:report"]
    assert report.read_text(encoding="utf-8") == "report update attempted\n"


def test_unavailable_snapshot_attempts_receipt_when_report_update_fails(tmp_path):
    workspace = tmp_path / "workspace"
    calls: list[str] = []

    def write(target, event, fields):
        calls.append(f"write:{event}")
        return write_receipt(target, event, fields)

    def update(_workspace):
        calls.append("update:report")
        raise RuntimeError("report failed")

    assert init.run(
        _args(workspace), available=lambda: False, write=write, update_report=update
    ) == 2
    assert calls == ["write:init", "write:snapshot", "update:report"]
    assert _receipt_events(workspace) == ["init", "snapshot"]


@pytest.mark.parametrize("backend", ("detect", "write", "snapshot"))
def test_backend_exception_output_does_not_echo_sensitive_details(tmp_path, capsys, backend):
    workspace = tmp_path / "workspace"

    def fail(*_args, **_kwargs):
        raise RuntimeError("SENTINEL_SECRET backend detail")

    kwargs = {"available": lambda: backend != "write"}
    if backend == "detect":
        kwargs["detect"] = fail
    elif backend == "write":
        kwargs["write"] = fail
        kwargs["available"] = lambda: False
    else:
        kwargs["take"] = fail
    assert init.run(_args(workspace), **kwargs) == 2
    assert "SENTINEL_SECRET" not in capsys.readouterr().out


def test_yaml_parser_error_does_not_echo_manifest_content(tmp_path, capsys):
    source_root = tmp_path / "source"
    payload = _custom_payload(source_root)
    profiles = source_root / "profiles"
    profiles.mkdir()
    (profiles / "profiles.yaml").write_text(
        "privacy_modes: [SENTINEL_SECRET\n", encoding="utf-8"
    )
    workspace = tmp_path / "workspace"

    assert init.run(_args(workspace, payload=str(payload)), available=lambda: False) == 2
    output = capsys.readouterr().out
    assert "could not read profiles manifest profiles.yaml" in output
    assert "SENTINEL_SECRET" not in output
    assert not workspace.exists()


def test_yaml_parser_error_does_not_echo_existing_profile_content(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    profile = workspace / "System/profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_text("work_types: [SENTINEL_SECRET\n", encoding="utf-8")
    before = _tree_state(workspace)

    assert init.run(_args(workspace), available=lambda: False) == 2
    output = capsys.readouterr().out
    assert "existing System/profile.yaml could not be read" in output
    assert "SENTINEL_SECRET" not in output
    assert _tree_state(workspace) == before


def test_target_file_and_missing_payload_are_actionable_usage_errors(tmp_path, capsys):
    target_file = tmp_path / "target-file"
    target_file.write_bytes(b"target sentinel")
    assert init.run(_args(target_file), available=lambda: False) == 2
    assert "workspace path is not a directory" in capsys.readouterr().out
    assert target_file.read_bytes() == b"target sentinel"

    missing_payload = tmp_path / "missing-payload"
    workspace = tmp_path / "workspace"
    assert init.run(
        _args(workspace, payload=str(missing_payload)), available=lambda: False
    ) == 2
    assert "payload source was not found" in capsys.readouterr().out
    assert not workspace.exists()


def test_default_payload_is_package_local_and_nonfilesystem_resources_fail_clearly(
    monkeypatch,
):
    package = Path(payload_module.__file__).resolve().parent
    assert package in shipped_payload().resolve().parents

    class NonFilesystemResource:
        def joinpath(self, *_parts):
            return self

    monkeypatch.setattr(
        payload_module.resources, "files", lambda _package: NonFilesystemResource()
    )
    with pytest.raises(PayloadError, match="unavailable as a filesystem resource"):
        payload_module.resolve_payload(None)


def test_repair_receipt_lists_exact_sorted_changes_and_sync_note(tmp_path):
    workspace = tmp_path / "workspace"
    assert init.run(_args(workspace), available=lambda: False) == 0
    (workspace / "Goals").rmdir()
    sync = {"at_risk": False, "reason": "Synthetic sync note."}
    assert init.run(
        _args(workspace), available=lambda: False, detect=lambda _path: sync
    ) == 0
    receipts = sorted((workspace / "System/receipts").glob("*-init*.md"))
    repaired = next(
        path
        for path in receipts
        if "Sync redirection: Synthetic sync note."
        in path.read_text(encoding="utf-8")
    )
    _frontmatter, body = records.parse_record(repaired.read_text(encoding="utf-8"))
    assert body == "Changes:\n- created Goals/\n\nSync redirection: Synthetic sync note."


def test_selector_precedence_preserves_existing_values_when_flags_are_omitted(tmp_path):
    workspace = tmp_path / "workspace"
    assert init.run(
        _args(workspace, work_types="quality"), available=lambda: False
    ) == 0
    profile = _profile(workspace)
    profile["status"] = "configured"
    profile["review_day"] = "friday"
    profile["spend"] = "thorough"
    (workspace / "System/profile.yaml").write_text(
        records.yaml.safe_dump(profile, sort_keys=False), encoding="utf-8"
    )

    assert init.run(
        _args(workspace, privacy_mode="private"), available=lambda: False
    ) == 0
    assert _profile(workspace) == {
        "schema": "apparatus/profile@v0",
        "status": "configured",
        "privacy_mode": "private",
        "work_types": ["quality"],
        "review_day": "friday",
        "spend": "thorough",
    }
    assert init.run(
        _args(workspace, work_types="writing,analysis"), available=lambda: False
    ) == 0
    final = _profile(workspace)
    assert final["privacy_mode"] == "private"
    assert final["work_types"] == ["analysis", "writing"]
    assert final["status"] == "configured"
    assert final["review_day"] == "friday"
    assert final["spend"] == "thorough"


def test_custom_payload_without_sibling_manifest_falls_back_to_shipped_manifest(tmp_path):
    payload = _custom_payload(tmp_path / "source")
    workspace = tmp_path / "workspace"
    assert init.run(
        _args(workspace, payload=str(payload)), available=lambda: False
    ) == 0
    assert _profile(workspace)["work_types"] == [
        "analysis",
        "quality",
        "project-management",
        "support",
        "writing",
    ]


def test_custom_payload_without_any_manifest_fails_before_mutation(tmp_path, monkeypatch, capsys):
    payload = _custom_payload(tmp_path / "source")
    missing = tmp_path / "missing-shipped-profiles.yaml"
    monkeypatch.setattr(payload_module, "shipped_profiles_manifest", lambda: missing)
    workspace = tmp_path / "workspace"

    assert init.run(
        _args(workspace, payload=str(payload)), available=lambda: False
    ) == 2
    assert "profiles manifest was not found" in capsys.readouterr().out
    assert not workspace.exists()


@pytest.mark.skipif(not Path("/tmp").is_symlink(), reason="/tmp is not a system symlink")
def test_external_system_symlink_is_canonicalized_before_workspace_boundary():
    with tempfile.TemporaryDirectory(dir="/tmp") as temporary_root:
        workspace = Path(temporary_root) / "workspace"
        assert init.run(_args(workspace), available=lambda: False) == 0
        assert check_workspace(workspace).ok


def test_payload_executor_rejects_forged_escape_plan(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"payload plan sentinel")
    forged = PayloadPlan(
        directories=(),
        files=(PayloadFile(Path("../outside.txt"), b"malicious"),),
        placeholders=(),
    )

    with pytest.raises(PayloadError, match="not normalized"):
        deploy_missing_payload_files(tmp_path / "unused", workspace, forged)
    assert outside.read_bytes() == b"payload plan sentinel"


def test_payload_executor_preserves_file_created_after_plan(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manifest = load_manifest(
        payload_module.shipped_profiles_manifest(), shipped_payload()
    )
    plan = plan_payload_deployment(shipped_payload(), manifest.managed_paths, workspace)
    welcome = workspace / "Welcome.md"
    welcome.write_bytes(b"user arrived after planning")

    deploy_missing_payload_files(shipped_payload(), workspace, plan)
    assert welcome.read_bytes() == b"user arrived after planning"


def test_payload_executor_revalidates_stale_target_symlink_before_any_copy(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manifest = load_manifest(
        payload_module.shipped_profiles_manifest(), shipped_payload()
    )
    plan = plan_payload_deployment(shipped_payload(), manifest.managed_paths, workspace)
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"payload stale-target sentinel")
    welcome = workspace / "Welcome.md"
    welcome.symlink_to(outside)

    with pytest.raises(PayloadError, match=r"Welcome\.md.*symbolic link"):
        deploy_missing_payload_files(shipped_payload(), workspace, plan)
    assert outside.read_bytes() == b"payload stale-target sentinel"
    assert not (workspace / "AGENTS.md").exists()


@pytest.mark.skipif(not Path("/tmp").is_symlink(), reason="/tmp is not a system symlink")
def test_custom_payload_under_external_system_symlink_works_for_plans_and_full_init():
    with tempfile.TemporaryDirectory(dir="/tmp") as temporary_root:
        logical_root = Path(temporary_root)
        payload = _custom_payload(logical_root / "source")
        direct_workspace = logical_root / "direct-workspace"
        manifest = load_manifest(
            payload_module.shipped_profiles_manifest(), payload
        )
        payload_plan = plan_payload_deployment(
            payload, manifest.managed_paths, direct_workspace
        )
        overlay_plan = plan_overlay(
            payload,
            direct_workspace,
            manifest,
            privacy_mode="standard",
            work_types=("analysis",),
        )
        assert payload_plan.files
        assert overlay_plan.writes
        deploy_missing_payload_files(payload, direct_workspace, payload_plan)
        apply_overlay_plan(direct_workspace, overlay_plan)
        assert (direct_workspace / "Welcome.md").is_file()
        assert (direct_workspace / "System/policy/standard.md").is_file()

        workspace = logical_root / "workspace"
        assert init.run(
            _args(workspace, payload=str(payload)), available=lambda: False
        ) == 0
        assert check_workspace(workspace).ok


@pytest.mark.parametrize("dangling", (False, True))
def test_sibling_profiles_directory_symlink_is_rejected_by_resolver_and_full_init(
    tmp_path, capsys, dangling
):
    bundle = tmp_path / "bundle"
    payload = _custom_payload(bundle)
    sentinel = tmp_path / "outside-sentinel.bin"
    sentinel.write_bytes(b"sibling manifest sentinel")
    if dangling:
        outside_profiles = tmp_path / "missing-profiles"
    else:
        outside_profiles = tmp_path / "outside-profiles"
        outside_profiles.mkdir()
        (outside_profiles / "profiles.yaml").write_bytes(
            payload_module.shipped_profiles_manifest().read_bytes()
        )
    (bundle / "profiles").symlink_to(outside_profiles, target_is_directory=True)

    with pytest.raises(PayloadError, match="profiles.*symbolic link"):
        payload_module.resolve_profiles_manifest(payload)
    workspace = tmp_path / "workspace"
    assert init.run(
        _args(workspace, payload=str(payload)), available=lambda: False
    ) == 2
    output = capsys.readouterr().out
    assert "profiles" in output
    assert "symbolic link" in output
    assert sentinel.read_bytes() == b"sibling manifest sentinel"
    assert not workspace.exists()


def test_direct_deploy_failure_exactly_cleans_invocation_created_root_and_parents(
    monkeypatch, tmp_path
):
    workspace_parent = tmp_path / "invocation-parent"
    workspace = workspace_parent / "workspace"
    payload_plan, overlay_plan, profile_content = _rollback_deployment_plan()
    original_create = WorkspaceAnchor.create_file

    def fail_during_overlay(anchor, relative, content, mode=0o600, **kwargs):
        if Path(relative).name == "managed-two.md":
            raise OSError("injected overlay deployment failure")
        return original_create(anchor, relative, content, mode, **kwargs)

    monkeypatch.setattr(
        init_deploy.WorkspaceAnchor,
        "create_file",
        fail_during_overlay,
    )
    with pytest.raises(OSError, match="injected overlay deployment failure"):
        init_deploy.deploy_init_plan(
            workspace,
            payload_plan,
            overlay_plan,
            profile_content,
            profile_write_required=True,
        )

    assert not workspace_parent.exists()
    assert not list(tmp_path.rglob(".apparatus-memory-*"))


@pytest.mark.parametrize(
    ("operation", "failure_name"),
    (
        ("create", "payload-two.md"),
        ("replace", "managed-two.md"),
        ("replace", "profile.yaml"),
        ("replace", "obsolete-one.md"),
    ),
)
def test_direct_deploy_operation_failures_restore_exact_existing_tree(
    monkeypatch, tmp_path, operation, failure_name
):
    workspace = tmp_path / "workspace"
    _seed_rollback_workspace(workspace)
    before = _tree_state(workspace)
    payload_plan, overlay_plan, profile_content = _rollback_deployment_plan()

    if operation == "create":
        original = WorkspaceAnchor.create_file

        def fail_operation(anchor, relative, content, mode=0o600, **kwargs):
            if Path(relative).name == failure_name:
                raise OSError(f"injected {failure_name} failure")
            return original(anchor, relative, content, mode, **kwargs)

        monkeypatch.setattr(
            init_deploy.WorkspaceAnchor,
            "create_file",
            fail_operation,
        )
    else:
        original = WorkspaceAnchor.replace_if_unchanged

        def fail_operation(anchor, relative, *args, **kwargs):
            if Path(relative).name == failure_name:
                raise OSError(f"injected {failure_name} failure")
            return original(anchor, relative, *args, **kwargs)

        monkeypatch.setattr(
            init_deploy.WorkspaceAnchor,
            "replace_if_unchanged",
            fail_operation,
        )

    with pytest.raises(OSError, match=f"injected {failure_name} failure"):
        init_deploy.deploy_init_plan(
            workspace,
            payload_plan,
            overlay_plan,
            profile_content,
            profile_write_required=True,
        )

    assert _tree_state(workspace) == before
    assert not list(workspace.rglob(".apparatus-memory-*"))


@pytest.mark.parametrize(
    ("commit_number", "fail_after_commit"),
    ((1, False), (1, True), (2, False), (2, True)),
)
def test_direct_deploy_commit_failures_restore_earlier_settled_replacements(
    monkeypatch, tmp_path, commit_number, fail_after_commit
):
    workspace = tmp_path / "workspace"
    _seed_rollback_workspace(workspace)
    before = _tree_state(workspace)
    payload_plan, overlay_plan, profile_content = _rollback_deployment_plan()
    original_commit = ReplacementTransaction.commit
    calls = 0

    def fail_commit(transaction):
        nonlocal calls
        calls += 1
        if calls == commit_number:
            if fail_after_commit:
                original_commit(transaction)
            raise OSError("injected replacement commit failure")
        return original_commit(transaction)

    monkeypatch.setattr(
        init_deploy.ReplacementTransaction,
        "commit",
        fail_commit,
    )
    with pytest.raises(OSError, match="injected replacement commit failure"):
        init_deploy.deploy_init_plan(
            workspace,
            payload_plan,
            overlay_plan,
            profile_content,
            profile_write_required=True,
        )

    assert calls >= commit_number
    assert _tree_state(workspace) == before
    assert not list(workspace.rglob(".apparatus-memory-*"))


@pytest.mark.parametrize("fail_after_discard", (False, True))
def test_direct_deploy_removal_commit_failure_rematerializes_preimage(
    monkeypatch, tmp_path, fail_after_discard
):
    workspace = tmp_path / "workspace"
    _seed_rollback_workspace(workspace)
    before = _tree_state(workspace)
    payload_plan, overlay_plan, profile_content = _rollback_deployment_plan()
    original_discard = ReplacementTransaction.discard_backup
    injected = False

    def fail_discard(transaction):
        nonlocal injected
        if not injected and transaction.target.relative.name == "obsolete-one.md":
            injected = True
            if fail_after_discard:
                original_discard(transaction)
            raise OSError("injected removal commit failure")
        return original_discard(transaction)

    monkeypatch.setattr(
        init_deploy.ReplacementTransaction,
        "discard_backup",
        fail_discard,
    )
    with pytest.raises(OSError, match="injected removal commit failure"):
        init_deploy.deploy_init_plan(
            workspace,
            payload_plan,
            overlay_plan,
            profile_content,
            profile_write_required=True,
        )

    assert injected
    assert _tree_state(workspace) == before
    assert not list(workspace.rglob(".apparatus-memory-*"))


def test_direct_deploy_post_settlement_gate_restores_every_operation(
    monkeypatch, tmp_path
):
    workspace = tmp_path / "workspace"
    _seed_rollback_workspace(workspace)
    before = _tree_state(workspace)
    payload_plan, overlay_plan, profile_content = _rollback_deployment_plan()
    original_entry_exists = WorkspaceAnchor.entry_exists
    obsolete_two_checks = 0

    def fail_post_settlement_gate(anchor, relative):
        nonlocal obsolete_two_checks
        if Path(relative).name == "obsolete-two.md":
            obsolete_two_checks += 1
            if obsolete_two_checks == 2:
                raise OSError("injected post-settlement gate failure")
        return original_entry_exists(anchor, relative)

    monkeypatch.setattr(
        init_deploy.WorkspaceAnchor,
        "entry_exists",
        fail_post_settlement_gate,
    )
    with pytest.raises(OSError, match="injected post-settlement gate failure"):
        init_deploy.deploy_init_plan(
            workspace,
            payload_plan,
            overlay_plan,
            profile_content,
            profile_write_required=True,
        )

    assert obsolete_two_checks == 2
    assert _tree_state(workspace) == before
    assert not list(workspace.rglob(".apparatus-memory-*"))


def test_direct_deploy_preserves_foreign_removal_substitution_and_fails_loudly(
    monkeypatch, tmp_path
):
    workspace = tmp_path / "workspace"
    _seed_rollback_workspace(workspace)
    payload_plan, overlay_plan, profile_content = _rollback_deployment_plan()
    original_discard = ReplacementTransaction.discard_backup
    target = workspace / "System/policy/obsolete-one.md"
    foreign = b"concurrent foreign replacement\n"
    injected = False

    def substitute_then_fail(transaction):
        nonlocal injected
        if not injected and transaction.target.relative.name == "obsolete-one.md":
            injected = True
            target.write_bytes(foreign)
            raise OSError("injected foreign removal substitution")
        return original_discard(transaction)

    monkeypatch.setattr(
        init_deploy.ReplacementTransaction,
        "discard_backup",
        substitute_then_fail,
    )
    with pytest.raises(OSError, match="rollback was incomplete"):
        init_deploy.deploy_init_plan(
            workspace,
            payload_plan,
            overlay_plan,
            profile_content,
            profile_write_required=True,
        )

    assert injected
    assert target.read_bytes() == foreign


@pytest.mark.skipif(os.name != "nt", reason="native Windows rollback regression")
def test_windows_direct_deploy_preserves_foreign_file_created_during_rollback(
    monkeypatch, tmp_path
):
    workspace_parent = tmp_path / "invocation-parent"
    workspace = workspace_parent / "workspace"
    payload_plan, overlay_plan, profile_content = _rollback_deployment_plan()
    original_create = WorkspaceAnchor.create_file
    original_unlink = WorkspaceAnchor.unlink_owned_if_present
    foreign = b"concurrent foreign file\n"
    injected = False

    def fail_during_overlay(anchor, relative, content, mode=0o600, **kwargs):
        if Path(relative).name == "managed-two.md":
            raise OSError("injected overlay deployment failure")
        return original_create(anchor, relative, content, mode, **kwargs)

    def introduce_foreign_file(anchor, owned):
        nonlocal injected
        removed = original_unlink(anchor, owned)
        if not injected and owned.relative == Path("payload-one.md"):
            injected = True
            (workspace / "foreign.bin").write_bytes(foreign)
        return removed

    monkeypatch.setattr(
        init_deploy.WorkspaceAnchor,
        "create_file",
        fail_during_overlay,
    )
    monkeypatch.setattr(
        init_deploy.WorkspaceAnchor,
        "unlink_owned_if_present",
        introduce_foreign_file,
    )

    with pytest.raises(OSError, match="rollback was incomplete"):
        init_deploy.deploy_init_plan(
            workspace,
            payload_plan,
            overlay_plan,
            profile_content,
            profile_write_required=True,
        )

    assert injected
    assert (workspace / "foreign.bin").read_bytes() == foreign
    assert not list(workspace.rglob(".apparatus-memory-*"))


@pytest.mark.skipif(os.name != "posix", reason="POSIX retained-root regression")
@pytest.mark.parametrize("boundary", ("root", "System", "nested"))
def test_init_rejects_posix_directory_replacement_and_preserves_foreign_tree(
    monkeypatch, tmp_path, capsys, boundary
):
    workspace = tmp_path / "workspace"
    assert init.run(_args(workspace), available=lambda: False) == 0
    capsys.readouterr()
    target = {
        "root": workspace,
        "System": workspace / "System",
        "nested": workspace / "System/policy",
    }[boundary]
    trigger = {
        "root": workspace / "Welcome.md",
        "System": workspace / "System/profile.yaml",
        "nested": workspace / "System/policy/standard.md",
    }[boundary]
    trigger.unlink()
    displaced = tmp_path / f"displaced-{boundary}"
    foreign = b"foreign tree\n"
    attempted = False
    original_create = WorkspaceAnchor.create_file

    def replace_after_create(anchor, relative, content, mode=0o600, **kwargs):
        nonlocal attempted
        owned = original_create(anchor, relative, content, mode, **kwargs)
        if attempted or Path(relative).name.startswith(".apparatus-"):
            return owned
        anchor_path = Path(anchor.workspace)
        should_replace = (
            (boundary == "root" and anchor_path == workspace)
            or (boundary == "System" and anchor_path == workspace / "System")
            or (boundary == "nested" and anchor_path == workspace / "System/policy")
        )
        if should_replace:
            attempted = True
            target.rename(displaced)
            target.mkdir(parents=True)
            (target / "foreign.bin").write_bytes(foreign)
        return owned

    monkeypatch.setattr(init_deploy.WorkspaceAnchor, "create_file", replace_after_create)
    assert init.run(_args(workspace), available=lambda: False) == 2
    assert attempted
    assert "could not deploy workspace" in capsys.readouterr().out
    assert (target / "foreign.bin").read_bytes() == foreign
    assert not list(target.rglob(".apparatus-init-*.tmp"))


@pytest.mark.skipif(os.name != "posix", reason="POSIX retained-root regression")
@pytest.mark.parametrize("workspace_exists", (False, True))
def test_workspace_first_object_handoff_rejects_root_substitution(
    monkeypatch, tmp_path, capsys, workspace_exists
):
    workspace = tmp_path / "workspace"
    if workspace_exists:
        workspace.mkdir()
        (workspace / "original.bin").write_bytes(b"original root\n")
    displaced = tmp_path / "displaced-workspace"
    foreign = b"foreign root\n"
    original_open = WorkspaceAnchor.open_directory
    substituted = False

    def substitute_after_retain(anchor, relative, **kwargs):
        nonlocal substituted
        retained = original_open(anchor, relative, **kwargs)
        if (
            not substituted
            and Path(anchor.workspace) == workspace.parent
            and Path(relative) == Path(workspace.name)
        ):
            substituted = True
            workspace.rename(displaced)
            workspace.mkdir()
            (workspace / "foreign.bin").write_bytes(foreign)
        return retained

    monkeypatch.setattr(
        init_deploy.WorkspaceAnchor,
        "open_directory",
        substitute_after_retain,
    )
    assert init.run(_args(workspace), available=lambda: False) == 2
    assert substituted
    assert "could not deploy workspace" in capsys.readouterr().out
    assert (workspace / "foreign.bin").read_bytes() == foreign
    assert not list(displaced.rglob(".apparatus-init-*.tmp"))
    if workspace_exists:
        assert (displaced / "original.bin").read_bytes() == b"original root\n"


@pytest.mark.skipif(os.name != "nt", reason="native Windows retained-root regression")
@pytest.mark.parametrize("boundary", ("root", "System"))
def test_windows_init_retained_handles_deny_directory_rename(
    monkeypatch, tmp_path, boundary
):
    workspace = tmp_path / "workspace"
    assert init.run(_args(workspace), available=lambda: False) == 0
    target = workspace if boundary == "root" else workspace / "System"
    replacement = tmp_path / f"renamed-{boundary}"
    attempts: list[str] = []
    original_matches = WorkspaceAnchor.matches_root_handle

    def attempt_rename(anchor, handle):
        anchor_path = Path(anchor.workspace)
        if not attempts and ((boundary == "root" and anchor_path == workspace) or (
            boundary == "System" and anchor_path == workspace / "System"
        )):
            try:
                target.rename(replacement)
            except OSError:
                attempts.append("blocked")
            else:  # pragma: no cover - exposes a native containment defect
                attempts.append("renamed")
        return original_matches(anchor, handle)

    monkeypatch.setattr(
        init_deploy.WorkspaceAnchor, "matches_root_handle", attempt_rename
    )
    assert init.run(
        _args(workspace, privacy_mode="private"), available=lambda: False
    ) == 0
    assert attempts == ["blocked"]
    assert not replacement.exists()


@pytest.mark.skipif(os.name != "nt", reason="native Windows reparse regression")
@pytest.mark.parametrize("boundary", ("workspace", "System", "nested"))
def test_windows_init_rejects_junction_boundaries_and_preserves_foreign_tree(
    tmp_path, capsys, monkeypatch, boundary
):
    outside = tmp_path / f"outside-{boundary}"
    outside.mkdir()
    foreign = outside / "foreign.bin"
    foreign.write_bytes(b"foreign junction\n")
    workspace = tmp_path / f"workspace-{boundary}"
    if boundary == "workspace":
        junction = workspace
    elif boundary == "System":
        workspace.mkdir()
        junction = workspace / "System"
    else:
        (workspace / "System").mkdir(parents=True)
        junction = workspace / "System/policy"
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    if boundary == "System":
        # Enrollment reads System/workspace.yaml through the retained safe root
        # before deployment; a System junction must stop at that earlier check.
        monkeypatch.setattr(init, "deploy_init_plan", lambda *_a, **_k: pytest.fail("unsafe enrollment reached deployment"))
    assert init.run(_args(workspace), available=lambda: False) == 2
    output = capsys.readouterr().out
    if boundary == "System":
        assert "Work-area enrollment or recovery storage is missing or unsafe" in output
    else:
        assert (
            "could not deploy workspace" in output
            or "could not prepare workspace deployment" in output
            or boundary == "workspace"
        )
    assert foreign.read_bytes() == b"foreign junction\n"
    assert sorted(path.name for path in outside.iterdir()) == ["foreign.bin"]


@pytest.mark.skipif(os.name != "nt", reason="native Windows retained-root regression")
def test_windows_missing_workspace_identity_mismatch_fails_before_deployment(
    monkeypatch, tmp_path, capsys
):
    workspace = tmp_path / "workspace"
    original_matches = WorkspaceAnchor.matches_root_handle
    probes: list[Path] = []

    def reject_workspace(anchor, handle):
        if Path(anchor.workspace) == workspace:
            probes.append(Path(anchor.workspace))
            return False
        return original_matches(anchor, handle)

    monkeypatch.setattr(init_deploy.WorkspaceAnchor, "matches_root_handle", reject_workspace)
    assert init.run(_args(workspace), available=lambda: False) == 2
    assert probes == [workspace]
    assert "could not deploy workspace" in capsys.readouterr().out
    assert not workspace.exists()
    assert not list(workspace.rglob(".apparatus-init-*.tmp"))
    assert not (workspace / "Welcome.md").exists()
