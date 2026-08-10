# Universal payload builder

`build_payload.py` turns the repository's starter payload and profile overlays
into the single distributable Apparatus payload. Run it from the repository:

```bash
uv run python tools/build_payload.py
```

The default output is `dist/apparatus-payload-<version>.zip`, using the version
from `packages/apparatus-core/pyproject.toml`. Use `--version VERSION` to set an
explicit version or `--out DIRECTORY` to choose another output directory.

The archive contains `payload/`, mirroring `starter/payload/`; `profiles/`,
mirroring `starter/profiles/`; and `manifest.txt`. The manifest starts with the
payload version, then lists the SHA-256 and path of every other archived file in
path order. Repository placeholders such as `.gitkeep` remain in the payload.

The builder stages the payload and runs the same renderer as `apparatus render`
before archiving it. Stale committed shims therefore cannot ship; the command
still succeeds and names each stale shim in a warning. Symbolic links, reparse
points, nonportable paths, OS metadata, and `__pycache__` content are excluded or
rejected before publication.

Entries are written in path order with regular-file mode `0644` and no
compression, so compression-library versions cannot change the bytes. Their
timestamp is `1980-01-01 00:00:00` unless `SOURCE_DATE_EPOCH` is set; that value
is interpreted in UTC and normalized to ZIP's two-second precision. No source
mtime, owner, absolute path, umask-derived mode, or wall-clock value enters the
archive. Repeated builds from the same tree and environment are byte-identical.
