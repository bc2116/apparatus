# PR-61 — Accept safe external aliases for backup destinations

## Problem and evidence

A backup destination may be spelled through a normal operating-system external
ancestor alias. The backup command must treat that spelling as the same safe
directory as its canonical spelling, without weakening the final-directory or
transactional identity protections.

This was reproduced from the current source checkout and from the built
`apparatus-core` 0.0.2 wheel. Each comparison used fresh, identically
initialized managed work-areas and the same default profile:

| Build identity | Source work-area | Destination spelling | Result |
| --- | --- | --- | --- |
| current source | canonical macOS path under `/private/tmp` | canonical path under `/private/tmp` | exit 0; one backup archive is published |
| current source | canonical macOS path under `/private/tmp` | macOS system alias `/tmp/...` to an external destination | exit 1: `Managed backup export could not be completed safely.`; no archive is published |
| built core 0.0.2 wheel | canonical macOS path under `/private/tmp` | canonical path under `/private/tmp` | exit 0; one backup archive is published |
| built core 0.0.2 wheel | canonical macOS path under `/private/tmp` | macOS system alias `/tmp/...` to an external destination | exit 1: `Managed backup export could not be completed safely.`; no archive is published |

The source trace enters `managed_state_backup.export_backup`, then constructs
`WorkspaceAnchor(destination_path)`. `backup._absolute()` retains the literal
`/tmp` spelling, so the POSIX anchor walks `/tmp` with `O_NOFOLLOW` and gets
`NotADirectoryError` because `/tmp` is a symlink to `/private/tmp`. The same
failure occurs in the installed wheel. This differs from the existing
external-ancestor normalization used for workspace preflight.

A deliberate **final destination-directory symlink** already exits 2 with
`destination path does not exist or is not a safe directory`. That is correct
fail-closed behavior and must remain so. The defect is an external-ancestor
alias only; it is not permission to follow a destination leaf link.

## Scope

Repair safe external-ancestor canonicalization for the **backup destination**
boundary on POSIX only. Preserve existing Windows destination handling unchanged;
this slice does not add ancestor junction/reparse support or claim that coverage.
A canonical source work-area plus an external-alias destination
must produce the same backup result as canonical spellings of both paths.

Use the established workspace-preflight approach: resolve only an existing
external ancestor, retain the final destination component lexically, and let
the no-follow/identity anchors select and verify that final object. Do not use
whole-path `Path.resolve()` or broadly change `backup._absolute()`. Do not
relax a destination leaf link, a linked `System`, source workspace boundaries,
inside-workspace rejection, ownership/collision rules, or pre/post-publication
identity checks. The result archive path, CLI destination output, and backup
receipt destination must all use the frozen canonical retained destination,
never an alias spelling that could later identify another directory.

This is the dedicated spare repair after PR-60. Do not combine it with resume,
source routing, backup format/scope, installer, payload, fixture, or broad
symlink-policy work. Source-alias behavior is outside this repair except that
existing behavior and safety checks must not regress.

## Likely ownership

- `packages/apparatus-core/src/apparatus_core/backup.py` — a narrowly named
  backup-destination preflight/canonicalization boundary built from the
  established external-ancestor primitive; legacy export uses it directly and
  managed export can share it.
- `packages/apparatus-core/src/apparatus_core/managed_state_backup.py` — only
  if needed to call the shared destination boundary before it creates anchored
  destination handles.
- `packages/apparatus-core/tests/test_backup.py` and
  `packages/apparatus-core/tests/test_managed_state_backup.py` — focused
  regression and negative-path tests in the existing Windows-safety-selected
  modules.
- `docs/plan/PR-61-backup-path-aliases.md` and `docs/plan/README.md` — prompt,
  status, and concise verification record.

Do not create a new test module. Both named test modules are already listed by
`.github/workflows/ci.yml` and the exact manifest in
`packages/apparatus-core/tests/test_ci_workflow.py`; therefore this focused
change needs no CI-selector edit. If implementation nevertheless requires a
new test file, add it to the Windows safety matrix **and** update
`BASELINE_SELECTORS` in `test_ci_workflow.py` in the same PR.

## Acceptance

1. In POSIX coverage, construct an external directory-ancestor alias to a real
   parent. With a canonical managed work-area and matched fresh destinations,
   direct managed export through the alias destination succeeds and has the
   same archive/result contract as canonical destination export. The test must
   prove a normal external ancestor alias, rather than replacing the final
   destination leaf.
2. Cover the CLI dispatch with a canonical managed work-area and aliased
   external destination. It exits 0 and publishes one archive; project files
   and Library originals retain existing managed-backup exclusions. A
   deterministic native product scenario is sufficient; do not use an AI CLI.
3. Cover the legacy export boundary as applicable: an external-alias
   destination succeeds for the existing valid legacy fixture, without
   changing source-path routing. Keep the tests in existing backup modules.
4. A final destination-directory link still fails closed and does not publish
   an archive. Preserve existing destination-inside-workspace, destination
   replacement/race, no-follow, and owned-archive collision tests unchanged.
5. Exercise the new alias branch itself: an external ancestor alias resolving
   to a destination inside the work area must exit 2 and publish no archive.
   Retarget an ancestor alias after destination preflight; publication must
   remain in the originally canonicalized and retained destination or fail
   cleanly, never write into the replacement target. Preserve unrelated files
   and exact owned-publication cleanup. Existing direct-path race tests remain.
6. Assert canonical retained spelling in `BackupResult.archive`, CLI destination
   output, and receipt destination. Add a platform guard test proving Windows
   continues through its unchanged destination path handling; do not describe
   POSIX symlink tests or test-module selection as Windows junction evidence.
7. The regression checks both a canonical spelling and its alias against fresh
   fixtures with the same profile. It does not infer success merely because an
   alias resolves on the host; archive publication and expected state are
   asserted.
8. Run the focused backup tests, `uv run pytest`, and the existing CI-workflow
   manifest test. Record the actual commands and outcomes in the PR
   verification note. Run a deterministic native CLI scenario from the built
   artifact or installed core using a canonical source plus ordinary system
   alias destination; record archive count and exit status without committing
   machine-specific paths. Set the PR-61 plan row to `✅ landed` only after
   those checks pass.

## Implementation notes

`payload._workspace_root_preflight()` documents the required safety shape:
canonicalize only the nearest existing ancestor, preserve the final boundary,
and rely on retained no-follow operations for the selected object. Reuse that
behavior through an appropriate shared boundary rather than duplicating a
whole-path resolution rule. Keep errors actionable but do not expose raw OS
paths or diagnostics in normal command output.

## Out of scope

- Reworking backup source/workspace aliases or command routing.
- Following final destination links, recursive link policy changes, or
  weakening the current anchor/race proofs.
- Changing backup contents, recovery semantics, receipts, payloads, installer
  behavior, or the PR-60 resume work.

## Verification record

- Focused existing backup modules: 89 passed, 11 platform skips on macOS.
- Exact Windows CI selector manifest: 8 passed. A native Windows guard verifies
  unchanged destination handling; POSIX alias checks are not junction evidence.
- Built core wheel SHA-256:
  `6284f08fd3fccb63e6fa98cfa236f8b7e219c0aeb796fe861bdabd1f7749ab5c`.
- Installed-wheel macOS check: matched fresh canonical and ordinary `/tmp`
  ancestor-alias destinations each exited 0 and published exactly one archive.
  CLI and receipt destinations identified the retained canonical path; project
  files and Library originals were excluded, and all sentinel files survived.
- The same installed-wheel check rejected a final destination link and an alias
  resolving inside the work area: exit 2, no archive, sentinels unchanged.
- The first local verification helper used a substring check that matched
  `/tmp` inside `/private/tmp`. It stopped on a correct canonical receipt.
  The corrected helper compared the exact destination field in fresh fixtures;
  no product change or product-command retry was needed for that correction.
- Full local suite: `uv run pytest` — 1469 passed, 42 skipped in 557.00 seconds.
- Independent Sol review passed with no actionable finding. It also confirmed
  a symlink-loop destination returns the bounded usage error. Current-head CI
  must pass before merge.
