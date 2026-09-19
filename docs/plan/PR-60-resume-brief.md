# PR-60 — Read-only resume brief

- **Target:** Apparatus core and command documentation.
- **Branch:** `pr-60-resume-brief`.
- **Plan slice:** N3 in [next-build.md](next-build.md).
- **Dependencies:** PR-58 must be landed before this PR is published, so its final
  Memory-facing guidance and exact payload bytes can be verified. Isolated
  implementation may begin on its reviewed head while CI runs; recut the
  predecessor mapping if the landed bytes differ. PR-59 is not a code
  dependency, but it is delivered before this slice.

## Goal

Add `apparatus resume WORKSPACE`, a small read-only brief for the one explicitly
selected work area. A fresh conversation can use its record links to continue
work without inventing task history, source freshness, or recovery coverage.
It is a summary, not a retrieval engine, dashboard, repair command, or write
boundary.

Read `README.md`, the design brief, ADR-0006, this prompt,
`docs/spec/workspace.md`, `docs/spec/records.md`,
`docs/spec/library-sources.md`, and `docs/spec/managed-recovery.md` before
implementation. The N3 text in `docs/plan/next-build.md` is binding for this
slice. Preserve the current PR-58 final bytes and unrelated work; do not assume
that this draft's source worktree is the execution base.

## Command contract

1. Register one command, `apparatus resume WORKSPACE`; add `resume` to the
   central workspace-verb routing set. It takes no selection, write, repair,
   snapshot, restore, or task-control flags. The global `--task ID` remains
   accepted only through the existing dispatcher and may validate an existing
   task context; its ID and control contents never appear in the brief.
2. A direct work-area argument is read as that work area. When `WORKSPACE` is an
   explicitly bound project, use the existing CLI project-context dispatch and
   `resolve_project_context` route; resolve it to the linked work area before
   every reader runs. The output labels this as `Work-area context`, not project
   context, project-specific goals, task history, or authorship. A missing,
   malformed, changed, unsafe, or mismatched project link is a usage/selection
   failure (exit 2), with the existing bounded binding message. Never ancestor
   search, infer a work area, or open a project outside its explicit link.
3. Render a deterministic plain-text brief in exactly this section order:

   ```text
   Work-area context
   Goals
   Sources
   Latest snapshot
   ```

   Each record link is a work-area-relative `/` path. Sort every listed record
   by that path. Show at most 20 active/waiting goals and 20 registered sources;
   if a section is longer, say exactly how many entries are shown and how many
   remain undisplayed. Never silently make a bounded list sound exhaustive.
   Snapshot output is one latest entry only. An entirely readable work area with
   no matching goals, no registrations, and no snapshots says so plainly.
   Render every source-provided goal `title`, `next-action`, and snapshot `label`
   through one deterministic presentation helper: replace control characters
   (including line breaks) with spaces, collapse Unicode whitespace to one ASCII
   space, trim, and cap the displayed value with an ASCII `...` marker. The
   complete displayed value is at most 240 Unicode code points: retain at most
   237 code points and append `...` only when truncating. Keep fixed
   section/field prefixes outside that value.
   This prevents a record value from forging a heading, completeness statement,
   or diagnostic while retaining useful text. It is syntactic rendering only:
   do not use model judgment, reinterpret the source value, or print raw OS,
   Git, YAML, or exception text on a failure path.
4. Goals use a new small read-only helper owned by this slice. Read only
   `Goals/*.md` through `WorkspaceAnchor` retained-root methods (the same safe
   listing/read pattern as `memory.recall`), parse exact frontmatter, and apply
   the existing `apparatus/goal@v0` validation. In addition, require `title`,
   `owner`, `done-when`, and `next-action` to each be nonblank strings before
   rendering: the generic validator currently permits non-string required
   values, which are not safe resume fields. Select only `status: active` and
   `status: waiting`; show each relative record path, status, title, and
   `next-action`. Do not add fields, write a goal, create `Goals/`, or use
   `check` as a reader. A missing Goals directory, unreadable/reparse file,
   malformed frontmatter, invalid schema, non-string/blank required goal field,
   folder mismatch, or changed root makes the Goals section `unavailable` with
   one actionable repair message. It must not print a partial list as complete.
5. Sources use only the existing no-write selected-source catalog reader
   `library.sources.list_sources`. It returns registrations and its truthful
   availability states (`available`, `missing`, `unavailable`, `unsafe`, or
   `ignored`) without opening source content. List the registered relative path
   and availability, plus only the applicable current repair guidance:
   missing originals remain selected and need an explicit repair/re-registration
   decision; ignored originals require review of `System/ignore`; unavailable or
   unsafe originals need a safe readable path. Do not call ingest, cards, search,
   recall, cache/index readers, or a future relink operation. In particular,
   availability is not extraction, index, search, card, citation, changed-content,
   or freshness evidence. Do not display `fresh`, `stale`, or a time-derived
   substitute unless a future no-write source-evidence API has explicitly
   established it; none exists in this slice. A catalog error is a Sources
   section `unavailable`, never an empty catalog.
6. Add a dedicated snapshot **read-only probe** at the snapshot-reader boundary
   rather than calling `apparatus restore --list` or any command handler. It
   may use the existing `git_available`, work-area layout routing, managed
   history reader, and `list_snapshots` mechanics, but it must never call or
   import command-level `snapshot.run`, `restore.run`, `take_snapshot`,
   `restore_snapshot`, `mark_snapshots_unavailable`, `update_report`, `doctor`,
   receipt publication, store initialization, or a Git write operation. It
   returns one of: `latest` (identifier, UTC timestamp, label, and scope),
   `none` (history safely inspected and empty), or `unavailable` (including
   Git absent, disabled/unreadable history, malformed managed state, or safe
   inspection failure). Do not conflate `none` with `unavailable`.
7. For a `managed-state` latest snapshot, state the actual declared coverage:
   it covers validated goals, `Memory/Facts`, `Memory/People`,
   `Memory/Decisions`, and legacy `Decisions` in every lifecycle state
   (current, outdated, and forgotten), `System/procedures`, non-recovery
   `System/receipts`, selected source registrations/cards and adopted-Skill
   ownership where present, and the named canon/shim/policy/guidance files
   declared by managed recovery: `AGENTS.md`, `CLAUDE.md`, `Welcome.md`,
   `.cursor/rules/apparatus.mdc`, `.github/copilot-instructions.md`,
   `System/profile.yaml`, `System/ignore`, `System/README.md`,
   `System/guidance/model-guidance.md`, and the standard/private policy files.
   It also covers exactly the named built-in Skill bodies where present, rather
   than recursively covering `.agents/skills`. Recovery-generated `snapshot`,
   `restore`, and `backup-export` receipts are excluded. It excludes project
   files, Library originals, extraction/index caches, task controls, project
   bindings/routing, and recovery storage. For a legacy workspace snapshot,
   show its existing scope label and say that this command has no managed-state
   coverage declaration for it. Never assert that a saved point contains any
   individual listed source or goal, or that it captures unsaved project work. A
   missing or unavailable snapshot affects this section only.
8. Return 0 for a fully inspected brief, including truthful empty sections and
   a safely empty snapshot history. Return 1 when a section is unavailable or a
   listed source is not `available`; retain the other readable sections and
   label the result partial. Return 2 only for invalid/missing/non-directory
   workspace selection, explicit-binding resolution, or an internal command
   contract failure. Diagnostics must be bounded, path-safe, and free of raw OS,
   Git, YAML, environment, or credential-bearing text.

## Read-only and safety invariants

The command must leave the complete workspace tree byte-for-byte unchanged on
every outcome: success, empty state, partial state, Git absent, missing history,
malformed goal, unavailable source/catalog, invalid workspace, and bound-project
failure. It creates no directory, cache, receipt, machine report, recovery store,
snapshot, task control, resume record, or temporary durable file. It does not
initialize Git or touch a root/project repository. Do not add a resume record
schema, goal ownership metadata, a source freshness model, a unified retrieval
API, automatic repair, task-close accounting, or a task-control migration.

Use retained-root and existing path-validation primitives throughout; do not add
raw recursive traversal, follow symlinks/reparse points, or reconstruct paths
from unvalidated input. Preserve the catalog's existing portable-path,
case-collision, ignored-source, and changed-root behavior. Preserve every
existing snapshot and restore behavior; this new probe is deliberately separate
because `restore --list` writes the machine report when Git is unavailable.

Hold one command-owned work-area `WorkspaceAnchor` (or the retained work-area
anchor from one resolved bound-project context) from selection through final
rendering. Validate that same root before and after each Goals, Sources, and
snapshot reader, again immediately before rendering, and do not print until all
sections are assembled in memory and that final validation succeeds. For a bound
project, call `ResolvedContext.validate()` at the same final boundary. A changed
direct root or bound context at any boundary is exit 2 with no mixed brief; it is
not a partial section. Existing readers that retain their own anchors, including
`list_sources`, are permitted only inside these outer before/after checks.

## Scope and owned files

Own only the focused surfaces needed for the command:

- `packages/apparatus-core/src/apparatus_core/commands/resume.py` (new);
- the command registry/dispatcher change in `packages/apparatus-core/src/apparatus_core/cli.py`;
- the smallest new read-only snapshot-probe API and tests in
  `packages/apparatus-core/src/apparatus_core/snapshots.py` if it cannot live
  cleanly beside the command without duplicating routing logic;
- `packages/apparatus-core/tests/test_resume.py` (new) and narrow additions to
  `test_project_binding.py`, `test_library_sources.py`, or `test_snapshots.py`
  only when they verify shared no-write behavior;
- `packages/apparatus-core/src/apparatus_core/instruction_updates.py`,
  `starter/payload/AGENTS.md`, its embedded counterpart, exact generated-shim
  sources/goldens, `packages/apparatus-core/tests/fixtures/instruction_updates_pr60/`,
  `packages/apparatus-core/tests/test_pr60_resume_guidance.py` (new), and
  focused instruction-update/migration tests described below;
- narrow additions to `.github/workflows/ci.yml` only when needed to select the
  new resume safety tests in the existing Windows safety CI lane; do not alter
  jobs, permissions, runners, matrices, cache keys, or unrelated test groups;
- the matching exact selector manifest assertion in
  `packages/apparatus-core/tests/test_ci_workflow.py`; keep its baseline list in
  lockstep with the narrow Windows safety selection above;
- `docs/spec/workspace.md` (or one narrowly linked command subsection) and
  `docs/spec/managed-recovery.md` only to describe this command's actual
  snapshot-coverage language;
- this prompt, `docs/plan/README.md` (add PR-60 as `✅ landed` in the same
  implementation PR), and the exact N3 link in `docs/plan/next-build.md`; and
- `docs/certification/evidence/resume-YYYY-MM-DD/` for the one bounded,
  synthetic fresh-conversation goal-continuation record below. Replace the date
  once with the observed date, keep every path relative to that evidence root,
  and retain only prompts, synthetic inputs/outputs, file hashes, outcome, app
  configuration available at observation, and explicit gaps. Do not retain raw
  chat exports, identities, home paths, credentials, or screenshots.

Do not edit starter/payload guidance, embedded payload, Memory writers, record
schemas, Library registration/ingest/index/card behavior, restore/snapshot
command handlers, machine reports, task controls, installers, conformance
fixtures, quickstarts, certification claims, package version, or release files.
The limited canon migration and its generated shims/goldens are the explicit
exceptions below. The command is implementation evidence only; its existence
does not establish a new support or certification claim.

## Canon guidance and exact migration

Make ordinary resume requests discoverable in the sole canonical `AGENTS.md`.
Immediately after the existing task-context guidance, add one concise instruction
with this meaning: for a request to resume or continue ordinary work, run the
read-only `apparatus resume WORKSPACE` brief, then read the relevant linked
records and current Memory/Library evidence before writing a narrative or
deliverable. It must preserve current task-retention behavior: no-save may read
the brief and existing evidence, but it does not create managed content; requested
project work remains possible. The command does not replace existing explicit
Memory, Library, task, source-grounding, or user-authority rules.

Use the same exact-byte, stock-only migration discipline as PR-58. After PR-58
lands, capture its **landed** canonical `AGENTS.md` bytes as the predecessor:

- add a distinct successor predecessor-digest mapping in
  `instruction_updates.py`; do not alter or reuse PR-58's mapping;
- add `packages/apparatus-core/tests/fixtures/instruction_updates_pr60/AGENTS.md`
  containing exactly those landed PR-58 predecessor bytes;
- update both canonical source and embedded payload copies of `AGENTS.md` with
  identical bytes; update generated shim sources and their exact golden outputs
  only through the existing render contract; and
- add focused migration tests that prove exact predecessor LF and CRLF upgrades,
  rendered-shim equality, custom canon preservation, valid Skill/task-control/
  Memory/project-file preservation, and repeat-run idempotence.

Do not migrate a canon merely because its prose is similar. If a competing canon
change lands first, recut the mapping and fixture from its verified final bytes
and rerun the focused tests. This is a concise discoverability addition in N3,
not a new onboarding flow or a payload-wide rewrite.

## Acceptance and validation

Add deterministic tests that prove all of the following.

- A work area with active, waiting, done, and dropped goals shows only active and
  waiting goals with their validated `next-action`s, in deterministic order;
  record links are usable relative paths and the bounded-count disclosure is
  accurate.
- A goal with a scalar/list/mapping value for each of `title`, `owner`,
  `done-when`, or `next-action`, and each blank-string variant, makes the Goals
  section unavailable rather than coercing or rendering that field.
- Multiline/control-character titles, next actions, and snapshot labels cannot
  create sections or headings, alter the partial/completeness result, or expose
  raw tool diagnostics. Assert the fixed whitespace renderer, an untruncated
  exactly-240-code-point value, and a 241-code-point value rendered as its first
  237 code points plus ASCII `...`; leave the stored record/snapshot bytes
  unchanged.
- Empty readable goals/sources/history produce the truthful empty brief. A
  missing snapshot history changes only the snapshot section.
- Missing, invalid, malformed, unsafe, or concurrently changed goal state yields
  a partial/unavailable Goals section and never calls a writer. Include a
  malformed selected-source registration/catalog and every source availability
  reason without inventing freshness or reading source bytes.
- A bound project resolves to exactly its linked work area. Missing/malformed,
  replaced, moved, unsafe, or workspace-ID-mismatched binding is rejected before
  the brief reads the wrong root. A project name must never be reported as a new
  ownership boundary.
- Replace the direct work-area root between sections and replace the bound
  project/work-area context at each reader boundary. Each case must return exit
  2 before output, with no mixed brief and an unchanged tree; assert the final
  `ResolvedContext.validate()` call for the bound case.
- Managed latest, legacy latest, empty history, list failure, and Git-absent
  probe results are distinct. Assert exact managed coverage/exclusion language.
  Instrument the unavailable-Git path so any call to machine-report update,
  snapshot/restore handler, store initialization, receipt writer, Git mutation,
  or doctor fails the test. This directly covers the `restore --list` regression.
- For every success and failure fixture, capture an immutable recursive tree
  before and after and assert equality. Include no-save with an existing task:
  it reads the valid next action and writes neither managed content nor task
  state. Include POSIX symlink and Windows reparse-path patterns using the
  repository's existing platform fixtures; a local platform skip is not Windows
  proof. Add the new resume safety tests to the existing Windows safety CI
  selection, update `test_ci_workflow.py`'s exact baseline-selector manifest in
  the same change, and verify that both CI diffs are limited to that selection.

Run focused tests while implementing, then at least:

```sh
uv run pytest packages/apparatus-core/tests/test_resume.py packages/apparatus-core/tests/test_project_binding.py packages/apparatus-core/tests/test_library_sources.py packages/apparatus-core/tests/test_snapshots.py
uv run pytest packages/apparatus-core/tests/test_instruction_updates.py packages/apparatus-core/tests/test_pr60_resume_guidance.py conformance/test_render.py conformance/test_payload.py
uv run python tools/build_payload.py
uv run pytest
git diff --check
```

After PR-58 is actually landed, perform the planned bounded fresh-conversation
acceptance in the owned synthetic evidence directory: one earlier saving task
updates a goal next action; a fresh no-save conversation invokes the brief,
reads the linked current Memory/Library evidence as appropriate, and saves only
its requested project deliverable. Keep source availability versus freshness,
snapshot coverage, unavailable sections, and app/native gaps explicit. Do not
launch AI CLIs, retry wording to force a pass, export raw chat data, or create a
new certification claim from deterministic tests.

## Codex execution prompt

Implement PR-60 on `pr-60-resume-brief`, and verify the landed PR-58
base before publishing. Preserve unrelated WIP and use the existing retained-root binding, catalog,
record, and snapshot readers. Add the smallest deterministic `apparatus resume
WORKSPACE` command and dedicated no-write snapshot probe described above. Prove
byte-for-byte immutability and the Git-absent no-machine-report path before
running the full suite. Keep all unavailable/partial distinctions visible, then
report exact test results and any unavailable native acceptance coverage. Prepare
only externally authorized delivery actions; this prompt grants no external
authority.
