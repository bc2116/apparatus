# PR-31: Record the lean product direction and refactor sequence

## Required reading

`AGENTS.md`, `README.md`, the design brief, ADR-0001 through ADR-0005,
`docs/plan/README.md`, and the existing PR-24 certification prompt.

## Objective

Record the owner's approved product rethink as a coherent target and bounded
migration sequence. This PR changes documentation only. Existing CLI, payload,
specs, and fixtures describe the implementation until their migration PRs land.

## Deliverables

- `docs/adr/ADR-0006-lean-workspace-and-skills.md`: accepted direction and
  explicit limited supersession of founding decisions.
- `docs/design/design-brief.md`: concise replacement requirements.
- `docs/plan/rework-sequence.md`: scope, dependencies, evidence, acceptance,
  and separate optional-module roadmap.
- `README.md`: accurate positioning and implemented-versus-planned status.
- `docs/plan/README.md`: execution entry, PR-31 row, certification hold, and
  economical execution guidance.
- Supersession notices in the five founding ADRs; a hold notice in PR-24.

## Acceptance criteria

1. Record project-local work; reference-based Library, cards and timely offers;
   task Memory control; sharing-gate removal; native Skills; native economical
   delegation; lightweight humanizer; learned Skills; task-first setup; quiet
   operations; and later modules. Preserve correction/forgetting and recovery.
2. Retain the three-capability foundation. No core model API, cross-CLI
   executor, mandatory native subagents, or per-install benchmark service.
3. Distinguish approved target from current implementation. Hold obsolete
   certification without discarding its work. Name spec/fixture migrations.
4. Give bounded implementation slices observable acceptance conditions and
   dependencies. Mark uncut work as not executable; an outline is not a
   self-contained PR prompt or authorization to implement everything.
5. Use original public-safe prose without private source names, internal
   systems, user data, or machine-specific paths.
6. Verify local Markdown links, `git diff --check`, and `uv run pytest`.
   Set PR-31 to `✅ landed` in this PR, effective on main only after PR merge.

## Out of scope

Runtime/payload/schema changes, release/deployment, other worktrees, modules,
and certification runs. Cut future executable prompts from the sequence.
