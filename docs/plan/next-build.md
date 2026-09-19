# Next build: dependable everyday work

- **Status:** N2, N1 and N3 landed; the bounded backup repair is PR-61.
  [PR-62](PR-62-integrated-readiness.md) records retained N6 source-build evidence.
  N4 and N5 are deliberately deferred; no public release is claimed.
- **Date:** 2026-09-13
- **Readiness review:** 2026-09-18; baseline remains `6ee463d`.
- **Baseline inspected:** `6ee463d`, the current 0.0.2 source baseline.
- **Size:** Up to six planned core PRs; eight PRs maximum for this cycle, including
  necessary splits and any optional pilot. These are planning labels, not
  reserved PR numbers. The count is a ceiling; a useful smaller release can stop earlier.

## What this build should accomplish

A person opens an existing project, asks the assistant to remember a fact or
decision, finishes some work, and returns in a fresh conversation. The saved
context is findable, the next action is visible, relevant Skills are usable,
and selected sources report their availability. Renamed-source repair remains
conditional on demonstrated early-use demand. The assistant states what actually saved and what remains unavailable.

Four priorities guide this cycle: reliable Memory saves, useful resumption,
evidence-backed native Skill discovery, and Library relinking when the early-use
trial justifies it. Preserve the
task-first experience and the plain-file fallback. Add no new account, service,
automatic collection, setup interview, or routine completion approval.

This is a proposed bounded extension of [the design brief](../design/design-brief.md)
and [ADR-0006](../adr/ADR-0006-lean-workspace-and-skills.md). It changes no accepted
decision, implementation status, or support claim by itself.

## Readiness and execution constraints

The bounded scope is suitable for focused implementation. The broader
proposal is a backlog, not an executable release plan: its module infrastructure
depends on demand that ADR-0006 explicitly leaves for later. Start
[PR-58, verifiable Memory saves](PR-58-verifiable-memory-saves.md), alongside
[PR-59, native discovery evidence](PR-59-native-skill-discovery-evidence.md).
Neither depends on the other. Cut N3 next, then use the early-use trial below
to decide whether N4 earns a place in this cycle. N5 depends on N1's actual
results. Keep the six-PR planning allowance and eight-PR ceiling.

Use the current AI app's native delegation for this cycle. Assign bounded
extraction to a fast model, well-specified implementation to a strong model, and
retain capable lead judgment and review at least as capable as authorship.
Do not launch AI CLIs as delegated executors. Ordinary terminal inspection and
tests remain available. New compatibility chats that require launching an AI
CLI are deferred under this run's constraint; retain their historical results
with their original build identity and record the missing current evidence.

Before adding repairs to this cycle, reproduce the reported missing command shim
after core installation and whether rerunning setup repairs it; test installer
wrapper behavior separately. Also reproduce the backup-path-alias case in an
isolated synthetic work area. Test the installer case with core alone first.
A verified core defect
uses a spare slot or displaces a feature; it does not justify module infrastructure.
Credential-pattern expansion is a separate safety change requiring its own
false-positive tests, not an assumed prerequisite for these four improvements.

Keep task-close accounting deferred: the last snapshot is not the task-start
filesystem state and cannot distinguish pre-existing unsaved edits. Direct
writer confirmation solves the immediate saved-record visibility problem.
Keep scheduling, integrations and graph work in their accepted later category;
this review does not turn them into permanent exclusions.

## Core slices

| Slice | User outcome | Dependency |
|---|---|---|
| N1. Observe Skill discovery — [PR-59](PR-59-native-skill-discovery-evidence.md) | Establish what works from an actual project before choosing adapters. | Existing baseline; can run beside N2. |
| N2. Make Memory saves verifiable — [PR-58](PR-58-verifiable-memory-saves.md) | Ordinary remember/save requests produce a confirmed Fact or Decision. | Existing baseline; first implementation. |
| N3. Show current saved context — [PR-60](PR-60-resume-brief.md) | A fresh conversation can assemble a useful resume brief, including without Git. | Existing baseline; integrate with N2. |
| N4. Relink a moved Library original | Point an existing selection at its new location while preserving trustworthy source context. | Existing baseline; prioritize after the early-use trial. |
| N5. Add only the discovery support needed | Relevant Skills are available through tested adapters and the canonical file fallback. | N1 evidence. |
| N6. Verify the combined experience | Demonstrate the retained improvements on one integrated build and prepare accurate release evidence. | Retained N2–N5 slices, with scope deferrals and native gaps explicit. |

N2, N3 and N4 have no technical dependency on one another. N4's scheduling follows
the early-use decision. Changes to shared
canon, embedded payload or migration preimages must integrate in order, using
the preceding landed bytes. Each PR includes its own specs, focused tests and
required full suite; N6 is not a substitute for those checks.

## User outcomes and the early-use trial

Successful storage must lead to useful work. Strengthen N2, N3 and N6 with these
acceptance cases, using existing Memory, Library and goal mechanisms:

- A fresh ordinary request uses relevant current Memory and Library evidence,
  including when its wording differs from the saved records. Include unrelated
  project context and outdated records; the assistant must select appropriate
  evidence, cite its source, and admit missing information. Separate assistant
  query selection from the current keyword-matching contract. This does not
  commission semantic search, an embedding service, or a unified retrieval API.
- Requests to inspect, correct, mark outdated or forget remembered information
  use existing operations and verify their results. Report actual retention
  limits. Do not add a dashboard, a new lifecycle or automatic capture.
- In a saving task, completion or a changed next step leaves the related goal
  accurate through the existing Skill-guided editing path. A fresh resume uses
  that updated state. Under no-save, goal files remain unchanged. Work-area
  context remains shared; do not invent project-specific ownership metadata.

Begin with the two-chat Memory check in PR-58. After N3, try three representative
task pairs: continue a document using an earlier decision, revise work after a
fact changes, and resume an unfinished task with a current next action. Include
a no-save continuation and distractor sources. Use synthetic or explicitly
authorized material; repository evidence stays synthetic and sanitized.

Observe the number of human reminders needed to find context, source correctness,
next-action accuracy, unwanted writes, and whether the resulting work is useful.
Use a short manual evidence note, without background telemetry or a new ledger.
Any context failure gets a bounded diagnosis before adding functionality. A
reproduced need for moved-source repair justifies N4; otherwise defer it and
finish the applicable N6 checks for the smaller release. N6's final integration
check still applies, but the first product-value observation must happen earlier.

### N1 — Observe Skill discovery

Complete the evidence portion of the already planned R4b. Use a small synthetic
Skill to test the work-area root and an independently bound project in available
native app surfaces, starting with Codex desktop for this execution. Submit real
prompts and verify that the assistant followed the canonical body. A menu entry
does not prove use. The existing Cursor IDE, Codex CLI and Claude Code CLI
results remain historical evidence; untested configurations keep explicit gaps.
Record a Windows observation where an authorized native environment is available;
record gaps otherwise. Additional apps do not become prerequisites.

Record app/version/settings, OS, prompt, actual file outcome and pass, fail,
partial or unavailable. Check duplicate-name behavior and preservation of an
existing project Skill. Refresh official discovery documentation when this
slice starts; paths and app behavior must come from then-current evidence.

**Done when:** a concise evidence note identifies which adapter/location pairs
are justified and which retain file-reading fallback. No adapter implementation
or expanded certification claim is required in this slice.

### N2 — Make Memory saves verifiable

Have successful managed Fact, People and Decision saves return a safe work-area-relative
record locator. Add a managed Decision writer using the existing decision
schema, explicit date, lifecycle, redaction and task-retention mechanisms.
Use the existing writer's returned locator rather than guessing its filename.
The Decision writer saves title, explicit date and reason to `Memory/Decisions/`;
existing legacy `Decisions/` records remain supported and are not relocated.
Update the concise canon guidance so explicit remembering requests select the
appropriate writer, verify its saved record and report the result accurately.
Do not infer consent to capture other conversation content.

**Done when:** focused tests cover successful locators, collisions, invalid
input, credential redaction and no-save refusal without partial writes. A real
chat using ordinary "remember this" wording persists a sourced Fact; another
explicit request persists a Decision with its reason. A fresh conversation
recalls the current records. Repeat a no-save case: the requested project
deliverable can save, while Memory does not. Passing cases establish evidence
for those exact configurations, not universal language understanding.
Include a differently worded follow-up and an explicit correction using the
existing writer, so the observed outcome covers useful current recall as well
as storage. The detailed first slice is PR-58.

**Owners:** Memory command/writer, Memory spec, canon migration fixtures and
related conformance tests. Existing correction and forgetting remain unchanged.

### N3 — Show current saved context

Add a read-only resume brief of the explicitly selected work area: active and
waiting goals with next actions, registered-source availability and repair
guidance, plus the latest snapshot and its actual coverage when available.
Link to records so the assistant can read relevant context before writing its
narrative. Keep output bounded and provide a truthful empty-state message.

Resolve a bound project through its existing work-area link. Label the result
as work-area context; it does not establish project-specific goal ownership,
task history, or who made a change. Do not list task controls or identifiers,
create caches, take a snapshot, initialize a store, or write a resume record.
Report source staleness only if existing no-write evidence supports it;
availability alone is not freshness.

Use a dedicated read-only snapshot probe, not `restore --list`: the latter can
write the machine report when Git is unavailable. Resume must not update that
report or invoke snapshot/restore, even on its failure paths.

**Done when:** the brief works with Git present and absent. Missing snapshot
history affects that section only. A missing/malformed goal or unavailable
source is reported without presenting incomplete context as complete. A
no-save fresh conversation uses the brief to identify a valid next action
without adding managed content. Requested project files remain possible.
Exercise the user-outcome cases above: the assistant combines the brief with
relevant existing Memory/Library readers to continue work, and observes a goal
whose next action was updated during an earlier saving task. The resume command
itself remains read-only and does not combine retrieval engines or edit goals.

**Owners:** a small core command using existing record, routing, catalog and
snapshot readers; normative command documentation and focused tests. No goal
writer, new goal fields or task-control schema is needed in this cycle.

### N4 — Relink a moved Library original

Add one explicit operation accepting an existing registered original and its
new work-area-relative path. The user supplies the new location; Apparatus
does not search the drive, move the file or register unrelated documents.
Use existing path validation and transaction/compensation mechanisms.
Specify one compensated publication across the old/new selections and derived
state; sequential calls to existing add and remove are insufficient. Define the
extraction-failure outcome before implementation, including which selection
remains authoritative, and test the failure at each publication boundary.

Registration and cache keys currently depend on the path. Specify the old-to-new
transition rather than promising an unchanged identifier. Re-ingest the new
original. Reuse a card only when its association is updated and fresh content
hashes and extractor evidence establish that it remains supported; otherwise
mark it stale and report the required refresh. An extraction failure must have
an explicit state, never a successful-recall claim.

**Done when:** renamed and moved registered files can be cited at the new path;
old selections no longer produce current hits. Missing, unsafe, colliding or
rejected targets preserve the prior registration. Interrupted publication
compensates its own writes and preserves originals. Changed content cannot
inherit a current card from old evidence. Under no-save, only the existing
explicitly requested Library exception permits the scoped operation; it does
not permit automatic card capture or carry-forward. Include Windows path cases.

**Owners:** Library command, registration/extraction/card helpers and their
specs/tests. If the transaction and card transition require two focused PRs,
use one of the two spare slots; finish both before claiming relink is delivered.

### N5 — Add only the discovery support needed

Implement the smallest adapter set justified by N1. Keep one editable canonical
Skill body, generated pointers where proven effective, exact ownership and
drift handling, and no-overwrite behavior for user content. Bound-project
adapters use the explicit binding rather than discovering another work area.
Built-in and adopted learned Skills retain ordinary file-reading fallback.

**Done when:** real prompts exercise the selected adapters from the relevant
root and bound project, the canonical body supplies the behavior, and existing
custom Skills survive render, repair and repeat binding. A moved bound project
requires the existing explicit rebind and never selects another area by guess.
Unavailable native
discovery leaves core work usable. If no adapter is justified, close this slice
with evidence and accurate fallback documentation instead of inventing one.

Limit new mechanisms to those that fit a focused slice. A substantially
different per-app mechanism uses a spare slot or remains an explicit native
coverage gap. Do not add home-directory installs, cross-app synchronization,
model routing or native delegation work here.

### Retained September 19 scope

The [integrated readiness record](../certification/next-build-readiness-2026-09-19.md)
closes this smaller source-build cycle with verifiable saves, useful fresh
continuation and a reproduced backup destination repair. N4 is deferred because
no early-use case established relinking demand. N5 is deferred because the
available observations do not isolate a discovery-adapter defect. Root named
Skill use passed; bound-project discovery and duplicate-name precedence remain
gaps. The existing file-reading fallback remains available. A deliberately
missing registered source is negative coverage, not demand for N4.

The three representative task pairs now have dated evidence: PR-58 revised work
after a fact changed; PR-60 resumed a current next action; PR-62 continued a
document using a saved Decision on the integrated candidate. These runs retain
their own build identities; they are not three trials of the same candidate.
The optional personal writing pilot is also deferred: no authorized writing
examples or user usefulness assessment is supplied for that separate pilot.
Signing, publishing and native installer release acceptance remain separate.

### N6 — Verify the combined experience

Reuse the existing two-chat acceptance pattern on one integrated core/payload:
finish project work and explicitly save context, then open a fresh conversation
and resume with sourced recall under no-save. Include the moved-source relink
case if N4 was retained, and proof of the relevant canonical Skill body. Record
an explicitly deferred N4 as out of this release's scope. Exercise Git-absent resume
and missing-source handling as bounded negative cases.

Record persisted files and hashes, exact configurations, failures and gaps.
Re-run behavior affected by the changes in available native app variants under
the execution constraint above. Initial CLI variants retain historical evidence
until rerun; an unavailable variant cannot receive a renewed passing claim.
Keep deterministic mechanics in tests and app behavior in actual chats. Native
discovery results remain separate from basic fallback compatibility.

**Done when:** focused and full tests are green and the release-readiness note
states exactly which outcomes passed on the candidate build. Update quickstarts
with tested behavior. Verify packaged payload consistency and applicable native
install/repair checks. Signing, publishing and other external release actions
retain their separate authorization and evidence requirements.

## Optional pilot: drafting from approved writing examples

After the core improvements, use at most one remaining slot for a small voice
drafting experiment through the existing learned-Skill mechanism. Start with
two requested drafting tasks using the user's own writing, explicitly supplied
or registered as Library sources. If the workflow is useful and repeated, offer a short editable Skill
and use the existing review/digest/adoption process. Save only synthetic examples
and a generic experiment recipe in the repository; runtime personal samples
remain in the user's authorized work area.

This is an optional Skill pilot, not a packaged `apparatus-voice` module.
No new module ownership, installer, profile, command, sample collector or voice
measurement engine is needed. Examples guide style; factual claims must come
from task sources. Reading already-approved examples and saving a requested
draft remain possible under no-save; automatic sample, profile and Skill
capture do not. Nothing is sent automatically.

**Success:** the user finds the drafts useful, facts and citations survive, and
the adopted Skill works on a later requested task without added ceremony. An
ordinary sample-guided draft is the comparison; the experiment may conclude
that no reusable Skill or packaged module is needed. No general improvement
claim follows from this small pilot.

## Scope decisions and stopping rule

- Plan for up to six core PRs. Allow up to eight total, including necessary splits and
  the optional pilot. Reduce scope before adding a ninth; the pilot is the
  first item to drop. Release earlier when the retained outcomes are useful and
  verified. Do not hide a large subsystem inside a nominally small PR.
- Verified release-blocking defects take priority and consume an available slot
  or displace a feature. Preserve focused PRs and safe migrations; do not weaken
  tests to meet the count. Re-scope explicitly if essential work will not fit.
- Defer the Journal, prose-check and Library exchange modules, all module
  platform work, and module-preserving installer changes until a packaged module
  has a demonstrated job. Existing core installer defects remain eligible for
  the preceding release-blocking rule.
- Defer goal-management verbs, duplicate/quality findings, forget-history counts,
  task-close accounting and learned-Skill revision/retirement. Existing record
  reading, editing, correction and forgetting remain available.
- Keep scheduling, integrations and graph/shared-Library possibilities in their
  accepted later category. No change to those product decisions is proposed.
- Each implementation prompt owns exact files, migrations, acceptance and
  dependencies. PR-58 and PR-59 are cut; other labels remain outlines. Add ready
  rows to the executable plan only when prompts exist. Prompt readiness is
  separate from executing work and authorizing external delivery actions.

## Source basis

The proposal uses current local product contracts and implementation gaps:

- [Design brief](../design/design-brief.md) and
  [ADR-0006](../adr/ADR-0006-lean-workspace-and-skills.md): task-first work,
  continuity, selected originals, portable Skills and optional later services.
- [Rework sequence](rework-sequence.md): R4b remains the next uncut discovery slice.
- [Memory command](../../packages/apparatus-core/src/apparatus_core/commands/memory.py):
  successful saves currently print a generic message; add supports Facts and
  People, while Decisions already have record/lifecycle semantics.
- [Records](../spec/records.md), [Memory](../spec/memory.md),
  [task controls](../spec/task-retention.md) and
  [recovery](../spec/managed-recovery.md): existing state and safety boundaries.
- [Library sources](../spec/library-sources.md) and
  [cards](../spec/library-cards.md): current remove/add relocation workaround,
  path-derived identity and evidence freshness.
- [Skills](../spec/skills.md) and [certification matrix](../certification/matrix.md):
  existing learned adoption, actual-app limitations and metadata-only discovery
  observations that still need runtime evidence.
