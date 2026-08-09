from __future__ import annotations

from pathlib import Path

import pytest
from apparatus_core.credentials import RedactionFinding, redact

FIXTURES = Path(__file__).parent / "fixtures/labeler"


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("fixture", "credential_class", "placeholder"),
    [
        ("password.txt", "password", "[redacted-password]"),
        ("api-key.txt", "api-key", "[redacted-api-key]"),
        ("private-key.txt", "private-key", "[redacted-private-key]"),
        ("encrypted-private-key.txt", "private-key", "[redacted-private-key]"),
        ("ssn.txt", "government-id", "[redacted-government-id]"),
        ("card-valid.txt", "payment-card", "[redacted-payment-card]"),
    ],
)
def test_each_floor_class_is_replaced_in_place_with_surrounding_prose(
    fixture, credential_class, placeholder
):
    original = _text(fixture)
    clean, findings = redact(original)
    assert placeholder in clean
    assert clean[:10] == original[:10]
    assert clean.endswith((".\n", "material ends.\n"))
    assert findings == [RedactionFinding(credential_class, 1)]


def test_invalid_luhn_and_undelimited_nine_digits_are_unchanged():
    original = _text("negative.txt")
    assert redact(original) == (original, [])


def test_overlap_order_and_replacements_are_idempotent():
    original = "token=4242424242424242 and password='sample-only'"
    once, findings = redact(original)
    twice, second_findings = redact(once)
    assert once == "token=[redacted-api-key] and password='[redacted-password]'"
    assert findings == [RedactionFinding("api-key", 1), RedactionFinding("password", 1)]
    assert twice == once
    assert second_findings == []


def test_unquoted_assignment_keeps_surrounding_sentence_punctuation():
    clean, findings = redact("Keep this sentence: password=sample-only.")
    assert clean == "Keep this sentence: password=[redacted-password]."
    assert findings == [RedactionFinding("password", 1)]
    assert redact(clean) == (clean, [])


def test_unquoted_assignments_stop_at_structural_delimiters_without_altering_them():
    original = (
        "[password=sample-one] {token=sample-two} "
        "?api_key=sample-three&next=yes password=sample-four#section"
    )
    clean, findings = redact(original)
    assert clean == (
        "[password=[redacted-password]] {token=[redacted-api-key]} "
        "?api_key=[redacted-api-key]&next=yes "
        "password=[redacted-password]#section"
    )
    assert findings == [
        RedactionFinding("api-key", 2),
        RedactionFinding("password", 2),
    ]


def test_identifier_candidates_embedded_in_alphanumeric_text_are_unchanged():
    original = "REF000-12-3456END REF4242424242424242END REF4000 0000 0000 0000 006"
    assert redact(original) == (original, [])


def test_findings_carry_only_stable_class_and_count_metadata():
    _clean, findings = redact("password=sample-only")
    assert vars(findings[0]) == {"credential_class": "password", "count": 1}
    serialized = repr(findings)
    assert "sample-only" not in serialized
