# PR-71 — Verify the retained core source build

## Outcome and authority

Complete C of [the bounded next-release plan](next-release-features.md), after
PR-70's completed comparison selected current Skills and omitted A2. Library
relinking remains deferred. This is the second and final planned slice; further
email testing remains deferred. The owner authorized autonomous execution.

Build from the reviewed PR-70 head `bfb18de` and verify core/payload source parity
with its eventual remote merge. PR-70 CI/merge may finish while these independent
acceptance checks run; do not merge this PR before PR-70 lands. If retained
product sources change, repeat affected acceptance against the changed candidate.

## Deliverables

- This prompt and completed plan/index status.
- `docs/certification/core-readiness-2026-10-12.md`.
- `docs/certification/evidence/core-readiness-2026-10-12/`: bounded repeatable
  acceptance runner, candidate identities, source-change inventory, commands,
  captured results, retention inventories, review and integrity manifest.

## Required evidence

1. Inventory retained core changes since PR-62's `6d05582` baseline. Preserve
   old evidence under its own identity. Build only core and the payload from
   the final retained source; optional module publication is outside this cycle.
2. Verify the built wheel's dependency floor `pypdf>=6.19.0`, resolved installed
   dependencies, imported package location outside the checkout, and exact
   embedded payload/profile fidelity. Build the payload twice and compare bytes.
3. Use a fresh external installed environment for init, repeat init, exact shim
   repair, command aliases, task/resume/check and synthetic Library Markdown/PDF
   extraction, including content-free extraction failure. No live connectors.
4. Exercise no-save command refusal and a requested project deliverable against
   a post-setup/task baseline. Compare bytes, size, mode, file modification time,
   additions and removals across work-area and recovery/control state. There is
   no blanket metadata exemption. Distinguish deterministic command checks from
   native assistant behavior; PR-70's native result retains its exact source scope.
5. Recheck the retained backup boundary with synthetic canonical and ordinary
   system-alias destinations and rejected final-link/inside-work-area aliases.
   Preserve protected inputs and verify archive exclusions and rejected outputs.
6. Record exact limits: source-built core/payload acceptance only; no new public
   version, signed/native installer, automatic discovery, live email or module
   qualification. Public artifacts remain unchanged.
7. Run `uv run pytest`, verify relative links, evidence integrity and privacy,
   obtain independent review and current-head CI, then verify remote merge.

## Scope and stopping

Documentation/evidence only unless a narrow acceptance defect is reproduced and
can be repaired within this PR under the plan. A larger blocker stops this slice
for an explicit scope revision; do not add an unplanned fifth PR. No release
publication, signing, native installer execution or additional email campaign.
Set the plan row to `✅ landed` in the proposed completed PR. Completion depends
on passing evidence and delivery gates, not merely producing this prompt.
