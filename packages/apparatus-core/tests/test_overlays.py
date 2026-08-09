from __future__ import annotations

from pathlib import Path

import pytest

from apparatus_core.overlays import (
    ManifestError,
    OverlayManifest,
    OverlayPlan,
    OverlayWrite,
    apply_overlay,
    apply_overlay_plan,
    load_manifest,
    plan_overlay,
)


def _payload(path: Path, names: tuple[str, ...]) -> Path:
    for name in names:
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"source {name}\n", encoding="utf-8")
    return path


def _write_manifest(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_shipped_manifest_references_only_real_payload_files():
    root = Path(__file__).parents[3]
    manifest = load_manifest(root / "starter/profiles/profiles.yaml", root / "starter/payload")
    assert tuple(manifest.privacy_modes) == ("standard", "private")
    assert tuple(manifest.work_types) == (
        "analysis",
        "quality",
        "project-management",
        "support",
        "writing",
    )
    assert manifest.default_work_types == tuple(manifest.work_types)
    required = {
        "System/procedures/welcome.md",
        "System/procedures/produce-deliverable.md",
        "System/procedures/research-and-summarize.md",
        "System/procedures/review-against-checklist.md",
        "System/procedures/weekly-review.md",
    }
    assert all(set(procedures) == required for procedures in manifest.work_types.values())


def test_dangling_or_non_normalized_paths_name_the_offending_entry(tmp_path):
    payload = _payload(tmp_path / "payload", ("System/policy/standard.md",))
    manifest = _write_manifest(
        tmp_path / "profiles.yaml",
        """privacy_modes:\n  standard: System/policy/missing.md\nwork_types:\n  analysis:\n    - System/policy/standard.md\ndefault:\n  privacy_mode: standard\n  work_types: [analysis]\n""",
    )
    with pytest.raises(ManifestError, match=r"privacy_modes\.standard.*missing\.md"):
        load_manifest(manifest, payload)
    manifest.write_text(manifest.read_text(encoding="utf-8").replace("missing.md", "../standard.md"), encoding="utf-8")
    with pytest.raises(ManifestError, match=r"privacy_modes\.standard.*normalized"):
        load_manifest(manifest, payload)


def test_synthetic_manifest_with_an_invented_mode_is_applied_without_mode_branches(tmp_path):
    payload = _payload(
        tmp_path / "payload",
        ("System/policy/experimental.md", "System/procedures/example.md"),
    )
    manifest_path = _write_manifest(
        tmp_path / "profiles.yaml",
        """privacy_modes:\n  experimental: System/policy/experimental.md\nwork_types:\n  invented:\n    - System/procedures/example.md\ndefault:\n  privacy_mode: experimental\n  work_types: [invented]\n""",
    )
    manifest = load_manifest(manifest_path, payload)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    changes = apply_overlay(
        payload, workspace, manifest, privacy_mode="experimental", work_types=("invented",)
    )
    assert (workspace / "System/policy/experimental.md").read_text(encoding="utf-8") == "source System/policy/experimental.md\n"
    assert (workspace / "System/procedures/example.md").is_file()
    assert any("experimental.md" in change for change in changes)


def test_profile_change_adds_selected_and_removes_only_managed_procedures(tmp_path):
    payload = _payload(
        tmp_path / "payload",
        (
            "System/policy/one.md",
            "System/policy/two.md",
            "System/procedures/alpha.md",
            "System/procedures/beta.md",
        ),
    )
    manifest = load_manifest(
        _write_manifest(
            tmp_path / "profiles.yaml",
            """privacy_modes:\n  one: System/policy/one.md\n  two: System/policy/two.md\nwork_types:\n  alpha:\n    - System/procedures/alpha.md\n  beta:\n    - System/procedures/beta.md\ndefault:\n  privacy_mode: one\n  work_types: [alpha]\n""",
        ),
        payload,
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    apply_overlay(payload, workspace, manifest, privacy_mode="one", work_types=("alpha",))
    user_procedure = workspace / "System/procedures/hand-copied.md"
    user_procedure.write_text("keep every byte\x00", encoding="utf-8")
    (workspace / "System/procedures/alpha.md").write_text("user changed managed file\n", encoding="utf-8")
    apply_overlay(payload, workspace, manifest, privacy_mode="two", work_types=("beta",))
    assert not (workspace / "System/procedures/alpha.md").exists()
    assert (workspace / "System/procedures/beta.md").read_text(encoding="utf-8") == "source System/procedures/beta.md\n"
    assert user_procedure.read_text(encoding="utf-8") == "keep every byte\x00"
    assert (workspace / "System/policy/one.md").is_file()
    assert (workspace / "System/policy/two.md").is_file()


def test_direct_overlay_rejects_managed_target_symlink_without_touching_outside(tmp_path):
    payload = _payload(
        tmp_path / "payload",
        ("System/policy/one.md", "System/procedures/example.md"),
    )
    manifest = load_manifest(
        _write_manifest(
            tmp_path / "profiles.yaml",
            """privacy_modes:\n  one: System/policy/one.md\nwork_types:\n  example:\n    - System/procedures/example.md\ndefault:\n  privacy_mode: one\n  work_types: [example]\n""",
        ),
        payload,
    )
    workspace = tmp_path / "workspace"
    target = workspace / "System/procedures/example.md"
    target.parent.mkdir(parents=True)
    outside = tmp_path / "outside-target.txt"
    outside.write_bytes(b"outside target sentinel")
    target.symlink_to(outside)

    with pytest.raises(ManifestError, match=r"System/procedures/example\.md.*symbolic link"):
        apply_overlay(payload, workspace, manifest, privacy_mode="one", work_types=("example",))
    assert outside.read_bytes() == b"outside target sentinel"
    assert target.is_symlink()
    assert not (workspace / "System/policy/one.md").exists()


def test_direct_overlay_rejects_managed_source_symlink_without_touching_outside(tmp_path):
    payload = _payload(
        tmp_path / "payload",
        ("System/policy/one.md", "System/procedures/example.md"),
    )
    outside = tmp_path / "outside-source.txt"
    outside.write_bytes(b"outside source sentinel")
    policy = payload / "System/policy/one.md"
    policy.unlink()
    policy.symlink_to(outside)
    manifest_path = _write_manifest(
        tmp_path / "profiles.yaml",
        """privacy_modes:\n  one: System/policy/one.md\nwork_types:\n  example:\n    - System/procedures/example.md\ndefault:\n  privacy_mode: one\n  work_types: [example]\n""",
    )

    with pytest.raises(ManifestError, match=r"privacy_modes\.one.*symbolic link"):
        load_manifest(manifest_path, payload)
    assert outside.read_bytes() == b"outside source sentinel"


def test_manifest_rejects_symlink_in_managed_source_pointer_components(tmp_path):
    payload = tmp_path / "payload"
    payload.mkdir()
    outside_system = tmp_path / "outside-system"
    _payload(
        outside_system,
        ("policy/one.md", "procedures/example.md"),
    )
    sentinel = outside_system / "sentinel.bin"
    sentinel.write_bytes(b"source component sentinel")
    (payload / "System").symlink_to(outside_system, target_is_directory=True)
    manifest_path = _write_manifest(
        tmp_path / "profiles.yaml",
        """privacy_modes:\n  one: System/policy/one.md\nwork_types:\n  example:\n    - System/procedures/example.md\ndefault:\n  privacy_mode: one\n  work_types: [example]\n""",
    )

    with pytest.raises(ManifestError, match=r"privacy_modes\.one.*'System'"):
        load_manifest(manifest_path, payload)
    assert sentinel.read_bytes() == b"source component sentinel"


@pytest.mark.parametrize(
    ("bad_entry", "replacement", "expected"),
    (
        ("privacy_modes.one", "AGENTS.md", "System/policy/"),
        ("work_types.example[0]", "Welcome.md", "System/procedures/"),
    ),
)
def test_manifest_rejects_overlay_pointers_outside_managed_folders(
    tmp_path, bad_entry, replacement, expected
):
    payload = _payload(
        tmp_path / "payload",
        (
            "AGENTS.md",
            "Welcome.md",
            "System/policy/one.md",
            "System/procedures/example.md",
        ),
    )
    policy = replacement if bad_entry.startswith("privacy") else "System/policy/one.md"
    procedure = replacement if bad_entry.startswith("work_types") else "System/procedures/example.md"
    manifest_path = _write_manifest(
        tmp_path / "profiles.yaml",
        f"""privacy_modes:\n  one: {policy}\nwork_types:\n  example:\n    - {procedure}\ndefault:\n  privacy_mode: one\n  work_types: [example]\n""",
    )

    with pytest.raises(ManifestError) as error:
        load_manifest(manifest_path, payload)
    assert bad_entry in str(error.value)
    assert expected in str(error.value)


def test_plan_overlay_independently_rejects_symlink_payload_root(tmp_path):
    real_payload = _payload(
        tmp_path / "real-payload",
        ("System/policy/one.md", "System/procedures/example.md"),
    )
    payload_link = tmp_path / "payload-link"
    payload_link.symlink_to(real_payload, target_is_directory=True)
    manifest = OverlayManifest(
        privacy_modes={"one": "System/policy/one.md"},
        work_types={"example": ("System/procedures/example.md",)},
        default_privacy_mode="one",
        default_work_types=("example",),
    )

    with pytest.raises(ManifestError, match="payload source path.*symbolic link"):
        plan_overlay(
            payload_link,
            tmp_path / "workspace",
            manifest,
            privacy_mode="one",
            work_types=("example",),
        )


def test_apply_overlay_plan_revalidates_stale_target_symlink_before_any_write(tmp_path):
    payload = _payload(
        tmp_path / "payload",
        ("System/policy/one.md", "System/procedures/example.md"),
    )
    manifest = load_manifest(
        _write_manifest(
            tmp_path / "profiles.yaml",
            """privacy_modes:\n  one: System/policy/one.md\nwork_types:\n  example:\n    - System/procedures/example.md\ndefault:\n  privacy_mode: one\n  work_types: [example]\n""",
        ),
        payload,
    )
    workspace = tmp_path / "workspace"
    plan = plan_overlay(
        payload,
        workspace,
        manifest,
        privacy_mode="one",
        work_types=("example",),
    )
    outside = tmp_path / "outside-target.txt"
    outside.write_bytes(b"stale target sentinel")
    target = workspace / "System/procedures/example.md"
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)

    with pytest.raises(ManifestError, match=r"System/procedures/example\.md.*symbolic link"):
        apply_overlay_plan(workspace, plan)
    assert outside.read_bytes() == b"stale target sentinel"
    assert not (workspace / "System/policy/one.md").exists()


@pytest.mark.parametrize("relative", ("../outside.txt", "/outside.txt", "System/../outside.txt"))
def test_apply_overlay_plan_rejects_forged_escape_paths(tmp_path, relative):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"forged plan sentinel")
    plan = OverlayPlan((OverlayWrite(relative, b"malicious"),), ())

    with pytest.raises(ManifestError, match="not normalized"):
        apply_overlay_plan(workspace, plan)
    assert outside.read_bytes() == b"forged plan sentinel"


def test_apply_overlay_plan_rejects_contained_non_overlay_target(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    welcome = workspace / "Welcome.md"
    welcome.write_bytes(b"welcome sentinel")
    plan = OverlayPlan((OverlayWrite("Welcome.md", b"malicious"),), ())

    with pytest.raises(ManifestError, match="outside managed folders"):
        apply_overlay_plan(workspace, plan)
    assert welcome.read_bytes() == b"welcome sentinel"


def test_apply_overlay_plan_rejects_write_remove_overlap(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    relative = "System/procedures/one.md"
    plan = OverlayPlan((OverlayWrite(relative, b"policy"),), (relative,))

    with pytest.raises(ManifestError, match="cannot write and remove"):
        apply_overlay_plan(workspace, plan)
    assert not (workspace / relative).exists()


def test_apply_overlay_plan_never_removes_policy_files(tmp_path):
    workspace = tmp_path / "workspace"
    policy = workspace / "System/policy/one.md"
    policy.parent.mkdir(parents=True)
    policy.write_bytes(b"policy sentinel")
    plan = OverlayPlan((), ("System/policy/one.md",))

    with pytest.raises(ManifestError, match="outside System/procedures"):
        apply_overlay_plan(workspace, plan)
    assert policy.read_bytes() == b"policy sentinel"
