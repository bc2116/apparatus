# PR-37: Library writer-lock release race

Implement on `pr-37-library-lock`, based on PR-34. This is an isolated repair
of an observed existing race, independent of the layout/adoption rework.
Follow ADR-0006: keep the local index rebuildable and preserve filesystem
protections. Use frontier capability and high effort for this filesystem
boundary; require independent review before publication.

## Problem and observed evidence

The concurrent-refresh regression failed during the PR-36 full suite. The
second writer reported `Library index writer lock is not private`, leaving
the current-source search empty. Both the index implementation and its test
were unchanged from PR-34 commit `068e645`.

A bounded native macOS create/unlink-versus-`lstat` probe observed a regular
file with mode `0600` and link count zero during release. The observation
occurred after 31 successful metadata reads, 21 absent reads, and two completed
creates. This is observed platform behavior, not a claim that every system
returns the same metadata. A separate release interleaving leaves the name
absent between exclusive-create collision and inspection.

## Implementation boundary

- Change only the non-Windows exclusive-create acquisition branch in
  `packages/apparatus-core/src/apparatus_core/library/index.py`.
- After an exclusive-create collision, retry when inspection reports absence,
  or a non-reparse regular file with mode exactly `0600` and link count zero.
  These observations grant no ownership: every retry must attempt exclusive
  creation again and validate the resulting descriptor normally.
- Keep the existing 500-attempt budget and 0.01-second wait between attempts.
  Persistent release observations end with the existing busy diagnostic.
- Preserve private-file validation, owned cleanup, cache confinement, and the
  separate Windows lock implementation. Reject other inspection errors,
  unsafe modes, hardlinks, directories, symlinks, and reparse paths.
- Change the existing concurrent-refresh test to collect worker results with
  futures so worker exceptions surface directly. Preserve its current-source
  result, lock cleanup, and outside-symlink nonmutation assertions.

No cache schema, retention, extraction, transaction, or public command changes.

## Acceptance and owned artifacts

The focused test file is
`packages/apparatus-core/tests/test_library_index.py`. Add deterministic
release interleavings using metadata from an actual opened/unlinked private
file, rather than fabricated platform constants. Prove reacquisition and
bounded exhaustion for both absence and zero-link observations. Preserve
rejection and nonmutation for unsafe lock metadata, including a zero-link
file with a nonprivate mode and an unreadable endpoint.

Run `uv sync --all-packages`, the focused index tests, and `git diff --check`.
Record results and platform gaps in
`docs/plan/PR-37-library-lock-verification.md`. Full-suite and supported-platform
CI checks remain required before declaring the PR done. Update the PR-37 row
in `docs/plan/README.md` in this same PR, with dependency PR-34.
