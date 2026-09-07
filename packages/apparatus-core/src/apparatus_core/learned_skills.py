"""Explicit learned-Skill ownership; unrelated native files remain unclaimed."""
from __future__ import annotations

from pathlib import PurePosixPath

from apparatus_core import records, skills

ADOPTED = "System/skills/adopted"
DRAFTS = "System/skill-drafts"
SCHEMA = "apparatus/learned-skill@v0"


class LearnedSkillError(ValueError):
    """A learned workflow cannot be read or published safely."""


def require_name(name: str) -> str:
    if not skills.valid_name(name) or not name.startswith("learned-") or name in skills.BUILTIN_PATHS.values():
        raise LearnedSkillError("Choose a portable Skill name beginning with learned- (at most 64 characters).")
    return name


def draft_path(name: str) -> str:
    return f"{DRAFTS}/{require_name(name)}.md"


def body_path(name: str) -> str:
    return skills.canonical_path(require_name(name))


def marker_path(name: str) -> str:
    return f"{ADOPTED}/{require_name(name)}.yaml"


def path_kind(relative: str) -> tuple[str, str] | None:
    path = PurePosixPath(relative)
    name = None
    kind = None
    if path.parent.as_posix() == ADOPTED and path.suffix == ".yaml":
        name, kind = path.stem, "learned-marker"
    elif len(path.parts) == 4 and path.parts[:2] == (".agents", "skills") and path.name == "SKILL.md":
        name, kind = path.parts[2], "learned-body"
    if name is None or not skills.valid_name(name) or not name.startswith("learned-"):
        return None
    expected = marker_path(name) if kind == "learned-marker" else body_path(name)
    return (kind, name) if relative == expected else None


def marker_bytes(name: str) -> bytes:
    return records.yaml.safe_dump({"schema": SCHEMA, "name": require_name(name)}, sort_keys=False).encode("utf-8")


def parse_marker(relative: str, content: bytes) -> str:
    identity = path_kind(relative)
    if identity is None or identity[0] != "learned-marker":
        raise LearnedSkillError("Learned Skill ownership needs a matching direct NAME.yaml path.")
    try:
        # Control files have two plain scalar fields; YAML aliases cannot add meaning.
        events = tuple(records.yaml.parse(content.decode("utf-8")))
        if any(isinstance(event, records.yaml.AliasEvent) or getattr(event, "anchor", None) is not None for event in events):
            raise ValueError("alias")
        node = records.yaml.compose(content.decode("utf-8"))
        if not isinstance(node, records.yaml.MappingNode) or len(node.value) != 2:
            raise ValueError("mapping")
        if any(not isinstance(k, records.yaml.ScalarNode) or not isinstance(v, records.yaml.ScalarNode) for k, v in node.value):
            raise ValueError("scalar")
        if {key.value for key, _ in node.value} != {"schema", "name"}:
            raise ValueError("keys")
        data = records.yaml.safe_load(content)
        if data != {"schema": SCHEMA, "name": identity[1]}:
            raise ValueError("values")
    except (ValueError, TypeError, UnicodeError, records.yaml.YAMLError) as error:
        raise LearnedSkillError("Learned Skill ownership is invalid; preserve the files and repair its schema/name.") from error
    return identity[1]


def validate_pairs(files: dict[str, bytes]) -> None:
    registered = set()
    bodies = set()
    for relative, content in files.items():
        identity = path_kind(relative)
        if identity is None:
            continue
        kind, name = identity
        if kind == "learned-marker":
            registered.add(parse_marker(relative, content))
        else:
            if skills.validate_skill(content, name):
                raise LearnedSkillError("An adopted Skill body is invalid; preserve it and repair its portable format.")
            bodies.add(name)
    if bodies != registered:
        raise LearnedSkillError("An adopted Skill is missing its body or ownership record; preserve and repair the pair.")


def registered_files(anchor, *, excluded=None) -> dict[str, bytes]:
    if not anchor.directory_exists(ADOPTED):
        return {}
    if excluded is not None and excluded(ADOPTED):
        raise LearnedSkillError("Ignore rules hide learned Skill ownership; adjust them before checking coverage.")
    result = {}
    for relative in anchor.list_files(ADOPTED, suffix=".yaml", include_hidden=False):
        relative = relative.as_posix()
        if excluded is not None and excluded(relative):
            raise LearnedSkillError("Ignore rules hide learned Skill ownership; adjust them before checking coverage.")
        with_proof = anchor.capture_file(relative, publication_compatible=True)
        try:
            content = with_proof.content
            name = parse_marker(relative, content)
            result[relative] = content
        finally:
            with_proof.close()
        body = body_path(name)
        if excluded is not None and excluded(body):
            raise LearnedSkillError("Ignore rules hide an adopted Skill; adjust them before checking coverage.")
        proof = anchor.capture_file(body, publication_compatible=True)
        try:
            result[body] = proof.content
        finally:
            proof.close()
    validate_pairs(result)
    return result
