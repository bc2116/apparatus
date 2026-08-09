# PR-04: Record schemas v1

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` (§5 workspace, §6 day-1 capabilities, §7 privacy)
- `docs/adr/ADR-0001-vocabulary.md`
- `docs/adr/ADR-0002-protocol-and-state.md` (governs this PR)
- `docs/adr/ADR-0004-privacy-model.md` (labels and receipts)
- `docs/plan/README.md`
- `docs/spec/workspace.md`
- `starter/payload/System/profile.yaml` (the profile schema must match this file)
- `conformance/README.md`

## Objective

When this PR lands, the seven v0 record kinds — procedure, goal, decision,
fact, person, profile, receipt — are specified in one normative document,
encoded as machine-readable structures inside `apparatus-core`, and pinned by
golden example records that a pytest parses and validates. Everything built
after this (starter procedures in PR-05, policy in PR-06, the `check`
validators in PR-09, memory verbs in PR-12) consumes these schemas instead of
inventing shapes ad hoc. Per ADR-0002, any schema beyond these seven requires
a new ADR.

## Deliverables

- `docs/spec/records.md` — the normative record-schema spec. One one-screen
  section per kind, each listing: required frontmatter fields, optional
  frontmatter fields, allowed enum values, body conventions, and filename
  rules. Shared conventions stated once up front:
  - Records are Markdown with a YAML frontmatter block delimited by `---`
    lines, one record per file (ADR-0002). `profile` is the one exception:
    plain YAML at `System/profile.yaml`, no Markdown body.
  - Every record carries `schema: apparatus/<kind>@v0` (the pattern the
    shipped `profile.yaml` already uses).
  - Filenames are kebab-case: lowercase `a–z`, digits, and single hyphens,
    `.md` extension. Receipt filenames follow one fixed convention:
    `YYYY-MM-DD-HHMMSS-<event>.md`, UTC, all lowercase; a same-second
    collision appends `-2`, `-3`, … before the extension. Every later PR
    that writes receipts uses this convention unchanged.
  - Every Markdown record kind accepts an optional `labels` field (list of
    strings) reserved for ADR-0004 write-time labeling; the labeler itself
    arrives in PR-12 and this PR only reserves the field.
  Per-kind minimums (expand with optional fields as the spec requires):
  - **procedure**: required `schema`, `title`, `intent` (one sentence: when
    the assistant should use it); body is an ordered list of numbered steps.
  - **goal**: required `schema`, `title`, `owner`, `status`, `done-when`
    (the verification oracle: how anyone could check completion),
    `next-action`. `status` enum: `active`, `waiting`, `done`, `dropped`.
  - **decision**: required `schema`, `title`, `date`; body states what was
    decided, why, and alternatives considered.
  - **fact**: required `schema`, `title`; optional `source`; body is the
    durable fact, one fact per file.
  - **person**: required `schema`, `name`; optional `role`, `organization`;
    body covers context, commitments, history. Covers organizations too.
  - **profile**: YAML keys exactly matching `starter/payload/System/profile.yaml`:
    `schema`, `status` (`unconfigured` | `configured`), `privacy_mode`
    (`standard` | `private`), `work_types` (list), `review_day` (nullable).
  - **receipt**: required `schema`, `event`, `timestamp` (UTC ISO 8601),
    `summary`; `event` enum, pinned here once for all of v1: `check`,
    `redaction`, `snapshot`, `restore`, `init`, `egress`, `library-ingest`,
    `recall`, `profile-apply`, `backup-export`; body holds detail.
    Machine-written, still human-legible. Later PRs consume values from
    this enum without redefining or extending it.
- `packages/apparatus-core/src/apparatus_core/records.py` — machine-readable
  schema definitions as plain Python structures (dicts, tuples, frozen
  dataclasses — implementer's choice). For each kind expose: kind name,
  required fields, optional fields, enum constraints, and the filename rule.
  No external schema-language dependency (no jsonschema, no pydantic).
- `packages/apparatus-core/pyproject.toml` — add `pyyaml` as a runtime
  dependency. Justification: YAML frontmatter and `profile.yaml` are the state
  format fixed by ADR-0002; the stdlib has no YAML parser; PyYAML is mature,
  MIT-licensed, and used strictly via `yaml.safe_load`. It is the one
  dependency the chosen format demands, consistent with `apparatus-core`
  shipping lean (ADR-0005).
- `conformance/golden/records/<kind>/…` — at least one valid example record
  per kind, one subdirectory per kind (e.g.
  `conformance/golden/records/goal/finish-quarterly-quality-report.md`,
  `conformance/golden/records/profile/profile.yaml`). Examples use invented,
  clearly fictional content — no real names, employers, or systems.
- `conformance/test_records.py` — pytest that parses every golden record's
  frontmatter (or YAML, for profile) with `yaml.safe_load` and validates it
  against `apparatus_core.records`: required fields present, enums respected,
  filename rules obeyed. Also validates the shipped
  `starter/payload/System/profile.yaml` against the profile schema.
- `conformance/README.md` — add the new fixture row(s) to the fixtures table.
- `docs/spec/workspace.md` — add a pointer from the "State format" section to
  `docs/spec/records.md`.
- `docs/plan/README.md` — status table row for PR-04 updated.

## Acceptance criteria

1. `docs/spec/records.md` exists, covers exactly seven kinds, and each kind's
   section fits on one screen (25 lines or fewer per kind, heading included).
2. Goal schema requires `owner`, `status`, `done-when`, and `next-action`;
   the spec explains `done-when` as a verification oracle in plain language.
3. Receipt schema's `event` enum is exactly `check`, `redaction`, `snapshot`,
   `restore`, `init`, `egress`, `library-ingest`, `recall`, `profile-apply`,
   `backup-export` — pinned once in this PR; later PRs consume these values
   and no PR extends the enum. The receipt filename convention is exactly
   `YYYY-MM-DD-HHMMSS-<event>.md` (UTC, all lowercase; a same-second
   collision appends `-2`, `-3`, …).
4. The profile schema matches the shipped `starter/payload/System/profile.yaml`
   key-for-key, and the pytest proves it by validating that very file.
5. `apparatus_core.records` is importable, contains no dependency beyond
   PyYAML, and every constraint asserted in `docs/spec/records.md` is
   represented in it (a reviewer can diff spec against code section by
   section).
6. `conformance/golden/records/` contains at least one valid example per
   kind, and `conformance/test_records.py` fails if any example violates its
   schema or filename rule (verify by temporarily breaking one locally).
7. All user-facing wording in the spec and example records follows ADR-0001
   vocabulary (workspace, procedure, check, snapshot, Library, Deliverables,
   Memory, System, assistant).
8. The PR's diff touches nothing under `starter/payload/` and does not touch
   `conformance/golden/payload-manifest.txt`.

## Conformance and tests

- Added: `conformance/golden/records/` fixture set and
  `conformance/test_records.py` (new executable spec surface).
- Unchanged: `conformance/golden/payload-manifest.txt` and
  `conformance/test_payload.py` — this PR ships no payload files.
- `uv run pytest` green, including the new record tests.

## Out of scope

- No validator CLI, no `check` verb, no CLI of any kind (PR-08/PR-09).
- No starter procedure content (PR-05) and no policy overlays (PR-06).
- No PII labeler or credential-floor implementation (PR-12) — only the
  reserved `labels` field and the `redaction` receipt event kind.
- No changes to the starter payload or its golden manifest.
- No eighth record kind, however tempting; that requires an ADR.

## Dependencies

- PR-03 (landed): workspace spec, starter payload, first conformance fixture.

## Open decisions

- **Goal `status` enum values.** The brief requires a status field but does
  not fix the vocabulary. Smallest reversible default: `active`, `waiting`,
  `done`, `dropped`; growing the enum later is additive and cheap.
- **Shape of the `labels` field.** PR-12 may need structured labels
  (kind + span). Smallest reversible default: a flat list of strings now;
  a structured form later would arrive with a `@v1` schema bump.
