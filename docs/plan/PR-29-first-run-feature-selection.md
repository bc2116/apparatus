# PR-29: First-run feature selection

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` (§2 audience, §3 principles, §6 day-1 capabilities)
- `docs/adr/ADR-0001-vocabulary.md`
- `docs/adr/ADR-0002-protocol-and-state.md` (profile schema; additive changes)
- `docs/plan/PR-11-init-profiles.md`, `PR-17-interview-profiles.md`,
  `PR-27-model-spend-guidance.md`, `PR-28-workspace-ignore-rules.md`
- `docs/spec/records.md`, `docs/spec/workspace.md`

## Objective

When this PR lands, first-run setup goes beyond the professional interview:
after the job-function questions, the welcome flow offers a short,
plain-language feature selection — each core feature with a one-line
explanation, a sensible default, and the explicit promise that everything can
be turned on or off later by asking the assistant. Choices are recorded in
the profile and honored by the machinery, so a cautious first-time user can
start minimal and grow, and nobody is stuck with a day-1 decision.

## Deliverables

- Profile schema, additive: optional `features` mapping in
  `docs/spec/records.md` and `records.py` with exactly these boolean keys and
  defaults — `library_indexing: true`, `snapshots: true`,
  `ignore_rules: true`. (Privacy mode and spend level remain their own
  existing profile keys; they are presented in the same selection step but
  are not `features` entries.) Additions beyond these three require a plan
  change, not an inline edit — record that rule in the spec.
- Welcome procedure update (`starter/payload/System/procedures/`): a feature
  selection step after the interview questions — for each feature and for
  privacy mode and spend level: one plain-language line on what it does, the
  default, and "you can change this any time by asking me." Written to the
  minimum agent contract (ADR-0003), vocabulary per ADR-0001.
- `Welcome.md` (payload): one short paragraph noting that features chosen at
  setup are changeable any time ("re-run my setup interview" or just ask).
- Honoring the toggles, with tests: `library_indexing: false` disables
  ingest/index/recall verbs with a plain-language "this feature is off; say
  the word and I'll enable it" outcome (exit 1, receipt written);
  `snapshots: false` makes snapshot steps no-ops that report honestly (never
  silently skip); `ignore_rules: false` disables `System/ignore` matching
  (built-in OS-noise defaults stay active).
- `apparatus profile apply` (PR-17's verb) applies feature changes
  idempotently; re-running the interview re-presents current values as the
  defaults.
- A seam note for PR-22 (bootstrapper): the installer's closing message
  points to the welcome conversation for feature choices; no PR-22 files are
  edited here.
- `docs/plan/README.md` — status row updated.

## Acceptance criteria

1. The profile accepts the optional `features` mapping with exactly the three
   keys; unknown feature keys are rejected by `check` with a plain-language
   message; absence of the mapping means all defaults.
2. Each toggle is proven by test in both states, including the honest-report
   requirement (a disabled feature explains itself and writes a receipt; it
   never silently succeeds or silently skips).
3. Disabling a feature and re-enabling it later loses no user content
   (indexes rebuild; snapshots resume; ignore matching resumes), proven by a
   round-trip test.
4. The welcome procedure's selection step covers the three features plus
   privacy mode and spend level, each with default and change-later promise,
   in ADR-0001 vocabulary.
5. Re-running the interview shows current settings as defaults and applies
   changes idempotently (receipts excluded from the idempotence comparison,
   matching PR-17's convention).
6. The shipped `profile.yaml` remains valid with and without the `features`
   mapping present.
7. `uv run pytest` green; golden payload manifest unchanged unless the
   welcome-procedure file set changes, in which case the change is deliberate
   and called out.

## Conformance and tests

- Updated: record-schema tests for the `features` mapping; welcome-procedure
  fixture if its file changes.
- Added: per-toggle behavior tests (both states), round-trip
  disable/re-enable test.
- Unchanged: PR-04 record examples except where a profile example gains the
  optional mapping (cover present and absent).

## Out of scope

- No new features behind new toggles (the three listed only).
- No pack management (`apparatus add` remains post-alpha).
- No bootstrapper changes (seam note only).
- No GUI; selection happens in conversation, recorded in files.

## Dependencies

PR-17 (interview wiring), PR-27 (spend key), and PR-28 (ignore rules) must
have landed, matching `docs/plan/README.md`.

## Open decisions

- **Disabled Library-search receipt.** The v1 receipt event enum is closed and
  normal Library search has no receipt. Smallest reversible default: a disabled
  Library-search control outcome writes the existing `library-ingest` event,
  with `Operation: Library search.` in its body. This records the Library
  indexing feature outcome without adding an event; normal search remains
  receipt-free.

- **Presentation order.** Smallest reversible default: interview questions
  first, then feature selection, so job-function context can inform the
  explanations.
- **Frugal-spend interaction.** Whether `spend: frugal` should suggest (never
  force) starting with `library_indexing` on but background refresh less
  frequent. Default: no coupling in v1; note the idea for later.
