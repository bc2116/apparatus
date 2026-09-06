# PR-35 verification

The new shared-work-area recovery backend is explicitly selected by a validated
layout marker. The starter does not deploy that marker until the adoption slice.
Legacy recovery remains compatible; managed recovery never uses work-area or
project Git repositories. See `docs/spec/managed-recovery.md` for exact coverage.

Acceptance coverage uses real Git and synthetic data:

- Public snapshot, restore and backup commands preserve the HEAD, index, config,
  staged, unstaged and untracked bytes of a dirty root and two dirty projects.
- Captures/manifests enumerate declared state only. Project and Library sentinels,
  unknown store files and unreachable history never enter a managed backup.
  An extracted backup supports listing and restoring its managed history.
- No-save automatic capture stops before Git/store changes. Requested snapshots
  and exports remain scoped exceptions; restore preserves current task controls.
- Exact source, routing, reference, receipt and destination proofs survive late
  failure checks. Restore and export compensate only their own changes and keep
  concurrent work. Unchanged saves create neither a snapshot nor a receipt.
- CLI checks reject damaged enrollment before capability bookkeeping, report
  invalid history without a traceback, and describe the actual recovery scope.
- Canonical/embedded payload content is unchanged; payload building succeeds.

Final macOS suite: **754 passed, 38 skipped**. Focused recovery, backup and
public-command coverage: **60 passed**. Payload build and diff checks passed.
Independent authoring-tier review accepted the complete implementation after one
classified repair: partial initialization now compensates owned creations so a
normal retry succeeds; concurrent additions are preserved. No recursive delegation
or model calls were added to the product.

The first actual Windows run found incompatible retained-file sharing modes in
the new backend. Immutable reads now use the existing publication-compatible
mode; mutable references and actual restore replacements keep their compare-and-swap
proofs. CLI restore releases preliminary destination pins before its pre-restore
snapshot, then acquires a new complete plan for the actual restore. Regressions
exercise native Git reads, retained receipt reads and the complete saving-task
restore path. The source-race fixture asserts the observed replacement outcome:
unchanged successful export when Windows blocks the competitor, or compensation
and preserved concurrent bytes when the competitor actually succeeds. Independent
review accepted this platform repair without lowering any filesystem checks.

The second Windows run reached 551 passing tests and 11 failures. Extra planning
handles on replaced references and restore destinations obstructed Windows backup
cleanup/rollback. Those validated planning handles now close immediately before
the existing CAS operation reacquires and checks the same identity and bytes;
transaction-owned proofs retain actual replacement and compensation. Unchanged
file proofs remain live. Four handoff/competing-inode regressions and independent
review cover this narrow repair; the filesystem backend and inventory allowlist
are unchanged.

Actual Windows CI is required before merge. The pull request records platform
results and the exact merged head; unit/platform checks are not AI app certification.
