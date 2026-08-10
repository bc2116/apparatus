"""The deliberately small, fail-closed ``System/ignore`` matcher."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
import os
from pathlib import Path
import re
import stat

from apparatus_core.fs_transactions import WindowsWorkspaceAnchor
from apparatus_core.render import is_reparse_path


_BUILT_IN_BASENAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})


class IgnoreRulesError(ValueError):
    """The workspace ignore file cannot safely govern content access."""


@dataclass(frozen=True)
class PatternIssue:
    """One actionable problem in or with ``System/ignore``."""

    code: str
    line: int
    pattern: str
    message: str


@dataclass(frozen=True)
class IgnoreReport:
    """Counts and rule provenance, without ignored paths or file contents."""

    built_in_paths: int = 0
    user_paths: int = 0
    file_present: bool = False
    user_patterns: int = 0
    valid: bool = True

    @property
    def skipped_paths(self) -> int:
        return self.built_in_paths + self.user_paths

    @property
    def provenance(self) -> str:
        if not self.valid:
            return "built-in defaults; System/ignore is invalid"
        if self.file_present:
            return (
                "built-in defaults and System/ignore "
                f"({self.user_patterns} user pattern(s))"
            )
        return "built-in defaults; System/ignore is missing"

    def sentence(self) -> str:
        return (
            f"Ignore rules: {self.provenance}; skipped {self.skipped_paths} path(s) "
            f"(built-in={self.built_in_paths}, user={self.user_paths})."
        )


@dataclass(frozen=True)
class IgnoreRules:
    """Supported patterns and findings from one workspace ignore file."""

    patterns: tuple[str, ...]
    issues: tuple[PatternIssue, ...]
    file_present: bool = False
    valid: bool = True

    def require_valid(self) -> IgnoreRules:
        """Return these rules or stop an ignore-aware content operation."""
        if not self.valid:
            message = self.issues[0].message if self.issues else "System/ignore is invalid."
            raise IgnoreRulesError(message)
        return self

    def classification(
        self, path: str | Path, *, is_directory: bool = False
    ) -> str | None:
        """Return the rule class hiding a relative file or directory path."""
        value = Path(path).as_posix().lstrip("/")
        parts = tuple(part for part in value.split("/") if part and part != ".")
        if not parts:
            return None
        if any(part == ".git" for part in parts) or parts[-1] in _BUILT_IN_BASENAMES:
            return "built-in"
        if any(
            _matches(pattern, parts, is_directory=is_directory)
            for pattern in self.patterns
        ):
            return "user"
        for boundary in range(1, len(parts)):
            if any(
                _matches(pattern, parts[:boundary], is_directory=True)
                for pattern in self.patterns
            ):
                return "user"
        return None

    def matches(self, path: str | Path, *, is_directory: bool = False) -> bool:
        """Whether a workspace-relative path is hidden from workspace machinery."""
        return self.classification(path, is_directory=is_directory) is not None

    def report(self, *, built_in_paths: int = 0, user_paths: int = 0) -> IgnoreReport:
        return IgnoreReport(
            built_in_paths=built_in_paths,
            user_paths=user_paths,
            file_present=self.file_present,
            user_patterns=len(self.patterns),
            valid=self.valid,
        )


def load_ignore_rules(workspace: str | Path) -> IgnoreRules:
    """Read ``System/ignore`` safely, distinguishing missing from invalid."""
    root = Path(workspace)
    system = root / "System"
    path = system / "ignore"
    if is_reparse_path(root) or is_reparse_path(system):
        return _invalid(
            "ignore-file-unsafe",
            "System/ignore must stay inside regular workspace directories, not symbolic links or reparse points.",
        )
    try:
        status = os.lstat(path)
    except FileNotFoundError:
        return IgnoreRules((), (), file_present=False)
    except OSError:
        return _invalid("ignore-file-read-error", "System/ignore could not be inspected safely.")
    if (
        is_reparse_path(path)
        or not stat.S_ISREG(status.st_mode)
    ):
        return _invalid(
            "ignore-file-unsafe",
            "System/ignore must be a regular workspace file, not a symbolic link or reparse point.",
        )
    try:
        content = _read_regular_file(system, path)
        text = content.decode("utf-8")
    except UnicodeError:
        return _invalid("ignore-file-encoding-error", "System/ignore must be UTF-8 text.")
    except OSError:
        return _invalid("ignore-file-read-error", "System/ignore could not be read safely.")

    patterns: list[str] = []
    issues: list[PatternIssue] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        pattern = raw.strip()
        if not pattern or pattern.startswith("#"):
            continue
        if pattern.startswith("!"):
            issues.append(
                PatternIssue(
                    "ignore-unsupported-pattern",
                    number,
                    pattern,
                    "Negated patterns are not supported in System/ignore.",
                )
            )
        elif "\\" in pattern or "[" in pattern or "]" in pattern:
            issues.append(
                PatternIssue(
                    "ignore-unsupported-pattern",
                    number,
                    pattern,
                    "Escapes and character classes are not supported in System/ignore.",
                )
            )
        else:
            patterns.append(pattern)
    return IgnoreRules(
        tuple(patterns), tuple(issues), file_present=True, valid=not issues
    )


def _invalid(code: str, message: str) -> IgnoreRules:
    return IgnoreRules(
        (),
        (PatternIssue(code, 0, "", message),),
        file_present=True,
        valid=False,
    )


def _read_regular_file(system: Path, path: Path) -> bytes:
    """Read through retained no-follow descriptors where the platform permits."""
    if os.name == "nt":  # pragma: no cover - selected Windows CI covers safety checks
        with WindowsWorkspaceAnchor(system.parent) as anchor:
            relative = Path("System") / path.name
            owned = anchor.capture_file(relative)
            try:
                if not anchor._matches_owned(owned) or not anchor._parent_is_current(
                    relative, owned.parent
                ):
                    raise OSError("System/ignore changed while it was read")
                return owned.content
            finally:
                owned.close()
    if os.name != "posix":  # pragma: no cover - defensive platform fallback
        before = os.lstat(path)
        content = path.read_bytes()
        after = os.lstat(path)
        if (
            not stat.S_ISREG(after.st_mode)
            or is_reparse_path(path)
            or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        ):
            raise OSError("System/ignore changed while it was read")
        return content

    root = os.open(
        system.parent,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    parent = -1
    descriptor = -1
    try:
        parent = os.open(
            system.name,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=root,
        )
        parent_before = os.fstat(parent)
        descriptor = os.open(
            path.name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent,
        )
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise OSError("System/ignore is not a regular file")
        content = b"".join(iter(lambda: os.read(descriptor, 65_536), b""))
        after = os.fstat(descriptor)
        current = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        parent_current = os.stat(
            system.name, dir_fd=root, follow_symlinks=False
        )
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ) or (before.st_dev, before.st_ino) != (
            current.st_dev,
            current.st_ino,
        ) or (parent_before.st_dev, parent_before.st_ino) != (
            parent_current.st_dev,
            parent_current.st_ino,
        ):
            raise OSError("System/ignore changed while it was read")
        return content
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if parent >= 0:
            os.close(parent)
        os.close(root)


def _matches(
    pattern: str, parts: tuple[str, ...], *, is_directory: bool
) -> bool:
    anchored = pattern.startswith("/")
    pattern = pattern.lstrip("/")
    directory_only = pattern.endswith("/")
    pattern = pattern.rstrip("/")
    if not pattern or (directory_only and not is_directory):
        return False
    pattern_parts = tuple(part for part in pattern.split("/") if part)
    if len(pattern_parts) == 1 and not anchored:
        return fnmatchcase(parts[-1], pattern_parts[0])
    candidate = "/".join(parts)
    expression = _glob_expression("/".join(pattern_parts))
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
