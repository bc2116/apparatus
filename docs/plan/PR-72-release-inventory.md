# PR-72 — Define the next core release

## Outcome and authority

Execute S1 of [the release sprint](long-sprint-2026-10-23.md). The owner selected
execution on 2026-10-23, including the repository's branch, PR, CI and merge
workflow. Final public delivery remains subject to approval of the qualified
candidate. This slice changes documentation only.

## Deliverables

- `docs/releases/next-release-inventory.md`: public baseline, classified source
  delta, current non-secret operator observations, scope and release checklist.
- `CHANGELOG.md`: grounded Unreleased notes; preserve historical release notes.
- This prompt, the retained sprint proposal, updated plan index, and focused
  prompts PR-73 through PR-75 for candidate, rehearsal and delivery.

## Acceptance

1. Compare `v0.0.2` with `1e8df7debc0aeb25062ad74fa13b54efe5591568`.
   Separate core, payload, dependencies, release tooling, optional-module and
   evidence-only changes. Map proposed claims to implementation and tests.
2. Check GitHub releases/tags and PyPI; record their identity. Treat 0.0.3 as
   available at observation time, never reserved. Recheck before versioning.
3. Inspect protected-environment rules and only non-secret release switches.
   Record unverified publisher/provider readiness explicitly. Do not read
   credentials, change configuration, dispatch workflows or publish artifacts.
4. Record admission decisions: omit S2 and C1 under the sprint's capacity rule;
   retain mandatory core acceptance. Do not imply the omitted example failed
   evaluation. This is S1 scope selection, not a completed experiment.
5. Check relative links, whitespace and diff scope; run `uv run pytest`; obtain
   independent review with this prompt, ADR-0005/0006/0007 and complete diff.
6. Set this row to landed in the completed PR, require current-head CI, merge
   remotely, and verify the remote commit before cleanup.

## Non-goals and recovery

No product changes, version bump, new module, email campaign, signing or
publication. Preserve original planning WIP until its contents are safely
retained. A failed check leaves this branch available for repair; no user
workspace or public distribution changes are needed.
