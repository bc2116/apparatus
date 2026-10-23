# PR-75 — Deliver and record the qualified core release

Depends on PR-74 and explicit final approval of its exact candidate. Execute S5
of [the release sprint](long-sprint-2026-10-23.md) and
[the release runbook](../release-runbook.md); ADR-0005/0006/0007 govern scope.

## Operational sequence

1. Refresh version/tag collision checks, reviewer gates and candidate identity.
   Set publish mode only under final approval. Tag the immutable PR-73 candidate,
   never a later documentation commit. Push the new matching version tag.
2. After protected PyPI publication succeeds, dispatch acceptance-only against
   that same tagged run. Verify Windows x64 and macOS install/repair receipts,
   hashes, installed version, repaired shipped file and preserved project files.
3. Withhold GitHub Release approval on failed native acceptance. PyPI is already
   public at this stage; its version cannot be reused or represented as undone.
4. Approve the final release gate only after native success. Verify public
   attachments, checksums and notes. Return publish mode to unset, including on
   failure/interruption when safe; otherwise hand off that exact obligation.

## Delivery record and acceptance

Add `docs/certification/release-delivery-0.0.3.md` and minimal corresponding
evidence (actual selected version controls paths). Update README and the dated
support matrix only to match the verified source, signatures, native results
and public delivery. Keep installer presentation, signed wrappers, installed
runtime and AI-app behavior as separate claims. Optional modules stay excluded.

Independent review receives the prompt, ADRs, evidence and full diff. Run
`uv run pytest`, doc checks and current-head CI; set the row landed in the
completed PR, merge remotely and verify. Clean up the branch/worktree only
after delivery is verified. If final authorization or setup is unavailable,
record a precise ready-but-unpublished handoff; do not label S5 completed.
