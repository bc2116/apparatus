"""Preserve the pre-split Windows coverage and its required aggregate gate."""
from __future__ import annotations

from collections import Counter
import os
from pathlib import Path
import shlex
import shutil
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
# Deliberate coverage changes must update this baseline and their acceptance evidence.
BASELINE_SELECTORS = """
packages/apparatus-core/tests/test_credentials.py
packages/apparatus-core/tests/test_fs_transactions.py
packages/apparatus-core/tests/test_labeler.py
packages/apparatus-core/tests/test_library_ingest.py
packages/apparatus-core/tests/test_library_index.py
packages/apparatus-core/tests/test_library_sources.py
packages/apparatus-core/tests/test_library_cards.py
packages/apparatus-core/tests/test_library_references.py
packages/apparatus-core/tests/test_library_reference_boundaries.py
packages/apparatus-core/tests/test_library_index_sources.py
packages/apparatus-core/tests/test_render.py
packages/apparatus-core/tests/test_instruction_updates.py
packages/apparatus-core/tests/test_explicit_memory_capture.py
packages/apparatus-core/tests/test_learned_skills.py
packages/apparatus-core/tests/test_skills.py
packages/apparatus-core/tests/test_skill_migration.py
packages/apparatus-core/tests/test_skill_checks.py
packages/apparatus-core/tests/test_skill_overlays.py
packages/apparatus-core/tests/test_skill_recovery.py
packages/apparatus-core/tests/test_task_first_welcome.py
packages/apparatus-core/tests/test_r6_skills.py
conformance/test_r6_guidance.py
packages/apparatus-core/tests/test_memory_lifecycle.py
packages/apparatus-core/tests/test_task_retention.py
packages/apparatus-core/tests/test_memory_profile_retention.py
packages/apparatus-core/tests/test_library_retention.py
packages/apparatus-core/tests/test_receipt_retention.py
packages/apparatus-core/tests/test_snapshot_retention.py
packages/apparatus-core/tests/test_workspace_layout.py
packages/apparatus-core/tests/test_workarea_adoption.py
packages/apparatus-core/tests/test_project_binding.py
packages/apparatus-core/tests/test_decision_memory.py
packages/apparatus-core/tests/test_managed_state_recovery.py
packages/apparatus-core/tests/test_managed_state_backup.py
packages/apparatus-core/tests/test_managed_recovery_commands.py
packages/apparatus-core/tests/test_backup.py
packages/apparatus-core/tests/test_receipts.py
packages/apparatus-core/tests/test_machine_report.py
packages/apparatus-core/tests/test_init.py
packages/apparatus-core/tests/test_memory_commands.py::test_standard_fact_scans_title_and_body_writes_labels_redaction_receipt_and_checks_clean
packages/apparatus-core/tests/test_memory_commands.py::test_standard_person_scans_name_role_and_body_but_stores_no_structural_fifth_label
packages/apparatus-core/tests/test_memory_commands.py::test_every_private_add_person_blocks_structurally_with_zero_effects
packages/apparatus-core/tests/test_memory_commands.py::test_private_sweep_redacts_refreshes_stale_managed_labels_keeps_unrelated_and_is_idempotent
packages/apparatus-core/tests/test_memory_commands.py::test_new_record_retries_suffix_when_exclusive_open_loses_a_race
packages/apparatus-core/tests/test_interview_profiles.py
packages/apparatus-core/tests/test_quiet_operations.py
packages/apparatus-core/tests/test_quiet_guidance.py
packages/apparatus-core/tests/test_check.py
packages/apparatus-core/tests/test_recall.py
packages/apparatus-core/tests/test_snapshots.py
conformance/test_welcome_e2e.py
packages/apparatus-core/tests/test_feature_selection.py
conformance/test_payload_archive.py
conformance/test_bootstrap_dry_run.py
""".split()
ETW = "conformance/test_bootstrap_dry_run.py::test_windows_optional_etw_witness_has_no_file_registry_or_network_syscalls"


def _jobs():
    return yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))["jobs"]


def test_windows_groups_preserve_each_selector_and_the_scoped_etw_exclusion():
    job = _jobs()["windows-safety"]
    assert job["runs-on"] == "windows-latest"
    assert job["permissions"] == {"contents": "read"}
    assert job["strategy"]["fail-fast"] is False
    assert not job.get("continue-on-error")
    groups = job["strategy"]["matrix"]["include"]
    assert len(groups) == 4
    assert len({group["group"] for group in groups}) == 4
    selected, excluded = [], []
    for group in groups:
        args = shlex.split(group["tests"])
        assert args
        if "--deselect" in args:
            position = args.index("--deselect")
            excluded.extend(args[position + 1:])
            args = args[:position]
        assert all(arg.startswith(("packages/", "conformance/")) for arg in args)
        selected.extend(args)
    assert Counter(selected) == Counter(BASELINE_SELECTORS)
    assert excluded == [ETW]
    step = job["steps"][-1]
    assert step["run"] == "uv run pytest --durations=20 ${{ matrix.tests }}"
    assert not step.get("continue-on-error")


def test_windows_aggregate_retains_the_required_check_and_always_observes_matrix():
    jobs = _jobs()
    gate = jobs["windows-safety-result"]
    assert gate["name"] == "windows-safety"
    assert gate["needs"] == "windows-safety"
    assert gate["if"] == "${{ always() }}"
    assert gate["permissions"] == {}
    assert not gate.get("continue-on-error")
    assert jobs["windows-safety"]["name"] == "Windows safety (${{ matrix.group }})"
    assert gate["steps"][0]["env"] == {
        "WINDOWS_SAFETY_RESULT": "${{ needs.windows-safety.result }}"
    }


@pytest.mark.parametrize("result", ["success", "failure", "cancelled", "skipped", "", "unknown"])
def test_windows_aggregate_accepts_only_success(result):
    shell = shutil.which("bash")
    if shell is None:
        pytest.skip("aggregate runs on an Ubuntu runner with bash")
    gate = _jobs()["windows-safety-result"]["steps"][0]
    process = subprocess.run(
        [shell, "-c", gate["run"]],
        env={**os.environ, "WINDOWS_SAFETY_RESULT": result},
        capture_output=True, text=True, check=False, timeout=5,
    )
    assert (process.returncode == 0) == (result == "success")
