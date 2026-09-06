"""Machine-local, rebuildable Library cache locations."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from apparatus_core.render import is_reparse_path


def library_cache_root(workspace: str | Path, *, create: bool = True) -> Path:
    """Resolve a safe cache location, creating it only for permitted writes."""
    root = Path(workspace).resolve()
    workspace_id = hashlib.sha256(os.fsencode(root)).hexdigest()[:12]
    override = Path(os.environ.get("APPARATUS_HOME", Path.home() / ".apparatus")).expanduser()
    raw_home = Path.cwd() / override if not override.is_absolute() else override
    if _has_unsafe_component(raw_home) or is_reparse_path(raw_home / "library"):
        raise ValueError("Library cache path must not contain symbolic links")
    home = raw_home.resolve(strict=False)
    library = home / "library"
    cache = library / workspace_id
    if cache == root or root in cache.parents or cache in root.parents:
        raise ValueError("Library cache must live outside the workspace")
    # `library` must still be an ordinary child after canonicalising the home.
    # This guards a component created between the first lstat and mkdir.
    if is_reparse_path(library) or cache.resolve(strict=False).parent != library.resolve(strict=False):
        raise ValueError("Library cache path must not contain symbolic links")
    if create and os.name == "posix":
        try:
            _mkdir_private_cache(home, workspace_id)
        except OSError as error:
            raise ValueError("Library cache path must not contain symbolic links") from error
    elif create:  # pragma: no cover - protected by the Windows reparse checks above
        cache.mkdir(parents=True, exist_ok=True)
    if is_reparse_path(cache) or cache.resolve(strict=False).parent != library.resolve(strict=False):
        raise ValueError("Library cache path must not contain symbolic links")
    return cache.resolve(strict=False)


def _mkdir_private_cache(home: Path, workspace_id: str) -> None:
    """Create the final cache components through retained no-follow parents."""
    home.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    home_fd = library_fd = cache_fd = -1
    try:
        home_fd = os.open(home, flags)
        try:
            os.mkdir("library", 0o700, dir_fd=home_fd)
        except FileExistsError:
            pass
        library_fd = os.open("library", flags, dir_fd=home_fd)
        try:
            os.mkdir(workspace_id, 0o700, dir_fd=library_fd)
        except FileExistsError:
            pass
        cache_fd = os.open(workspace_id, flags, dir_fd=library_fd)
    finally:
        for descriptor in (cache_fd, library_fd, home_fd):
            if descriptor >= 0:
                os.close(descriptor)


def _has_unsafe_component(path: Path) -> bool:
    """Reject configured-home link components without rejecting macOS aliases.

    macOS exposes `/var` (and `/tmp`) as stable system aliases.  They are not
    user-controlled cache components, so preserve their normal canonical-path
    behaviour while rejecting every other existing link/reparse component.
    """
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        if not is_reparse_path(current):
            continue
        if os.name != "nt" and current in {Path("/var"), Path("/tmp")}:
            continue
        return True
    return False
