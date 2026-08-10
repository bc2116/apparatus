"""The deliberately small, workspace-relative ``System/ignore`` matcher."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
import re


_BUILT_IN_BASENAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})


@dataclass(frozen=True)
class PatternIssue:
    """One unsupported user pattern, reported without exposing matched paths."""

    line: int
    pattern: str
    message: str


@dataclass(frozen=True)
class IgnoreRules:
    """Supported patterns and syntax findings from one workspace ignore file."""

    patterns: tuple[str, ...]
    issues: tuple[PatternIssue, ...]

    def matches(self, path: str | Path) -> bool:
        """Whether a workspace-relative path is hidden from workspace machinery."""
        value = Path(path).as_posix().lstrip("/")
        parts = tuple(part for part in value.split("/") if part and part != ".")
        if not parts:
            return False
        if any(part == ".git" for part in parts) or parts[-1] in _BUILT_IN_BASENAMES:
            return True
        return any(_matches(pattern, parts) for pattern in self.patterns)


def load_ignore_rules(workspace: str | Path) -> IgnoreRules:
    """Read ``System/ignore`` when present; a missing file means no user rules."""
    path = Path(workspace) / "System" / "ignore"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return IgnoreRules((), ())
    except (OSError, UnicodeError):
        return IgnoreRules((), (PatternIssue(0, "", "System/ignore could not be read as UTF-8 text."),))
    patterns: list[str] = []
    issues: list[PatternIssue] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        pattern = raw.strip()
        if not pattern or pattern.startswith("#"):
            continue
        if pattern.startswith("!"):
            issues.append(PatternIssue(number, pattern, "Negated patterns are not supported in System/ignore."))
        elif "\\" in pattern or "[" in pattern or "]" in pattern:
            issues.append(PatternIssue(number, pattern, "Escapes and character classes are not supported in System/ignore."))
        elif pattern.startswith("/"):
            patterns.append(pattern)
        else:
            patterns.append(pattern)
    return IgnoreRules(tuple(patterns), tuple(issues))


def _matches(pattern: str, parts: tuple[str, ...]) -> bool:
    anchored = pattern.startswith("/")
    pattern = pattern.lstrip("/")
    directory = pattern.endswith("/")
    pattern = pattern.rstrip("/")
    if not pattern:
        return False
    pattern_parts = tuple(part for part in pattern.split("/") if part)
    if len(pattern_parts) == 1 and not anchored:
        return any(fnmatchcase(part, pattern_parts[0]) for part in parts)
    candidate = "/".join(parts)
    expression = _glob_expression("/".join(pattern_parts))
    if directory:
        return bool(re.fullmatch(expression + r"(?:/.*)?", candidate))
    return bool(re.fullmatch(expression, candidate))


def _glob_expression(pattern: str) -> str:
    """Translate only *, ?, and **; unlike fnmatch, * does not cross '/'."""
    pieces: list[str] = []
    index = 0
    while index < len(pattern):
        character = pattern[index]
        if character == "*" and index + 1 < len(pattern) and pattern[index + 1] == "*":
            if index + 2 < len(pattern) and pattern[index + 2] == "/":
                pieces.append("(?:.*/)?")
                index += 3
            else:
                pieces.append(".*")
                index += 2
        elif character == "*":
            pieces.append("[^/]*")
            index += 1
        elif character == "?":
            pieces.append("[^/]")
            index += 1
        else:
            pieces.append(re.escape(character))
            index += 1
    return "".join(pieces)
