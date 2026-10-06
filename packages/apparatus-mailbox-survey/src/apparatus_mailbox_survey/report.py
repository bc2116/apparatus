"""Validate report structure without retaining source content or taking actions."""

import re

import yaml
from yaml.events import AliasEvent, MappingStartEvent, SequenceStartEvent
from yaml.events import MappingEndEvent, SequenceEndEvent, ScalarEvent

MAX_BYTES = 1024 * 1024
MAX_ENTRIES = 10_000
MAX_DEPTH = 64
MAX_FINDINGS = 50
SCHEMA = "apparatus/mailbox-survey@v1"
_PORTABLE_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class _StrictLoader(yaml.SafeLoader):
    def construct_object(self, node, deep=False):
        if node.tag not in {
            "tag:yaml.org,2002:" + kind
            for kind in ("map", "seq", "str", "int", "float", "bool", "null")
        }:
            raise yaml.YAMLError("Unsupported value tag")
        return super().construct_object(node, deep=deep)

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise yaml.YAMLError("Invalid mapping keys")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _preflight(text):
    """Check events before construction, including parser recursion boundaries."""
    stack = []
    for event in yaml.parse(text, Loader=_StrictLoader):
        if isinstance(event, AliasEvent) or getattr(event, "anchor", None) is not None:
            raise yaml.YAMLError("Anchors and aliases are unsupported")
        if isinstance(event, (ScalarEvent, MappingStartEvent, SequenceStartEvent)):
            if stack:
                stack[-1][1] += 1
                if stack[-1][1] > stack[-1][0]:
                    raise yaml.YAMLError("Collection limit exceeded")
            if isinstance(event, (MappingStartEvent, SequenceStartEvent)):
                stack.append([MAX_ENTRIES * (2 if isinstance(event, MappingStartEvent) else 1), 0])
                if len(stack) > MAX_DEPTH:
                    raise yaml.YAMLError("Nesting limit exceeded")
        elif isinstance(event, (MappingEndEvent, SequenceEndEvent)):
            stack.pop()


def validate_report(content: bytes | str) -> list[str]:
    """Return value-free field findings; an empty list means structurally valid.

    Input is limited to 1 MiB of UTF-8, 10,000 entries per collection, and
    64 nested collections. Findings stop after 50 with a truncation marker.
    No files, network, or workspace state are accessed.
    This does not establish evidence quality or authority.
    """
    if not isinstance(content, (bytes, str)):
        return ["report: expected UTF-8 bytes or text"]
    try:
        raw = content if isinstance(content, bytes) else content.encode("utf-8")
        if len(raw) > MAX_BYTES:
            return ["report: exceeds 1 MiB limit"]
        text = raw.decode("utf-8")
    except UnicodeError:
        return ["report: invalid UTF-8"]
    try:
        _preflight(text)
        report = yaml.load(text, Loader=_StrictLoader)
    except (yaml.YAMLError, ValueError, TypeError, KeyError, AttributeError,
            RecursionError, OverflowError):
        return ["report: invalid YAML or unsupported keys, anchors, aliases, tags, or limits"]
    findings = []

    def error(path, message):
        if len(findings) < MAX_FINDINGS:
            findings.append(f"{path}: {message}")
        elif len(findings) == MAX_FINDINGS:
            findings.append("report: additional findings omitted")

    def fields(value, expected, path):
        if not isinstance(value, dict):
            error(path, "expected mapping")
            return False
        if set(value) != set(expected):
            error(path, "missing or unknown fields")
            return False
        return True

    def string(value, path):
        if not isinstance(value, str) or not value.strip():
            error(path, "expected nonempty string")
            return False
        return True

    def sequence(value, path):
        if not isinstance(value, list):
            error(path, "expected list")
            return False
        return True

    top = ("schema", "action", "scope", "inventory", "items", "categories",
           "uncategorized", "coverage_gaps", "next_steps")
    if not fields(report, top, "report"):
        return findings
    if report["schema"] != SCHEMA:
        error("schema", "unsupported schema")
    if report["action"] != "none":
        error("action", "must be none")

    coverage = None
    if fields(report["scope"], ("source", "description", "coverage"), "scope"):
        scope = report["scope"]
        if scope["source"] not in ("sample", "connected-mailbox"):
            error("scope.source", "unsupported source")
        string(scope["description"], "scope.description")
        coverage = scope["coverage"]
        if coverage not in ("sample", "partial", "complete"):
            error("scope.coverage", "unsupported coverage")
        if coverage == "complete" and scope["source"] != "connected-mailbox":
            error("scope.coverage", "complete requires connected-mailbox source")

    counts = None
    count_names = ("total", "reviewed", "unavailable", "skipped", "unassessed")
    if fields(report["inventory"], count_names, "inventory"):
        inventory = report["inventory"]
        valid_counts = True
        for name in count_names:
            value = inventory[name]
            if name == "total" and value is None:
                continue
            if type(value) is not int or value < 0:
                error(f"inventory.{name}", "expected nonnegative integer" + (" or null" if name == "total" else ""))
                valid_counts = False
        if valid_counts:
            counts = inventory
            if counts["total"] is not None and counts["total"] != sum(counts[name] for name in count_names[1:]):
                error("inventory.total", "must equal status sum")
            if coverage == "complete" and (counts["total"] is None or any(counts[name] for name in count_names[2:])):
                error("inventory", "complete requires known total and all items reviewed")

    item_ids = set()
    if sequence(report["items"], "items"):
        for index, item in enumerate(report["items"]):
            path = f"items[{index}]"
            if not fields(item, ("id", "source", "summary"), path):
                continue
            for name in ("id", "source", "summary"):
                string(item[name], f"{path}.{name}")
            if isinstance(item["id"], str):
                if len(item["id"]) > 1024:
                    error(f"{path}.id", "exceeds 1024 character limit")
                if item["id"] in item_ids:
                    error(f"{path}.id", "duplicate item ID")
                item_ids.add(item["id"])
        if counts is not None and len(report["items"]) != counts["reviewed"]:
            error("items", "count must equal inventory.reviewed")

    assigned = set()
    category_ids = set()
    if sequence(report["categories"], "categories"):
        for index, category in enumerate(report["categories"]):
            path = f"categories[{index}]"
            if not fields(category, ("id", "name", "description", "examples"), path):
                continue
            for name in ("id", "name", "description"):
                string(category[name], f"{path}.{name}")
            identity = category["id"]
            if isinstance(identity, str):
                if len(identity) > 64 or not _PORTABLE_ID.fullmatch(identity):
                    error(f"{path}.id", "expected portable ID")
                if identity in category_ids:
                    error(f"{path}.id", "duplicate category ID")
                category_ids.add(identity)
            if sequence(category["examples"], f"{path}.examples"):
                if not category["examples"]:
                    error(f"{path}.examples", "requires reviewed evidence")
                seen = set()
                for example_index, identity in enumerate(category["examples"]):
                    refpath = f"{path}.examples[{example_index}]"
                    if string(identity, refpath):
                        if identity in seen:
                            error(refpath, "duplicate evidence reference")
                        if identity not in item_ids:
                            error(refpath, "unknown reviewed item")
                        seen.add(identity)
                        assigned.add(identity)

    uncategorized = set()
    if sequence(report["uncategorized"], "uncategorized"):
        for index, identity in enumerate(report["uncategorized"]):
            path = f"uncategorized[{index}]"
            if string(identity, path):
                if identity in uncategorized:
                    error(path, "duplicate evidence reference")
                if identity not in item_ids:
                    error(path, "unknown reviewed item")
                if identity in assigned:
                    error(path, "item already categorized")
                uncategorized.add(identity)
    if item_ids - assigned - uncategorized:
        error("uncategorized", "reviewed items omitted from category coverage")
    for name in ("coverage_gaps", "next_steps"):
        if sequence(report[name], name):
            for index, explanation in enumerate(report[name]):
                string(explanation, f"{name}[{index}]")
    if isinstance(report["coverage_gaps"], list):
        if coverage == "complete" and report["coverage_gaps"]:
            error("coverage_gaps", "complete coverage cannot have gaps")
        gaps_required = coverage == "partial" or (counts is not None and (
            counts["total"] is None or any(counts[name] for name in count_names[2:])))
        if gaps_required and not report["coverage_gaps"]:
            error("coverage_gaps", "requires coverage explanations")
    return findings
