# Development Plan

Executable work is pre-cut into focused PRs with self-contained prompts.
The [approved rework sequence](rework-sequence.md) also contains explicitly
uncut outlines; these are not ready-to-execute prompts.

**Current entry:** PR-32 removes the sharing gate. PR-33 implements R2a:
Memory correction, outdated status, forgetting, and current-record recall.
PR-34 implements R2b: task retention across managed writers and derived content.
PR-35 implements R3a: isolated recovery for shared work areas.
PR-36 implements R3b: layout, project bindings and existing-folder adoption.
PR-38 implements R4a: portable Skill files, migration, checks and recovery.
PR-39 implements R5: task-first welcome and everyday work, independently of R4b.
PR-40 implements R6: economical native work and selective prose editing.
PR-41 implements R7: draft and review-bound adoption of learned Skills.
PR-46 implements R11 installer routing and explicit adoption on the integrated
PR-45 core, with separate native setup/release evidence.
PR-47 records the lean [actual-app compatibility gate](../certification/matrix.md):
two focused chats passed for the named Cursor IDE, Codex CLI and Claude Code CLI
configurations, with earlier failures and desktop gaps preserved. Signed native
`0.0.2` install and repair passed on Mac ARM64 and Windows x64. The matrix tracks
public release availability separately; native discovery adapters remain planned.
PR-24 is held; its old checklist must not certify the new target. Preserve any
existing certification work.

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

## Original implementation phases

These phases describe the legacy baseline, not the approved rework. The new
sequence is linked above; R1, R2 and R3 are implemented in PR-32 through PR-36;
later slices remain planned.

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
| 16 | [recall with citations](PR-16-recall.md) | 3 | ✅ landed | 15 |
| 17 | [Interview wired to profile deployment](PR-17-interview-profiles.md) | 4 | ✅ landed | 11, 12, 27 |
| 18 | [Egress gate v1](PR-18-egress-gate.md) | 4 | ✅ landed | 12 |
| 19 | [Welcome flow end-to-end](PR-19-welcome-e2e.md) | 4 | ✅ landed | 17, 18, 16 |
| 20 | [Universal payload builder](PR-20-payload-builder.md) | 5 | ✅ landed | 13, 19 |
| 21 | [Release pipeline](PR-21-release-pipeline.md) | 5 | ✅ landed | 20 |
| 22 | [Bootstrapper v1](PR-22-bootstrapper.md) | 5 | ✅ landed | 21, 30 |
| 23 | [Code-signing and IT one-pager](PR-23-signing-it-onepager.md) | 5 | ✅ landed | 22 |
| 24 | [App certification and quickstarts](PR-24-certification.md) | 6 | blocked — recut after rework | Rework R12 |
| 25 | [Snapshot export (backup) v1](PR-25-snapshot-export.md) | 4 | ✅ landed | 10 |
| 26 | [Installer wrapper and signed artifacts](PR-26-installer-wrapper.md) | 5 | ✅ landed | 22, 23 |
| 27 | [Model and spend guidance v1](PR-27-model-spend-guidance.md) | 1 | ✅ landed | 04 |
| 28 | [Workspace ignore rules v1](PR-28-workspace-ignore-rules.md) | 4 | ✅ landed | 09, 14, 15, 16, 18 |
| 29 | [First-run feature selection](PR-29-first-run-feature-selection.md) | 4 | ✅ landed | 17, 27, 28 |
| 30 | [Embed payload in apparatus-core](PR-30-embed-payload-wheel.md) | 5 | ✅ landed | 20 |
| 31 | [Lean product direction and refactor sequence](PR-31-product-rework-plan.md) | Rework | ✅ landed | Existing baseline |
| 32 | [Remove the sharing gate](PR-32-remove-sharing-gate.md) | Rework | ✅ landed | 31 |
| 33 | [Memory lifecycle and current recall](PR-33-memory-lifecycle.md) | Rework | ✅ landed | 32 |
| 34 | [Task Memory retention](PR-34-task-retention.md) | Rework | ✅ landed | 33 |
| 35 | [Isolated recovery for shared work areas](PR-35-managed-recovery.md) | Rework | ✅ landed | 34 |
| 36 | [Work-area adoption and project binding](PR-36-workarea-adoption.md) | Rework | ✅ landed | 35 |
| 37 | [Library writer-lock release race](PR-37-library-lock.md) | Repair | ✅ landed | 34 |
| 38 | [Portable built-in Skills](PR-38-portable-skills.md) | Rework | ✅ landed | 36, 37 |
| 39 | [Task-first welcome and everyday work](PR-39-task-first-welcome.md) | Rework | ✅ landed | 38 |
| 40 | [Economizer and humanizer Skills](PR-40-economizer-humanizer.md) | Rework | ✅ landed | 39 |
| 41 | [Capture learned Skills](PR-41-learned-skills.md) | Rework | ✅ landed | 39, 40 |
| 42 | [Patched PDF dependency](PR-42-pdf-dependency.md) | Repair | ✅ landed | 35 |
| 43 | [Library references to originals](PR-43-library-references.md) | Rework | ✅ landed | 41, 42 |
| 44 | [Library cards and completion offers](PR-44-library-cards.md) | Rework | ✅ landed | 43 |
| 45 | [Quiet operations and concrete repair guidance](PR-45-quiet-operations.md) | Rework | ✅ landed | 44 |
| 46 | [Install into a chosen work area](PR-46-installer-adoption.md) | Rework | ✅ landed | 45 |
| 48 | [Feature reads through external path aliases](PR-48-feature-path-aliases.md) | Repair | ✅ landed | 46 |
| 49 | [Accurate Library cache diagnostics](PR-49-cache-diagnostics.md) | Repair | ✅ landed | 48 |
| 50 | [Explicit Memory fact capture](PR-50-explicit-memory-capture.md) | Repair | ✅ landed | 49 |
| 51 | [First-publication acceptance gate](PR-51-release-acceptance-gate.md) | Release | ✅ landed | 50 |
| 52 | [Optional hosted Windows signing](PR-52-hosted-windows-signing.md) | Release | ✅ landed | 51 |
| 53 | [Repair the Azure signing rehearsal](PR-53-azure-signing-rehearsal.md) | Release | ✅ landed | 52 |
| 54 | [Run Windows safety groups in parallel](PR-54-parallel-windows-safety.md) | CI | ✅ landed | 53 |
| 55 | [Prepare the first release notes](PR-55-first-release-notes.md) | Release | ✅ landed | 54 |
| 56 | [Verify published installers on clean native runners](PR-56-native-installer-acceptance.md) | Release | ✅ landed | 55 |
| 57 | [Diagnose native Windows signature checks](PR-57-native-signature-diagnostics.md) | Release | ✅ landed | 56 |
| 47 | [Prove the reworked first task](PR-47-first-task-certification.md) | Rework | ✅ landed | 49 |

Statuses: `ready` (prompt complete, dependencies may still be pending),
`in progress — <branch>`, `✅ landed`, `blocked — <reason>`. Rework outlines
use `planned — prompt not cut` and cannot be picked up as executable PRs.

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
- **Strong tier, medium-high effort:** PR-08–11, 13–17, 20, 21, 25–30 —
  well-specified implementation work; the prompts carry checkable acceptance
  criteria precisely so this tier can land them. Run PR-19 at high effort
  (integration debugging).
- **Strong tier, writing-focused:** PR-23, 24 — user-facing prose is the
  deliverable; review for tone as well as substance.
- **Fast tier:** bounded read-only extraction or mechanical work with a
  written spec and checkable output. Never assign product-policy decisions,
  migrations, or final review to this tier solely to save cost. New rework
  prompts assign capability and effort per role, not one model for all work.
- **Rework authoring:** frontier/high for architecture, privacy/retention, and
  cross-cutting migration contracts; spec-backed implementation can use a
  strong model at appropriate effort. Keep teams small, retries bounded, and
  review at least as capable as authorship. Do not spawn recursively without
  a concrete independent need. Use current available model/effort controls;
  dated guidance is advisory, not proof of quota enforcement.
- **Budget-limited pattern:** a strong-tier session implements; a
  frontier-tier session reviews the diff against the prompt's acceptance
  criteria and the ADRs. Verification catches the failure class that matters
  here (invented scope, contract violations) at a fraction of authorship
  cost.
- **Escalation rule (learned in execution):** when a slice's author–review
  loop hits a **second blocking rework cycle on the same deliverable**,
  first classify the findings — contract ambiguity gets fixed in the prompt
  or spec before any more authoring; capability shortfall gets model
  escalation; **platform infeasibility gets a proof or platform-mechanism
  repair — fix the proof, not the model**. Escalate a capability-shortfall
  author one tier (strong → frontier) and/or one effort step, and raise the
  reviewer with it (reviewer never weaker than author, high effort for the
  re-review). Run time far beyond a slice's reasonable expectation is
  corroborating evidence, never a trigger by itself. The escalation holds for
  the remainder of that slice and resets for the next. Economics: repeated
  rework is the most expensive path — a cheap author plus two rework cycles
  plus repeat reviews costs more than one stronger authorship pass, so
  escalating promptly is the frugal move. The PR-22 / PR #25 proof chain
  (`98d1851` → `f9ba8d0`) established platform infeasibility as this third
  classification after the fourth observed harness-versus-physics instance;
  its frontier author and reviewer remain fixed while the proof is repaired.

## Optional modules and updated entry paths

The [design brief](../design/design-brief.md#7-later-modules-and-exclusions)
records the later-module roadmap. No module is a prerequisite for the core
refactor, and no speculative module catalog is scheduled. Native economical
subagent guidance and lightweight humanizer Skills are core work now.

Existing-folder adoption is part of the reworked first version, alongside the
installer. It is no longer a developer-only post-alpha promise. The existing
extension mechanism remains; modules extend core primitives rather than fork
Library, Memory, Skills, or recovery.
