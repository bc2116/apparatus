# PR-36 verification

Synthetic fixtures cover fresh work areas and explicit existing-folder adoption.
No real user work area is enrolled by this development work.

- Fresh and empty-folder init enroll one work area with a stable UUID, one Library,
  shared Memory and no mandatory Projects, Deliverables or root Decisions folder.
  Existing repositories, unrelated files and valid omitted-selector profile bytes
  survive adoption and repair. First snapshots use the isolated backend.
- Relative project bindings and exact instruction pointers publish together;
  custom UTF-8 instructions and line endings survive. Missing pointers repair;
  invalid controls, edited blocks and Git/app metadata destinations fail before
  publication. Late failures compensate owned files and preserve competing edits.
- Special command handlers reuse the CLI's selected context. Rebinding between
  selection and execution cannot call another area's engine; a selected project
  cannot become an init destination merely by losing its link. Direct check/render
  engines require the selected work area and do not follow project bindings.
- New and legacy decision roots remain distinct and use existing correction,
  outdated, forgetting and current-only recall controls. No-save suppresses new
  content while allowing maintenance. A missing profile does not permit explicit
  setup selectors to bypass the same task guard.
- Work-area instruction migration recognizes complete known bytes, preserves
  custom canon, and rejects foreign pointers. Rendering retains canon, enrollment
  and destination proofs through deployment, including same-byte root/marker
  substitutions. Compatible read proofs coexist with native readers on Windows;
  explicit replacement still has its normal rollback ownership.

Independent implementation review accepted the complete change after one grouped
repair covering the four reproduced issues above. The stable local full suite,
after integrating the current recovery repair and merged Library lock fix, passed
**838 tests with 38 skipped**. Focused check/render coverage passed all 68
tests after moving project selection entirely to command handlers. The 32 project
binding tests include real dispatch into special handlers after a late rebind.

The recovery dependency's final merge and actual Windows CI remain required
before merge. PR-35's platform repair and the separately reproduced Library lock
release race are tracked in their own focused changes; this suite includes both.
Packaging checks do not establish native AI app discovery, app certification,
signing readiness, project-file recovery or live sync support.
