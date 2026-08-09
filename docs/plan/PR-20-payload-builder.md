# PR-20: Universal payload builder

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` — especially §5 (workspace), §9 (distribution), §10 (architecture)
- `docs/adr/ADR-0002-protocol-and-state.md`
- `docs/adr/ADR-0003-harness-agnostic-contract.md`
- `docs/adr/ADR-0005-distribution-and-packaging.md`
- `docs/plan/README.md`
- `docs/spec/workspace.md` — the payload tree and the placeholder rules
- `conformance/README.md` and `conformance/golden/payload-manifest.txt`
- `.github/workflows/ci.yml`

## Objective

When this PR lands, one command turns `starter/` into the distributable
artifact of record: a versioned, reproducible, universal payload archive that
the release pipeline (PR-21) publishes and the bootstrapper (PR-22) deploys.
The build renders shims from canon as part of the build itself, so a stale
committed shim can never ship; it bundles the profile overlays so `init`
applies them at deploy time; and it is deterministic, so two builds of the same
tree are byte-identical and reviewable. There is exactly one artifact — not
per-app, not per-profile — per ADR-0003 ("the payload is built once; profiles
vary content, apps do not").

## Deliverables

- `tools/build_payload.py` — new; builder script with no third-party
  dependencies (Python stdlib plus `apparatus_core`, see criterion 6), run as
  `uv run python tools/build_payload.py` (uv only so the PR-13 render code in
  `apparatus_core` is importable).
- `tools/README.md` — new; one page: what the builder does, how to run it
  locally, determinism guarantees, archive layout.
- `conformance/test_payload_archive.py` — new conformance test (see below).
- `conformance/README.md` — modified; register the new fixture/test in the
  table.
- `.github/workflows/ci.yml` — modified; on pushes to `main`, build the
  archive and upload it with `actions/upload-artifact`.
- `docs/plan/README.md` — modified; status table row for PR-20.

## Acceptance criteria

1. `uv run python tools/build_payload.py` writes
   `dist/apparatus-payload-<version>.zip` (and `dist/` is gitignored). The
   version is read from `packages/apparatus-core/pyproject.toml`; a
   `--version` flag overrides it and `--out` overrides the output directory.
2. Archive layout: a top-level `payload/` tree mirroring `starter/payload/`
   (after the fresh shim render, step 3); a top-level `profiles/` tree
   mirroring `starter/profiles/` (design brief §10: `starter/` holds
   "payload + profiles"; the overlay root and its manifest are defined in
   PR-11 and consumed by `init`); and a top-level `manifest.txt` recording the payload
   version plus one `sha256  path` line per archived file, sorted by path.
3. Shims are freshly rendered during the build: the builder stages a copy of
   `starter/payload/`, invokes the same render implementation the `apparatus
   render` command uses (PR-13) against the staged copy, and archives the
   result. Committed shim drift therefore cannot reach the artifact. If the
   fresh render differs from the committed shims, the builder still succeeds
   but prints a drift warning naming each differing file.
4. Reproducibility: archive entries are sorted by path; every entry carries a
   fixed timestamp (1980-01-01 00:00, or `SOURCE_DATE_EPOCH` when set) and
   fixed permission bits; no OS metadata files (`.DS_Store`, `Thumbs.db`,
   `desktop.ini`) or `__pycache__` content is ever included. Two consecutive
   builds of the same tree are byte-identical (asserted by the conformance
   test), and a reviewer can confirm from the builder source that nothing
   environment-dependent — usernames, absolute paths, wall-clock timestamps,
   umask-derived permissions — reaches the archive or `manifest.txt`.
5. `.gitkeep` placeholders are retained in the archive, per
   `docs/spec/workspace.md` ("zip-shaped payload distributions").
6. The builder is Python stdlib plus `apparatus_core` only — no new
   third-party dependency is added anywhere in this PR.
7. CI: pushes to `main` run the builder and upload
   `apparatus-payload-<version>.zip` as a workflow artifact. Pull-request runs
   still execute the builder (via the conformance test) but do not upload.
8. Exit codes: 0 on success, nonzero with a clear message on any structural
   failure (missing starter tree, render failure, unwritable output).
9. The status table in `docs/plan/README.md` is updated in this PR.

## Conformance and tests

- New `conformance/test_payload_archive.py`, building into `tmp_path`:
  - the entry set under `payload/` in the archive equals
    `conformance/golden/payload-manifest.txt` exactly (the manifest as it
    stands after PR-07/PR-13, which includes canon and shims);
  - each shim file in the archive byte-matches a fresh render from canon;
  - building twice yields byte-identical archives;
  - every line in the embedded `manifest.txt` matches the actual SHA-256 of
    the corresponding archive entry, and no entry is unlisted.
- Register the test in the `conformance/README.md` table.
- Do not modify `conformance/golden/payload-manifest.txt` in this PR; if it
  fails, the payload or an earlier PR drifted — fix that, never the fixture.
- `uv run pytest` green is required.

## Out of scope

- No tag-triggered releases, PyPI publishing, or GitHub Releases (PR-21).
- No bootstrapper or installer work (PR-22) and no signing (PR-23).
- No per-app or per-profile artifact variants — one universal archive only.
- No changes to starter payload content, shim content, or render behavior.
- No tarball/second archive format; zip only in v0.
- No new CLI verb — this is a repository build tool, not a user-facing
  `apparatus` command; users never build payloads (ADR-0005).

## Dependencies

- PR-13 (render — canon to shims) and PR-19 (welcome flow end-to-end), per the
  status table in `docs/plan/README.md`.

## Open decisions

- None. The single universal archive, zip format, and determinism rules are
  fixed by ADR-0003, ADR-0005, and the acceptance criteria above; how the
  published archive is consumed on a user machine belongs to the release
  pipeline and bootstrapper (PR-21 and PR-22).
