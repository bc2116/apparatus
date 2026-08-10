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
from apparatus_core.ignore import load_ignore_rules
from apparatus_core.library.extractors import EXTRACTOR_VERSION
from apparatus_core.render import is_reparse_path


class IndexError(RuntimeError):
    """The derived Library index cannot safely be used."""


class FtsUnavailable(IndexError):
    """This Python SQLite build has no FTS5 support."""


class _CorruptDatabaseError(IndexError):
    """A legacy database connection retained a verified corrupt endpoint."""

    def __init__(self, connection: sqlite3.Connection):
        super().__init__("Library index could not be opened")
        self.connection = connection


_DATABASE_FDS: dict[int, int] = {}
_DATABASE_HANDLES: dict[int, int] = {}


@dataclass(frozen=True)
class SearchHit:
    source_path: str
    snippet: str
    score: float


def refresh(cache: Path, workspace: str | Path | None = None) -> None:
    """Synchronize changed extracted cache pairs into the local FTS index."""
    with _writer_lock(cache):
        desired = _extracted_sources(cache) if workspace is None else _extracted_sources(cache, workspace)
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


def rebuild(cache: Path) -> None:
    """Discard and deterministically recreate this cache's derived index."""
    with _writer_lock(cache):
        desired = _extracted_sources(cache)
        if hasattr(sqlite3.Connection, "deserialize"):
            connection = _fresh_database()
            try:
                _build_replacement(connection, desired)
                _publish_database(cache, connection)
            except sqlite3.Error as error:
                raise IndexError("Library index could not be rebuilt") from error
            finally:
                _close_database(connection)
            return
        _rebuild_legacy(cache, desired)


def _fresh_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
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


def search(cache: Path, query: str, limit: int = 5) -> list[SearchHit]:
    """Return deterministic FTS5 hits, with higher bm25-derived scores first."""
    if limit < 1:
        raise ValueError("search limit must be positive")
    terms = _query_terms(query)
    if not terms:
        return []
    connection = _database_for_operation(cache)
    try:
        try:
            _create_schema(connection)
            rows = connection.execute(
                "SELECT source_path, snippet(library_fts, 1, '[', ']', '…', 12), "
                "-bm25(library_fts) AS score FROM library_fts "
                "WHERE library_fts MATCH ? ORDER BY score DESC, source_path ASC LIMIT ?",
                (terms, limit),
            ).fetchall()
        except sqlite3.Error as error:
            raise IndexError("Library index could not be opened") from error
    finally:
        _close_database(connection)
    hits = [SearchHit(str(path), str(snippet), float(score)) for path, snippet, score in rows]
    if not all(math.isfinite(hit.score) for hit in hits):
        raise IndexError("local search returned an invalid score")
    return hits


def has_extractions(cache: Path) -> bool:
    """Whether PR-14 has produced at least one extraction record."""
    extractions = cache / "extractions"
    if not extractions.is_dir() or is_reparse_path(extractions):
        return False
    return any(extractions.rglob("*.json"))


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
    cache: Path, workspace: str | Path | None = None
) -> dict[str, tuple[str, str, str]]:
    _assert_private_cache(cache)
    extractions = cache / "extractions"
    if not extractions.is_dir() or is_reparse_path(extractions):
        return {}
    sources: dict[str, tuple[str, str, str]] = {}
    rules = load_ignore_rules(workspace) if workspace is not None else None
    for record_path in _record_paths(extractions):
        relative = record_path.relative_to(extractions).as_posix()[:-5]
        text_path = record_path.with_suffix(".txt")
        try:
            record = json.loads(_read_private_file(record_path).decode("utf-8"))
        except (OSError, ValueError):
            continue
        if not _is_extracted_record(record, relative, text_path):
            continue
        if rules is not None and rules.matches(str(record["source_path"])):
            continue
        try:
            sources[record["source_path"]] = (
                record["source_sha256"], record["extractor_version"], _read_private_file(text_path).decode("utf-8")
            )
        except OSError:
            continue
    return sources


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
                if not _private_regular(status) or is_reparse_path(lock):
                    raise IndexError("Library index writer lock is not private")
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


def _record_paths(extractions: Path) -> list[Path]:
    """Walk cache records without following links, junctions, or special files."""
    records: list[Path] = []

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
                visit(child)
            elif child.name.endswith(".json"):
                if not _private_regular(status):
                    raise IndexError("Library extraction record is not a private regular file")
                records.append(child)

    visit(extractions)
    return records


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
