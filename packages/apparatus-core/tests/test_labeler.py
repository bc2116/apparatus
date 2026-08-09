from __future__ import annotations

from pathlib import Path

from apparatus_core.labeler import Label, apply_labels, find_labels

FIXTURES = Path(__file__).parent / "fixtures/labeler"


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_each_fixed_pattern_class_is_detected_without_a_name_class():
    assert find_labels(_text("email.txt")) == [Label("pii/email", 1)]
    assert find_labels(_text("phone.txt")) == [Label("pii/phone", 1)]
    assert find_labels(_text("address.txt")) == [Label("pii/address", 1)]
    assert find_labels(_text("id.txt")) == [Label("pii/id", 1)]
    assert find_labels("Fictional Person") == []


def test_negative_prose_and_credential_fixtures_do_not_create_pii_labels():
    for name in (
        "negative.txt",
        "password.txt",
        "api-key.txt",
        "private-key.txt",
        "encrypted-private-key.txt",
        "ssn.txt",
        "card-valid.txt",
    ):
        assert find_labels(_text(name)) == []


def test_label_application_preserves_body_bytes_and_is_idempotent():
    body = "First line\r\nSecond line without final newline"
    record = (
        "---\r\nschema: apparatus/fact@v0\r\ntitle: Sample\r\nlabels:\r\n- custom/review\r\n- pii/phone\r\n---\r\n"
        + body
    )
    labels = find_labels("sample.person@example.invalid")
    refreshed = apply_labels(record, labels)
    assert refreshed.endswith(body)
    assert "custom/review" in refreshed
    assert "pii/email" in refreshed
    assert "pii/phone" not in refreshed
    assert apply_labels(refreshed, labels) == refreshed


def test_findings_never_carry_values_spans_hashes_or_excerpts():
    finding = find_labels("sample.person@example.invalid")[0]
    assert vars(finding) == {"name": "pii/email", "count": 1}
