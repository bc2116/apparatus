# PR-73 — Freeze and qualify the next core candidate

Depends on PR-72. Execute S3 of [the release sprint](long-sprint-2026-10-23.md);
S2 and C1 were omitted during scope selection. Read ADR-0005/0006/0007, the
[inventory](../releases/next-release-inventory.md), and the release runbook.

## Deliverables and acceptance

1. Recheck GitHub tags/releases and PyPI; choose unused 0.0.3 unless a collision
   requires a new documented candidate. Update core `pyproject.toml`, runtime
   version, applicable lock entry and changelog consistently. Preserve the
   monorepo and optional-module versions. Payload generation reads core metadata.
2. Add `docs/certification/release-candidate-0.0.3.md` and a corresponding
   `docs/certification/evidence/release-candidate-0.0.3/` capsule. If the version
   changes, use that version in both paths. Record source/build-input hashes,
   exact commands, results, limitations and a checkable integrity manifest.
3. Build wheel, sdist and payload from the retained source. Verify all embedded
   resources against canon, distribution version/dependency identity and clean
   external installation. Reuse the prior core-readiness probe as a method,
   preserving its original evidence. Test aliases, init/rerun/repair, adoption
   with custom instructions/projects, Memory capture/recall, bound-project
   resume, citations/staleness, no-save and managed recovery boundaries.
4. Refresh focused first-task/continuation observations on actual available
   Codex CLI, Claude Code CLI and Cursor IDE surfaces. Record versions/settings,
   source identity and exact limits. Desktop and CLI are separate. Unavailable
   surfaces remain explicit gaps; a failing advertised path requires repair or
   narrower claims. No agent result may impersonate another app.
5. Run `uv run pytest`, affected build/doc checks, independent review with this
   prompt and ADRs, and current-head CI including Windows lanes. The status row
   is landed in the completed PR. Verify remote merge and nominate its exact
   commit as immutable candidate, checking merged-source parity.

## Boundaries and recovery

No feature additions, email campaigns, module publication, signing or public
release. No fixture weakening. One reproduced release blocker may use the
sprint's repair allowance; preserve failed evidence. A capacity stop leaves a
truthful checkpoint, not a qualified candidate. Version-only source changes
still require new artifact identity and acceptance. Do not merge rehearsal
receipts before dispatching the candidate from main.
