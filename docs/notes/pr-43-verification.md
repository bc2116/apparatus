# PR-43 verification

These results cover the PR-43 working tree based on plan commit `40e62c8`, before
integration of intervening PR-40/41 work. They do not establish the final rebased
PR's behavior or actual Windows results.

## Source selection and retrieval

Synthetic acceptance tests exercise project-original registration, selected-only
extraction, exact work-area-relative citations, and an unselected sibling content
read guard. They cover same-size/same-mtime changes, partial coverage with healthy
hits and without hits, missing/moved/ignored/unavailable originals, immediate
no-save exclusion after removal, explicit single-source no-save extraction,
Memory suppression, feature-off guards, terminal extraction outcomes versus
corrupt cache, cold caches, and whole-work-area moves. Original files remain in
place. Registration-only real-Git snapshot/export/restore tests preserve later
registrations and exclude project originals and extraction caches.

An independent implementation review identified two defects: changed valid
registration records collided with restore-owned temporary backups, and direct
index refresh/rebuild still enumerated only legacy Library cache paths. The
repairs retain exact transaction-owned temporary identities/bytes during catalog
validation and use the unified retained source-evidence map for direct writers.
Foreign catalog entries remain errors; no filename-prefix exemption is used.

Direct writer regressions failed before the repair. They now cover registered
rows, stale/removed/ignored exclusions, the no-save guard and scoped explicit
exception, empty-cache compatibility, and source proof validation after actual
database publication. The lock-interleaving regression preserves its witnessed
competing edit (or actual native denial), rejects stale acceptance, and verifies
the current second writer and lock/temporary cleanup. The quarantine failure
injector remains at the actual quarantine boundary, preserving corrupt bytes and
file/handle cleanup assertions without replacing filesystem capability checks.

Focused index/source/retention/boundary validation passed **85 tests** in 16.15
seconds. The initial cross-component reference acceptance file passed **16 tests**
in 11.61 seconds; those cases also participate in the full suite.

## Packaging and remaining gates

- The universal payload ZIP builder passed.
- `uv build --package apparatus-core` produced a wheel and source distribution.
- All **23** canonical/embedded starter files match byte-for-byte and match the
  wheel and source distribution; the **21** payload files also match the universal
  archive. The wheel's source helper, ingest/index and Library command modules
  match current source bytes.
- `git diff --check` passed.
- Full `uv run pytest -o addopts= -q`: **1,052 passed, 38 skipped** in
  **317.91 seconds**, against the frozen source tree.

The new source, acceptance, boundary and direct-index suites are included in the
Windows CI lane. Independent review accepted the production repairs. Its final
fixture correction uses the retained transaction target as the Windows-safe
publication witness; both changed-registration rollback cases passed afterward.
The complete boundary selection passed 12 tests, including the changed valid
record restore and foreign backup-lookalike preservation. Actual Windows CI,
upstream PR integration, and post-integration validation remain delivery gates.
These tests demonstrate local persistence, filesystem, SQLite and real-Git
behavior. They do not certify model answers, native AI-app invocation, semantic
search, cards, cloud/shared catalogs, project-source recovery or live sync.
