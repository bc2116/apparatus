# PR-54: Run Windows safety groups in parallel

The serial Windows safety job took 41m49s in CI run 34184818702. Pytest accounted
for 41m19s: 1,082 passed, 87 skipped, one deselected. Five recovery scenarios
accounted for 18m31s. Reduce elapsed time without removing coverage.

Split the existing 54 selectors into four explicit Windows runner groups,
separating the slow learned-Skill, Skill recovery, workspace migration, and
Library scenarios. Keep the sole ETW deselection and dedicated bootstrap
jobs unchanged. Use independent runners and retain all failure results.

Keep the required check named `windows-safety` through an aggregate job that
always observes the matrix and accepts only success. Do not alter repository
branch protections, permissions, action versions, dependencies, release
signing, product code, or payload. Changed-file selection is a separate future
decision; this slice runs all existing tests on every current CI trigger.

Acceptance:

- Compare the selector multiset and ETW exclusion with the pre-split baseline.
- Verify aggregate behavior for success, failure, cancellation, skipping,
  missing and unknown results; preserve the existing scoped-filesystem proof.
- Run focused checks, `uv run pytest`, independent frontier review, and CI.
- Record actual elapsed time and total runner time in the PR before merge.
  A 10–15 minute routine-CI target remains an estimate until observed.
- Record validation in `docs/notes/pr-54-verification.md` and mark this plan row
  landed in the implementation PR. Keep any unmeasured performance limit clear.

CI changes retain frontier authorship and independent frontier review.
Bounded read-only extraction of timing facts may use a fast model; it does
not own policy, implementation, or review.
