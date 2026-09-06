# PR-34 verification

Task decisions are opaque file-backed controls, with per-invocation retention
across Memory, profile seeds, Library, receipts, snapshots and backup. Restore
preserves live controls in place. The source contract and historical limits are
in `docs/spec/task-retention.md`.

- Integrated macOS suite before and after rebasing onto merged PR-33:
  **668 passed, 38 skipped**.
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

Independent authoring-tier review accepted the complete implementation and the
Library repairs. Initial Windows CI passed 478 tests but rejected three recovery
fixtures: text-pipe CRLF conversion created a different Git filename. The fixture
now uses binary NUL framing and verifies the exact raw tree entry before testing
the unchanged production guard. Independent review accepted this platform proof
repair. Actual Windows CI must pass before merge; skips are not certification.
The pull request records remote CI and merge state.
