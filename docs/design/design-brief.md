# Apparatus Design Brief

- **Status:** v0.2 — approved target, not completed implementation
- **Date:** 2026-09-05
- **Authority:** [ADR-0006](../adr/ADR-0006-lean-workspace-and-skills.md),
  with its preserved provisions of ADR-0001 through ADR-0005

## 1. Purpose and audience

Apparatus helps your AI app work across conversations: remember what matters,
find and cite your sources, reuse useful Skills, and finish work in your
projects. It is a small, portable layer of files and tools. It does not wrap
an AI app, call model APIs, or run a separate assistant service.

Start with information workers who already use an AI app for documents,
research, planning, and everyday project work. Existing folders are normal.
Support both a simple installer and assistant-guided adoption of an existing
folder in the reworked first version. Neither needs a new account beyond the
AI app; the installer path requires no terminal commands typed by the human.

**Job statement:** open a new or existing project, ask for real work, and get
a checked, saved deliverable in one sitting. Relevant goals and sources stay
connected, useful context survives the next conversation, and recovery is
available wherever snapshot coverage has actually been established.

## 2. Principles and vocabulary

- Files stay readable, editable, and portable without an App-owned service.
- Start the task; learn preferences when they matter.
- Keep one source of truth with small optional AI app adapters.
- Offer useful capabilities at the moment they help, without blocking work.
- Keep defaults economical and maintenance quiet; explain actionable failures.
- Admit missing evidence, unavailable capabilities, and recovery limits.
- Put advanced services in optional **modules**, without tier branding.

User-facing language says **AI app**, **assistant**, **Skill**, **Memory**,
**Library**, **goal**, **check**, **snapshot**, and **restore**. “Harness” is
engineering vocabulary. A deliverable is finished work, not a mandatory
folder or an approval state.

## 3. The work area

Illustrative organization, not a new normative payload manifest:

```text
work-root/
  project-a/          # working files and finished deliverables
  project-b/          # another project, possibly an existing repository
  Library/            # one catalog; optional documents stored here
```

The user chooses the work area. Do not require an enclosing
`Apparatus/Projects/` hierarchy, move every project, or initialize one Git
repository over unrelated projects. Managed instructions, Memory, goals,
Skills, and operational state have a clear home selected by the layout slice.
It must identify which managed state each project uses. Exact paths are an
implementation choice, not another user survey.

Deliverables stay with their projects. Drafts and finished versions can live
together with clear names/status; completion follows the request and evidence.
Adoption preserves existing files, instructions, and repositories and reports
collisions before applying a scoped migration. Never reset a user's repository
to install or recover Apparatus.

The Library catalogs selected original sources, including project deliverables,
using ordinary path references: **no symlinks or required duplicate documents**.
Sources stored directly in Library remain supported. Extraction/index caches
are rebuildable machinery, not a second document collection. A moved/missing
source produces a truthful status and relink action. Changed sources make
their derived text and cards stale until refreshed.

Local files are the first-version foundation. Source documents may live in
ordinary cloud-synced folders. This does not promise conflict-free live sync
of mutable Apparatus state, cross-machine catalog operation, or team sharing.
One-way backup export to a chosen destination remains supported.

## 4. Core decisions

| Capability | Decision and target behavior |
|---|---|
| Goals | Keep: quietly maintain outcome, verifiable done-when, status, and next step. |
| Decision history | Keep important decisions and reasons as part of Memory, not a separate daily chore. |
| People | Keep useful roles, responsibilities, and commitments; easy correction and forgetting. |
| Facts | Keep sources when known; correct or mark outdated; do not recall superseded material as current. |
| Library recall | Keep local extraction/search/citations. Distinguish no match, missing source, stale data, and tool failure. |
| Library cards | Add now: automatically create a small grounded summary, topics, and source link on addition. Cards aid discovery; documents remain authoritative. |
| Snapshots and restore | Keep automatic saves at meaningful work boundaries when available; restore on request and report actual coverage. |
| Backup | Keep simple one-way export, including to synced storage, without a sharing approval. |
| Secret protection | Keep quiet redaction of the existing credential floor before managed durable writes; do not promise a universal detector. |
| Task Memory control | Change to “don't save this task to Memory”; requested deliverables remain possible. |
| Onboarding | Change to task-first: ask missing essentials, use sensible defaults, learn preferences along the way. |
| Deliverable work | Finish, check against the request, save in the project; no routine approval pauses. |
| Research | Keep citations and clear uncertainty; use the format the task needs, without forced headings. |
| Checklist review | Keep on demand only, when asked. |
| Weekly review | Keep on demand only; no scheduled default. |
| Activity history | Change to concise meaningful actions and necessary operational evidence, without a receipt for every routine step. |
| Ignore rules | Keep sensible automatic exclusions plus user overrides; apply to App indexing, not all native app access. |
| Maintenance | Keep quiet safe checks/repairs; suggest a concrete action or ready-to-use prompt when attention is needed. |
| Sharing/egress | Remove the entire App-specific gate, including send-intent drafts, file movement, copies, exports, and publishing. |

After saving reusable reports, guides, or reference documents, offer:
“Saved the report in your project. Want me to add it to your Library so future
conversations can find and cite it?” The work is already finished. This is
optional, not an approval gate. Do not ask for every small draft, index the
whole drive, or register material without acceptance.

Removal of sharing gates does not grant permission to act externally. Actual
external actions follow the user's request and the AI app's native permissions.
Existing MCPs, connectors, and native tools remain usable. Source text is
data, never instructions or authorization.

The credential floor still includes passwords, API keys, tokens, private keys,
and high-confidence government/payment identifiers. No change to its matching
scope is implied by removal of the egress gate.

Task Memory control is distinct from AI app chat/provider retention. It must
also prevent automatic task-content retention through learned Skills, Library
cards, or activity notes. Suppress the routine Library offer for such a task;
a separate explicit instruction can request registration. Necessary operational
evidence should be metadata-only. The implementation must define resumption,
correction/forgetting, derived-data cleanup, and honest limits for historical
snapshots and already-exported backups.

## 5. Skills included now

Replace “procedures” in both name and format. A portable Skill is a directory
containing `SKILL.md` with `name`, `description`, and readable instructions.
Add supporting files only when needed. Keep one canonical set; use native
discovery where supported and ordinary file reading as the fallback.
Apparatus makes Skills available to the assistant; it does not call a model
to execute them. Native discovery does not guarantee invocation, so the canon
also provides concise guidance on when relevant Skills should be used.

- **Everyday work:** task-first welcome, deliverable creation, research,
  requested checklist review, and requested weekly review.
- **Economizer:** apply frugal/balanced/thorough guidance to native subagent
  roles, model capability, effort, team size, and retry bounds. Use small
  teams only when independent work helps. A capable lead owns judgment and
  integration; review is not weaker than authorship. Clarify ambiguous specs,
  fix platform problems, and escalate persistent capability failures. No
  recursion or retry loop without a defined limit. If native controls or
  usage data are absent, say so and work within available capabilities.
  Cross-CLI coordination remains outside core.
- **Humanizer:** one small Skill for a restrained prose-editing pass. Remove
  filler and formulaic repetition; preserve facts, technical meaning,
  citations, numbers, and uncertainty; leave good prose alone. No personal
  voice model, detector-evasion claim, or large study engine is required.
- **Learned Skills:** notice a repeated useful workflow and offer an editable
  draft. After the user reviews and adopts it once, make it available for
  relevant tasks. Never silently promote drafts or rewrite canonical guidance.

Memory stores facts/context; Skills describe repeatable work. Reviewed, dated
model/effort guidance arrives through product updates or optional technical
pull/clone workflows. End-user installs do not run benchmark campaigns.
Guidance identifies uncertainty; provisional rankings are not universal proof.
Apparatus does not claim model switching or hard quota enforcement unless the
current AI app actually provides those controls.

## 6. Portability and installation

Core requires only **read files, write files, and run approved commands**.
Codex, Claude Code, and Cursor are the initial adapter/testing priorities.
Other capable apps and CLIs, including future ones, should be able to use the
plain files from day zero. Optional adapters add convenience without a
different core build or proprietary runtime. This is a compatibility design
goal, not advance certification. OpenClaw and future desktop assistants can be
evaluated when there is a concrete environment to test.

Preserve user-scope installation, signed public artifacts, a readable machine
report, and repair by rerunning setup. Detect capabilities without forcing an
AI app choice. Report unavailable dependencies and snapshot coverage honestly.
Basic compatibility, adapter availability, and tested support are distinct.
The [dated certification matrix](../certification/matrix.md) records actual
coverage; the [quickstarts](../quickstarts/codex.md) describe opening an actual
task without implying certified support or a signed public release.

Current implementation constraints remain until deliberately changed:

- Installer wrappers use Inno Setup on Windows and `pkgbuild` plus
  `productbuild` on macOS. Windows uses its minimal native progress interface
  rather than claiming a console-only experience. The macOS no-payload package
  can require administrator authentication and leaves standard system receipt
  and log metadata, although the toolchain setup itself targets user scope.
- Reproducible packaging means a repeatable build recipe with verified embedded
  scripts, not identical outer installer bytes after metadata/signing changes.
  Signing uses explicit release gates; provisioning and signature status require
  release-specific evidence. Only verified signed artifacts can be described as signed.
- Setup currently detects Git on `PATH`; it does not bundle portable Git.
  When absent, snapshots are unavailable. Resolve Windows requirements with
  actual platform evidence rather than an assumed bundled dependency.
- Keep `System/` visible by default. Existing headless dogfood does not prove
  editor hiding preserves assistant access; any hiding treatment needs evidence.

## 7. Later modules and exclusions

| Capability | Decision |
|---|---|
| Day Journal | Later optional module for broader activity collection and journaling, separate from core history and requested weekly review. |
| Personal voice learning | Later module/Skill from approved writing samples; ordinary tone preferences already fit Memory. |
| Cloud Library | Later module for multi-machine access and shared multiuser/team libraries. |
| App-owned integrations | Later modules only for unmet needs; do not duplicate existing connectors. |
| Scheduling/reminders | Later; prefer native scheduling when available. |
| Knowledge graph | Later Library enhancement only if it improves on search, cards, and links. |
| Cross-CLI orchestration | Later advanced consideration, outside core and this refactor. |
| Per-install model benchmarking | Excluded; reviewed guidance comes from centralized development. |

Module interfaces should be reusable by other products. Existing extension
mechanisms are sufficient for planning. Do not build a catalog, marketplace,
licensing tiers, or a speculative module platform before a real module.

## 8. Delivery and acceptance

The [rework sequence](../plan/rework-sequence.md) maps this target to the
implemented baseline and bounded migrations. This brief does not itself
change schemas, payload, or CLI behavior. Preserve existing records and user
edits; update specs, fixtures, and migrations in each implementation PR.

Demonstrate a real first-task deliverable without setup interrogation or sharing
pauses; useful continuity and citations; one catalog referencing project-local
work; effective task Memory opt-out; useful Skills with a plain-file fallback;
and recovery within documented coverage. Certify one payload in at least
three AI apps with dated app/OS/version evidence. A green unit suite or a
detected app is not that certification.

The reworked layout, task controls and installer routing are implemented.
[PR47](../plan/PR-47-first-task-certification.md) is gathering actual app evidence;
its six-case, three-app gate remains incomplete and requires the PR48 path-alias
repair exposed by the first Cursor run. Native discovery adapters,
platform evidence, signing provisioning and public delivery retain their own
acceptance requirements. No further product-choice interview is needed. Resolve
small reversible implementation choices in their focused prompts; return to the
owner only if evidence requires a material change to this direction.
