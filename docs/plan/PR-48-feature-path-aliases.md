# PR-48 — Read feature settings through external path aliases

Depends on PR-46. A live first-task run saved its project deliverable but failed
the snapshot feature check through macOS's ordinary `/var` alias. The identical
profile succeeded through the canonical `/private/var` ancestor. A read-only
reproduction outside the AI app establishes a core path-handling defect, not
an invalid profile or missing native permission. PR-47 must use a baseline
containing this repair before completing certification.

## Scope

Repair the shared feature-profile read boundary with the existing workspace
preflight primitive. Canonicalize only external ancestors before retaining the
workspace and profile; keep the workspace leaf, `System`, and profile protected
by current no-follow, identity, content and post-parse checks. Do not replace
these proofs with unrestricted `Path.resolve()` or normalize away an unsafe
workspace leaf. Preserve missing-profile compatibility and closed validation.

Primary ownership is `features.py`, focused regression tests, this prompt, the
plan row and a short verification note. Change other production code only if a
reproduced consequence requires it and record why. No payload/Skill changes,
new adapter, privacy-policy changes or installer changes belong in this repair.

## Acceptance

1. An external ancestor alias and its canonical path give identical feature
   settings. CLI snapshot feature dispatch and direct feature consumers both
   work through the alias; coverage is not limited to the CLI argument parser.
2. A workspace-leaf link, linked `System` or linked profile still fails closed.
   Existing pathname replacement and same-byte identity checks remain enforced.
3. Real enabled and disabled selections are respected; absent pre-profile state
   retains its existing compatibility behavior. Preflight errors become the
   established actionable feature error rather than an uncaught traceback.
4. Exercise a real managed snapshot in a synthetic alias fixture and preserve
   project originals and its Git repository. Keep the earlier failed app run
   as diagnostic evidence; do not relabel it as a passing certification case.
5. Focused boundary tests and full `uv run pytest` pass. Include any new test
   file in Windows coverage when needed. Alias support and platform skips are
   reported precisely; do not weaken race tests or create a new broad test suite.

Use frontier/high for this filesystem-boundary repair and independent review.
Keep the author/reviewer loop bounded; distinguish contract or platform failures
from model capability. Deliver a focused DCO-signed PR with native CI evidence.
