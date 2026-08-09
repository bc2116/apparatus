# PR-19: Welcome flow end-to-end

## Context — required reading

- `AGENTS.md` — session rules, hard rules, definition of done
- `docs/design/design-brief.md` — §1 job statement (this PR proves it), §6
  day-1 capabilities, §7 privacy model, §13 success metrics
- `docs/adr/ADR-0001-vocabulary.md` — canonical terms for all user-facing text
- `docs/adr/ADR-0002-protocol-and-state.md` — record kinds, receipts, snapshots
- `docs/adr/ADR-0003-harness-agnostic-contract.md` — the test may simulate
  only read files, write files, run approved commands
- `docs/adr/ADR-0004-privacy-model.md` — egress and credential-floor behavior
  the story must exercise
- `docs/spec/workspace.md` and `docs/spec/egress.md` — normative shapes the
  test asserts against
- `docs/plan/README.md` — phases, status table (update it in this PR)
- `docs/plan/PR-16-recall.md`, `docs/plan/PR-17-interview-profiles.md`,
  `docs/plan/PR-18-egress-gate.md` — the verbs this PR integrates
- The first dogfood report under `docs/notes/` (landed in PR-07) — match its
  format and naming convention for the second report

## Objective

When this PR lands, the day-1 job statement is an executable test: from a
fresh `apparatus init`, through the welcome procedure (interview answers →
profile apply → seeded People and Goals), through the produce-deliverable
procedure (draft in `Projects/`, a Library source cited via recall, the egress
gate, filing to `Deliverables/`, a goal update), to a snapshot — with receipts
and record validity asserted at every step, using nothing beyond the three
ADR-0003 capabilities. Integration defects between PR-16, PR-17, and PR-18 are
found and fixed here, and a second dogfood report records a manual pass of the
same story in a real AI app. This PR is done when the job statement's
mechanical path runs green as a test.

## Deliverables

- `conformance/test_welcome_e2e.py` — new scripted end-to-end test (see
  Acceptance criteria for the exact step sequence).
- `conformance/fixtures/welcome-e2e/profile-configured.yaml` — a configured
  profile: work type, two key people (one person, one organization), one
  current effort with `done_when` and `next_action`, source locations, standard
  privacy mode, a review day.
- `conformance/fixtures/welcome-e2e/library/reference-note.md` — a small
  source document containing one citable fact, one person name matching one
  of the profile fixture's two key people (so it exists in `Memory/People/`
  after profile apply and the egress gate's People-derived exact-match can
  find it), and one clearly fake credential in the style PR-12's fixtures
  established (so the drafted deliverable can quote content that exercises
  both the People-derived enumeration and the credential floor at egress).
- Integration fixes in `packages/apparatus-core/src/apparatus_core/` and, if
  the story surfaces procedure-text defects, in
  `starter/payload/System/procedures/` — smallest possible diffs, each one
  enumerated in the PR description with the step that surfaced it.
- `docs/notes/dogfood-02-welcome-end-to-end.md` — second dogfood report
  (naming adjusted to match the PR-07 report's convention if it differs).
- `conformance/README.md` — fixtures table updated with the new fixture rows.
- `docs/plan/README.md` — status row for PR-19 updated.

## Acceptance criteria

1. The end-to-end test simulates an assistant using only ADR-0003's three
   capabilities: it writes and reads workspace files directly and invokes
   `apparatus` verbs as subprocesses (the installed console script or
   equivalent). The flow itself imports no `apparatus_core` internals;
   assertions may read files directly.
2. Step sequence, each step asserted before the next: (a) `apparatus init`
   into a temp directory, then `apparatus check` green on the fresh workspace;
   (b) fixture profile written to `System/profile.yaml`; (c)
   `apparatus profile apply` → seeded People and Goal records exist, pass
   `apparatus check`, and an apply receipt exists; (d) fixture document copied
   into `Library/`, then `apparatus library ingest` runs and its receipt
   exists (PR-15 ships no separate index verb; the index refreshes
   automatically when recall queries it); (e) `apparatus recall` (PR-16)
   returns the fixture fact with a citation resolving to the
   Library source, and a query about an absent topic returns an honest miss
   with no citation; (f) a draft is written under `Projects/` quoting the
   cited fact, the person name, and the fake-credential line; (g)
   `apparatus egress check <workspace> <draft>` — the workspace argument
   explicit, per the verb shape — exits 1 with no decision, writes the
   redacted copy, and enumerates both findings (the People-matched name and
   the credential); with `--decision use-redacted` it exits 0 and writes an
   egress receipt; (h) the
   redacted copy is filed into `Deliverables/`; (i) the seeded goal record is
   updated (status and next action reflect the filed deliverable); (j)
   `apparatus snapshot` succeeds and writes a snapshot receipt; (k) final
   `apparatus check` over the whole workspace is green.
3. Every receipt produced along the way (apply, ingest, recall, egress,
   snapshot, plus any redaction receipts) exists under `System/receipts/`
   and is schema-valid.
4. No fabricated grounding: the recall-miss assertion in step (e) proves a
   miss is reported honestly rather than dressed as recall (brief §6 item 4).
5. Integration fixes change no conformance fixture except deliberately, called
   out in the PR description; no fixture is loosened to make a failure pass.
6. The dogfood report records: date, the AI app used (app names are acceptable
   in `docs/notes/` — it is internal engineering documentation, not
   user-facing), the story as run manually, every point of friction, whether
   the human typed zero terminal commands, and follow-up candidates for the
   plan. No personal data, secrets, or machine-specific absolute paths.
7. `uv run pytest` is green, including the new end-to-end test, on a machine
   with git available.

## Conformance and tests

- New: `conformance/test_welcome_e2e.py` plus the two fixtures under
  `conformance/fixtures/welcome-e2e/`. This test is the executable form of the
  job statement and becomes the regression net for Phases 2–4 behavior.
- Existing fixtures (payload manifest, record schemas, egress golden trio)
  change only if an integration fix deliberately changes pinned behavior, with
  the change called out in the PR description.
- If snapshot behavior differs when git is absent, the end-to-end test may
  require git and skip with an explicit reason otherwise; degraded-mode
  coverage stays in PR-10's tests.
- `uv run pytest` green is required.

## Out of scope

- No new features: this PR wires and fixes what PR-04 through PR-18 landed.
  Anything larger than a small integration fix goes back to the plan as a new
  PR proposal instead of landing here.
- No restore-path exercise (PR-10 owns snapshot/restore coverage) and no
  private-mode end-to-end variant (the standard profile is the day-1 story).
- No payload builder, packaging, installer, or release work (PR-20 through
  PR-23), and no certification-matrix work (PR-24).
- No timing or performance assertions; the timed first-time-user test in
  brief §13 is a later, human-run activity.

## Dependencies

PR-16 (recall with citations), PR-17 (interview wired to profile deployment),
and PR-18 (egress gate v1) must have landed, matching `docs/plan/README.md`.
Everything earlier arrives transitively through those three.

## Open decisions

- None. This PR integrates decisions already made in PR-16, PR-17, and PR-18;
  anything the story surfaces that is larger than a small integration fix
  goes back to the plan as a new PR proposal (see Out of scope) instead of
  being decided here.
