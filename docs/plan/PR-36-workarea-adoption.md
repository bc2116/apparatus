# PR-36: Enroll work areas and bind existing projects

R3b after PR-35. The reviewed recovery backend is the dependency; rebase onto its
verified merge before final validation and delivery. Development uses synthetic
fixtures only. No existing real work area is enrolled as part of this PR.
Read ADR-0006, the design brief, and the PR-35 recovery spec first.

## Result and scope

`apparatus init WORKAREA` creates the new layout in a fresh directory.
`apparatus init WORKAREA --adopt` explicitly enrolls an existing unmarked folder,
including a legacy Apparatus workspace or an existing repository. Rerunning init
on an enrolled work area repairs only declared managed files. Unmarked existing
folders require the explicit adoption option before receiving enrollment; no
implicit conversion during ordinary repair or any read command.

Keep `Goals/`, `Memory/People/`, `Memory/Facts/`, `Memory/Decisions/`, `System/`,
`Library/` and canonical `AGENTS.md` at the chosen root. Project directories use
existing names beside those roots; finished files remain within their project.
Do not create mandatory `Projects/`, root `Deliverables/` or root `Decisions/`.
Preserve those old directories and every existing file if present. No movement,
renaming, deduplication, repository adoption, source registration or Skills-format
migration is implicit. Procedures remain at their current paths until R4.

Publish PR-35's existing `System/workspace.yaml` schema with a freshly generated
UUID only on first enrollment. Reuse the UUID on every repair. Malformed markers,
residual managed recovery without its marker, or foreign occupants of managed
control paths fail before deployment. Enrollment never touches root/project `.git`,
including gitfiles, configuration, indexes, locks or working-tree content.
Old root history remains physically intact but is not listed as managed recovery.
Do not claim a history conversion or offer root-clean replay.

## Concrete project binding

Add `apparatus project bind PROJECT --workspace WORKAREA` and read-only
`apparatus project show PROJECT`. Binding explicitly authorizes only the two
project-side changes described below. Require an already valid enrolled work area
and an existing project directory within it, distinct from its managed roots.
Nested existing projects remain usable, including old `Projects/name` folders;
there is no discovery walk and no requirement to relocate them.

Use a single closed `.apparatus/workspace.yaml` in the explicit project root:

```yaml
schema: apparatus/project@v0
workspace: ..
workspace_id: <matching work-area UUID>
```

The serialized path is portable, normalized, relative to that project directory;
allow the explicit leading `..` components needed to address the chosen area.
Reject absolute/drive/UNC paths, malformed components, symlink/reparse traversal,
unknown/duplicate fields, mismatched UUIDs and a target outside the supplied
work-area relationship. Do not reuse `normalize_workspace_relative` unchanged:
it deliberately rejects `..`, which a binding needs. Revalidate both retained
roots and exact marker/binding preimages at publication. Never search ancestors,
siblings, repository metadata or a global registry to repair a broken binding.
A moved project receives an actionable explicit rebind instruction.

A no-op requires both the exact intended binding and the exact recognized pointer
block. Recreate a missing pointer transactionally. Preserve/report an edited,
malformed or duplicate block; delimiters alone never prove ownership. Recognized
block bytes are versioned constants, including an explicit CRLF equivalent.
A different valid binding is a collision unless `project bind --replace` explicitly
requests retargeting to the supplied valid work area. This permits repair after a
project move without manual deletion; retain the old control/pointer preimages and
compensate both together. Invalid or unknown-schema controls remain repair conflicts.
Do not put absolute machine paths, project content or per-task state in the binding.

Add an exact delimited Apparatus pointer block to the project's `AGENTS.md`, or
create a pointer-only file if absent. The block tells the assistant to read the
binding, validate/resolve it, read the selected work-area `AGENTS.md`, and retain
project-local instructions and deliverables. It contains no duplicated canon,
policy, task choice or project summary. Preserve all existing bytes outside the
owned block, including newline style. Malformed/duplicate markers, non-UTF-8 canon,
unsafe paths or an unrelated occupant of the control directory fail preflight.
Only a proven owned block may later change; never replace an entire custom file.
If app-specific discovery files are explicitly installed for a project, apply the
same owned-block rule; binding itself need only install the portable AGENTS pointer.
Read/write/approved commands remain the fallback; do not claim every app loads it
without adapter evidence. Existing app instructions are never overwritten.

Provide `read_project_binding(PROJECT) -> ProjectBinding | None`,
`resolve_project_context(PROJECT) -> ResolvedContext`, and
`bind_project(PROJECT, WORKAREA) -> BindingResult`. These objects expose exact
retained validation, not ambient active-workspace state. Show returns the explicit
resolved area and opaque UUID without scanning project content. Existing engines
continue to receive an explicit resolved work-area root: do not independently add
ancestor discovery to Memory, Library, receipts or snapshots. The CLI resolution matrix is explicit:

- `backup`, `doctor`, `library`, `memory`, `profile`, `recall`, `snapshot`, `restore`,
  and all `task start/show/no-memory` actions resolve the supplied root's exact
  binding when present, with or without global `--task`. Do this before the outer
  task-operation wrapper. `doctor` uses its existing current-folder default when
  no workspace argument is supplied. No binding means the explicit path itself,
  never an ancestor search; ordinary workspace/profile checks still apply.
- `check PROJECT` validates its binding and exact owned pointer first, then checks
  the selected work area. It never traverses project contents or silently repairs.
- `render PROJECT` only repairs the exact recognized project pointer using the
  binding transaction; it does not render or modify work-area adapters. Work-area
  `render` keeps its existing scope with the new ownership checks.
- `init` retains its explicit destination and rejects a bound project as a work-area
  enrollment target, with a prompt to use the resolved work area. `project bind`
  retains both explicit destinations; `project show` is read-only. These commands
  resolve any supplied task context against the chosen work area without changing
  destination semantics. Unregistered extension verbs are not implicitly rerouted.

Context selection is frozen for the invocation after retained-root/binding validation;
all engines receive that selected root. A later binding edit never redirects a running
operation or reinterprets its task choice. No global active-workspace state is added.

## Deployment, instructions and recovery boundary

Reuse `PayloadPlan`, `OverlayPlan`, `instruction_updates`, and the retained
`deploy_init_plan` publication machinery. Plan every affected path and collision
before any mutation. Integrate enrollment into the same exact-preimage deployment
transaction, validate it through final acceptance, and compensate it with other
owned files if deployment fails. Enrollment is control metadata, not a static UUID
shipped in the payload. A fully committed deployment may remain installed if its
subsequent first snapshot is unavailable/fails; output must distinguish those
states and preserve its marker so no later call falls back to legacy Git.

Current init unconditionally adds `.git` to directory targets when Git is present
and passes `inspect_git_store=True`; remove those assumptions for new/enrolled
work areas. The first snapshot must route to PR-35's dedicated backend only after
successful enrollment. Missing Git reports managed snapshots unavailable, not
failed project recovery. An enrolled no-save task skips the automatic snapshot;
init/adoption grants no blanket snapshot or Memory exception. Do not rewrite a
valid existing profile just to normalize defaults/formatting on a repair; explicit
profile changes keep their existing retention guards. Task controls stay untouched.

Preserve custom work-area `AGENTS.md` byte-for-byte. Recognize the newly retired
PR-34 shipped bytes for exact migration to project-local guidance; preserve CRLF
preimages. Generate missing work-area app pointers from the *final actual canon*,
not blindly from the bundled canon. Existing non-generated/custom pointers that
would conflict are preflight collisions, with concrete reconciliation instructions;
do not silently overwrite them. For enrolled areas, make `render` honor the same
ownership/collision contract. The current renderer overwrites any registered
regular-file endpoint and is not sufficient for non-destructive adoption.
Rendering project-owned blocks must not overwrite root canon or copy it locally.

## Decisions compatibility

New decision records belong in `Memory/Decisions`; existing `Decisions/*.md`
remain readable, checkable and recoverable in place. Scan both declared roots;
report exact source paths and do not collapse same-named distinct records.
PR-35 already captures/restores both. No automatic move is required for this slice.

There is a real lifecycle gap: main's `memory.record_path`, `memory.recall` and
`records.validate` support current/outdated/forgotten only for Facts and People;
`decision` requires title/date and lacks status. Merely moving a folder would not
make decisions usable as current Memory. Recommended bounded completion: extend
those existing kind/root tables, decision optional status/default-current behavior,
and content-free tombstone validation to decisions in both new and legacy roots.
Reuse `commands/memory.py`'s existing correct/outdated/forget transactions and task
guards; no new lifecycle engine or automatic decision writer. Update current-only
recall to include both decision roots and exclude outdated/forgotten title/body.
If that extension is deferred explicitly, docs must call decision CLI continuity
incomplete; do not claim R3 Memory acceptance solely from folder placement.

## Ownership and shared API

The lead owns `project_binding.py`, `commands/project.py`, the command entry point
and `cli.py` resolution; `records.py`, `memory.py`, `commands/memory.py` and their
focused lifecycle tests; all normative docs, plan/status and final integration.

The enrollment author owns `commands/init.py`, narrow `init_deploy.py` changes,
layout-marker creation helpers in `workspace_layout.py`, `test_workarea_adoption.py`
and existing `test_init.py`. Preserve existing safety assertions when deliberately
adapting the changed enrollment semantics.

The instruction author owns `instruction_updates.py`, `render.py`, `commands/render.py`,
`check.py`, `commands/check.py`, corresponding focused tests and welcome/payload
conformance. Keep canonical and embedded starter payload/profile files synchronized.
Remove only obsolete shipped placeholders, add `Memory/Decisions/.gitkeep`, and update
project-local guidance. Coordinate any init-test change with the enrollment author.

Read `PR-36-adoption-api.md` before dependent implementation. No one reverts another
role's work. Do not add a new recovery mechanism, lifecycle framework, registry,
model executor or shared mutable context service. Keep the authoring/migration roles
at frontier/high with independent review; no recursive delegation. At most two
classified implementation repair passes before rechecking the contract/platform proof.

## Acceptance tests and delivery gates

- Fresh packaged init produces one Library and the declared managed roots, valid
  UUID marker and dedicated recovery; no root `.git`, Projects or Deliverables.
  Check is clean without old mandatory folders; repeated init preserves UUID and
  yields a no-change snapshot honestly (currently init treats no snapshot as error).
- Adopt a dirty root repository containing two dirty sibling repositories. Capture
  actual HEAD/index/config plus staged/unstaged/untracked bytes. Init, binding,
  repair, failed collision/late-race rollback, snapshot and managed restore preserve
  every unrelated witness; no project Git discovery is invoked.
- Two differently named projects resolve the same explicit area and one Library;
  their finished files stay local. Exercise nested legacy project paths. A foreign
  nearby marker, moved project, UUID mismatch or absent binding never triggers
  ancestor guessing. Control and pointer creation commit/compensate together.
- Custom canon remains exact; custom adapters are either preserved with their owned
  block or cause a preflight collision with zero writes. Known shipped migration,
  differing line endings, interrupted publication and concurrent custom edits are
  tested with all original safety assertions retained.
- New and legacy decisions retain bytes and paths, appear in check/current recall,
  and use existing lifecycle controls correctly; forgotten decision title/date/body
  disappear from current reads. No silent moving or duplicate-record deletion.
- Live task controls survive conversion, failed enrollment/bind, restore and
  concurrent opt-out. Project CLI routing resolves before task enforcement; no-save
  cannot accidentally become a legacy saving operation in a project directory.
- Existing unconverted workspaces retain explicit legacy behavior; no read command
  enrolls them. All enrolled backup/restore paths use PR-35 and report managed-only
  coverage, excluding project originals/bindings. Installing app pointers does not
  claim their recovery is covered by the managed-state archive.
- Run focused tests, full `uv run pytest`, embedded-payload/conformance checks and
  actual Windows CI. Independent review covers the exact final diff. Follow normal
  branch/PR/remote-main verification and cleanup; no adoption until PR-35 is landed.
