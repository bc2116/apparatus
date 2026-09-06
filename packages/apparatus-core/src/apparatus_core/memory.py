"""Current-only Memory reads over validated, retained-root workspace files."""

from __future__ import annotations

from pathlib import Path, PureWindowsPath

from apparatus_core import records
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.ignore import IgnoreRulesError, load_ignore_rules
from apparatus_core.labeler import split_record_exact


class MemoryReadError(ValueError):
    """Memory coverage cannot be established safely."""


def record_path(value: str | Path) -> tuple[Path, str]:
    text = value.as_posix() if isinstance(value, Path) else str(value)
    path = Path(text)
    if (
        path.is_absolute() or PureWindowsPath(text).drive or "\\" in text
        or ".." in path.parts or path.as_posix() != text
        or len(path.parts) < 3 or path.parts[0] != "Memory"
        or path.parts[1] not in {"Facts", "People"}
        or any(part.startswith(".") for part in path.parts)
        or not records.KEBAB_FILENAME.fullmatch(path.name)
    ):
        raise MemoryReadError("RECORD must name a kebab-case Markdown file under Memory/Facts or Memory/People")
    return path, "fact" if path.parts[1] == "Facts" else "person"


def read_record(anchor: WorkspaceAnchor, relative: Path, kind: str):
    try:
        original, identity = anchor.read_file(relative)
        data, body = split_record_exact(original.decode("utf-8", errors="strict"))
        if records.validate(kind, data, filename=relative.name, body=body):
            raise ValueError("invalid schema")
    except (OSError, UnicodeError, ValueError, records.yaml.YAMLError) as error:
        raise MemoryReadError("Memory contains an unreadable, unsafe, or invalid record; repair it before retrying") from error
    return original, identity, data, body


def recall(anchor: WorkspaceAnchor, query: str, *, limit: int = 5) -> dict:
    """Match all casefolded whitespace-separated terms; validate all visible records."""
    terms = query.casefold().split()
    if not terms:
        raise MemoryReadError("QUERY must contain text")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
        raise MemoryReadError("--limit must be between 1 and 20")
    try:
        rules = load_ignore_rules(anchor.workspace).require_valid()
    except IgnoreRulesError as error:
        raise MemoryReadError("Memory recall could not load valid ignore rules; repair System/ignore or the profile") from error
    matches = []
    try:
        for folder, kind in (("Memory/Facts", "fact"), ("Memory/People", "person")):
            if rules.matches(folder, is_directory=True):
                continue
            for relative in anchor.list_memory_records(folder):
                if rules.matches(relative):
                    continue
                record_path(relative)
                original, _identity, data, _body = read_record(anchor, relative, kind)
                if data.get("status", "current") != "current":
                    continue
                text = original.decode("utf-8")
                if all(term in text.casefold() for term in terms):
                    matches.append({"source": relative.as_posix(), "text": text})
        if not anchor.root_is_current():
            raise OSError("workspace changed")
    except OSError as error:
        raise MemoryReadError("Memory traversal was unsafe or changed; no complete recall result is available") from error
    matches.sort(key=lambda match: match["source"])
    return {"status": "matched" if matches else "no-match", "results": matches[:limit],
            "truncated": len(matches) > limit}
