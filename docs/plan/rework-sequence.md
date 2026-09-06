# Lean product rework sequence

**Approved direction, 2026-09-05.** Read
[ADR-0006](../adr/ADR-0006-lean-workspace-and-skills.md) and the
[design brief](../design/design-brief.md) for product decisions. This document
orders implementation; it is not a claim that the rework has shipped.

## Current baseline

At the start of this review, the implemented pre-alpha includes twelve CLI
command families, five procedure files, local Memory and Library retrieval,
snapshots, backup, profile overlays, and packaging machinery. Library ingest
accepts sources in the workspace Library; it does not yet provide a catalog of
project references or generated cards. Procedures do not yet use the native
Skill format. Private behavior is profile-wide, not task-scoped.

The legacy specification also requires the sharing gate, seven-question
interview, separate finished-output folder, and routine receipts. These are
implemented behaviors to migrate, not new product requirements. Existing
tests deliberately pin them. Packaging code and earlier dogfood do not
establish public release, signing readiness, or current app certification.

## Execution rule

PR-31 records this direction only. The following slices are **planned — prompt
not cut**, not ready to execute. Start by cutting PR-32 for R1 below. Each
prompt must state exact owned paths, migration behavior, acceptance tests, and
dependencies; then add its row to the main plan. Do not implement the entire
sequence on one branch. Product decisions below need no repeated interview.

Before each migration, inspect the current code and any intervening changes.
Keep source payload and its embedded package copy synchronized using the
existing build tooling. Deliberately update affected schemas, normative specs,
fixtures, tests, and operator documentation in the same behavior-changing PR.
Never loosen a fixture simply because it conflicts with this future target.
Preserve custom user instructions and legacy records; migration must be scoped,
repeatable, and recoverable, with explicit collision handling.

## Implementation slices

### R1 — Remove the sharing gate

**First implementation slice; no dependencies beyond PR-31.** Remove the
App-specific draft/export/share approval protocol, command exposure, and starter
instructions. Inventory the backup/egress coupling before deleting code: keep
credential redaction, path containment, transaction safety, and source-as-data
protections. Remove the gate from the IT explanation too. Preserve readability
of old receipts, without letting obsolete policies remain active in migrated
workspaces. A compatibility tombstone, if needed, must not run a hidden gate.

**Source owners:** `commands/egress.py`, `egress.py`, `backup.py`, entry-point
registration, starter policy/canon/procedures, `docs/spec/egress.md`, and their
egress/backup/payload conformance tests. Core paths are under
`packages/apparatus-core/src/apparatus_core/`.

**Accept when:** a requested draft, copy/move, and backup export require no
extra App decision; credential-floor and filesystem safety regressions still
pass; native external-action authority is preserved; old receipts remain
inspectable. This slice does not yet remove the private profile.

### R2 — Task Memory control and corrections

**After R1.** Replace global private-mode semantics with an explicit task
retention contract. Define task identity/resumption and how a files-only
assistant carries the instruction to managed writers, without storing task
content in the control marker. Keep requested file deliverables possible.
Make People/Facts correction, forgetting, and outdated status observable in
recall. Decision history remains part of Memory conceptually; physical record
placement is addressed by R3.

**Source owners:** `memory.py`, `commands/memory.py`, `records.py`, profile
overlays, record/workspace specs, and Memory/profile tests. Specify a safe
migration for existing private profiles; do not silently enable retention for
them during conversion. Review snapshot/cache/receipt effects together.

**Accept when:** a synthetic opted-out task leaves no task content in managed
Memory or derived notes; the restriction survives intended resumption; a
requested deliverable still saves; correction/outdated/forget changes affect
recall. Document historical snapshot/export limits honestly. Later Skills,
cards, and history must use this same retention contract, not invent another.

### R3 — Work-area layout and project-local deliverables

**After R2.** Specify the smallest layout supporting sibling projects and one
Library, identifying where instructions, goals, Memory (including decisions),
Skills, and operational state live and how a project finds them. Support a
fresh folder and non-destructive adoption of an existing folder/repository.
Remove mandatory central Deliverables placement. Keep snapshots scoped to
managed/project state they can actually recover; never initialize a repository
over unrelated projects or reset an existing repository as recovery.

**Source owners:** `docs/spec/workspace.md`, payload/deployment/render paths,
`check.py` folder mapping, snapshot/restore scope, starter deliverable guidance,
and layout/adoption conformance. Preserve existing documents and custom canon.

**Accept when:** two sibling projects retain their own finished files; both
resolve their intended managed context; adoption preserves an existing dirty
repository; collisions are reported; repeated migration is safe; restore does
not modify unrelated project work. A missing snapshot facility is reported.

### R4 — Portable native Skills

**After R3.** Migrate procedure names, schema, paths, and discovery together.
Choose one canonical Skill directory set, with optional native adapters and
plain-file fallback. Each `SKILL.md` has name/description and readable body;
do not keep independently editable duplicate copies. Preserve customized
legacy procedures by explicit migration/reporting, not overwrite.

**Source owners:** `docs/spec/records.md`, `records.py`, `check.py`, render and
overlay validation, starter profiles/procedures, manifest and payload tests.
Verify the current public Skill specification and each adapter's actual
discovery behavior when cutting the prompt; do not guess paths from app names.

**Accept when:** the same Skill can be read as plain files and discovered by
each tested native adapter; absent native support leaves core usable; migration
preserves custom content; render/drift checks cover the canonical relationship.

### R5 — Task-first welcome and everyday Skills

**After R4.** Replace interview and feature-selection ceremony with useful
defaults and only missing essential questions. Finish/check/save project work
without routine approvals. Preserve research citations without forced sections.
Checklist and weekly reviews remain requested-only. Ship sensible indexing
ignore defaults; users can change preferences later.

**Source owners:** welcome and everyday Skills, `interview.py`, profile command
and overlay defaults, ignore spec, welcome/feature-selection integration tests.

**Accept when:** a fresh user's actual request produces a saved deliverable
before any optional setup; no seven-question interview, routine sharing pause,
or unrequested review occurs; existing preferences survive rerunning setup.

### R6 — Economizer and lightweight humanizer Skills

**After R4; may be authored independently of R5.** Add small portable guidance
Skills. Economizer selects bounded native roles, capability/effort, team and
retry limits within the spend preference. Check actual available controls and
dated roster data. Keep judgment/review capable and a single-assistant fallback.
Humanizer is one restrained editing pass that leaves good prose alone.

**Source owners:** built-in Skills, `docs/spec/model-guidance.md`, replaceable
guidance data and adapter notes; relevant payload/skill conformance. No model
launcher, CLI coordination, quota service, or benchmark engine.

**Accept when:** representative tasks with and without native delegation use
bounded resources and truthful capability claims; ambiguous specs and platform
failures do not cause blind worker escalation; humanizer examples preserve
facts/citations/numbers/uncertainty, including an already-good negative control.
Use small centrally maintained checks; no per-install trials or efficacy claims
beyond the evidence obtained.

### R7 — Capture learned Skills

**After R2 and R4.** Offer a reusable workflow after useful repetition, produce
an editable draft, and adopt it only after the user's one-time review. Reuse
native discovery and fallback from R4. Factual Memory is not a Skill library.

**Accept when:** an adopted example is available for relevant future work;
rejected/unreviewed drafts cannot activate; task retention control prevents
automatic content capture; no autonomous canon rewriting occurs. Keep the
lifecycle small; no promotion framework or evaluation service is added.

### R8 — Library references to originals

**After R3.** Add a readable registration catalog, source resolution, and
rebuildable local extraction/indexing for selected project documents. Keep
in-Library sources compatible. Bound scope to registered sources; preserve
path validation and reject symlink-based catalog shortcuts. Define relocation,
changed-file detection, unavailable mounts, and truthful retrieval states.

**Source owners:** Library ingest/index/recall, cache handling, Library command,
record/workspace/ignore specs, and extraction/search/recall safety tests.

**Accept when:** a project report is searchable/citable without being copied
or moved; cache rebuild preserves registration; moved, missing, ignored, and
changed sources are handled honestly; irrelevant sibling files are not indexed.

### R9 — Lightweight cards and completion offers

**After R2, R5, and R8.** On source addition, the current assistant writes a
small grounded card with summary/topics/link; core validates provenance without
calling a model. Mark incomplete extraction/card generation honestly. Refresh
or invalidate stale cards alongside sources. Offer Library addition for useful
finished work after completion, avoiding repeated offers for small drafts.

**Accept when:** acceptance registers the original and creates a supported
card; declining leaves the finished deliverable intact; opted-out tasks are
not automatically offered/captured; cards cannot turn unsupported summaries
into source authority; absent extraction is not presented as full coverage.

### R10 — Quiet operations and actionable maintenance

**After R1, R2, R3, and R9.** Reduce routine receipt proliferation while keeping
meaningful history and evidence necessary for redaction, recovery, and repair.
Do not delete old history or replace proven filesystem protections. Retention
control applies to notes, and source content must not leak into diagnostic text.

**Source owners:** receipt producers/schema, doctor/check, snapshot/backup and
repair paths, System guidance, IT documentation, affected operational tests.

**Accept when:** routine work stays quiet; a real failure supplies a concrete
fix/prompt; a synthetic repair and restore have sufficient verifiable evidence;
unavailable recovery remains explicit; no task content enters opted-out notes.

### R11 — Installer and existing-folder delivery

**After R5 and R10, with R6–R9 integrated.** Carry the reworked payload and
adoption behavior through package embedding, installers, rerun/repair, machine
reporting, and user docs. Preserve user-scope setup and signing requirements.
Audit snapshot/backup coverage for registered files outside managed state;
do not imply that backing up a catalog backs up its source documents.

**Accept when:** fresh install and existing-folder adoption reach the same
usable core; repair preserves custom work; unavailable Git is reported; public
signing claims match real artifacts. Packaging checks do not count as native
app certification. Resolve Windows prerequisites with actual platform evidence.

### R12 — Recut certification and prove the first-task experience

**After R11.** Replace the held PR-24 checklist and dependencies in a focused
new prompt, preserving any useful prior work as evidence for its original
payload only. Prioritize Codex, Claude Code, and Cursor. Prove the same payload
across at least three available AI apps with dated versions and OS evidence;
do not substitute fabricated rows for unavailable apps.

Exercise task-first work, project-local completion, Memory control, source
recall/cards, Skills/fallback, snapshot/restore, and absence of sharing gates.
Optional native delegation gets separate capability evidence, not a core
pass prerequisite. Publish concise per-app quickstarts and an honest support
matrix. Future capable apps retain the basic file contract from day zero;
tested support is a separate claim.

## Optional modules: parked, not prerequisites

The [module decisions](../design/design-brief.md#7-later-modules-and-exclusions)
cover Day Journal, personal voice, cloud/team Library, integrations, scheduling,
and graph work. Cross-CLI orchestration is advanced later consideration.
No module blocks this refactor; no speculative module platform is in the
queue. Benchmarks remain centralized development work, with reviewed guidance
distributed through updates. Existing native tools need no App module to work.

## Resume and validation

The next concrete step is to cut the self-contained PR-32 prompt for R1 from
current source, including backup coupling and legacy-workspace migration.
Do not resume the old PR-24 checklist. No product implementation is included
in PR-31, and no further product-choice interview is required.

Each implementation PR runs its meaningful targeted acceptance checks and
the repository-required `uv run pytest`. Record skips/coverage gaps. CI,
signing, actual AI app runs, and release publication are distinct evidence;
report which completed. Budget-limited sessions finish a bounded slice or
leave a clean branch and exact next step rather than starting a broad refactor.
