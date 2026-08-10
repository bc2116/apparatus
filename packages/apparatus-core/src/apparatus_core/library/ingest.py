"""Deterministic, incremental ingestion of Library files into derived cache state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import os
import stat
import tempfile
import unicodedata

from apparatus_core.cache import library_cache_root
from apparatus_core.fs_transactions import WindowsWorkspaceAnchor
from apparatus_core.ignore import IgnoreReport, IgnoreRules, load_ignore_rules
from apparatus_core.library.extractors import EXTRACTOR_VERSION, extract_bytes
from apparatus_core.receipts import write_receipt
from apparatus_core.render import is_reparse_path

_NOISE = {".DS_Store", "Thumbs.db", "desktop.ini"}
_STATUSES = ("scanned", "ignored", "extracted", "unchanged", "no_text", "unsupported", "error")


@dataclass(frozen=True)
class IngestResult:
    cache: Path
    counts: dict[str, int]
    flagged: tuple[tuple[str, str, str], ...]
    ignore_report: IgnoreReport = field(default_factory=IgnoreReport)

    @property
    def ok(self) -> bool:
        return not self.flagged


@dataclass(frozen=True)
class _TraversalFailure:
    relative: str


def ingest_library(workspace: str | Path) -> IngestResult:
    """Extract all visible Library sources and write one honest receipt."""
    root = Path(workspace)
    rules = load_ignore_rules(root).require_valid()
    if is_reparse_path(root) or is_reparse_path(root / "Library"):
        raise ValueError("workspace and Library must not be symbolic links")
    library = root / "Library"
    library_fd = _open_library_directory(library)
    windows_anchor = _windows_source_anchor(root)
    try:
        return _ingest_library(root, library, library_fd, windows_anchor, rules)
    finally:
        _close_source_anchors(library_fd, windows_anchor)


def _ingest_library(
    root: Path,
    library: Path,
    library_fd: int,
    windows_anchor: WindowsWorkspaceAnchor | None,
    rules: IgnoreRules,
) -> IngestResult:
    """Run ingestion while the workspace's source anchor remains retained."""
    cache = library_cache_root(root)
    extractions = cache / "extractions"
    if is_reparse_path(cache) or is_reparse_path(extractions):
        raise ValueError("Library cache must not contain symbolic links")
    extractions.mkdir(parents=True, exist_ok=True)
    _validate_private_cache_tree(extractions)
    counts = {status: 0 for status in _STATUSES}
    flagged: list[tuple[str, str, str]] = []
    seen: set[tuple[str, ...]] = set()
    built_in_ignored = 0
    user_ignored = 0
    entries = _library_entries(library, library_fd, rules)
    for source in entries:
        if isinstance(source, _TraversalFailure):
            counts["scanned"] += 1
            counts["error"] += 1
            flagged.append((_safe(source.relative), "error", "Library directory could not be traversed"))
            continue
        relative = source.relative_to(library).as_posix()
        try:
            source_status = os.lstat(source)
        except OSError:
            counts["scanned"] += 1
            counts["error"] += 1
            flagged.append((_safe(relative), "error", "source could not be inspected"))
            continue
        classification = rules.classification(
            "Library/" + relative,
            is_directory=stat.S_ISDIR(source_status.st_mode),
        )
        if classification is not None:
            counts["ignored"] += 1
            if classification == "built-in":
                built_in_ignored += 1
            else:
                user_ignored += 1
            continue
        if source.name in _NOISE or any(part.startswith(".") for part in source.relative_to(library).parts):
            continue
        if is_reparse_path(source):
            relative = source.relative_to(library).as_posix()
            counts["scanned"] += 1; counts["error"] += 1
            flagged.append((_safe(relative), "error", "symbolic-link sources are not supported"))
            continue
        if stat.S_ISDIR(source_status.st_mode):
            continue
        if not stat.S_ISREG(source_status.st_mode):
            relative = source.relative_to(library).as_posix()
            counts["scanned"] += 1; counts["error"] += 1
            flagged.append((_safe(relative), "error", "source is not a regular file"))
            continue
        seen.add(_portable_key(relative))
        counts["scanned"] += 1
        try:
            content, before, after, current = _read_source(source, library_fd, relative, windows_anchor)
        except OSError:
            counts["error"] += 1; flagged.append((_safe(relative), "error", "source could not be read")); continue
        if is_reparse_path(source) or (before is not None and (current is None or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino))):
            flagged.append((_safe(relative), "error", "source changed while it was read")); counts["error"] += 1; continue
        digest = hashlib.sha256(content).hexdigest()
        record_path = extractions / (relative + ".json")
        text_path = extractions / (relative + ".txt")
        if not _private_cache_path(cache, record_path) or not all(
            _private_regular_or_missing(path) for path in (record_path, text_path)
        ):
            raise ValueError("Library cache target is not a private regular file")
        old = _read_record(record_path)
        source_path = "Library/" + relative
        if _valid_record(old, source_path, digest, len(content), text_path):
            counts["unchanged"] += 1
            status = old.get("status")
            if status in {"no_text", "unsupported", "error"}:
                flagged.append((_safe(relative), str(status), _safe(str(old.get("error") or "no text extracted"))))
            continue
        result = extract_bytes(source, content)
        timestamp = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
        record = {
            "source_path": source_path,
            "source_sha256": digest,
            "size_bytes": len(content),
            "extractor": result.extractor,
            "extractor_version": EXTRACTOR_VERSION,
            "status": result.status,
            "error": result.error,
            "character_count": len(result.text),
            "timestamp": timestamp,
        }
        record_path.parent.mkdir(parents=True, exist_ok=True)
        _publish_pair(record_path, text_path, json.dumps(record, sort_keys=True, indent=2) + "\n", result.text if result.status == "extracted" else None)
        counts[result.status] += 1
        if result.status in {"no_text", "unsupported", "error"}:
            flagged.append((_safe(relative), result.status, _safe(result.error or "no text extracted")))
    _remove_deleted(extractions, seen)
    ignore_report = rules.report(
        built_in_paths=built_in_ignored, user_paths=user_ignored
    )
    body = (
        ignore_report.sentence()
        + "\n\nFlagged Library files:\n"
        + ("\n".join(f"- {_safe(path)}: {status}: {_safe(reason)}" for path, status, reason in flagged) if flagged else "- none")
    )
    summary = "Library ingest: " + ", ".join(f"{name}={counts[name]}" for name in _STATUSES) + "."
    write_receipt(root, "library-ingest", {"summary": summary, "body": body})
    return IngestResult(cache, counts, tuple(flagged), ignore_report)


def _windows_source_anchor(root: Path) -> WindowsWorkspaceAnchor | None:
    if os.name != "nt":
        return None
    return WindowsWorkspaceAnchor(root)  # pragma: no cover - selected Windows CI


def _close_source_anchors(library_fd: int, windows_anchor: WindowsWorkspaceAnchor | None) -> None:
    if library_fd >= 0:
        os.close(library_fd)
    if windows_anchor is not None:
        windows_anchor.close()


def _open_library_directory(library: Path) -> int:
    """Retain a no-follow Library directory before its contents are traversed."""
    if os.name != "posix":
        return -1
    try:
        return os.open(library, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as error:
        raise ValueError("workspace and Library must not be symbolic links") from error


def _library_entries(
    library: Path, library_fd: int, rules: IgnoreRules
) -> list[Path | _TraversalFailure]:
    """List sources without following symbolic links or Windows junctions."""
    entries: list[Path | _TraversalFailure] = []

    def visit(directory: Path) -> None:
        try:
            descriptor = os.dup(library_fd) if directory == library and library_fd >= 0 else directory
            with os.scandir(descriptor) as scan:
                children = sorted((directory / entry.name for entry in scan), key=lambda path: path.as_posix())
        except OSError:
            relative = directory.relative_to(library).as_posix()
            entries.append(_TraversalFailure("Library" if relative == "." else relative))
            return
        for child in children:
            entries.append(child)
            relative = child.relative_to(library).as_posix()
            try:
                child_status = os.lstat(child)
            except OSError:
                continue
            is_directory = stat.S_ISDIR(child_status.st_mode)
            ignored = rules.matches(
                "Library/" + relative, is_directory=is_directory
            )
            if not ignored and not is_reparse_path(child) and is_directory:
                visit(child)

    visit(library)
    return entries


def _read_source(source: Path, library_fd: int, relative: str, windows_anchor: WindowsWorkspaceAnchor | None = None) -> tuple[bytes, os.stat_result | None, os.stat_result | None, os.stat_result | None]:
    """Read one regular source from a retained, non-following descriptor."""
    if library_fd < 0:  # pragma: no cover - Windows uses its selected CI suite
        if windows_anchor is None:
            raise OSError("safe Library reads are unavailable")
        content, _identity = windows_anchor.read_file(Path("Library") / relative)
        return content, None, None, None
    else:
        descriptor = os.open(relative, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=library_fd)
    try:
        before = os.fstat(descriptor)
        content = b"".join(iter(lambda: os.read(descriptor, 65536), b""))
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        current = source.stat()
    except OSError:
        current = None
    return content, before, after, current


def _read_record(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _remove_deleted(extractions: Path, seen: set[tuple[str, ...]]) -> None:
    for record_path in _cache_files(extractions, ".json"):
        relative = record_path.relative_to(extractions).as_posix()[:-5]
        if _portable_key(relative) in seen:
            continue
        _unlink_cache_path(extractions, record_path)
        text_path = record_path.with_suffix(".txt")
        if text_path.exists():
            _unlink_cache_path(extractions, text_path)
    for text_path in _cache_files(extractions, ".txt"):
        relative = text_path.relative_to(extractions).as_posix()[:-4]
        if _portable_key(relative) not in seen:
            _unlink_cache_path(extractions, text_path)


def _unlink_cache_path(extractions: Path, path: Path) -> None:
    """Unlink stale cache state through its retained no-follow parent on POSIX."""
    if os.name != "posix":  # pragma: no cover - selected Windows CI covers reparse rejection
        path.unlink()
        return
    relative = path.relative_to(extractions)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    current = os.open(extractions, flags)
    try:
        for part in relative.parts[:-1]:
            following = os.open(part, flags, dir_fd=current)
            os.close(current)
            current = following
        expected = os.lstat(path)
        actual = os.stat(relative.name, dir_fd=current, follow_symlinks=False)
        if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
            raise OSError("stale cache target changed before cleanup")
        os.unlink(relative.name, dir_fd=current)
    finally:
        os.close(current)


def _atomic_write(path: Path, content: str | bytes) -> None:
    """Publish bytes only from an invocation-owned same-directory temporary."""
    data = content.encode("utf-8") if isinstance(content, str) else content
    descriptor, name = tempfile.mkstemp(prefix=".apparatus-library-", dir=path.parent)
    temporary = Path(name)
    identity: tuple[int, int] | None = None
    try:
        status = os.fstat(descriptor)
        identity = (status.st_dev, status.st_ino)
        output = os.fdopen(descriptor, "wb")
        descriptor = -1
        with output:
            output.write(data)
            output.flush()
        if not _temporary_matches(temporary, identity, data):
            raise OSError("library temporary changed before replacement")
        os.replace(temporary, path)
        if not _published_matches(path, identity, data):
            raise OSError("library replacement changed before verification")
    except OSError:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        _remove_owned_temporary(temporary, identity, data)
        raise


def _publish_pair(record: Path, text: Path, record_text: str, text_value: str | None) -> None:
    old_record = record.read_bytes() if record.exists() else None
    old_text = text.read_bytes() if text.exists() else None
    try:
        if text_value is None:
            if text.exists(): text.unlink()
        else:
            _atomic_write(text, text_value)
        _atomic_write(record, record_text)
    except OSError:
        if old_text is None and text.exists(): text.unlink()
        elif old_text is not None: _atomic_write(text, old_text)
        if old_record is None and record.exists(): record.unlink()
        elif old_record is not None: _atomic_write(record, old_record)
        raise


def _temporary_matches(temporary: Path, identity: tuple[int, int], data: bytes) -> bool:
    try:
        status = os.lstat(temporary)
        return stat.S_ISREG(status.st_mode) and (status.st_dev, status.st_ino) == identity and temporary.read_bytes() == data
    except OSError:
        return False


def _remove_owned_temporary(temporary: Path, identity: tuple[int, int] | None, data: bytes) -> None:
    if identity is None:
        return
    if _temporary_matches(temporary, identity, data):
        try:
            temporary.unlink()
        except OSError:
            pass


def _published_matches(path: Path, identity: tuple[int, int], data: bytes) -> bool:
    try:
        status = os.lstat(path)
        mode_is_private = not _requires_private_mode() or stat.S_IMODE(status.st_mode) == 0o600
        return stat.S_ISREG(status.st_mode) and status.st_nlink == 1 and (status.st_dev, status.st_ino) == identity and mode_is_private and path.read_bytes() == data
    except OSError:
        return False


def _requires_private_mode() -> bool:
    return os.name == "posix"


def _private_regular_or_missing(path: Path) -> bool:
    """A cache endpoint must be absent or an unlinked-to regular private file."""
    try:
        status = os.lstat(path)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return stat.S_ISREG(status.st_mode) and status.st_nlink == 1


def _private_cache_path(cache: Path, target: Path) -> bool:
    current = target.parent
    while current != cache:
        if is_reparse_path(current):
            return False
        if current == current.parent:
            return False
        current = current.parent
    return not is_reparse_path(cache)


def _validate_private_cache_tree(directory: Path) -> None:
    """Refuse a nested cache junction before scanning or publishing anything."""
    try:
        with os.scandir(directory) as scan:
            children = [Path(entry.path) for entry in scan]
    except OSError as error:
        raise ValueError("Library cache could not be inspected safely") from error
    for child in children:
        if is_reparse_path(child):
            raise ValueError("Library cache must not contain symbolic links")
        try:
            if stat.S_ISDIR(os.lstat(child).st_mode):
                _validate_private_cache_tree(child)
        except OSError as error:
            raise ValueError("Library cache could not be inspected safely") from error


def _cache_files(directory: Path, suffix: str) -> list[Path]:
    files: list[Path] = []
    try:
        with os.scandir(directory) as scan:
            children = sorted((Path(entry.path) for entry in scan), key=lambda path: path.as_posix())
    except OSError:
        return files
    for child in children:
        if is_reparse_path(child):
            continue
        try:
            status = os.lstat(child)
        except OSError:
            continue
        if stat.S_ISDIR(status.st_mode):
            files.extend(_cache_files(child, suffix))
        elif child.name.endswith(suffix):
            files.append(child)
    return files


def _valid_record(record: dict | None, source: str, digest: str, size: int, text: Path) -> bool:
    if not isinstance(record, dict) or set(record) != {"source_path", "source_sha256", "size_bytes", "extractor", "extractor_version", "status", "error", "character_count", "timestamp"}:
        return False
    if record.get("source_path") != source or record.get("source_sha256") != digest or not isinstance(record.get("source_sha256"), str) or len(record["source_sha256"]) != 64 or any(c not in "0123456789abcdef" for c in record["source_sha256"]) or type(record.get("size_bytes")) is not int or record.get("size_bytes") != size or record.get("extractor") not in {"utf-8", "python-docx", "pypdf", "none"} or record.get("extractor_version") != EXTRACTOR_VERSION or type(record.get("character_count")) is not int or record["character_count"] < 0 or not _utc(record.get("timestamp")):
        return False
    status = record.get("status")
    suffix = Path(source).suffix.lower()
    expected = {".md": "utf-8", ".txt": "utf-8", ".docx": "python-docx", ".pdf": "pypdf"}.get(suffix, "none")
    if record["extractor"] != expected:
        return False
    if suffix in {".md", ".txt", ".docx", ".pdf"}:
        if status not in {"extracted", "no_text", "error"}:
            return False
    elif status != "unsupported":
        return False
    if status == "extracted":
        if record.get("error") is not None or not text.is_file() or is_reparse_path(text): return False
        try: return len(text.read_text(encoding="utf-8")) == record["character_count"]
        except (OSError, UnicodeError): return False
    if status == "no_text": return record.get("error") is None and record["character_count"] == 0 and not text.exists()
    return status in {"unsupported", "error"} and isinstance(record.get("error"), str) and bool(record["error"]) and record["character_count"] == 0 and not text.exists()


def _safe(value: str) -> str:
    return "".join(" " if unicodedata.category(character).startswith("C") else character for character in value)


def _portable_key(value: str) -> tuple[str, ...]:
    return tuple(unicodedata.normalize("NFC", part).casefold() for part in Path(value).parts)


def _utc(value: object) -> bool:
    if not isinstance(value, str): return False
    try: return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%dT%H:%M:%SZ") == value
    except ValueError: return False
