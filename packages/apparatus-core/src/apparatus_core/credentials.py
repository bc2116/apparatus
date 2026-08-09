"""Deterministic credential-floor redaction for durable workspace text."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class RedactionFinding:
    """A stable credential class and count, never a matched value or span."""

    credential_class: str
    count: int


@dataclass(frozen=True)
class _Candidate:
    start: int
    end: int
    credential_class: str


_PRIVATE_KEY = re.compile(
    r"-----BEGIN (?P<kind>(?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY)-----"
    r"[\s\S]*?"
    r"-----END (?P=kind)-----"
)

# Assignment matching is deliberately bounded to explicit credential words.
# The captured value excludes whitespace and common prose delimiters. Quoted
# values keep their quotes; only their contents are replaced.
_ASSIGNMENT = re.compile(
    r"(?ix)"
    r"\b(?P<name>password|passwd|pwd|api[_-]?key|access[_-]?token|auth[_-]?token|"
    r"bearer[_-]?token|token)\b"
    r"(?P<between>\s*[:=]\s*)"
    r"(?:(?P<quote>['\"])(?P<quoted>[^'\"\r\n]+)(?P=quote)|"
    r"(?P<plain>[^\s,;\[\]{}()&#<>]+))"
)
_SSN = re.compile(r"(?<!\w)\d{3}-\d{2}-\d{4}(?!\w)")
_CARD = re.compile(r"(?<!\w)(?<!\d[ -])(?:\d[ -]?){12,18}\d(?![ -]?\d)(?!\w)")
_PLACEHOLDER = re.compile(r"^\[redacted-[a-z-]+\]$")


def _assignment_candidates(text: str) -> Iterable[_Candidate]:
    for match in _ASSIGNMENT.finditer(text):
        value_group = "quoted" if match.group("quoted") is not None else "plain"
        value = match.group(value_group)
        end = match.end(value_group)
        if value_group == "plain":
            # Keep sentence punctuation outside an unquoted assigned value.
            trimmed = value.rstrip(".!?)")
            if not trimmed:
                continue
            end -= len(value) - len(trimmed)
            value = trimmed
        if _PLACEHOLDER.fullmatch(value):
            continue
        name = match.group("name").casefold().replace("-", "_")
        credential_class = (
            "password" if name in {"password", "passwd", "pwd"} else "api-key"
        )
        yield _Candidate(match.start(value_group), end, credential_class)


def _luhn_valid(value: str) -> bool:
    digits = [int(character) for character in value if character.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _pattern_candidates(
    text: str,
    pattern: re.Pattern[str],
    credential_class: str,
    predicate: Callable[[str], bool] | None = None,
) -> Iterable[_Candidate]:
    for match in pattern.finditer(text):
        if predicate is None or predicate(match.group(0)):
            yield _Candidate(match.start(), match.end(), credential_class)


def _candidates(text: str) -> list[_Candidate]:
    # Earlier classes win the unlikely case of an overlap. Assignments precede
    # identifier patterns so only the assigned value is replaced.
    ordered = [
        *_pattern_candidates(text, _PRIVATE_KEY, "private-key"),
        *_assignment_candidates(text),
        *_pattern_candidates(text, _SSN, "government-id"),
        *_pattern_candidates(text, _CARD, "payment-card", _luhn_valid),
    ]
    accepted: list[_Candidate] = []
    for candidate in ordered:
        if any(
            candidate.start < item.end and item.start < candidate.end
            for item in accepted
        ):
            continue
        accepted.append(candidate)
    return sorted(accepted, key=lambda item: item.start)


def redact(text: str) -> tuple[str, list[RedactionFinding]]:
    """Replace credential-floor matches and return class/count-only findings."""
    if not isinstance(text, str):
        raise TypeError("credential-floor input must be text")
    candidates = _candidates(text)
    if not candidates:
        return text, []
    pieces: list[str] = []
    counts: Counter[str] = Counter()
    cursor = 0
    for candidate in candidates:
        pieces.append(text[cursor : candidate.start])
        pieces.append(f"[redacted-{candidate.credential_class}]")
        counts[candidate.credential_class] += 1
        cursor = candidate.end
    pieces.append(text[cursor:])
    findings = [
        RedactionFinding(credential_class=name, count=counts[name])
        for name in sorted(counts)
    ]
    return "".join(pieces), findings
