"""Synthetic report consistency and strict input tests."""

import copy

import pytest
import yaml

from apparatus_mailbox_survey import validate_report
from apparatus_mailbox_survey.report import MAX_BYTES, MAX_ENTRIES


def report():
    return {
        "schema": "apparatus/mailbox-survey@v1", "action": "none",
        "scope": {"source": "connected-mailbox", "description": "Synthetic authorized scope", "coverage": "complete"},
        "inventory": {"total": 2, "reviewed": 2, "unavailable": 0, "skipped": 0, "unassessed": 0},
        "items": [{"id": "a", "source": "synthetic:a", "summary": "Synthetic receipt"}, {"id": "b", "source": "synthetic:b", "summary": "Synthetic delivery"}],
        "categories": [{"id": "purchases", "name": "Purchases", "description": "Synthetic purchase evidence", "examples": ["a"]}],
        "uncategorized": ["b"], "coverage_gaps": [], "next_steps": ["Consider a bounded follow-up survey."],
    }


def check(value):
    return validate_report(yaml.safe_dump(value))


def test_full_overlapping_and_uncategorized():
    value = report()
    assert check(value) == []
    value["categories"].append({"id": "deliveries", "name": "Deliveries", "description": "Overlap is allowed", "examples": ["a", "b"]})
    value["uncategorized"] = []
    assert check(value) == []


@pytest.mark.parametrize("coverage,total,gaps", [("sample", 2, []), ("partial", 2, ["Bounded synthetic selection"]), ("sample", None, ["Population unknown"]), ("partial", None, ["Population unknown"])])
def test_sample_partial_and_unknown(coverage, total, gaps):
    value = report()
    value["scope"].update(source="sample", coverage=coverage)
    value["inventory"]["total"] = total
    value["coverage_gaps"] = gaps
    assert check(value) == []


@pytest.mark.parametrize("coverage,source", [("complete", "connected-mailbox"), ("sample", "sample"), ("partial", "connected-mailbox")])
def test_empty(coverage, source):
    value = report()
    value["scope"].update(source=source, coverage=coverage)
    value["inventory"].update(total=0, reviewed=0)
    for name in ("items", "categories", "uncategorized"):
        value[name] = []
    value["coverage_gaps"] = ["No source coverage established"] if coverage == "partial" else []
    assert check(value) == []


@pytest.mark.parametrize("field", list(report()))
def test_missing_or_extra_top_fields(field):
    value = report()
    del value[field]
    assert check(value)
    value = report()
    value["delete"] = "SENSITIVE_MARKER"
    findings = check(value)
    assert findings and "SENSITIVE_MARKER" not in str(findings)


@pytest.mark.parametrize("section,index", [("scope", None), ("inventory", None), ("items", 0), ("categories", 0)])
def test_nested_exact_fields(section, index):
    value = report()
    target = value[section] if index is None else value[section][index]
    target["label"] = "ignored mutation"
    assert check(value)
    del target["label"]
    target.pop(next(iter(target)))
    assert check(value)


@pytest.mark.parametrize("bad", [True, False, -1, 1.0, float("inf"), float("nan"), "1", None, [], {}])
@pytest.mark.parametrize("field", ["reviewed", "unavailable", "skipped", "unassessed"])
def test_counts_strict(field, bad):
    value = report()
    value["inventory"][field] = bad
    assert check(value)


@pytest.mark.parametrize("bad", [True, -1, 2.0, float("inf"), float("nan"), "2"])
def test_total_strict(bad):
    value = report()
    value["inventory"]["total"] = bad
    assert check(value)


@pytest.mark.parametrize("case", ["status-sum", "reviewed-count", "unknown-complete", "sample-complete", "gaps-complete", "missing-partial-gap", "missing-unknown-gap", "missing-unavailable-gap", "skipped-complete", "unassessed-complete"])
def test_coverage_inventory_consistency(case):
    value = report()
    if case == "status-sum":
        value["inventory"]["total"] = 3
    elif case == "reviewed-count":
        value["inventory"].update(total=3, reviewed=3)
    elif case == "unknown-complete":
        value["inventory"]["total"] = None
    elif case == "sample-complete":
        value["scope"]["source"] = "sample"
    elif case == "gaps-complete":
        value["coverage_gaps"] = ["Gap"]
    elif case == "missing-partial-gap":
        value["scope"]["coverage"] = "partial"
    elif case == "missing-unknown-gap":
        value["scope"]["coverage"] = "sample"
        value["inventory"]["total"] = None
    elif case == "missing-unavailable-gap":
        value["scope"]["coverage"] = "sample"
        value["inventory"].update(total=3, unavailable=1)
    else:
        value["inventory"].update(total=3)
        value["inventory"][case.split("-")[0]] = 1
    assert check(value)


@pytest.mark.parametrize("case", ["duplicate-item", "duplicate-category", "duplicate-example", "dangling-example", "dangling-uncategorized", "duplicate-uncategorized", "covered-uncategorized", "hidden-omission", "empty-examples", "empty-items"])
def test_evidence_consistency(case):
    value = report()
    if case == "duplicate-item":
        value["items"][1]["id"] = "a"
    elif case == "duplicate-category":
        value["categories"].append(copy.deepcopy(value["categories"][0]))
    elif case == "duplicate-example":
        value["categories"][0]["examples"] = ["a", "a"]
    elif case == "dangling-example":
        value["categories"][0]["examples"] = ["missing"]
    elif case == "dangling-uncategorized":
        value["uncategorized"] = ["missing"]
    elif case == "duplicate-uncategorized":
        value["uncategorized"] = ["b", "b"]
    elif case == "covered-uncategorized":
        value["uncategorized"] = ["a", "b"]
    elif case == "hidden-omission":
        value["uncategorized"] = []
    elif case == "empty-examples":
        value["categories"][0]["examples"] = []
    else:
        value["items"] = []
    assert check(value)


@pytest.mark.parametrize("bad", ["Uppercase", "with_underscore", "two--hyphens", "-leading", "trailing-", "with space", "path/slash", "é", "x" * 65])
def test_portable_category_ids(bad):
    value = report()
    value["categories"][0]["id"] = bad
    assert check(value)


def test_item_id_limit_and_opaque_ids():
    value = report()
    value["items"][0]["id"] = "opaque:/é"
    value["categories"][0]["examples"] = ["opaque:/é"]
    assert check(value) == []
    value["items"][0]["id"] = "x" * 1025
    assert check(value)


@pytest.mark.parametrize("path", [("scope", "description"), ("items", 0, "id"), ("items", 0, "source"), ("items", 0, "summary"), ("categories", 0, "name"), ("categories", 0, "description"), ("next_steps", 0)])
@pytest.mark.parametrize("bad", ["", " \n ", None, 10, []])
def test_nonempty_strings(path, bad):
    value = report()
    target = value
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = bad
    assert check(value)


@pytest.mark.parametrize("content", [b"\xff", "\ud800", "[unclosed", "a: 1\na: 2", "a: &SECRET_ANCHOR []\nb: *SECRET_ANCHOR", "a: &SECRET_ANCHOR [*SECRET_ANCHOR]", "? [a,b]\n: value", "1: value", "!!python/object:example {}", "a: 1\n---\nb: 2", "[" * 65 + "]" * 65, "a: !!timestamp impossible"])
def test_malformed_yaml_and_safe_diagnostics(content):
    findings = validate_report(content)
    assert findings
    assert not any(token in str(findings) for token in ("SECRET_ANCHOR", "unclosed", "impossible", "example"))


def test_utf8_byte_limit():
    value = yaml.safe_dump(report(), allow_unicode=True)
    assert validate_report(value.encode()) == []
    padded = value + "#" + "x" * (MAX_BYTES - len(value.encode()) - 1)
    assert len(padded.encode()) == MAX_BYTES
    assert validate_report(padded) == []
    assert validate_report(padded + "x")
    assert validate_report("é" * (MAX_BYTES // 2 + 1))


def test_collection_limits():
    value = report()
    value["next_steps"] = ["Advice"] * MAX_ENTRIES
    assert check(value) == []
    value["next_steps"].append("Advice")
    assert check(value)
    assert validate_report("extra: {" + ", ".join(f"k{i}: v" for i in range(MAX_ENTRIES + 1)) + "}")


@pytest.mark.parametrize("section", ["items", "categories", "uncategorized", "coverage_gaps", "next_steps"])
def test_lists_required(section):
    value = report()
    value[section] = {}
    assert check(value)


def test_api_does_not_change_source_or_use_network(monkeypatch):
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected I/O")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr("builtins.open", forbidden)
    raw = yaml.safe_dump(report()).encode()
    before = bytes(raw)
    assert validate_report(raw) == []
    assert raw == before


@pytest.mark.parametrize("section,field,bad", [(None, "schema", "other"), (None, "action", "delete"), ("scope", "source", "provider"), ("scope", "coverage", "global"), ("scope", "source", []), ("scope", "coverage", {})])
def test_enumerations(section, field, bad):
    value = report()
    target = value if section is None else value[section]
    target[field] = bad
    assert check(value)


@pytest.mark.parametrize("status", ["unavailable", "skipped", "unassessed"])
def test_partial_status_with_gap_is_valid(status):
    value = report()
    value["scope"]["coverage"] = "partial"
    value["inventory"].update(total=3)
    value["inventory"][status] = 1
    value["coverage_gaps"] = ["One synthetic item was not reviewed"]
    assert check(value) == []


def test_nested_duplicate_key_and_unknown_tags():
    value = yaml.safe_dump(report())
    value = value.replace("  total: 2", "  total: 2\n  total: 2")
    assert validate_report(value)
    for content in ("a: !!set {x: null}", "a: !!binary YQ==", "a: {<<: {x: 1}}", "a: 2026-10-06"):
        assert validate_report(content)


def test_wrong_root_and_input_types():
    for content in ("", "[]", "null", "hello", "123", "true"):
        assert validate_report(content)
    assert validate_report(None)


@pytest.mark.parametrize("content", ["a: !!bool INVALID_MARKER", "a: !!int INVALID_MARKER", "a: !!float INVALID_MARKER", "a: !!map [INVALID_MARKER]", "a: !!seq INVALID_MARKER"])
def test_invalid_explicit_basic_tags_are_safe(content):
    findings = validate_report(content)
    assert findings
    assert "INVALID_MARKER" not in str(findings)


def test_multibyte_text_within_limit_is_valid():
    value = report()
    value["items"][0]["summary"] = "Synthetic café receipt"
    assert validate_report(yaml.safe_dump(value, allow_unicode=True).encode("utf-8")) == []


def test_all_reviewed_items_can_be_uncategorized():
    value = report()
    value["categories"] = []
    value["uncategorized"] = ["a", "b"]
    assert check(value) == []


def test_unused_anchors_rejected():
    value = yaml.safe_dump(report()).replace("action: none", "action: &unused none")
    assert validate_report(value)


def test_findings_bounded_and_no_values_echoed():
    value = report()
    value["items"] = [{"id": "SENSITIVE_MARKER", "source": "", "summary": ""} for _ in range(100)]
    findings = check(value)
    assert len(findings) == 51
    assert findings[-1] == "report: additional findings omitted"
    assert "SENSITIVE_MARKER" not in str(findings)
