"""Derived local FTS5 search index for extracted Library text."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import secrets
import sqlite3
import stat
import tempfile
import time

from apparatus_core import fs_transactions
from apparatus_core.cache import library_cache_root
from apparatus_core.retention import operation
from apparatus_core.ignore import IgnoreReport, IgnoreRules, load_ignore_rules
from apparatus_core.library.extractors import EXTRACTOR_VERSION
from apparatus_core.library.ingest import _valid_record
from apparatus_core.render import is_reparse_path


class IndexError(RuntimeError):
    """The derived Library index cannot safely be used."""


class NoExtractionsError(IndexError):
    """Existing Library extraction evidence is unavailable."""

    def __init__(self, message: str, *, readonly: bool = False):
        super().__init__(message)
        self.readonly = readonly


class FtsUnavailable(IndexError):
    """This Python SQLite build has no FTS5 support."""


class _CorruptDatabaseError(IndexError):
    """A legacy database connection retained a verified corrupt endpoint."""

    def __init__(self, connection: sqlite3.Connection):
        super().__init__("Library index could not be opened")
        self.connection = connection


_DATABASE_FDS: dict[int, int] = {}
_DATABASE_HANDLES: dict[int, int] = {}
_WINDOWS_LOCK_METADATA_RETRIES = 3


@dataclass(frozen=True)
class SearchHit:
    source_path: str
    snippet: str
    score: float


def refresh(
    cache: Path, workspace: str | Path, *, task_id: str | None = None,
    requested: bool = False,
) -> IgnoreReport:
    """Update derived state only with this invocation's Library permission."""
    with operation(workspace, task_id=task_id, requested=("library",) if requested else ()) as context:
        context.require_library_write()
        return _refresh_authorized(cache, workspace)


def _refresh_authorized(cache: Path, workspace: str | Path) -> IgnoreReport:
    """Synchronize changed extracted cache pairs into the local FTS index."""
    rules = load_ignore_rules(workspace).require_valid()
    with _writer_lock(cache):
        desired, report = _extracted_sources(cache, rules)
        connection = _database_for_operation(cache)
        try:
            with connection:
                _create_schema(connection)
                _refresh_connection(connection, desired)
            _publish_database(cache, connection)
        except sqlite3.Error as error:
            raise IndexError("Library index could not be opened") from error
        finally:
            _close_database(connection)
    return report


def _refresh_connection(connection: sqlite3.Connection, desired: dict[str, tuple[str, str, str]]) -> None:
    existing = {
            row[0]: (row[1], row[2])
            for row in connection.execute(
                "SELECT source_path, source_sha256, extractor_version FROM indexed_sources"
            )
    }
    for source_path in sorted(set(existing) - set(desired)):
        connection.execute("DELETE FROM library_fts WHERE source_path = ?", (source_path,))
        connection.execute("DELETE FROM indexed_sources WHERE source_path = ?", (source_path,))
    for source_path in sorted(desired):
        source_hash, version, text = desired[source_path]
        if existing.get(source_path) == (source_hash, version):
            continue
        connection.execute("DELETE FROM library_fts WHERE source_path = ?", (source_path,))
        connection.execute("DELETE FROM indexed_sources WHERE source_path = ?", (source_path,))
        connection.execute(
            "INSERT INTO library_fts(source_path, text) VALUES (?, ?)",
            (source_path, text),
        )
        connection.execute(
            "INSERT INTO indexed_sources(source_path, source_sha256, extractor_version, indexed_at) VALUES (?, ?, ?, ?)",
            (source_path, source_hash, version, _timestamp()),
        )


def rebuild(
    cache: Path, workspace: str | Path, *, task_id: str | None = None,
    requested: bool = False,
) -> IgnoreReport:
    """Update derived state only with this invocation's Library permission."""
    with operation(workspace, task_id=task_id, requested=("library",) if requested else ()) as context:
        context.require_library_write()
        return _rebuild_authorized(cache, workspace)


def _rebuild_authorized(cache: Path, workspace: str | Path) -> IgnoreReport:
    """Discard and deterministically recreate this cache's derived index."""
    rules = load_ignore_rules(workspace).require_valid()
    with _writer_lock(cache):
        desired, report = _extracted_sources(cache, rules)
        if hasattr(sqlite3.Connection, "deserialize"):
            connection = _fresh_database()
            try:
                _build_replacement(connection, desired)
                _publish_database(cache, connection)
            except sqlite3.Error as error:
                raise IndexError("Library index could not be rebuilt") from error
            finally:
                _close_database(connection)
            return report
        _rebuild_legacy(cache, desired)
        return report


def _fresh_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA temp_store = MEMORY")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _build_replacement(
    connection: sqlite3.Connection, desired: dict[str, tuple[str, str, str]]
) -> None:
    with connection:
        _create_schema(connection)
        _refresh_connection(connection, desired)


def _rebuild_legacy(
    cache: Path, desired: dict[str, tuple[str, str, str]]
) -> None:
    connection: sqlite3.Connection | None = None
    try:
        for attempt in range(2):
            try:
                connection = _database(cache)
                with connection:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute("DROP TABLE IF EXISTS library_fts")
                    connection.execute("DROP TABLE IF EXISTS indexed_sources")
                    _create_schema(connection)
                    _refresh_connection(connection, desired)
                _publish_database(cache, connection)
                return
            except _CorruptDatabaseError as error:
                connection = error.connection
                corruption: BaseException = error
            except (IndexError, sqlite3.Error) as error:
                if not _is_corrupt_database(error):
                    if isinstance(error, IndexError):
                        raise
                    raise IndexError("Library index could not be rebuilt") from error
                corruption = error
            if connection is None:
                raise IndexError("Library index could not be rebuilt") from corruption
            if attempt:
                _close_database(connection)
                connection = None
                raise IndexError("Library index could not be rebuilt") from corruption
            try:
                _discard_corrupt_database(cache, connection)
            finally:
                connection = None
    finally:
        if connection is not None:
            _close_database(connection)


def _is_corrupt_database(error: BaseException) -> bool:
    current: BaseException | None = error
    while current is not None:
        message = str(current).lower()
        if "not a database" in message or "malformed" in message:
            return True
        current = current.__cause__
    return False


def _discard_corrupt_database(
    cache: Path, connection: sqlite3.Connection | None
) -> None:
    """Discard only a validated corrupt derived database before a legacy retry."""
    if connection is None:
        raise IndexError("Library index could not be rebuilt")
    database = cache / "index.sqlite3"
    descriptor = _DATABASE_FDS.pop(id(connection), -1)
    handle = _DATABASE_HANDLES.pop(id(connection), -1)
    try:
        connection.close()
        if handle >= 0:
            fs_transactions._win_delete_handle(handle)
            return
        if descriptor < 0 or _is_windows():
            raise IndexError("Library index could not be rebuilt")
        _unlink_retained_corrupt_database(cache, database, descriptor)
    except (OSError, sqlite3.Error) as error:
        raise IndexError("Library index could not be rebuilt") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if handle >= 0:
            fs_transactions._win_close(handle)


def _unlink_retained_corrupt_database(cache: Path, database: Path, descriptor: int) -> None:
    expected = os.fstat(descriptor)
    if not _private_regular(expected):
        raise IndexError("Library index could not be rebuilt")
    parent = os.open(
        cache,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    temporary = f".apparatus-index-quarantine-{secrets.token_hex(16)}"
    temporary_descriptor = -1
    temporary_identity: tuple[int, int] | None = None
    exchanged = False
    quarantined_removed = False
    try:
        temporary_descriptor = os.open(
            temporary,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent,
        )
        if _is_posix():
            os.fchmod(temporary_descriptor, 0o600)
        temporary_status = os.fstat(temporary_descriptor)
        temporary_identity = (temporary_status.st_dev, temporary_status.st_ino)
        if not _private_regular(temporary_status) or temporary_status.st_size != 0:
            raise IndexError("Library index could not be rebuilt")
        fs_transactions.exchange_names(parent, database.name, temporary)
        exchanged = True
        quarantined = os.stat(temporary, dir_fd=parent, follow_symlinks=False)
        if (quarantined.st_dev, quarantined.st_ino) != (expected.st_dev, expected.st_ino):
            fs_transactions.exchange_names(parent, database.name, temporary)
            exchanged = False
            _unlink_owned_relative(parent, temporary, temporary_identity)
            raise IndexError("Library index could not be rebuilt")
        if not _unlink_owned_relative(parent, temporary, (expected.st_dev, expected.st_ino)):
            raise IndexError("Library index could not be rebuilt")
        quarantined_removed = True
        if not _unlink_owned_relative(parent, database.name, temporary_identity):
            raise IndexError("Library index could not be rebuilt")
        exchanged = False
    except Exception:
        if exchanged and not quarantined_removed:
            try:
                fs_transactions.exchange_names(parent, database.name, temporary)
            except OSError:
                pass
            else:
                exchanged = False
        elif exchanged:
            _unlink_owned_relative(parent, database.name, temporary_identity)
            exchanged = False
        raise
    finally:
        if temporary_descriptor >= 0:
            os.close(temporary_descriptor)
        if not exchanged:
            _unlink_owned_relative(parent, temporary, temporary_identity)
        os.close(parent)


def _unlink_owned_relative(
    parent: int, name: str, identity: tuple[int, int] | None
) -> bool:
    if identity is None:
        return False
    try:
        status = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if (
            stat.S_ISREG(status.st_mode)
            and status.st_nlink == 1
            and (status.st_dev, status.st_ino) == identity
        ):
            os.unlink(name, dir_fd=parent)
            return True
    except OSError:
        return False
    return False


def _search_connection(connection: sqlite3.Connection, query: str, limit: int) -> list[SearchHit]:
    if limit < 1:
        raise ValueError("search limit must be positive")
    terms = _query_terms(query)
    if not terms:
        return []
    try:
        rows = connection.execute(
            "SELECT source_path, snippet(library_fts, 1, '[', ']', '…', 12), "
            "-bm25(library_fts) AS score FROM library_fts "
            "WHERE library_fts MATCH ? ORDER BY score DESC, source_path ASC LIMIT ?",
            (terms, limit),
        ).fetchall()
    except sqlite3.Error as error:
        raise IndexError("Library index could not be opened") from error
    hits = [SearchHit(str(path), str(snippet), float(score)) for path, snippet, score in rows]
    if not all(math.isfinite(hit.score) for hit in hits):
        raise IndexError("local search returned an invalid score")
    return hits


def search(cache: Path, query: str, limit: int = 5) -> list[SearchHit]:
    """Read an existing index without creating schema, journals, or database files."""
    if limit < 1:
        raise ValueError("search limit must be positive")
    if not _query_terms(query):
        return []
    connection = _readonly_database(cache)
    try:
        return _search_connection(connection, query, limit)
    finally:
        _close_database(connection)


def _readonly_database(cache: Path) -> sqlite3.Connection:
    _assert_private_cache(cache)
    database = cache / "index.sqlite3"
    _assert_sidecars(database)
    descriptor = handle = -1
    connection = None
    try:
        content = _read_database(database)
        if content is None:
            raise IndexError("Library index is unavailable")
        if hasattr(sqlite3.Connection, "deserialize"):
            connection = _fresh_database()
            connection.deserialize(content)
        elif _is_posix():
            descriptor = os.open(database, os.O_RDONLY | os.O_NOFOLLOW)
            if not _private_regular(os.fstat(descriptor)):
                raise IndexError("Library index is not a private regular file")
            connection = sqlite3.connect(f"file:/dev/fd/{descriptor}?mode=ro&immutable=1", uri=True)
            _DATABASE_FDS[id(connection)] = descriptor
            descriptor = -1
        else:
            handle = fs_transactions._win_open(
                database, directory=False, lock_name=True, retain_readable=True,
            )
            connection = sqlite3.connect(database.as_uri() + "?mode=ro&immutable=1", uri=True)
            _DATABASE_HANDLES[id(connection)] = handle
            handle = -1
        connection.execute("PRAGMA temp_store = MEMORY")
        connection.execute("PRAGMA query_only = ON")
        return connection
    except (OSError, sqlite3.Error) as error:
        if connection is not None:
            _close_database(connection)
        raise IndexError("Library index could not be opened") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if handle >= 0:
            fs_transactions._win_close(handle)


def retrieve(
    workspace: str | Path, query: str, limit: int = 5, *,
    task_id: str | None = None, rebuild_index: bool = False, requested: bool = False,
) -> tuple[list[SearchHit], IgnoreReport]:
    """Share retrieval and retention behavior between Library search and recall."""
    if limit < 1:
        raise ValueError("search limit must be positive")
    with operation(workspace, task_id=task_id, requested=("library",) if requested else ()) as context:
        rules = load_ignore_rules(workspace).require_valid()
        persistent = context.save_memory or (requested and rebuild_index)
        if rebuild_index:
            context.require_library_write()
        cache = library_cache_root(workspace, create=persistent)
        if not has_extractions(cache, rules):
            raise NoExtractionsError("Existing Library extractions are unavailable.", readonly=not persistent)
        if persistent:
            report = rebuild(cache, workspace) if rebuild_index else refresh(cache, workspace)
            return search(cache, query, limit), report
        desired, report = _extracted_sources(cache, rules, strict=True)
        connection = _fresh_database()
        try:
            _build_replacement(connection, desired)
            return _search_connection(connection, query, limit), report
        except sqlite3.Error as error:
            raise IndexError("Library index could not be opened") from error
        finally:
            connection.close()


def has_extractions(cache: Path, rules: IgnoreRules) -> bool:
    """Whether the cache has a visible or ignored extraction boundary."""
    extractions = cache / "extractions"
    if not extractions.is_dir() or is_reparse_path(extractions):
        return False
    records, built_in_ignored, user_ignored = _record_paths(extractions, rules)
    return bool(records or built_in_ignored or user_ignored)


def _database(cache: Path) -> sqlite3.Connection:
    _assert_private_cache(cache)
    database = cache / "index.sqlite3"
    _assert_sidecars(database)
    connection: sqlite3.Connection | None = None
    descriptor = -1
    legacy = not hasattr(sqlite3.Connection, "deserialize")
    try:
        if not legacy:
            content = _read_database(database)
            connection = sqlite3.connect(":memory:")
            if content:
                connection.deserialize(content)
        elif not _legacy_windows_unavailable():  # Python 3.10 POSIX: retain one no-follow fd.
            descriptor = _open_database_fd(database)
            connection = sqlite3.connect(f"/dev/fd/{descriptor}")
            _DATABASE_FDS[id(connection)] = descriptor
            descriptor = -1
            connection.execute("PRAGMA journal_mode = MEMORY")
        else:  # pragma: no cover - selected Windows CI exercises this branch
            connection = _windows_legacy_connection(database)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
    except _CorruptDatabaseError:
        raise
    except sqlite3.Error as error:
        if legacy and connection is not None and _is_corrupt_database(error):
            raise _CorruptDatabaseError(connection) from error
        if connection is not None:
            _close_database(connection)
        elif descriptor >= 0:
            os.close(descriptor)
        raise IndexError("Library index could not be opened") from error
    except OSError as error:
        if connection is not None:
            _close_database(connection)
        elif descriptor >= 0:
            os.close(descriptor)
        raise IndexError("Library index could not be opened") from error


def _database_for_operation(cache: Path) -> sqlite3.Connection:
    """Open an index for refresh/search without leaking a corrupt legacy handle."""
    try:
        return _database(cache)
    except _CorruptDatabaseError as error:
        _close_database(error.connection)
        raise IndexError("Library index could not be opened") from error


def _read_database(database: Path) -> bytes | None:
    try:
        status = os.lstat(database)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise IndexError("Library index could not be inspected") from error
    if not _private_regular(status):
        raise IndexError("Library index is not a private regular file")
    descriptor = os.open(
        database,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0),
    )
    try:
        before = os.fstat(descriptor)
        if not _private_regular(before):
            raise IndexError("Library index is not a private regular file")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 65_536):
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size) != (after.st_dev, after.st_ino, after.st_size):
            raise IndexError("Library index changed while it was read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _publish_database(cache: Path, connection: sqlite3.Connection) -> None:
    """Atomically replace the index from an in-memory SQLite snapshot."""
    database = cache / "index.sqlite3"
    _assert_sidecars(database)
    if id(connection) in _DATABASE_HANDLES:
        try:
            fs_transactions._win_identity(_DATABASE_HANDLES[id(connection)])
        except OSError as error:
            raise IndexError("Library index changed during publication") from error
        _assert_replaceable_database(database)
        _assert_sidecars(database)
        return
    if not hasattr(connection, "serialize"):
        _assert_replaceable_database(database)
        _assert_sidecars(database)
        return
    content = connection.serialize()
    descriptor, temporary_name = tempfile.mkstemp(prefix=".apparatus-index-", dir=cache)
    temporary = Path(temporary_name)
    identity: tuple[int, int] | None = None
    try:
        status = os.fstat(descriptor)
        identity = (status.st_dev, status.st_ino)
        if _is_posix():
            os.fchmod(descriptor, 0o600)
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("Library index could not be written")
            view = view[written:]
        os.fsync(descriptor)
        os.close(descriptor); descriptor = -1
        if not _temporary_matches(temporary, identity, content):
            raise IndexError("Library index temporary changed before publication")
        _assert_sidecars(database)
        _assert_replaceable_database(database)
        os.replace(temporary, database)
        _assert_sidecars(database)
        if not _published_matches(database, identity, content):
            raise IndexError("Library index changed during publication")
    except (OSError, IndexError) as error:
        if descriptor >= 0:
            os.close(descriptor)
        _remove_owned_temporary(temporary, identity, content)
        if isinstance(error, IndexError):
            raise
        raise IndexError("Library index could not be published") from error


def _assert_replaceable_database(database: Path) -> None:
    try:
        status = os.lstat(database)
    except FileNotFoundError:
        return
    if not _private_regular(status):
        raise IndexError("Library index is not a private regular file")


def _open_database_fd(database: Path) -> int:
    try:
        status = os.lstat(database)
    except FileNotFoundError:
        descriptor = -1
        identity: tuple[int, int] | None = None
        try:
            descriptor = os.open(
                database, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            created = os.fstat(descriptor)
            identity = (created.st_dev, created.st_ino)
            if _is_posix():
                os.fchmod(descriptor, 0o600)
            return descriptor
        except FileExistsError:
            return _open_database_fd(database)
        except Exception:
            if descriptor >= 0:
                os.close(descriptor)
            _remove_empty_owned_database(database, identity)
            raise
    if not _private_regular(status):
        raise IndexError("Library index is not a private regular file")
    descriptor = os.open(database, os.O_RDWR | os.O_NOFOLLOW)
    if not _private_regular(os.fstat(descriptor)):
        os.close(descriptor)
        raise IndexError("Library index is not a private regular file")
    return descriptor


def _remove_empty_owned_database(
    database: Path, identity: tuple[int, int] | None
) -> None:
    """Remove only a failed, still-owned exclusive database creation."""
    if identity is None:
        return
    try:
        status = os.lstat(database)
        if (
            stat.S_ISREG(status.st_mode)
            and status.st_nlink == 1
            and status.st_size == 0
            and (status.st_dev, status.st_ino) == identity
        ):
            database.unlink()
    except OSError:
        pass


def _close_database(connection: sqlite3.Connection) -> None:
    descriptor = _DATABASE_FDS.pop(id(connection), -1)
    handle = _DATABASE_HANDLES.pop(id(connection), -1)
    try:
        connection.close()
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if handle >= 0:
            fs_transactions._win_close(handle)


def _legacy_windows_unavailable() -> bool:
    """Select the retained-handle backend only for legacy Windows Python."""
    return os.name != "posix"


def _windows_legacy_connection(database: Path) -> sqlite3.Connection:
    """Open legacy Windows SQLite only while a no-reparse name lock is retained."""
    handle = -1
    connection: sqlite3.Connection | None = None
    try:
        try:
            status = os.lstat(database)
        except FileNotFoundError:
            status = None
        if status is None:
            handle = fs_transactions._win_open(
                database, directory=False, create=True, lock_name=True,
                share_existing_write=True,
            )
        else:
            if not _private_regular(status):
                raise IndexError("Library index is not a private regular file")
            handle = fs_transactions._win_open(
                database, directory=False, lock_name=True, share_existing_write=True,
            )
        connection = sqlite3.connect(database)
        _DATABASE_HANDLES[id(connection)] = handle
        handle = -1
        connection.execute("PRAGMA journal_mode = MEMORY")
        return connection
    except sqlite3.Error as error:
        if connection is not None and _is_corrupt_database(error):
            raise _CorruptDatabaseError(connection) from error
        if connection is not None:
            _close_database(connection)
        elif handle >= 0:
            fs_transactions._win_close(handle)
        raise IndexError("Library index could not be opened safely") from error
    except Exception as error:
        if connection is not None:
            _close_database(connection)
        elif handle >= 0:
            fs_transactions._win_close(handle)
        if isinstance(error, IndexError):
            raise
        raise IndexError("Library index could not be opened safely") from error


def _temporary_matches(path: Path, identity: tuple[int, int], content: bytes) -> bool:
    try:
        status = os.lstat(path)
        return _private_regular(status) and (status.st_dev, status.st_ino) == identity and path.read_bytes() == content
    except OSError:
        return False


def _published_matches(path: Path, identity: tuple[int, int], content: bytes) -> bool:
    return _temporary_matches(path, identity, content)


def _remove_owned_temporary(path: Path, identity: tuple[int, int] | None, content: bytes) -> None:
    if identity is not None and _temporary_matches(path, identity, content):
        try:
            path.unlink()
        except OSError:
            pass


def _assert_sidecars(database: Path) -> None:
    for suffix in ("-journal", "-wal", "-shm"):
        path = Path(str(database) + suffix)
        try:
            status = os.lstat(path)
        except FileNotFoundError:
            continue
        except OSError as error:
            raise IndexError("Library index sidecar could not be inspected") from error
        if not _private_regular(status):
            raise IndexError("Library index sidecar is not a private regular file")


def _private_regular(status: os.stat_result) -> bool:
    return (
        stat.S_ISREG(status.st_mode)
        and status.st_nlink == 1
        and (not _is_posix() or stat.S_IMODE(status.st_mode) == 0o600)
    )


def _is_posix() -> bool:
    """Whether this platform exposes POSIX file modes and ``fchmod``."""
    return os.name == "posix"


def _is_windows() -> bool:
    """Whether the retained Win32 no-reparse backend is available."""
    return os.name == "nt"


def _create_schema(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("CREATE VIRTUAL TABLE IF NOT EXISTS library_fts USING fts5(source_path UNINDEXED, text)")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS indexed_sources("
            "source_path TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL, "
            "extractor_version TEXT NOT NULL, indexed_at TEXT NOT NULL)"
        )
    except sqlite3.OperationalError as error:
        if "fts5" in str(error).lower() or "no such module" in str(error).lower():
            raise FtsUnavailable("local search is unavailable because this Python does not include SQLite FTS5") from error
        raise IndexError("Library index could not be prepared") from error


def _extracted_sources(
    cache: Path, rules: IgnoreRules, *, strict: bool = False,
) -> tuple[dict[str, tuple[str, str, str]], IgnoreReport]:
    _assert_private_cache(cache)
    extractions = cache / "extractions"
    if not extractions.is_dir() or is_reparse_path(extractions):
        if strict:
            raise NoExtractionsError("Existing Library extractions are unavailable.", readonly=True)
        return {}, rules.report()
    sources: dict[str, tuple[str, str, str]] = {}
    record_paths, built_in_ignored, user_ignored = _record_paths(
        extractions, rules
    )
    for record_path in record_paths:
        relative = record_path.relative_to(extractions).as_posix()[:-5]
        text_path = record_path.with_suffix(".txt")
        try:
            record = json.loads(_read_private_file(record_path).decode("utf-8"))
        except (OSError, ValueError) as error:
            if strict:
                raise NoExtractionsError("Existing Library extraction evidence is invalid.", readonly=True) from error
            continue
        if strict and isinstance(record, dict) and record.get("status") in (
            "no_text", "unsupported", "error"
        ):
            # Valid terminal extraction outcomes provide no searchable text.
            # Apply the ingest metadata contract before omitting them so a
            # malformed pair cannot masquerade as a legitimate empty result.
            try:
                valid_terminal = _valid_record(
                    record, "Library/" + relative, record.get("source_sha256"),
                    record.get("size_bytes"), text_path,
                )
            except (TypeError, ValueError):
                valid_terminal = False
            if not valid_terminal:
                raise NoExtractionsError("Existing Library extraction evidence is invalid.", readonly=True)
            continue
        if not _is_extracted_record(record, relative, text_path):
            if strict:
                raise NoExtractionsError("Existing Library extraction evidence is unavailable.", readonly=True)
            continue
        try:
            sources[record["source_path"]] = (
                record["source_sha256"], record["extractor_version"], _read_private_file(text_path).decode("utf-8")
            )
        except (OSError, UnicodeError) as error:
            if strict:
                raise NoExtractionsError("Existing Library extraction evidence is invalid.", readonly=True) from error
            continue
    return sources, rules.report(
        built_in_paths=built_in_ignored, user_paths=user_ignored
    )


def _is_extracted_record(record: object, relative: str, text_path: Path) -> bool:
    if not isinstance(record, dict):
        return False
    source_path = "Library/" + relative
    digest = record.get("source_sha256")
    return (
        record.get("source_path") == source_path
        and record.get("status") == "extracted"
        and record.get("extractor_version") == EXTRACTOR_VERSION
        and isinstance(digest, str)
        and len(digest) == 64
        and all(character in "0123456789abcdef" for character in digest)
        and _private_path(text_path)
    )


def _assert_private_cache(cache: Path) -> None:
    if is_reparse_path(cache):
        raise IndexError("Library cache must not contain symbolic links")
    extractions = cache / "extractions"
    if extractions.exists() and is_reparse_path(extractions):
        raise IndexError("Library extraction cache must not contain symbolic links")


@contextmanager
def _writer_lock(cache: Path):
    """Hold a private cross-process cache lock through one writer snapshot."""
    _assert_private_cache(cache)
    lock = cache / ".apparatus-index.lock"
    if _is_windows():
        with _windows_writer_lock(lock):
            yield
        return
    descriptor = -1
    identity: tuple[int, int] | None = None
    try:
        for _attempt in range(500):
            try:
                descriptor = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
                status = os.fstat(descriptor)
                identity = (status.st_dev, status.st_ino)
                if _is_posix():
                    os.fchmod(descriptor, 0o600)
                status = os.fstat(descriptor)
                if not _private_regular(status):
                    raise IndexError("Library index writer lock is not private")
                break
            except FileExistsError:
                try:
                    status = os.lstat(lock)
                except OSError as error:
                    raise IndexError("Library index writer lock could not be inspected") from error
                if not _private_regular(status) or is_reparse_path(lock):
                    raise IndexError("Library index writer lock is not private")
                time.sleep(0.01)
        else:
            raise IndexError("Library index is busy")
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        _remove_owned_lock(lock, identity)
        raise
    try:
        yield
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        _remove_owned_lock(lock, identity)


@contextmanager
def _windows_writer_lock(lock: Path):
    """Acquire a no-reparse, name-locked writer lock on Windows."""
    handle = -1
    identity: tuple[int, int] | None = None
    unsafe_metadata_attempts = 0
    try:
        for _attempt in range(500):
            try:
                handle = fs_transactions._win_open(
                    lock, directory=False, create=True, lock_name=True
                )
                status = os.lstat(lock)
                identity = (status.st_dev, status.st_ino)
                if not _private_regular(status) or is_reparse_path(lock):
                    raise IndexError("Library index writer lock is not private")
                break
            except FileExistsError:
                try:
                    status = os.lstat(lock)
                except OSError as error:
                    raise IndexError("Library index writer lock could not be inspected") from error
                if is_reparse_path(lock):
                    raise IndexError("Library index writer lock is not private")
                # A concurrent Win32 creator can expose the name before its
                # final metadata is observable. Retry only a bounded number
                # of regular-but-not-yet-private observations; a directory,
                # device, or persistent unsafe endpoint is not a writer.
                if not stat.S_ISREG(status.st_mode):
                    raise IndexError("Library index writer lock is not private")
                if not _private_regular(status):
                    unsafe_metadata_attempts += 1
                    if unsafe_metadata_attempts >= _WINDOWS_LOCK_METADATA_RETRIES:
                        raise IndexError("Library index writer lock is not private")
                    time.sleep(0.01)
                    continue
                unsafe_metadata_attempts = 0
                time.sleep(0.01)
        else:
            raise IndexError("Library index is busy")
    except Exception:
        if handle >= 0:
            try:
                fs_transactions._win_delete_handle(handle)
            except OSError:
                pass
            finally:
                fs_transactions._win_close(handle)
        else:
            _remove_owned_lock(lock, identity)
        raise
    try:
        yield
    finally:
        if handle >= 0:
            try:
                fs_transactions._win_delete_handle(handle)
            except OSError:
                pass
            finally:
                fs_transactions._win_close(handle)
        else:
            _remove_owned_lock(lock, identity)


def _remove_owned_lock(lock: Path, identity: tuple[int, int] | None) -> None:
    if identity is None:
        return
    try:
        status = os.lstat(lock)
        if _private_regular(status) and (status.st_dev, status.st_ino) == identity:
            lock.unlink()
    except OSError:
        pass


def _record_paths(
    extractions: Path, rules: IgnoreRules
) -> tuple[list[Path], int, int]:
    """Walk cache records without following links, junctions, or special files."""
    records: list[Path] = []
    built_in_ignored = 0
    user_ignored = 0

    def count(classification: str) -> None:
        nonlocal built_in_ignored, user_ignored
        if classification == "built-in":
            built_in_ignored += 1
        else:
            user_ignored += 1

    def visit(directory: Path) -> None:
        try:
            with os.scandir(directory) as scan:
                children = sorted((directory / entry.name for entry in scan), key=lambda path: path.as_posix())
        except OSError as error:
            raise IndexError("Library extraction cache could not be inspected") from error
        for child in children:
            try:
                status = os.lstat(child)
            except OSError as error:
                raise IndexError("Library extraction cache could not be inspected") from error
            if is_reparse_path(child):
                raise IndexError("Library extraction cache must not contain symbolic links")
            if stat.S_ISDIR(status.st_mode):
                relative = child.relative_to(extractions).as_posix()
                classification = rules.classification(
                    "Library/" + relative, is_directory=True
                )
                if classification is not None:
                    count(classification)
                    continue
                visit(child)
            elif child.name.endswith(".json"):
                if not _private_regular(status):
                    raise IndexError("Library extraction record is not a private regular file")
                relative = child.relative_to(extractions).as_posix()[:-5]
                classification = rules.classification("Library/" + relative)
                if classification is not None:
                    count(classification)
                    continue
                records.append(child)

    visit(extractions)
    return records, built_in_ignored, user_ignored


def _private_path(path: Path) -> bool:
    try:
        return _private_regular(os.lstat(path)) and not is_reparse_path(path)
    except OSError:
        return False


def _read_private_file(path: Path) -> bytes:
    status = os.lstat(path)
    if not _private_regular(status) or is_reparse_path(path):
        raise IndexError("Library extraction cache is not a private regular file")
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0),
    )
    try:
        before = os.fstat(descriptor)
        if not _private_regular(before):
            raise IndexError("Library extraction cache is not a private regular file")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 65_536):
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size) != (after.st_dev, after.st_ino, after.st_size):
            raise IndexError("Library extraction cache changed while it was read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _query_terms(query: str) -> str:
    return " ".join('"' + term.replace('"', '""') + '"' for term in query.split())


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
