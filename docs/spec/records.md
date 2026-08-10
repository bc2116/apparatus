# Record Schemas (v0)

- **Status:** Normative for all workspace records; pinned by
  `conformance/golden/records/` and `conformance/test_records.py`.
- Governing decision: ADR-0002 (protocol and state). Machine-readable form:
  `packages/apparatus-core/src/apparatus_core/records.py` — the two change
  together, section by section.
- Per ADR-0002, any record kind beyond these seven requires a new ADR.

## Shared conventions

- A record is Markdown with a YAML frontmatter block delimited by `---` lines,
  one record per file. **profile** is the one exception: plain YAML at
  `System/profile.yaml`, no Markdown body.
- Every record carries `schema: apparatus/<kind>@v0`.
- Filenames are kebab-case: lowercase `a–z`, digits, and single hyphens, with
  the `.md` extension. Receipts follow one fixed convention:
  `YYYY-MM-DD-HHMMSS-<event>.md`, UTC, all lowercase; a same-second collision
  appends `-2`, `-3`, … before the extension. Every PR that writes receipts
  uses this convention unchanged.
- Every Markdown record kind accepts an optional `labels` field — a flat list
  of strings reserved for write-time labeling (ADR-0004). The labeler arrives
  in PR-12; this spec only reserves the field.
- Dates are `YYYY-MM-DD`; timestamps are UTC ISO 8601 (`…THH:MM:SSZ`).
- Fields not listed for a kind are permitted and preserved; validators ignore
  them. **profile** is again the exception: its key set is closed.

## procedure

A step-by-step playbook the assistant follows.

- Required frontmatter: `schema`, `title`, `intent` (one sentence: when the
  assistant should use this procedure).
- Optional frontmatter: `labels`.
- Body: an ordered list of numbered steps. Steps are written to the minimum
  agent contract (ADR-0003) — read files, write files, run approved commands.
- Filename: kebab-case, e.g. `file-a-meeting-note.md`.

## goal

One page per goal, with a verification oracle.

- Required frontmatter: `schema`, `title`, `owner`, `status`, `done-when`,
  `next-action`.
- `status` enum: `active` | `waiting` | `done` | `dropped`.
- `done-when` is the verification oracle: a plain-language statement of how
  anyone — not just the author — could check that the goal is complete
  (e.g. "the finished report is in Deliverables/ and the recipient confirmed
  receipt"), not a restatement of the title.
- Optional frontmatter: `labels`.
- Body: context, notes, history.
- Filename: kebab-case, e.g. `finish-quarterly-quality-report.md`.

## decision

A running record of what was decided and why.

- Required frontmatter: `schema`, `title`, `date` (`YYYY-MM-DD`).
- Optional frontmatter: `labels`.
- Body states what was decided, why, and the alternatives considered.
- Filename: kebab-case, e.g. `choose-a-report-template.md`.

## fact

One durable fact per file, with its source where known.

- Required frontmatter: `schema`, `title`.
- Optional frontmatter: `source` (a workspace-relative path or a plain-text
  reference), `labels`.
- Body: the fact itself, stated so it stays useful out of context.
- Filename: kebab-case, e.g. `preferred-report-format.md`.

## person

One page per person **or organization** the user works with.

- Required frontmatter: `schema`, `name`.
- Optional frontmatter: `role`, `organization`, `labels`.
- Body: context, commitments, history.
- Privacy: every record under `Memory/People/` is structurally labeled person
  data (ADR-0004) — no frontmatter label is needed for that to hold.
- Filename: kebab-case, e.g. `alex-rivera.md`.

## profile

The workspace's setup choices. Plain YAML at `System/profile.yaml` — no
Markdown body. The key set is closed to the five required keys and the
optional keys listed here:

- `schema`: `apparatus/profile@v0`.
- `status`: `unconfigured` | `configured`.
- `privacy_mode`: `standard` | `private`.
- `work_types`: list of strings (may be empty).
- `review_day`: `null`, or a lowercase weekday name (`monday` … `sunday`).
- Optional `spend`: `frugal` | `balanced` | `thorough` (the spend level;
  omitted profiles remain valid).
- Optional `key_people`: a list of `{name, role, organization}` mappings.
  `name` is required; `role` and `organization` are optional non-empty strings.
- Optional `current_efforts`: a list of `{title, done_when, next_action}`
  mappings. `title` is required; `done_when` and `next_action` are optional
  non-empty strings.
- Optional `source_locations`: a list of plain-language location strings.

The assistant supplies a complete configured profile to
`apparatus profile apply --stdin` through standard input. The command applies
the credential floor recursively before publishing the profile; interview
answers never belong in command arguments or durable temporary files. Plain
`apparatus profile apply` remains the compatible path for an existing profile
and sanitizes legacy configured answers before deriving records.

## receipt

A machine-written, human-legible record of one machinery event.

- Required frontmatter: `schema`, `event`, `timestamp` (UTC ISO 8601),
  `summary` (one sentence).
- `event` enum, pinned here once for all of v1 — later PRs consume these
  values and no PR extends the enum:
  `check` | `redaction` | `snapshot` | `restore` | `init` | `egress` |
  `library-ingest` | `recall` | `profile-apply` | `backup-export`.
- Optional frontmatter: `labels`.
- Body: the detail — what was examined, found, redacted, archived.
- Filename: `YYYY-MM-DD-HHMMSS-<event>.md` (UTC, all lowercase; same-second
  collisions append `-2`, `-3`, …). The `<event>` in the filename must equal
  the `event` field.
