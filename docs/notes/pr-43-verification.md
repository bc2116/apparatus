# PR-43 verification

## Integrated validation

The rebase onto captured PR-41 head `1e79cb9` completed at **`735d4b2`**. Conflict
resolution preserves both learned-Skill ownership/pair validation and Library
registration capture, historical validation and restore. The canonical-root
Windows check repair remains installed. Plan rows remain ordered through PR-43,
with PR-43 depending on PR-41 and PR-42.

- `uv sync --all-packages` installed **pypdf 6.16.1**; the wheel also declares
  `pypdf>=6.16.1`.
- Focused integrated learned-Skill, R6, Library, check and recovery/backup tests:
  **299 passed** in **185.15 seconds**.
- Integrated full `uv run pytest -o addopts= -q`: **1,149 passed, 38 skipped** in
  **373.90 seconds**.
- Universal payload ZIP, wheel and source distribution builders passed.
- All **25 starter files** match canonical source, captured PR-41, embedded
  source, wheel and source distribution. All **23 payload files** also match the
  universal archive. All **seven built-in Skills** and learned-Skill fallback
  remain intact; learned-Skill and Library implementation modules match the wheel.
- `git diff --check` passed. No production edits were needed after resolving the
  rebase conflicts; no Library payload edits or R9 cards were introduced.

These are local macOS integration results. Actual Windows CI remains necessary.
Any later upstream note-only rebases should preserve these source bytes; changed
production code requires its own validation.

## Earlier validation checkpoint

The detailed evidence below was collected on the PR-43 working tree based on plan
commit `40e62c8`, before PR-40/41 source integration. Its smaller counts are retained
as historical evidence, separate from the integrated results above.

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
record restore and foreign backup-lookalike preservation. Upstream source
integration and post-integration validation are now recorded above. Actual Windows
CI remains a delivery gate.
These tests demonstrate local persistence, filesystem, SQLite and real-Git
behavior. They do not certify model answers, native AI-app invocation, semantic
search, cards, cloud/shared catalogs, project-source recovery or live sync.
