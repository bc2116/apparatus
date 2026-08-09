# Development Plan

All work is pre-cut into focused PRs. Each planned PR has a self-contained
prompt file in this directory that any contributor — human or AI agent — can
execute in a cold session with nothing but this repository checked out.

## How to execute a PR

1. Read `AGENTS.md` (session rules), `docs/design/design-brief.md`, and the
   ADRs in `docs/adr/`.
2. Open this table, pick the lowest-numbered PR whose status is **ready** and
   whose dependencies have landed.
3. Read its prompt file completely. Branch `pr-XX-short-slug`.
4. Implement exactly that scope. Keep `uv run pytest` green; update conformance
   fixtures only as the prompt directs.
5. Update this table's status column in the same PR.

Governing rules: one PR per branch; fixtures are the executable spec and are
never loosened to pass; dogfooding starts the moment PR-07 lands; DCO sign-off
on every commit.

## Phases

- **Phase 0 — birth:** repository skeleton, decisions, this plan. *(landed at bootstrap)*
- **Phase 1 — protocol on files:** the workspace works as pure files in ≥ 2 AI apps, before any CLI exists.
- **Phase 2 — CLI v1:** `apparatus` verbs in dependency order; deterministic checks and snapshots.
- **Phase 3 — Library:** ingest, local index, grounded recall with citations.
- **Phase 4 — onboarding and egress:** interview → profile deployment; the egress gate; welcome end-to-end.
- **Phase 5 — packaging:** payload builder, release pipeline, bootstrapper, signing, IT one-pager.
- **Phase 6 — certification:** the same payload certified across AI apps; quickstarts; support matrix.

## Status

| PR | Title | Phase | Status | Depends on |
|---|---|---|---|---|
| 01 | Repository skeleton | 0 | ✅ landed (bootstrap) | — |
| 02 | Founding ADRs, design brief, development plan | 0 | ✅ landed (bootstrap) | — |
| 03 | Workspace spec, universal starter payload, first conformance fixture | 1 | ✅ landed (bootstrap) | 01 |
| 04 | [Record schemas v1](PR-04-record-schemas.md) | 1 | ready | 03 |
| 05 | [Starter procedures](PR-05-starter-procedures.md) | 1 | ready | 04 |
| 06 | [Policy overlays and egress-gate spec](PR-06-policy-overlays-egress-spec.md) | 1 | ready | 04 |
| 07 | [Instruction canon, shims, first dogfood](PR-07-shims-first-dogfood.md) | 1 | ready | 05, 06 |
| 08 | [CLI skeleton and doctor](PR-08-cli-skeleton-doctor.md) | 2 | ready | 07 |
| 09 | [check — validators](PR-09-check.md) | 2 | ready | 08 |
| 10 | [snapshot and restore](PR-10-snapshot-restore.md) | 2 | ready | 08 |
| 11 | [init and profile overlay engine](PR-11-init-profiles.md) | 2 | ready | 09, 10 |
| 12 | [Memory verbs, PII labeler, credential floor](PR-12-memory-labeler.md) | 2 | ready | 09 |
| 13 | [render — canon to shims](PR-13-render.md) | 2 | ready | 09 |
| 14 | [Library ingest and text extraction](PR-14-library-ingest.md) | 3 | ready | 09 |
| 15 | [Library local search index](PR-15-library-index.md) | 3 | ready | 14 |
| 16 | [recall with citations](PR-16-recall.md) | 3 | ready | 15 |
| 17 | [Interview wired to profile deployment](PR-17-interview-profiles.md) | 4 | ready | 11, 12 |
| 18 | [Egress gate v1](PR-18-egress-gate.md) | 4 | ready | 12 |
| 19 | [Welcome flow end-to-end](PR-19-welcome-e2e.md) | 4 | ready | 17, 18, 16 |
| 20 | [Universal payload builder](PR-20-payload-builder.md) | 5 | ready | 13, 19 |
| 21 | [Release pipeline](PR-21-release-pipeline.md) | 5 | ready | 20 |
| 22 | [Bootstrapper v1](PR-22-bootstrapper.md) | 5 | ready | 21 |
| 23 | [Code-signing and IT one-pager](PR-23-signing-it-onepager.md) | 5 | ready | 22 |
| 24 | [App certification and quickstarts](PR-24-certification.md) | 6 | ready | 22 |
| 25 | [Snapshot export (backup) v1](PR-25-snapshot-export.md) | 4 | ready | 10 |
| 26 | [Installer wrapper and signed artifacts](PR-26-installer-wrapper.md) | 5 | ready | 22, 23 |

Statuses: `ready` (prompt complete, dependencies may still be pending),
`in progress — <branch>`, `✅ landed`, `blocked — <reason>`.

## Post-alpha (deliberately not in this plan)

Two commitments from the design brief and ADRs are real but sequenced after
alpha. They are listed here so no promise is silently unowned:

- **Pack delivery** — the `apparatus add <pack>` verb and the installer's
  capability catalog on re-run (ADR-0005 §5; design brief §9). Waiting on the
  first real pack; the plugin registry (PR-08) is the enabling substrate, so
  this is additive when it starts.
- **Developer adopt-into-existing-repo entry path** — the secondary-audience
  entry from design brief §2: the same protocol delivered with developer
  vocabulary into a repository the developer already has. Nothing in core may
  exist only for developers; this path is docs and tooling on top of the
  certified core.
