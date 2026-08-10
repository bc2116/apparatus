"""Machine-readable schemas for the seven v0 workspace record kinds.

Normative source: docs/spec/records.md. Per ADR-0002 the spec and this module
change together, and any record kind beyond these seven requires a new ADR.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field

import yaml

SCHEMA_VERSION = "v0"

RECEIPT_EVENTS: tuple[str, ...] = (
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
GOAL_STATUSES: tuple[str, ...] = ("active", "waiting", "done", "dropped")
PROFILE_STATUSES: tuple[str, ...] = ("unconfigured", "configured")
PRIVACY_MODES: tuple[str, ...] = ("standard", "private")
SPEND_LEVELS: tuple[str, ...] = ("frugal", "balanced", "thorough")
REVIEW_DAYS: tuple[str, ...] = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

KEBAB_FILENAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
RECEIPT_FILENAME = re.compile(
    r"^(\d{4}-\d{2}-\d{2}-\d{6})-("
    + "|".join(RECEIPT_EVENTS)
    + r")(?:-(?:[2-9]|[1-9]\d+))?\.md$"
)
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

FRONTMATTER_DELIMITER = "---"


@dataclass(frozen=True)
class RecordSchema:
    """One record kind: field requirements, enums, and filename rule."""

    kind: str
    required: tuple[str, ...]
    optional: tuple[str, ...]
    enums: dict[str, tuple[str, ...]] = field(default_factory=dict)
    filename_rule: str = "kebab-case: lowercase a-z, digits, single hyphens, .md"
    filename_pattern: re.Pattern | None = KEBAB_FILENAME
    markdown_body: bool = True
    closed: bool = False  # True: no keys beyond required + optional (profile)

    @property
    def schema_id(self) -> str:
        return f"apparatus/{self.kind}@{SCHEMA_VERSION}"


SCHEMAS: dict[str, RecordSchema] = {
    "procedure": RecordSchema(
        kind="procedure",
        required=("schema", "title", "intent"),
        optional=("labels",),
    ),
    "goal": RecordSchema(
        kind="goal",
        required=("schema", "title", "owner", "status", "done-when", "next-action"),
        optional=("labels",),
        enums={"status": GOAL_STATUSES},
    ),
    "decision": RecordSchema(
        kind="decision",
        required=("schema", "title", "date"),
        optional=("labels",),
    ),
    "fact": RecordSchema(
        kind="fact",
        required=("schema", "title"),
        optional=("source", "labels"),
    ),
    "person": RecordSchema(
        kind="person",
        required=("schema", "name"),
        optional=("role", "organization", "labels"),
    ),
    "profile": RecordSchema(
        kind="profile",
        required=("schema", "status", "privacy_mode", "work_types", "review_day"),
        optional=("spend",),
        enums={
            "status": PROFILE_STATUSES,
            "privacy_mode": PRIVACY_MODES,
            "spend": SPEND_LEVELS,
        },
        filename_rule="fixed name: profile.yaml",
        filename_pattern=re.compile(r"^profile\.yaml$"),
        markdown_body=False,
        closed=True,
    ),
    "receipt": RecordSchema(
        kind="receipt",
        required=("schema", "event", "timestamp", "summary"),
        optional=("labels",),
        enums={"event": RECEIPT_EVENTS},
        filename_rule=(
            "YYYY-MM-DD-HHMMSS-<event>.md, UTC, all lowercase; "
            "same-second collisions append -2, -3, ... before the extension"
        ),
        filename_pattern=RECEIPT_FILENAME,
    ),
}


def parse_record(text: str) -> tuple[dict, str]:
    """Split a Markdown record into (frontmatter dict, body).

    The record must open with a `---` line and close the frontmatter with a
    second `---` line (ADR-0002). Raises ValueError on malformed input.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
        raise ValueError("record must start with a '---' frontmatter line")
    for index in range(1, len(lines)):
        if lines[index].strip() == FRONTMATTER_DELIMITER:
            frontmatter = yaml.safe_load("\n".join(lines[1:index]))
            if not isinstance(frontmatter, dict):
                raise ValueError("frontmatter must be a YAML mapping")
            body = "\n".join(lines[index + 1 :])
            return frontmatter, body
    raise ValueError("frontmatter is never closed by a second '---' line")


def _is_date(value: object) -> bool:
    if isinstance(value, _dt.datetime):
        return False  # a date field must be a date, not a timestamp
    if isinstance(value, _dt.date):
        return True
    return isinstance(value, str) and bool(_DATE.match(value))


def _is_utc_timestamp(value: object) -> bool:
    if isinstance(value, _dt.datetime):
        return value.tzinfo is not None and value.utcoffset() == _dt.timedelta(0)
    return isinstance(value, str) and bool(_UTC_TIMESTAMP.match(value))


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def validate(kind: str, data: dict, filename: str | None = None) -> list[str]:
    """Validate parsed record data (and optionally its filename).

    Returns a list of plain-language problems; an empty list means valid.
    """
    problems: list[str] = []
    schema = SCHEMAS.get(kind)
    if schema is None:
        return [f"unknown record kind: {kind!r} (the seven kinds are {sorted(SCHEMAS)})"]

    for name in schema.required:
        value = data.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            # profile's review_day is the one nullable required field, but the
            # key itself must still be present (the profile key set is closed)
            if (
                schema.kind == "profile"
                and name == "review_day"
                and name in data
                and value is None
            ):
                continue
            problems.append(f"required field missing or empty: {name}")

    expected_schema = schema.schema_id
    if "schema" in data and data["schema"] != expected_schema:
        problems.append(f"schema must be {expected_schema!r}, found {data['schema']!r}")

    for name, allowed in schema.enums.items():
        value = data.get(name)
        if value is not None and value not in allowed:
            problems.append(f"{name} must be one of {', '.join(allowed)}; found {value!r}")

    if "labels" in data and data["labels"] is not None and not _is_string_list(data["labels"]):
        problems.append("labels must be a flat list of strings")

    if schema.closed:
        allowed_keys = set(schema.required) | set(schema.optional)
        for name in data:
            if name not in allowed_keys:
                problems.append(f"profile keys are closed; unexpected key: {name}")

    if schema.kind == "profile":
        if not _is_string_list(data.get("work_types", [])):
            problems.append("work_types must be a list of strings")
        review_day = data.get("review_day")
        if review_day is not None and review_day not in REVIEW_DAYS:
            problems.append(
                f"review_day must be null or one of {', '.join(REVIEW_DAYS)}; found {review_day!r}"
            )

    if schema.kind == "decision" and "date" in data and not _is_date(data["date"]):
        problems.append("date must be YYYY-MM-DD")

    if schema.kind == "receipt":
        if "timestamp" in data and not _is_utc_timestamp(data["timestamp"]):
            problems.append("timestamp must be UTC ISO 8601, e.g. 2026-08-09T14:15:30Z")
        if filename is not None:
            match = RECEIPT_FILENAME.match(filename)
            if match and data.get("event") and match.group(2) != data["event"]:
                problems.append(
                    f"filename event {match.group(2)!r} must equal the event field {data['event']!r}"
                )

    if filename is not None and schema.filename_pattern is not None:
        if not schema.filename_pattern.match(filename):
            problems.append(f"filename {filename!r} violates the rule: {schema.filename_rule}")

    return problems
