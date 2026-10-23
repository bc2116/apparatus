# PR-74 — Verify the signed release rehearsal

Depends on PR-73's qualified merged candidate. Execute S4 of
[the release sprint](long-sprint-2026-10-23.md), governed by ADR-0005 and
[the release runbook](../release-runbook.md).

## Deliverables and acceptance

- Before dispatch, confirm source SHA equals the immutable candidate and main
  still names that commit. Recheck protected signing rules and non-secret mode
  switches. Manually dispatch the existing Release workflow as a dry-run;
  never create/reuse/move a release tag for rehearsal.
- Add `docs/certification/release-rehearsal-0.0.3.md` and its matching evidence
  directory (use the actual selected version). Record workflow/source identity,
  seven distributables, notes/checksums, tool identities and actual Windows
  signature plus macOS signing/notarization results. Verify every checksum.
- Confirm no PyPI version or GitHub Release was created. A bootstrap resolving
  the old published package does not qualify installation of the new candidate.
- Preserve failures. Stop for protected approval/setup when needed, retaining
  the exact run and pending gate; never approve a gate solely to consume time.
- Review the evidence independently against PR-73, ADRs and the full diff;
  run required `uv run pytest`, doc checks/current-head CI, mark the row landed,
  merge remotely and verify. This documentation commit is not the release tag
  target. Product-input changes require a new candidate and repeated checks.

## Scope

No publication or account-configuration changes. Rehearsal execution follows
the owner's sprint authorization and native protected approvals. Present the
exact qualified candidate, signatures and remaining gaps for final release
approval. If blocked, retain an unpublished handoff rather than claim delivery.
