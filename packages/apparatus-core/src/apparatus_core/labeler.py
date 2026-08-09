"""Deterministic PII labeling for Memory records."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

import yaml

EMAIL = "pii/email"
PHONE = "pii/phone"
ADDRESS = "pii/address"
ID = "pii/id"
MANAGED_LABELS: tuple[str, ...] = (EMAIL, PHONE, ADDRESS, ID)


@dataclass(frozen=True)
class Label:
    """A stable label and count, never matched text or positional data."""

    name: str
    count: int


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        EMAIL,
        re.compile(
            r"(?i)(?<![\w.+-])[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
            r"[a-z0-9-]+(?:\.[a-z0-9-]+)+(?![\w-])"
        ),
    ),
    (
        PHONE,
        re.compile(
            r"(?<![\w\d])(?:\+?1[ .-])?(?:\(\d{3}\)[ ]?|\d{3}[ .-])"
            r"\d{3}[ .-]\d{4}(?![\w\d])"
        ),
    ),
    (
        ADDRESS,
        re.compile(
            r"(?ix)(?<!\w)\d{1,6}\s+"
            r"(?:[a-z0-9][a-z0-9.'-]*\s+){0,5}"
            r"(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|"
            r"court|ct|parkway|pkwy|place|pl|way)\.?(?!\w)"
        ),
    ),
    (
        ID,
        re.compile(
            r"(?ix)(?<!\w)(?:employee|customer|member|account|case|record)[ _-]?id"
            r"\s*[:#=]\s*[a-z0-9](?:[a-z0-9_-]{2,31})(?!\w)"
        ),
    ),
)


def find_labels(text: str) -> list[Label]:
    """Return deterministic class/count labels for *text*."""
    if not isinstance(text, str):
        raise TypeError("label input must be text")
    counts = Counter(
        {
            name: sum(1 for _match in pattern.finditer(text))
            for name, pattern in _PATTERNS
        }
    )
    return [Label(name, counts[name]) for name in MANAGED_LABELS if counts[name]]


def label_names(labels: Iterable[Label]) -> tuple[str, ...]:
    """Normalize labels to the fixed managed-label order."""
    found = {label.name for label in labels}
    unknown = found.difference(MANAGED_LABELS)
    if unknown:
        raise ValueError("unknown managed label")
    return tuple(name for name in MANAGED_LABELS if name in found)


def refresh_frontmatter_labels(data: dict, labels: Iterable[Label]) -> dict:
    """Replace stale managed labels while retaining unrelated labels in order."""
    existing = data.get("labels", [])
    if existing is None:
        existing = []
    if not isinstance(existing, list) or not all(
        isinstance(item, str) for item in existing
    ):
        raise ValueError("labels must be a flat list of strings")
    unmanaged = [item for item in existing if item not in MANAGED_LABELS]
    refreshed = unmanaged + list(label_names(labels))
    result = dict(data)
    if refreshed:
        result["labels"] = refreshed
    else:
        result.pop("labels", None)
    return result


def split_record_exact(text: str) -> tuple[dict, str]:
    """Parse frontmatter while returning the body with every character intact."""
    opening = re.match(r"\A---(?:\r\n|\n)", text)
    if opening is None:
        raise ValueError("record must start with a '---' frontmatter line")
    closing = re.search(r"(?m)^---(?P<ending>\r\n|\n|\Z)", text[opening.end() :])
    if closing is None:
        raise ValueError("frontmatter is never closed by a second '---' line")
    frontmatter_start = opening.end()
    frontmatter_end = frontmatter_start + closing.start()
    body_start = frontmatter_start + closing.end()
    data = yaml.safe_load(text[frontmatter_start:frontmatter_end])
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a YAML mapping")  # noqa: TRY004
    return data, text[body_start:]


def render_record(data: dict, body: str) -> str:
    """Render deterministic frontmatter without changing *body*."""
    frontmatter = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    return f"---\n{frontmatter}---\n{body}"


def apply_labels(record_text: str, labels: Iterable[Label]) -> str:
    """Refresh managed frontmatter labels and preserve the exact record body."""
    data, body = split_record_exact(record_text)
    refreshed = refresh_frontmatter_labels(data, labels)
    if refreshed == data:
        return record_text
    return render_record(refreshed, body)
