# PR-27: Model and spend guidance v1

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` (§3 principles, §6 day-1 capabilities, §9–§10)
- `docs/adr/ADR-0001-vocabulary.md` (this PR amends it)
- `docs/adr/ADR-0002-protocol-and-state.md` (profile schema is closed; additive changes)
- `docs/adr/ADR-0003-harness-agnostic-contract.md` (governs this PR)
- `docs/plan/README.md` (including "Execution guidance", which uses the same abstraction)
- `docs/spec/records.md` and `packages/apparatus-core/src/apparatus_core/records.py`
- `docs/plan/PR-17-interview-profiles.md` (consumes this PR's `spend` key)

## Objective

When this PR lands, the workspace carries harness-agnostic guidance that tells
the assistant how much model capability and effort to apply to a piece of
work, controlled by a user-owned spend dial. The design survives model churn
by construction: the stable layer maps work roles and spend levels to
capability tiers and effort — never to model names — and concrete model names
live only in a dated, replaceable roster. Per ADR-0003 the guidance is data
the assistant reads and applies within whatever AI app is running; core never
selects, switches, or invokes models itself.

## Deliverables

- `docs/spec/model-guidance.md` — the normative spec:
  - **Roles:** `lead` (orchestration, synthesis, verification), `worker`
    (scoped delegated subtasks), `reviewer` (checking finished work).
  - **Spend levels:** `frugal` | `balanced` | `thorough` (canonical terms;
    see the ADR-0001 amendment below). `balanced` is the default.
  - **Capability tiers:** `frontier` (the provider's most capable reasoning
    model), `strong` (the provider's main workhorse), `fast` (small or
    latency-optimized).
  - **Effort dial:** `low` | `medium` | `high`, applied where the AI app
    exposes such a control; advisory otherwise.
  - **The stable mapping table** (role × spend level → tier + effort),
    encoding these principles: the lead is never weaker than the workers it
    verifies; `frugal` means a cheaper lead AND less delegation, never an
    expensive fleet under a cheap lead; `thorough` upgrades verification
    before it upgrades drafting; `fast` tier is permitted only for mechanical
    transformations whose output the lead fully checks.
  - **The escalation policy** (reactive spend adjustment): the primary
    signal is a **second blocking review cycle on the same deliverable**;
    run time far beyond the stated expectation is secondary, corroborating
    evidence only — never a trigger by itself. Before escalating, classify
    the review findings: **ambiguity** in the task contract gets fixed in
    the contract (escalating a model to compensate for an unclear ask
    wastes spend and hides the real defect); **capability** shortfall gets
    escalation. Escalation raises the worker one tier and/or one effort
    step, and the reviewer rises with it so the reviewer is never weaker
    than the author, at high effort for the re-review. Escalation is sticky
    for the remainder of that piece of work, noted in that work's receipt,
    and resets afterward — it never permanently ratchets the dial. Triggers
    are identical at every spend level: the dial sets starting tiers,
    evidence adjusts them. Rationale stated in the spec: repeated rework is
    the most expensive path (a cheap author plus two rework cycles plus
    repeat reviews costs more than one stronger authorship pass), so
    escalation is the economizing move, not an overspend.
  - **The roster contract:** concrete model names appear only in the roster
    section of the workspace guidance file, dated, marked advisory, and
    expected to be edited as models change. A roster entry older than the
    staleness window is treated as a hint, not an instruction, and the
    assistant prefers its app's current equivalents by tier.
- `starter/payload/System/guidance/model-guidance.md` — the shipped guidance
  the assistant reads: the stable mapping rendered in plain language, the
  spend dial's meaning, the escalation policy in plain language (when work
  bounces back a second time, step up the model or effort — and step the
  reviewer up with it; reset when the piece of work is done), and a
  placeholder roster whose example entries are clearly fictional (e.g.
  `example-frontier-model`), with instructions to replace them with the
  models actually available in the user's AI app.
- `docs/adr/ADR-0001-vocabulary.md` — add the canonical vocabulary row:
  concept "how much model capability and cost to apply", canonical term
  **spend level** with values `frugal` | `balanced` | `thorough`; do not use
  "cheap mode", "budget", or tier adjectives banned elsewhere.
- Profile schema, additive: optional `spend` key (values `frugal` |
  `balanced` | `thorough`) in `docs/spec/records.md` and
  `packages/apparatus-core/src/apparatus_core/records.py`, following the
  additive-optional-key pattern; add `spend: balanced` with a short comment
  to `starter/payload/System/profile.yaml`.
- `docs/spec/workspace.md` — add `System/guidance/` to the System contents
  table.
- `conformance/golden/payload-manifest.txt` — updated deliberately for the
  new payload file.
- `docs/plan/README.md` — status row updated.

## Acceptance criteria

1. `docs/spec/model-guidance.md` exists and defines roles, spend levels,
   capability tiers, effort dial, the full stable mapping table, and the
   roster contract with its staleness rule.
2. No real-world model, vendor, or AI-app brand name appears anywhere in the
   spec or the shipped guidance file; roster examples are clearly fictional.
3. The stable mapping never names a model; grep for the fictional roster
   names finds them only in the roster section.
4. ADR-0001 contains the spend-level vocabulary row, and all user-facing text
   in the shipped guidance uses it.
5. The profile schema accepts an optional `spend` key with exactly the three
   canonical values, rejects others, and the shipped `profile.yaml` (now
   carrying `spend: balanced`) validates via the existing conformance test.
6. The shipped guidance file states explicitly that Apparatus never switches
   models itself and that the assistant applies the guidance within its app's
   capabilities (ADR-0003).
7. Payload manifest and workspace spec updated in this PR, called out in the
   PR description.
8. The escalation policy appears in both the spec and the shipped guidance,
   and covers: the rework-cycle primary signal, run time as corroborating
   only, the ambiguity-versus-capability classification step, the
   reviewer-never-weaker-than-author invariant during escalation, sticky-
   for-the-work-then-reset behavior, and identical triggers at every spend
   level.
9. `uv run pytest` green.

## Conformance and tests

- Updated: `conformance/golden/payload-manifest.txt` (one new file),
  golden profile example may gain `spend` (optional — schema tests must cover
  both present and absent).
- Added: schema tests for the `spend` enum (valid values, rejection of
  others, absence allowed).
- Unchanged: all other fixtures.

## Out of scope

- No CLI verb, no model detection, no cost accounting or token metering.
- No per-app adapter notes (certification-time material, PR-24).
- No interview wiring — PR-17 adds the spend question and writes the key.
- No pack-level or fleet-level model policy.

## Dependencies

PR-04 (record schemas) must have landed, matching `docs/plan/README.md`.
PR-17 consumes this PR's `spend` key and depends on it.

## Open decisions

- **Escalation thresholds.** Smallest reversible defaults: escalate on the
  second blocking review cycle for the same deliverable; treat run time as
  corroborating only, and only when it exceeds roughly twice the stated
  expectation.
- **Staleness window for roster entries.** Smallest reversible default:
  90 days from the roster's dated header.
- **Guidance file format.** Smallest reversible default: Markdown with a
  small YAML block for the mapping table, keeping it human-readable first
  (ADR-0002 files-first).
