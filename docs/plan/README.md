# Development Plan

All work is pre-cut into focused PRs. Each planned PR has a self-contained
prompt file in this directory that any contributor — human or AI agent — can
execute in a cold session with nothing but this repository checked out.

## How to execute a PR

1. Read `AGENTS.md` (session rules), `docs/design/design-brief.md`, and the
   ADRs in `docs/adr/`.
2. Open this table, pick the lowest-numbered PR whose status is **ready** and
   whose dependencies have landed.
3. Read its prompt file completely. Branch `pr-XX-short-slug` (a dedicated
   git worktree is the recommended shape for parallel work).
4. Implement exactly that scope. Keep `uv run pytest` green; update conformance
   fixtures only as the prompt directs.
5. In the same PR, set this table's row for your PR to `✅ landed`. The change
   reaches `main` only when the PR merges, so the table stays correct on
   `main` at all times — a row must never read `in progress` after its PR has
   merged.
6. Ship it: push the branch, open a GitHub PR, wait for CI, and merge — never
   merge locally into `main`. After verifying the merge commit on remote
   `main`, delete the branch and remove the worktree it lived in.

Governing rules: one PR per branch; fixtures are the executable spec and are
never loosened to pass; dogfooding starts the moment PR-07 lands; DCO sign-off
on every commit.

## Phases

- **Phase 0 — birth:** repository skeleton, decisions, this plan. *(landed at bootstrap)*
- **Phase 1 — protocol on files:** the workspace works as pure files in ≥ 2 AI
  apps, before any CLI exists. PR-07 exercised this files-only exit in two AI
  apps; this records evidence for the gate, not that every Phase 1 PR has
  landed.
- **Phase 2 — CLI v1:** `apparatus` verbs in dependency order; deterministic checks and snapshots.
- **Phase 3 — Library:** ingest, local index, grounded recall with citations.
- **Phase 4 — onboarding and egress:** interview → profile deployment; the egress gate; welcome end-to-end; ignore rules; first-run feature selection.
- **Phase 5 — packaging:** payload builder, release pipeline, bootstrapper, signing, IT one-pager.
- **Phase 6 — certification:** the same payload certified across AI apps; quickstarts; support matrix.

## Status

| PR | Title | Phase | Status | Depends on |
|---|---|---|---|---|
| 01 | Repository skeleton | 0 | ✅ landed (bootstrap) | — |
| 02 | Founding ADRs, design brief, development plan | 0 | ✅ landed (bootstrap) | — |
| 03 | Workspace spec, universal starter payload, first conformance fixture | 1 | ✅ landed (bootstrap) | 01 |
| 04 | [Record schemas v1](PR-04-record-schemas.md) | 1 | ✅ landed | 03 |
| 05 | [Starter procedures](PR-05-starter-procedures.md) | 1 | ✅ landed | 04 |
| 06 | [Policy overlays and egress-gate spec](PR-06-policy-overlays-egress-spec.md) | 1 | ✅ landed | 04 |
| 07 | [Instruction canon, shims, first dogfood](PR-07-shims-first-dogfood.md) | 1 | ✅ landed | 05, 06 |
| 08 | [CLI skeleton and doctor](PR-08-cli-skeleton-doctor.md) | 2 | ✅ landed | 07 |
| 09 | [check — validators](PR-09-check.md) | 2 | ✅ landed | 08 |
| 10 | [snapshot and restore](PR-10-snapshot-restore.md) | 2 | ✅ landed | 08 |
| 11 | [init and profile overlay engine](PR-11-init-profiles.md) | 2 | ✅ landed | 09, 10 |
| 12 | [Memory verbs, PII labeler, credential floor](PR-12-memory-labeler.md) | 2 | ✅ landed | 09 |
| 13 | [render — canon to shims](PR-13-render.md) | 2 | ✅ landed | 09 |
| 14 | [Library ingest and text extraction](PR-14-library-ingest.md) | 3 | ✅ landed | 09 |
| 15 | [Library local search index](PR-15-library-index.md) | 3 | ✅ landed | 14 |
| 16 | [recall with citations](PR-16-recall.md) | 3 | ready | 15 |
| 17 | [Interview wired to profile deployment](PR-17-interview-profiles.md) | 4 | ready | 11, 12, 27 |
| 18 | [Egress gate v1](PR-18-egress-gate.md) | 4 | ready | 12 |
| 19 | [Welcome flow end-to-end](PR-19-welcome-e2e.md) | 4 | ready | 17, 18, 16 |
| 20 | [Universal payload builder](PR-20-payload-builder.md) | 5 | ready | 13, 19 |
| 21 | [Release pipeline](PR-21-release-pipeline.md) | 5 | ready | 20 |
| 22 | [Bootstrapper v1](PR-22-bootstrapper.md) | 5 | ready | 21 |
| 23 | [Code-signing and IT one-pager](PR-23-signing-it-onepager.md) | 5 | ready | 22 |
| 24 | [App certification and quickstarts](PR-24-certification.md) | 6 | ready | 22 |
| 25 | [Snapshot export (backup) v1](PR-25-snapshot-export.md) | 4 | ready | 10 |
| 26 | [Installer wrapper and signed artifacts](PR-26-installer-wrapper.md) | 5 | ready | 22, 23 |
| 27 | [Model and spend guidance v1](PR-27-model-spend-guidance.md) | 1 | ready | 04 |
| 28 | [Workspace ignore rules v1](PR-28-workspace-ignore-rules.md) | 4 | ready | 09, 14, 15, 16 |
| 29 | [First-run feature selection](PR-29-first-run-feature-selection.md) | 4 | ready | 17, 27, 28 |

Statuses: `ready` (prompt complete, dependencies may still be pending),
`in progress — <branch>`, `✅ landed`, `blocked — <reason>`.

## Execution guidance: model capability and effort

Expressed in capability tiers, never model names, so it stays true as models
change — the same abstraction PR-27 ships to users. Map tiers to whatever
your provider currently offers: **frontier** = its most capable reasoning
model, **strong** = its main workhorse, **fast** = small or
latency-optimized.

- **Frontier tier, high effort:** PR-05, 06, 07, 12, 18, 22 —
  design-sensitive surfaces: product voice, the safety spec and gates, the
  hostile-environment installer. (PR-04 belonged to this class and has
  landed.)
- **Strong tier, medium-high effort:** PR-08–11, 13–17, 20, 21, 25–29 —
  well-specified implementation work; the prompts carry checkable acceptance
  criteria precisely so this tier can land them. Run PR-19 at high effort
  (integration debugging).
- **Strong tier, writing-focused:** PR-23, 24 — user-facing prose is the
  deliverable; review for tone as well as substance.
- **Fast tier: never**, for any planned PR. These prompts are cut for
  one-session execution by a capable model, not for decomposition into
  micro-tasks.
- **Budget-limited pattern:** a strong-tier session implements; a
  frontier-tier session reviews the diff against the prompt's acceptance
  criteria and the ADRs. Verification catches the failure class that matters
  here (invented scope, contract violations) at a fraction of authorship
  cost.
- **Escalation rule (learned in execution):** when a slice's author–review
  loop hits a **second blocking rework cycle on the same deliverable**,
  first classify the findings — contract ambiguity gets fixed in the prompt
  or spec before any more authoring; capability shortfall gets escalation.
  Escalate the author one tier (strong → frontier) and/or one effort step,
  and raise the reviewer with it (reviewer never weaker than author, high
  effort for the re-review). Run time far beyond a slice's reasonable
  expectation is corroborating evidence, never a trigger by itself. The
  escalation holds for the remainder of that slice and resets for the next.
  Economics: repeated rework is the most expensive path — a cheap author
  plus two rework cycles plus repeat reviews costs more than one stronger
  authorship pass, so escalating promptly is the frugal move.

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
