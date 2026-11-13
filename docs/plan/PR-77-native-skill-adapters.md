# PR-77 — Native Skill adapters

- **Target:** Apparatus core render, check and project binding; Skill and
  workspace specs.
- **Branch:** `pr-77-native-skill-adapters`.
- **Plan slice:** Owner direction 2026-11-12, second of three Native Reach
  prompts (following the 0.0.3 release delivery in PR-75). This is the adapter
  cut that the rework sequence names R4b.
- **Dependencies:** PR-75 landed on `main`. Independent of PR-76; the two touch
  different engine files. Whichever merges second rebases its quickstart, README,
  and changelog edits.
- **Capability:** strong tier at medium-high effort for implementation;
  frontier tier at high effort for review, because this writes into user
  project folders.

## Goal

Make the Skills an AI app can already read by path appear in that app's own
Skill listing, in the work area and in every bound project, without a second
editable copy. `apparatus render` writes small generated adapter files that
carry each Skill's name and description and point to its one canonical body.

**Owner priority decision, 2026-11-12:** build the adapters on the documented
discovery paths now. Earlier planning required runtime discovery evidence
before any adapter; the [bounded probe](../certification/matrix.md) was
inconclusive and did not justify one. The owner has chosen to build first and
observe afterwards. Observation still limits what is claimed.

Read `AGENTS.md`, the design brief, ADR-0003, ADR-0006, this prompt,
`docs/spec/skills.md`, `docs/spec/workspace.md`,
`docs/spec/managed-recovery.md`, and the
[discovery sources note](../notes/skill-discovery-sources.md) first.

## Where adapters go

The documented paths in the discovery note are the only basis. Do not add a
path that note does not record.

| Location | Adapter files written | Why |
|---|---|---|
| Work-area root | `.claude/skills/NAME/SKILL.md` | Claude Code reads its own project Skill folder. Codex and Cursor document `.agents/skills`, which already holds the canonical bodies, so they need nothing here. |
| Bound project root | `.agents/skills/NAME/SKILL.md` and `.claude/skills/NAME/SKILL.md` | A project that is its own repository does not expose the work area's Skill folder; the matrix records that for Codex CLI and Claude Code CLI. |

Cursor documents `.claude/skills` as a compatibility location, so it can see
one Skill through two roots. Two entries that lead to the same canonical body
are acceptable; record what Cursor actually shows.

## Which Skills get adapters

Exactly the canonical Skills Apparatus owns, when their body is present and
valid: the built-in set from `skills.BUILTIN_PATHS`, and each adopted learned
Skill that has a valid ownership record under `System/skills/adopted/`.

Never for a draft, a legacy procedure pointer, a custom or third-party Skill,
or a module-installed Skill. Those remain user-owned or belong to their own
lifecycle.

## Adapter content and ownership

1. An adapter is a deterministic function of the Skill name, the canonical
   `description` copied verbatim, the relative path to the canonical body, and
   a generator marker. No timestamp, no absolute path, no machine detail.
2. Its frontmatter has `name` equal to its directory and that `description`,
   serialized so any punctuation survives, and it passes the existing
   `validate_skill`. Its body is a generated-file notice and one instruction
   with this meaning: read the canonical body at the stated relative path and
   follow it; that file is the single editable source; if it cannot be read,
   say so and continue without this Skill.
3. The relative path uses `/` separators. In the work area it is relative to
   the work-area root. In a bound project it is built from the binding's
   stored relative work-area path. If that path is missing or unsafe, write no
   project adapters and report why.
4. Ownership is recognized the way pointer files are today: only when the
   complete bytes equal a current or known earlier generated output for that
   target. A marker or header alone proves nothing.
5. Plain files only. No symlinks, no copies of canonical bodies, no global or
   user-home files.

## Lifecycle

1. `apparatus init` (fresh, rerun and adoption) and `apparatus render
   WORKAREA` create or refresh work-area adapters.
2. `apparatus project bind` and `apparatus render PROJECT` create or refresh
   that project's adapters. This deliberately amends two spec sentences: that
   project binding adds no app-specific paths, and that `render PROJECT`
   repairs only its pointer. Rewrite both in `docs/spec/workspace.md` and the
   app-compatibility section of `docs/spec/skills.md` in this PR.
3. An owned adapter whose canonical Skill no longer qualifies is removed by
   the next render.
4. A target occupied by unrecognized bytes is the user's file. Never overwrite
   or remove it. Skip that one target, render the rest, and report each
   conflict by relative path with reconciliation guidance. `render` exits 1
   when any conflict remains; `init` and `project bind` print the same notice
   and keep their own exit status, so a setup rerun is not failed by a
   user-owned native Skill.
5. `apparatus render TARGET --remove-skill-adapters` removes only recognized
   owned adapters and any directory it leaves empty, then stops. It never
   removes a non-empty directory or an unrecognized file. A later render
   creates them again; a persisted opt-out is not part of this PR and is
   recorded under `Open questions` in the design brief.
6. `skill adopt` reports that native adapters refresh at the next render. It
   does not enumerate or write into bound projects.
7. Publish through the existing retained-root, preflight and preimage
   primitives. Preserve concurrent edits and compensate only owned writes on
   failure. Never traverse ordinary project content.

## Check

In a root with at least one owned adapter, `check` reports, with the existing
repair hint style and no Skill text:

- an owned adapter that differs from what render would write (drift);
- a qualifying Skill with no adapter in a root that has others (missing);
- an owned adapter with no qualifying Skill (orphan).

A root with no owned adapters produces no adapter findings, so existing work
areas and bound projects stay clean until the next render, and stay clean
after removal. An unrecognized occupant is never a finding.

## Recovery

Adapters are regenerated, not recovered. Extend the existing sentence in
`docs/spec/managed-recovery.md` that places project native adapters outside
coverage so it also names work-area adapters. Restore neither captures nor
deletes them; rendering after a restore brings them back in line.

## Scope and owned files

- `packages/apparatus-core/src/apparatus_core/render.py` and
  `commands/render.py`; a small new module for adapter generation and
  ownership if that keeps `render.py` readable;
- `project_binding.py` and `commands/project.py` for the bind path;
- `packages/apparatus-core/src/apparatus_core/commands/init.py` and
  `init_deploy.py` where init invokes render and prints conflict notices
  without changing exit status;
- `packages/apparatus-core/src/apparatus_core/check.py` and
  `packages/apparatus-core/src/apparatus_core/commands/check.py` for the three
  findings; `commands/skill.py` for the one notice;
- new tests in `packages/apparatus-core/tests/test_skill_adapters.py`, narrow
  additions to existing render, binding, check and init tests, a conformance
  case if a fixture pins the rendered tree, and the Windows safety selection
  in `.github/workflows/ci.yml` with its selector manifest in
  `test_ci_workflow.py`;
- `docs/spec/skills.md`, `docs/spec/workspace.md`,
  `docs/spec/managed-recovery.md`, and the design brief's `Open questions`;
- `README.md` status text, `CHANGELOG.md` under Unreleased, and the three
  quickstarts, each limited to what was observed;
- `docs/notes/pr-77-verification.md` and dated matrix rows;
- this prompt and the PR-77 row in `docs/plan/README.md`.

Do not change any canonical Skill body, the starter canon, the Skill index
block, record schemas, learned-Skill adoption rules, module installation or
recovery coverage. No canon bytes change, so no instruction migration is
needed. Update conformance fixtures only where the rendered tree is pinned,
deliberately and never to make a failure pass.

## Non-goals

No user-home installation, no symlinks, no per-app option flags, no adapters
for module-installed Skills, no persisted opt-out, no discovery probing
command, and no promise that an AI app invokes a listed Skill.

## Acceptance and validation

Deterministic tests:

- Fresh init, rerun, adoption, `render WORKAREA`, `project bind` and `render
  PROJECT` each produce exactly the expected adapter set, and a second run
  changes nothing.
- Adapter bytes are stable, contain only relative `/` paths, and validate as
  Skills. A description with a colon, a quotation mark and non-ASCII text
  survives exactly.
- Editing a canonical description produces a drift finding and render repairs
  it. Adopting a learned Skill produces a missing finding in a root that has
  adapters, and render adds it. Removing a canonical body produces an orphan
  finding and render removes the adapter.
- An unrecognized occupant is preserved byte-for-byte through init, bind,
  render and removal; render exits 1 and names it; init and bind keep their
  exit status.
- Removal deletes only recognized adapters and empty directories it owns, and
  leaves a root with no adapter findings.
- A missing or unsafe binding writes no project adapters. No absolute path
  reaches any written file.
- A draft, a custom Skill, a legacy pointer and a module-installed Skill get
  no adapter.
- Symlink, reparse-point and case-collision targets are refused through the
  existing path fixtures. A local platform skip is not Windows proof; the new
  tests run in the Windows safety lane.
- Snapshot, restore and backup neither capture nor delete adapters.

Observation, after the mechanism is green and not a gate on merging it. For
each available app among Codex, Claude Code and Cursor, open the app in a
bound project that is its own repository inside a scratch work area:

1. Does the app's own Skill listing show the adapted Skills?
2. Does a request that names one Skill lead the assistant to read the
   canonical body? Use a scratch learned Skill whose body contains a harmless
   marker instruction so the result is observable in the saved output.
3. In Cursor, how are the two roots displayed?

Record pass, fail or unavailable per app as dated matrix rows with app,
version and operating system, plus a short note. Do not create a per-PR
evidence directory. If an app lists an adapter but does not follow it, revise
the adapter's instruction wording once. If it still fails, stop and report to
the owner with the two options, a generated full-body copy for that root or
dropping that root, and do not describe that root as working. Update the
quickstart sentence about unproven thin wrappers only to match what was seen.

```sh
uv run pytest packages/apparatus-core/tests/test_skill_adapters.py conformance/test_render.py
uv run pytest
git diff --check
```

## Execution prompt

Implement PR-77 on `pr-77-native-skill-adapters`. Generate adapters only for
the roots and Skills named above, through the existing render and binding
transactions. Prove idempotence, ownership recognition, occupant preservation
and relative-path-only output before the full suite. Amend the two spec
sentences deliberately. Then run the per-app observation where an app is
available and record exact outcomes, including failures. Report test results,
each observed app result and any root you could not verify. Prepare only
externally authorized delivery actions; this prompt grants no external
authority.
