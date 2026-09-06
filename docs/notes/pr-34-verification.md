# PR-34 verification

Task decisions are opaque file-backed controls, with per-invocation retention
across Memory, profile seeds, Library, receipts, snapshots and backup. Restore
preserves live controls in place. The source contract and historical limits are
in `docs/spec/task-retention.md`.

- Initial integrated macOS suite: **668 passed, 38 skipped**.
- Targeted task/Memory/profile, Library, receipt, snapshot/backup and migration
  tests exercise missing/unsafe IDs, resumed and concurrent tasks, suppression
  before input, scope isolation, metadata binding, cache read-only behavior,
  explicit operation exceptions, failure cleanup and live-control preservation.
- Canonical and embedded payload, rendered pointers and golden pointer bytes
  updated deliberately. Payload builder and distribution conformance passed.
- Library review repaired valid terminal extraction status handling and a
  disappeared extraction directory that could otherwise report false no-match.
- Authoring-tier lead and bounded authoring-tier implementation/review roles;
  no recursive delegation or model calls in the product. Retention and recovery
  remain in the policy/migration class rather than tiered-down implementation.

Final independent review and actual Windows CI must pass before merge. Platform
skips are not certification. The pull request records remote CI and merge state.
