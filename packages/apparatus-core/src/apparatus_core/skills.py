"""Portable built-in Skill metadata, validation and legacy file pointers."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apparatus_core.fs_transactions import WorkspaceAnchor

from apparatus_core import records

LEGACY_PROCEDURES = {
    f"System/procedures/{slug}.md": f"apparatus-{slug}"
    for slug in ("welcome", "produce-deliverable", "research-and-summarize",
                 "review-against-checklist", "weekly-review")
}
HISTORICAL_SKILL_PATHS = {f".agents/skills/{name}/SKILL.md": name for name in LEGACY_PROCEDURES.values()}
BUILTIN_PATHS = {**HISTORICAL_SKILL_PATHS, **{
    f".agents/skills/{name}/SKILL.md": name
    for name in ("apparatus-economizer", "apparatus-humanizer")
}}
NEW_SKILL_PATHS = {path: name for path, name in BUILTIN_PATHS.items() if path not in HISTORICAL_SKILL_PATHS}
_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}

# Complete PR-38 and PR-39 shipped orientation bytes, normalized only for CRLF.
# Keep historical witnesses when later payload revisions change the prose.
_SKILL_ORIENTATION_DIGESTS = {
    "Welcome.md": {"9c9612b04aae89667e0f9697d99a9b146dc2ee9f4d143c19dc54534cb1ecad87", "5bcf362d72d507a8896498d9da83646cc95b8e2b3395cfbbe21b631860048be1"},
    "System/README.md": {"32d22c2e88c1cd3aa49a3dc74b6d54d84bc51c5ed3c96b19e59553796fde911d", "51ee1850ff9653584142b0b5a789040169bed33ce6f42c0a6c6d8ab984ddb5d6"},
}

HISTORICAL_SKILL_INDEX = """<!-- Apparatus Skill index: v1 -->
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


SKILL_INDEX = HISTORICAL_SKILL_INDEX.replace("index: v1", "index: v2").replace(
    "\nSkills provide instructions", "\n- Economical native work: `.agents/skills/apparatus-economizer/SKILL.md`.\n"
    "- Requested prose editing or a light final pass: `.agents/skills/apparatus-humanizer/SKILL.md`.\n"
    "\nSkills provide instructions",
)

# Exact orientation for the seven-Skill payload; older witnesses remain above.
PREVIOUS_CURRENT_ORIENTATION_DIGESTS: dict[str, str] = {'Welcome.md': 'a69d8616bcb28bfeda08b0ca15d908945626d4bebc71531631dc1f439b7fe508',
 'System/README.md': '9e0ea94ba15433754a4fde40121293bb1bc4a17efe3ce297d5ddcb3991cfbdb3'}


CURRENT_ORIENTATION_DIGESTS: dict[str, str] = {'Welcome.md': 'cd52bfa9c714b9d2b3b9aa835732d7c414c346f0157a44f7f5c3e2a47eb0036b',
 'System/README.md': '9d77710dd6a053040603207a286544e61f7a5e07c0e5add6b9b93361ae73d004'}

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
    name = LEGACY_PROCEDURES[legacy_path]
    title = name.removeprefix("apparatus-").replace("-", " ").capitalize()
    header = records.yaml.safe_dump({"schema": "apparatus/procedure@v0", "title": title,
                                    "intent": "Follow this workflow through its canonical Skill."}, sort_keys=False)
    body = (f"Read `{canonical_path(name)}` from the selected work-area root and follow it.\n"
            "Keep the current task's Memory decision.\n")
    return f"---\n{header}---\n\n{body}".encode("utf-8")


def is_legacy_pointer(legacy_path: str, content: bytes) -> bool:
    if legacy_path not in LEGACY_PROCEDURES:
        return False
    pointer = legacy_pointer(legacy_path)
    return content in (pointer, pointer.replace(b"\n", b"\r\n"))


def has_skill_index(content: bytes) -> bool:
    """Recognize the complete shipped index, never its delimiters alone."""
    normalized = content.replace(b"\r\n", b"\n")
    return any(index.encode("utf-8") in normalized for index in (HISTORICAL_SKILL_INDEX, SKILL_INDEX))


def is_shipped_skill_orientation(relative: str, content: bytes) -> bool:
    """Recognize a whole known orientation file, never its header or links."""
    expected = _SKILL_ORIENTATION_DIGESTS.get(relative)
    digest = hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()
    return digest in {CURRENT_ORIENTATION_DIGESTS.get(relative), PREVIOUS_CURRENT_ORIENTATION_DIGESTS.get(relative)} or (expected is not None and digest in expected)


def read_skill_payload(anchor: WorkspaceAnchor) -> dict[str, bytes]:
    """Validate an exact historical five-file or current seven-file source set.

    Only named directories, orientation files and mapped legacy paths are read.
    Source validation is independent of a profile's selected work types.
    """
    def optional(relative: str) -> bytes | None:
        try:
            return anchor.read_file(relative)[0]
        except FileNotFoundError:
            return None
        except OSError as error:
            raise ValueError(
                f"payload file {relative!r} could not be read safely; require a readable "
                "regular file without symbolic links or reparse points"
            ) from error

    directories = {path: anchor.directory_exists(Path(path).parent) for path in BUILTIN_PATHS}
    orientation = {path: optional(path) or b"" for path in ("AGENTS.md", "Welcome.md", "System/README.md")}
    current = any(directories[path] for path in NEW_SKILL_PATHS) or any(
        SKILL_INDEX.encode() in content.replace(b"\r\n", b"\n")
        or hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest() in {CURRENT_ORIENTATION_DIGESTS.get(path), PREVIOUS_CURRENT_ORIENTATION_DIGESTS.get(path)}
        for path, content in orientation.items()
    )
    native = current or any(directories.values()) or any(
        has_skill_index(content) or is_shipped_skill_orientation(path, content)
        for path, content in orientation.items()
    )
    if not native:
        return {}
    required = BUILTIN_PATHS if current else HISTORICAL_SKILL_PATHS
    result = {}
    for path, name in required.items():
        content = optional(path)
        if content is None or validate_skill(content, name):
            raise ValueError(f"payload Skill {path!r} is missing or invalid; use a complete portable Skill payload")
        result[path] = content
    for path in LEGACY_PROCEDURES:
        if optional(path) is not None:
            raise ValueError(f"native payload contains legacy workflow {path!r}; ship only its canonical Skill")
    return result
