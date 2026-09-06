"""Portable built-in Skill metadata, validation and legacy file pointers."""

from __future__ import annotations

import hashlib
import re

from apparatus_core import records

BUILTIN_SKILLS = {
    f"System/procedures/{slug}.md": f"apparatus-{slug}"
    for slug in ("welcome", "produce-deliverable", "research-and-summarize",
                 "review-against-checklist", "weekly-review")
}
BUILTIN_PATHS = {f".agents/skills/{name}/SKILL.md": name for name in BUILTIN_SKILLS.values()}
_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}

# Complete PR-38 shipped orientation bytes, normalized only for CRLF. Keep
# these historical witnesses when later payload revisions change the prose.
_SKILL_ORIENTATION_DIGESTS = {
    "Welcome.md": "9c9612b04aae89667e0f9697d99a9b146dc2ee9f4d143c19dc54534cb1ecad87",
    "System/README.md": "32d22c2e88c1cd3aa49a3dc74b6d54d84bc51c5ed3c96b19e59553796fde911d",
}

SKILL_INDEX = """<!-- Apparatus Skill index: v1 -->
## Skills

Read the relevant Skill from this work-area root; keep the other bodies closed.

- Getting started: `.agents/skills/apparatus-welcome/SKILL.md`.
- Producing finished work: `.agents/skills/apparatus-produce-deliverable/SKILL.md`.
- Research with sources: `.agents/skills/apparatus-research-and-summarize/SKILL.md`.
- A requested checklist review: `.agents/skills/apparatus-review-against-checklist/SKILL.md`.
- A requested weekly review: `.agents/skills/apparatus-weekly-review/SKILL.md`.

Skills provide instructions for the assistant. Apparatus does not execute them
or call a model. Ordinary file reading is the fallback when native discovery is
unavailable. In a project, use its explicit work-area link before resolving paths.
<!-- /Apparatus Skill index -->
"""


def valid_name(value: object) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= 64 and bool(_NAME.fullmatch(value))


def canonical_path(name: str) -> str:
    if not valid_name(name):
        raise ValueError("Skill name must use lowercase letters, digits and single internal hyphens.")
    return f".agents/skills/{name}/SKILL.md"


def _unique_keys(node: object, checked: dict[int, bool] | None = None) -> bool:
    """Reject duplicate mapping keys and recursive aliases before YAML coercion."""
    if checked is None:
        checked = {}
    if id(node) in checked:
        return checked[id(node)]
    checked[id(node)] = False
    valid = True
    if isinstance(node, records.yaml.MappingNode):
        keys = [key.value for key, _ in node.value
                if isinstance(key, records.yaml.ScalarNode)
                and key.tag == "tag:yaml.org,2002:str"]
        valid = (len(keys) == len(node.value) and len(keys) == len(set(keys))
                 and all(_unique_keys(value, checked) for _, value in node.value))
    elif isinstance(node, records.yaml.SequenceNode):
        valid = all(_unique_keys(value, checked) for value in node.value)
    checked[id(node)] = valid
    return valid


def validate_skill(content: bytes | str, expected_name: str) -> list[str]:
    """Validate the common portable format, without treating fields as authority."""
    try:
        text = content.decode("utf-8", errors="strict") if isinstance(content, bytes) else content
        lines = text.splitlines(keepends=True)
        if not lines or lines[0].rstrip("\r\n") != "---":
            return ["Skill must start with YAML frontmatter."]
        closing = next((i for i in range(1, len(lines)) if lines[i].rstrip("\r\n") == "---"), None)
        if closing is None:
            return ["Skill frontmatter needs a closing delimiter."]
        header = "".join(lines[1:closing])
        node = records.yaml.compose(header)
        if not isinstance(node, records.yaml.MappingNode):
            return ["Skill frontmatter must be a mapping."]
        if not _unique_keys(node):
            return ["Skill frontmatter keys must be unique scalar names."]
        data = records.yaml.safe_load(header)
    except (UnicodeError, AttributeError, TypeError, RecursionError, records.yaml.YAMLError):
        return ["Skill must be UTF-8 with valid YAML frontmatter."]
    problems = []
    if set(data) - _FIELDS:
        problems.append("Skill frontmatter contains unsupported portable fields.")
    name = data.get("name")
    if not valid_name(name) or name != expected_name:
        problems.append("Skill name must be valid and match its directory name.")
    description = data.get("description")
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        problems.append("Skill description must contain 1 through 1024 characters.")
    for field, limit in (("license", None), ("compatibility", 500), ("allowed-tools", None)):
        if field in data:
            value = data[field]
            if not isinstance(value, str) or not value.strip() or (limit is not None and len(value) > limit):
                problems.append(f"Skill {field} must be a nonempty string" + (f" of at most {limit} characters." if limit else "."))
    if "metadata" in data:
        metadata = data["metadata"]
        if not isinstance(metadata, dict) or any(not isinstance(key, str) or not isinstance(value, str)
                                                 for key, value in metadata.items()):
            problems.append("Skill metadata must map strings to strings.")
    if not "".join(lines[closing + 1:]).strip():
        problems.append("Skill needs a readable instruction body.")
    return problems


def legacy_pointer(legacy_path: str) -> bytes:
    """One exact compatibility pointer; it contains no second workflow body."""
    name = BUILTIN_SKILLS[legacy_path]
    title = name.removeprefix("apparatus-").replace("-", " ").capitalize()
    header = records.yaml.safe_dump({"schema": "apparatus/procedure@v0", "title": title,
                                    "intent": "Follow this workflow through its canonical Skill."}, sort_keys=False)
    body = (f"Read `{canonical_path(name)}` from the selected work-area root and follow it.\n"
            "Keep the current task's Memory decision.\n")
    return f"---\n{header}---\n\n{body}".encode("utf-8")


def is_legacy_pointer(legacy_path: str, content: bytes) -> bool:
    if legacy_path not in BUILTIN_SKILLS:
        return False
    pointer = legacy_pointer(legacy_path)
    return content in (pointer, pointer.replace(b"\n", b"\r\n"))


def has_skill_index(content: bytes) -> bool:
    """Recognize the complete shipped index, never its delimiters alone."""
    value = SKILL_INDEX.encode("utf-8")
    return value in content or value.replace(b"\n", b"\r\n") in content


def is_shipped_skill_orientation(relative: str, content: bytes) -> bool:
    """Recognize a whole known orientation file, never its header or links."""
    expected = _SKILL_ORIENTATION_DIGESTS.get(relative)
    return expected is not None and hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest() == expected
