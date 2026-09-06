import re
from pathlib import Path

import yaml

from apparatus_core import records, skills

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN = REPO_ROOT / "conformance" / "golden" / "records"
SHIPPED_PROFILE = REPO_ROOT / "starter" / "payload" / "System" / "profile.yaml"
SHIPPED_SKILLS = REPO_ROOT / "starter/payload/.agents/skills"
EXPECTED_SHIPPED_SKILLS = {
    "apparatus-produce-deliverable",
    "apparatus-research-and-summarize",
    "apparatus-review-against-checklist",
    "apparatus-weekly-review",
    "apparatus-welcome",
}


def _golden_files() -> list[tuple[str, Path]]:
    found = [
        (kind_dir.name, path)
        for kind_dir in sorted(GOLDEN.iterdir())
        if kind_dir.is_dir()
        for path in sorted(kind_dir.iterdir())
        if path.is_file()
    ]
    assert found, "no golden records found"
    return found


def test_every_kind_has_at_least_one_golden_example():
    kinds = {kind for kind, _ in _golden_files()}
    assert kinds == set(records.SCHEMAS), (
        f"golden coverage mismatch: missing {set(records.SCHEMAS) - kinds}, "
        f"unexpected {kinds - set(records.SCHEMAS)}"
    )


def test_golden_records_are_valid():
    failures = []
    for kind, path in _golden_files():
        text = path.read_text(encoding="utf-8")
        if records.SCHEMAS[kind].markdown_body:
            data, _body = records.parse_record(text)
        else:
            data = yaml.safe_load(text)
        problems = records.validate(kind, data, filename=path.name)
        if problems:
            failures.append(f"{path.relative_to(REPO_ROOT)}: {problems}")
    assert not failures, "\n".join(failures)


def test_shipped_payload_profile_is_valid():
    data = yaml.safe_load(SHIPPED_PROFILE.read_text(encoding="utf-8"))
    problems = records.validate("profile", data, filename=SHIPPED_PROFILE.name)
    assert not problems, problems


def test_shipped_starter_skills_are_valid():
    paths = sorted(SHIPPED_SKILLS.glob("*/SKILL.md"))
    assert {path.parent.name for path in paths} == EXPECTED_SHIPPED_SKILLS

    failures = []
    for path in paths:
        try:
            data, body = records.parse_record(path.read_text(encoding="utf-8"))
        except ValueError as error:
            failures.append(f"{path.relative_to(REPO_ROOT)}: {error}")
            continue
        problems = skills.validate_skill(path.read_bytes(), path.parent.name)
        step_numbers = [
            int(match.group(1))
            for line in body.splitlines()
            if (match := re.match(r"^(\d+)\. ", line))
        ]
        if not step_numbers or step_numbers != list(range(1, len(step_numbers) + 1)):
            problems.append("body must contain consecutively numbered steps starting at 1")
        if problems:
            failures.append(f"{path.relative_to(REPO_ROOT)}: {problems}")

    assert not failures, "\n".join(failures)


def test_shipped_starter_skills_use_native_authority_without_share_markers():
    for path in sorted(SHIPPED_SKILLS.glob("*/SKILL.md")):
        _data, body = records.parse_record(path.read_text(encoding="utf-8"))
        text = " ".join(body.split())
        assert "[share]" not in text
        assert "egress" not in text.lower()
        assert "the user's authority" in text
        assert "native permissions" in text


def test_welcome_skill_ends_with_snapshot_and_receipt_confirmation():
    _data, body = records.parse_record(
        (SHIPPED_SKILLS / "apparatus-welcome/SKILL.md").read_text(encoding="utf-8")
    )
    steps = [
        (int(match.group(1)), line)
        for line in body.splitlines()
        if (match := re.match(r"^(\d+)\. ", line))
    ]
    assert steps[-2][0] == 8 and "snapshot" in steps[-2][1].lower()
    assert steps[-1][0] == 9 and "receipt" in steps[-1][1].lower()


def test_missing_required_field_is_a_problem():
    data, _ = records.parse_record(
        (GOLDEN / "goal" / "finish-quarterly-quality-report.md").read_text(encoding="utf-8")
    )
    del data["done-when"]
    assert any("done-when" in p for p in records.validate("goal", data))


def test_bad_enum_value_is_a_problem():
    assert any(
        "status" in p
        for p in records.validate(
            "goal",
            {
                "schema": "apparatus/goal@v0",
                "title": "t",
                "owner": "o",
                "status": "someday",
                "done-when": "d",
                "next-action": "n",
            },
        )
    )


def test_receipt_event_enum_retains_the_ten_v1_values_for_historical_records():
    assert records.RECEIPT_EVENTS == (
        "check",
        "redaction",
        "snapshot",
        "restore",
        "init",
        "egress",
        "library-ingest",
        "recall",
        "profile-apply",
        "backup-export",
    )


def test_receipt_filename_rules():
    ok = records.validate(
        "receipt",
        {
            "schema": "apparatus/receipt@v0",
            "event": "snapshot",
            "timestamp": "2026-08-09T14:15:30Z",
            "summary": "s",
        },
        filename="2026-08-09-141530-snapshot.md",
    )
    assert ok == []
    base = {
        "schema": "apparatus/receipt@v0",
        "event": "snapshot",
        "timestamp": "2026-08-09T14:15:30Z",
        "summary": "s",
    }
    for suffix in ("-2", "-9", "-10", "-19", "-20", "-100"):
        assert (
            records.validate("receipt", base, filename=f"2026-08-09-141530-snapshot{suffix}.md")
            == []
        ), f"legal collision suffix rejected: {suffix}"
    for bad_suffix in ("-0", "-1", "-02"):
        assert records.validate(
            "receipt", base, filename=f"2026-08-09-141530-snapshot{bad_suffix}.md"
        ), f"illegal collision suffix accepted: {bad_suffix}"
    wrong_event = records.validate(
        "receipt",
        {
            "schema": "apparatus/receipt@v0",
            "event": "check",
            "timestamp": "2026-08-09T14:15:30Z",
            "summary": "s",
        },
        filename="2026-08-09-141530-snapshot.md",
    )
    assert any("must equal the event field" in p for p in wrong_event)
    uppercase = records.validate(
        "receipt",
        {
            "schema": "apparatus/receipt@v0",
            "event": "check",
            "timestamp": "2026-08-09T14:15:30Z",
            "summary": "s",
        },
        filename="2026-08-09T141530Z-check.md",
    )
    assert any("violates the rule" in p for p in uppercase)


def test_profile_key_set_is_closed():
    data = yaml.safe_load(SHIPPED_PROFILE.read_text(encoding="utf-8"))
    data["nickname"] = "buddy"
    assert any("closed" in p for p in records.validate("profile", data))


def test_profile_review_day_key_must_be_present_even_when_null():
    data = yaml.safe_load(SHIPPED_PROFILE.read_text(encoding="utf-8"))
    assert data["review_day"] is None and records.validate("profile", data) == []
    del data["review_day"]
    assert any("review_day" in p for p in records.validate("profile", data))


def test_profile_spend_accepts_only_canonical_values_and_is_optional():
    assert records.SPEND_LEVELS == ("frugal", "balanced", "thorough")
    data = yaml.safe_load(SHIPPED_PROFILE.read_text(encoding="utf-8"))
    for spend in records.SPEND_LEVELS:
        data["spend"] = spend
        assert records.validate("profile", data) == []

    data["spend"] = "cheap"
    problems = records.validate("profile", data)
    assert any("spend must be one of frugal, balanced, thorough" in problem for problem in problems)

    data["spend"] = None
    problems = records.validate("profile", data)
    assert any("spend must be one of frugal, balanced, thorough" in problem for problem in problems)

    del data["spend"]
    assert records.validate("profile", data) == []


def test_kebab_filename_rule():
    data = {"schema": "apparatus/fact@v0", "title": "t"}
    assert records.validate("fact", data, filename="ok-name-2.md") == []
    assert any(
        "violates the rule" in p
        for p in records.validate("fact", data, filename="Not_Kebab.md")
    )


def test_historical_egress_receipt_remains_valid():
    data = {
        "schema": "apparatus/receipt@v0",
        "event": "egress",
        "timestamp": "2026-08-09T14:15:30Z",
        "summary": "Historical sharing decision from an earlier payload.",
        "decision": "stop",
        "outcome": "stopped",
        "anything_left_workspace": False,
    }
    assert records.validate(
        "receipt", data, filename="2026-08-09-141530-egress.md"
    ) == []
