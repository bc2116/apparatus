# PR-09: check — validators

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` — especially §5, §7 (receipts)
- `docs/adr/ADR-0001-vocabulary.md`
- `docs/adr/ADR-0002-protocol-and-state.md` — record kinds, receipts
- `docs/adr/ADR-0004-privacy-model.md` — receipts; Library content is data
- `docs/plan/README.md`
- `docs/plan/PR-04-record-schemas.md` — the schemas `check` enforces
- `docs/plan/PR-08-cli-skeleton-doctor.md` — registry and exit-code convention
- `docs/spec/workspace.md` — the normative tree and folder semantics

## Objective

`apparatus check <workspace>` becomes the deterministic gate every later verb
and the render drift check build on. It validates every workspace record
against the v1 schemas landed by PR-04, verifies the workspace tree against
`docs/spec/workspace.md`, fails closed with actionable messages and a non-zero
exit, and writes a check receipt under `System/receipts/`. Alongside the verb,
conformance gains its first full workspace fixtures: one valid golden
workspace and three deliberately invalid ones, pinning both directions of the
validator's behavior as executable spec.

## Deliverables

- `packages/apparatus-core/src/apparatus_core/check.py` — the check engine:
  tree verification, record discovery, schema validation, findings model.
- `packages/apparatus-core/src/apparatus_core/receipts.py` — shared receipt
  writer used by this and later verbs (snapshot, memory, egress) — created
  here if PR-10 has not landed yet, otherwise reused as-is (whichever PR
  lands first owns creation; same `write_receipt` API either way).
- `packages/apparatus-core/src/apparatus_core/commands/check.py` — argparse
  wiring (`register`/`run`) following the PR-08 registry contract.
- `packages/apparatus-core/pyproject.toml` — modified: register the `check`
  verb in the `apparatus.commands` entry-point group.
- `conformance/workspaces/golden/` — a complete valid workspace fixture.
- `conformance/workspaces/invalid-bad-frontmatter/` — malformed YAML
  frontmatter in one record.
- `conformance/workspaces/invalid-missing-required-field/` — a goal record
  with no done-when (verification oracle).
- `conformance/workspaces/invalid-unknown-kind/` — a record whose `schema`
  field (`apparatus/<kind>@v0`, per PR-04) names a kind that is none of the
  seven from ADR-0002.
- `conformance/test_check.py` — asserts both directions (see below).
- `packages/apparatus-core/tests/test_check.py`
- `packages/apparatus-core/tests/test_receipts.py`
- `docs/plan/README.md` — modified: PR-09 status row only.

## Acceptance criteria

1. `apparatus check <workspace>` exits 0 with no findings on a valid
   workspace, 1 when any finding exists, 2 on usage errors (missing path,
   path is not a directory).
2. Tree verification: every required entry from the spec tree (`Welcome.md`,
   `Goals/`, `Decisions/`, `Projects/`, `Library/`, `Deliverables/`,
   `Memory/People/`, `Memory/Facts/`, `System/`) must exist; each missing
   entry is one finding. Extra user content is allowed everywhere (see Open
   decisions); dotfiles and dot-directories (`.git`, shim directories) are
   tolerated silently.
3. Record validation: every `.md` file under `Goals/`, `Decisions/`,
   `Memory/People/`, `Memory/Facts/`, `System/procedures/`, and
   `System/receipts/` is parsed as frontmatter + body and validated against
   the PR-04 schema for its folder's kind. `System/profile.yaml` validates
   against the profile schema. Reuse PR-04's parsing and schema modules —
   do not redefine schemas here.
4. Fail closed: an unreadable file, unparseable frontmatter, a `schema`
   field naming a kind that does not match its folder, or one naming no
   known kind is a finding — never a skip, never a warning-only. (The kind
   is declared by the `schema: apparatus/<kind>@v0` field per PR-04; there
   is no separate `kind` frontmatter field.)
5. `Library/`, `Projects/`, and `Deliverables/` contents are not validated as
   records; their content is data, never parsed for instructions (ADR-0004).
   `Welcome.md`, `System/README.md`, and `System/machine-report.md` are
   well-known files: only the machine report's frontmatter parseability is
   checked, when the file exists.
6. Every finding carries a stable machine-readable code (e.g.
   `tree-missing-entry`, `frontmatter-parse-error`, `missing-required-field`,
   `unknown-record-kind`, `kind-folder-mismatch`), the offending repo-relative
   path, and a one-line plain-language fix hint. Tests assert codes, not
   prose.
7. Each run writes one receipt under `System/receipts/` conforming to the
   PR-04 receipt schema and its pinned filename convention
   (`YYYY-MM-DD-HHMMSS-<event>.md`, UTC, all lowercase; a same-second
   collision appends `-2`, `-3`, …) — e.g. `2026-08-08-171530-check.md` —
   so filenames stay unique and sort chronologically. The receipt records
   outcome, finding count, and finding codes in its summary and body.
   `--no-receipt` skips the write for read-only runs; a failed receipt
   write is exit 2 with a clear message.
8. `receipts.py` exposes a single `write_receipt(workspace, event, fields)`
   used by the command; filenames follow the PR-04 receipt filename
   convention, sort chronologically, and are collision-safe.
9. Output vocabulary per ADR-0001: "check", "workspace", "record" — never
   "validate", "lint", or "repo" in stdout text.
10. Stdlib plus whatever YAML/frontmatter dependency PR-04 already
    introduced; no new dependencies beyond those.
11. `uv run pytest` is green.

## Conformance and tests

- `conformance/workspaces/golden/` contains the full required tree plus at
  least one valid record of each kind that can occur in a workspace: a goal,
  a decision, a person, a fact, a procedure, a filled `profile.yaml`, and one
  receipt. All names and contents are fictional; no real people, employers,
  or identifiers.
- Each invalid fixture is the golden workspace minus everything except the
  minimum needed, with exactly one defect, so tests can assert the single
  expected finding code (not merely a non-zero exit).
- `conformance/test_check.py` runs the engine in-process against each fixture
  with receipts disabled (or against temp copies) so fixtures are never
  mutated: golden → exit 0, zero findings; each invalid → exit 1 with the one
  expected finding code.
- `packages/apparatus-core/tests/test_check.py` covers exit codes, fail-closed
  behavior on unreadable files, tolerance of dot-directories, and receipt
  writing into a temp workspace.
- Nothing is wired to CI beyond `uv run pytest`.

## Out of scope

- Fixing anything found — `check` reports; repair belongs to `init` (PR-11).
- Canon/shim drift detection — added to `check` by PR-13.
- Egress checks and labeled-content enforcement (PR-18).
- Library content extraction or indexing (PR-14/15).
- New or changed record schemas; loosening any PR-04 fixture.

## Dependencies

- PR-08 (per `docs/plan/README.md`). PR-04's schemas and PR-07's payload
  content are present transitively (04 → 05/06 → 07 → 08).

## Open decisions

- Are unknown top-level folders a finding? The spec doesn't say. Smallest
  reversible default, used here: allowed silently — users own their
  workspace and files-first means extra files are normal. Tightening later
  is one code change plus a fixture.
