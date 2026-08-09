# PR-17: Interview wired to profile deployment

## Context — required reading

- `AGENTS.md` — session rules, hard rules, definition of done
- `docs/design/design-brief.md` — §5 workspace, §6 day-1 capabilities
  (especially §6.1 welcome interview → profile), §7 privacy model
- `docs/adr/ADR-0001-vocabulary.md` — canonical terms for all user-facing text
- `docs/adr/ADR-0002-protocol-and-state.md` — record kinds; goals carry
  verification oracles; receipts
- `docs/adr/ADR-0003-harness-agnostic-contract.md` — the assistant may only
  read files, write files, and run approved commands
- `docs/adr/ADR-0004-privacy-model.md` — privacy mode is selected in the
  interview; private mode is a profile overlay
- `docs/plan/README.md` — phases, status table (update it in this PR)
- `docs/spec/workspace.md` — folder semantics; `System/profile.yaml`
- `docs/plan/PR-11-init-profiles.md` and `docs/plan/PR-12-memory-labeler.md` —
  the overlay engine, labeler, and credential floor this PR builds on

## Objective

When this PR lands, the welcome interview is mechanically wired to profile
deployment: the assistant records the interview answers from design brief §6.1
(kind of work, key people, current efforts, source locations, privacy needs,
operating cadence, spend preference) into `System/profile.yaml`, then runs
`apparatus profile apply`, which idempotently re-runs the PR-11 overlay engine
and additionally seeds starter records from the answers — one `Memory/People/`
page per named person or organization and one `Goals/` record per current
effort. Re-running the interview later updates the profile and overlays with
zero loss of user content. This is the first half of the day-1 job statement:
setup becomes real workspace state, not just a conversation.

## Deliverables

- `packages/apparatus-core/src/apparatus_core/interview.py` — new module:
  parse and validate the interview-answer fields of `System/profile.yaml`;
  derive seed records (people pages, goal records) deterministically.
- `packages/apparatus-core/src/apparatus_core/commands/profile.py` — new:
  argparse wiring (`register`/`run`) for `apparatus profile apply`,
  registered in the `apparatus.commands` entry-point group in
  `packages/apparatus-core/pyproject.toml` per the PR-08 registry contract
  (PR-11 ships only `init`; this PR owns the `profile` verb). It re-runs the
  PR-11 overlay engine (`overlays.py` — reuse, never duplicate) and then
  runs seeding.
- `docs/spec/records.md` and
  `packages/apparatus-core/src/apparatus_core/records.py` — extend the
  profile schema with the new answer fields as optional keys (PR-04 pins the
  schema and the shipped `profile.yaml` to each other, and
  `conformance/test_records.py` validates the shipped file, so schema and
  payload must change together). The change is additive and deliberate; call
  it out in the PR description. The apply receipt uses the `profile-apply`
  event value already pinned in the PR-04 receipt `event` enum — no enum
  change in this PR.
- `starter/payload/System/profile.yaml` — extend the commented schema
  (`apparatus/profile@v0`) with the answer fields: `key_people` (list of
  `{name, role, organization}`, role/organization optional), `current_efforts`
  (list of `{title, done_when, next_action}`), `source_locations` (list of
  plain-language location strings), keeping the existing `status`,
  `privacy_mode`, `work_types`, and `review_day` fields.
- `starter/payload/System/procedures/welcome.md` (filename as landed in
  PR-05) — update the welcome procedure to the wired flow: ask the six
  interview questions, write answers to `System/profile.yaml`, set
  `status: configured`, run `apparatus profile apply`, then confirm the seeded
  records with `apparatus check`. Vocabulary per ADR-0001 throughout.
- `packages/apparatus-core/tests/test_interview_profiles.py` — new tests
  (see Conformance and tests).
- `docs/plan/README.md` — status row for PR-17 updated.

## Acceptance criteria

1. `apparatus check` validates a configured `System/profile.yaml`: wrong types,
   malformed entries (e.g., a key person without a name), or an effort missing
   `title` fail the check with an actionable message naming the field.
2. On a workspace with a configured profile, `apparatus profile apply` deploys
   the profile overlay (PR-11 behavior unchanged) and creates
   `Memory/People/<kebab-case-name>.md` for every entry in `key_people` and
   `Goals/<kebab-case-title>.md` for every entry in `current_efforts`.
3. Seeded goal records satisfy ADR-0002: owner, status, done-when, next
   action. `done_when` and `next_action` come from the profile when present.
4. Seeded person records carry role/organization context when given and are
   written through the PR-12 write pipeline (credential floor → labeler →
   mode gate) per ADR-0004, acquiring whatever frontmatter labels the
   labeler's pattern classes find — names are a feature; labels are silent
   metadata, and a record with no matching pattern carries none.
5. All seeded records pass `apparatus check` immediately after apply.
6. Idempotence: a second `apparatus profile apply` with an unchanged profile
   changes no file in the workspace outside `System/receipts/` — each run
   still writes its own receipt (criterion 8). The test verifies the rest of
   the tree byte-for-byte.
7. No data loss on re-interview: after a user or assistant edits a seeded
   record, re-running apply with an updated profile (new person, new effort,
   changed cadence) seeds only the new records and never overwrites, renames,
   or deletes any existing record. Existing-file collisions are skip-and-report,
   never clobber.
8. Every apply writes one receipt record under `System/receipts/` (event
   `profile-apply`, schema-valid via `apparatus check`) listing overlay
   actions and records seeded/skipped.
9. The welcome procedure requires nothing beyond ADR-0003's three capabilities
   and contains no AI-app brand names.
10. `uv run pytest` is green.

## Conformance and tests

- `conformance/golden/payload-manifest.txt` is unchanged: this PR edits the
  content of `System/profile.yaml` and `System/procedures/welcome.md`, not the
  payload file set. PR-04's golden example records remain valid without edits
  (the new profile keys are optional; the receipt `event` enum is untouched —
  `profile-apply` is already pinned there); the schema spec and `records.py`
  change only as the deliverables list — nothing is loosened.
- New tests in `packages/apparatus-core/tests/test_interview_profiles.py`,
  each on a temp-directory workspace created with `apparatus init`:
  - fresh apply: configured profile → overlay deployed, records seeded,
    `apparatus check` green, receipt present;
  - re-apply idempotence: second apply changes nothing outside
    `System/receipts/`, verified byte-for-byte over the rest of the tree;
  - re-interview update: edit a seeded goal, add a person and an effort to the
    profile, re-apply → new records seeded, edited record untouched;
  - validation: malformed profile fields fail `apparatus check` and cause
    `profile apply` to exit non-zero without writing records.
- `uv run pytest` green is required.

## Out of scope

- No conversational or interactive UI in the CLI. The interview is a
  conversation the assistant runs; the CLI only consumes `System/profile.yaml`.
- No natural-language parsing: profile fields are structured YAML written by
  the assistant, not free-text transcripts.
- No changes to the overlay engine's own semantics, `init`, private-mode
  policy content (PR-06), or the labeler/credential floor (PR-12).
- No egress behavior (PR-18) and no end-to-end welcome test (PR-19).
- No new record kinds beyond ADR-0002's seven; no `Welcome.md` regeneration
  work beyond what PR-11 already does on profile change.

## Dependencies

PR-11 (init and profile overlay engine), PR-12 (memory verbs, PII labeler,
credential floor), and PR-27 (model and spend guidance — defines the `spend`
profile key this interview writes) must have landed, matching
`docs/plan/README.md`.

## Open decisions

- Whether apply should also create a `Projects/<kebab-case-title>/` working
  folder per current effort. Smallest reversible default: no — seed records
  only; the produce-deliverable procedure creates working folders on demand.
- What to seed when the user cannot articulate `done_when` during the
  interview. Smallest reversible default: allow `done_when` to be omitted in
  the profile; the seeded goal then gets `status: waiting` (the PR-04 goal
  enum has no `draft` value) and next action "Agree with the owner what done
  looks like", so the oracle gap is explicit instead of invented.
- What `owner` seeded goals carry: the goal schema requires it, but the
  profile has no user-name field and the interview does not ask for one.
  Smallest reversible default: the literal `me` — the workspace is
  single-user (ADR-0002); a later PR can capture a display name in the
  profile and improve seeding without migration.
