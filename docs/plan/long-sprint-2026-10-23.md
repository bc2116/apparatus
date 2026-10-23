# Long sprint: finish and qualify the next release

- **Status:** Execution selected by the owner on 2026-10-23. S1 and S3 are landed;
  S4 records the successful signed rehearsal. Publication is held for approval.
- **Verified starting source:** `1e8df7debc0aeb25062ad74fa13b54efe5591568`.
- **Starting delivery state:** public core version `0.0.2`; the completed
  [prior cycle](next-release-features.md) established source-build acceptance.
- **Outcome:** deliver accumulated core improvements through the existing release
  process, with at most one justified small workflow addition before the freeze.
- **Size:** five planned PRs, eight maximum including decisions, repairs and
  conditional work. Publication itself is an operational step, not another PR.
  Planning labels below do not reserve PR numbers.

Execution admission: S2 and C1 are omitted under the capacity policy, without
running an example comparison or admitting a new feature. S1 records that scope
decision. The retained sequence is PR-72 inventory, PR-73 candidate, PR-74 signed
rehearsal and PR-75 delivery. The original eight-PR ceiling remains binding;
account observations stay outside the repository.

After the reserve checkpoint, the owner explicitly authorized using the reserve
to merge GitHub PR #74 and run the signed rehearsal. This bounded continuation
covers S3 merge and S4 verification/delivery. S5 publication remains withheld;
it does not reopen optional work or authorize a release tag.

## What moves the product forward

The main opportunity is to get already-built improvements into a qualified
release. Verifiable Memory saves, the resume brief, recovery improvements and
the newer PDF dependency floor exist in source. Their exact delta from the
public package belongs in the release inventory, not an inferred feature list.
The latest document-review experiment did not justify another Skill or module.
Do not repeat that experiment merely because more capacity is available.

The one proposed addition is **requested meeting notes from supplied text**:
decisions, actions, stated owners, stated dates and unresolved questions, saved
in the project. Start with a reusable example using existing Skills. This is a
proposal to select a new, bounded workflow, not evidence of unmet user demand
or approval for a second module. No active Skill or module ships by implication.

The sprint ends at the first of completion, a confirmed usage reset to 99–100%
remaining, the existing 30% remaining reserve, or an execution blocker with no
independent in-scope work. A long sprint is resumable; it need not remain active
until the calendar reset if useful authorized work is finished.

## Authority and scope

[ADR-0006](../adr/ADR-0006-lean-workspace-and-skills.md),
[ADR-0007](../adr/ADR-0007-optional-mailbox-module.md), the
[design brief](../design/design-brief.md), and the
[release runbook](../release-runbook.md) govern this plan. The completed cycle's
four-PR ceiling is historical; the proposed new allowance is not an extension
used to relabel old work or bypass its deferrals.

The owner selected sprint execution, including routine local work, the
repository's push/PR/CI/merge delivery process and candidate rehearsal. Native
protected approvals still apply. Final public publication remains separate:
prepare the exact candidate and evidence before requesting that approval.
Carry existing authorization forward without asking again.

Core, its portable payload and the existing native installers are the release
scope. Optional-module publication is excluded. Further email testing, including
new supplied-message campaigns, stays deferred; existing regression tests run.
Keep private reference-workspace mappings and account usage observations outside
this repository. Adapt developed ideas in original code and prose only.

## Ordered work blocks

| Block | Concrete result | PR allowance | Entry and completion condition |
|---|---|---|---|
| S1 | Release inventory, scope and operator checklist | 1 | Start with current source/public artifact identity; every proposed release claim maps to retained source and evidence. |
| S2 | One evaluated meeting-notes example, or a documented decision to omit it | 1 | Select this workflow for the new sprint; apply the small comparison below. No second experiment. |
| S3 | Final versioned candidate and refreshed acceptance | 1 | S2 and any admitted conditional work finish or are dropped; tests, installed artifacts and affected app flows qualify that exact candidate. |
| S4 | Signed rehearsal and artifact verification | 1 | Candidate checks pass and dispatch/signing are authorized; all required artifacts and signature results are accounted for. |
| S5 | Publication, native acceptance and final delivery record | 1 | Explicit release authorization; follow the existing staged PyPI/native/GitHub Release sequence. |
| C1 | One demonstrated core usability gap | 0–2 | Admit before S3 only under the trigger below; never add both relinking and discovery adapters. |
| R | A focused release-blocking repair | 0–1 | A reproduced failure affects the retained candidate; independent review and repeated affected checks pass. |

Five planned PRs plus two conditional PRs and one repair gives eight. A scope
decision, split or repair counts. If a block needs more, drop optional work or
revise the plan explicitly; do not create a ninth PR. Publish-related receipts
are included in S4/S5, not hidden extra PRs. A repair needed before a rehearsal
uses R even if discovered earlier. Incorporate this planning document into S1
if it is submitted; do not add a separate uncounted planning PR.

Sequence: **S1 → S2 → optional C1 → S3 → S4 → S5**. S1 inventory gathering and
S2 fixture design may run in parallel. Source freeze, signing and publication
remain sequential. No feature work enters after S3 without invalidating and
repeating the affected acceptance and rehearsal evidence.

### S1 — Make the release delta concrete

Inspect the current main branch, release/tag/package identity and package scope.
Classify changes since the last public release as core behavior, payload,
dependencies, installer/release machinery, optional-module-only, or evidence-only.
Use that inventory to draft `CHANGELOG.md` under Unreleased and a release checklist.
Preserve the old release's historical claims. Choose the next unused version
only after checking both release tags and the package index; `0.0.3` is a
candidate, not a reservation.

Review the release workflow and operator setup read-only. Record whether the
required protected environments, signing providers, runner surfaces and trusted
publisher can be verified; unknown is not ready. Do not inspect credentials or
change account configuration. A credential/setup blocker does not prevent local
candidate work, but it does prevent claiming a signed or public release.

Write one self-contained implementation prompt per admitted PR, covering files,
non-goals, dependencies, acceptance and recovery. Follow the repository branch,
DCO, CI and status-table rules when executing. This document is sequencing, not
a substitute for those prompts.

### S2 — A useful supplied-notes workflow, without another platform

Proposed user request: “Turn these notes into decisions, actions and open
questions; save the result in this project.” Keep the source available and cite
its relevant passages or locations. Never invent an owner, deadline, decision,
commitment or resolved contradiction. Mark unspecified fields plainly. Proposed
actions and accepted decisions must remain distinct.

The default delivery path is a repository documentation example: a copyable
request, output outline, synthetic example and instructions for using the
existing deliverable/checklist Skills with ordinary file reading. Link it from
the appropriate quickstart. Name it a documentation example; it is not included
in the installer unless separately packaged and verified. No new CLI verb,
core record type, background capture, recording, connector, model API, active
Skill installation or automatic Memory update is part of this block.

Use three fixed synthetic cases: clean decisions/actions, contradictory or
missing owners/dates, and a sparse case where there is no decision to infer.
Compare the current Skills with the proposed example, using the same request,
sources, app/model settings and a predeclared answer key. Retain six first
outputs, one per case per arm. Keep the answer key outside worker access when
possible; disclose any weaker isolation instead of calling it blind.

An independent reviewer scores supported decisions/actions, missed explicit
commitments, invented commitments, owners/dates, uncertainty and source binding.
Require zero invented commitments and no lost explicit commitments. Deliver the
example only if it fixes a reproducible baseline omission or reduces essential
human correction without worse source fidelity. Formatting preference alone is
insufficient. These small trials support a bounded decision, not an efficacy claim.

For an accepted example, run a saving task and a fresh no-save continuation.
Inventory managed state after task setup and before work. Requested deliverables
may change; no-save must not add task-derived Memory, goals, Library cards or
learned Skills. A deliberate synthetic follow-up should also preserve unresolved
questions. Reuse existing helpers rather than building a general evaluation tool.

Limit this to six comparison outputs and two acceptance conversations. Preserve
failed outputs. At most two diagnosed repair passes are allowed; any targeted
rerun is additional evidence and consumes the same block's allowance. If the
advantage or delivery path remains unclear, omit the example and move to S3.
Do not replace it with voice, a journal or another module experiment.

### C1 — One conditional core improvement

**First candidate: explicit Library relinking.** Admit only after a real moved
registered-source task demonstrates the burden of remove/add, or the owner
records a deliberate priority override. A synthetic missing-file fixture proves
correctness, not demand. The source scout confirmed the gap; that is not itself
the trigger. Follow [the existing relink constraints](next-release-features.md#b--library-relinking-deferred-by-default).

The first of at most two PRs establishes the transition contract and tests; the
second delivers the full command and qualification. Specify old/new paths,
identity collisions, extraction failure, catalog/cache publication, changed
content, stale cards, no-save, recovery and safe compensation before coding.
Preserve originals and prior registration on rejection. Never search the drive
or move the source. Include Windows and POSIX failure cases. Sequential add/remove
is not a substitute for a safe relink transition. An incomplete command does not
enter the release.

**Alternative: one native discovery repair.** Choose this instead of relinking
only for a reproduced failure in a named AI app/version. First confirm explicit
file-reading fallback still works. Any adapter must preserve one canonical body,
custom content and truthful discovery/use distinctions. An adapter/menu entry
does not prove the assistant used the Skill. Do not promise untested desktop
or CLI variants. If neither trigger exists, spend no PRs here.

Do not start C1 below 45% account capacity remaining. Admit it only if the
complete transition, review, affected app checks and final acceptance can fit
before the stop boundary; otherwise leave a scoped prompt for a later sprint.

### S3 — Freeze and qualify the final candidate

Set the selected version consistently in package metadata, runtime version,
applicable lock metadata, payload manifest generation and changelog. Preserve
the separate development module version. Inventory all changed build inputs.
After S3 merges, nominate its exact merged commit as the immutable release
candidate. Verify merged-source parity and attach final checks to that identity.
S4 and S5 evidence PRs may subsequently advance main, but do not change the
release source. The rehearsal source and eventual release tag must identify
that same candidate commit. Any release-input change requires a new candidate
and repeated affected qualification.

Run the affected tests during each change and the required full `uv run pytest`
for each implementation PR. On the final retained candidate, require current
CI including Windows lanes, build the wheel/sdist and portable payload, and
exercise the installed wheel from a clean external environment. Verify aliases,
fresh init, rerun repair, existing-folder adoption, custom instruction/project
preservation, Memory save/recall, bound-project resume, source citation/staleness,
no-save continuation and managed recovery boundaries. Reuse the
[core-readiness capsule](../certification/core-readiness-2026-10-12.md) as a method,
not a certificate for changed bytes. Capture source, dependency and artifact
hashes and exact changed-state inventories.

Refresh the lean two-chat first-task/continuation checks for the named available
Codex CLI, Claude Code CLI and Cursor IDE configurations, focusing on changed
behavior and final payload identity. Use synthetic work and record app, version,
model, settings and source. Codex desktop is an additional gap to close only if
the actual desktop surface can be exercised; CLI/subagent results cannot stand
in for it. An unavailable surface remains a documented support gap. A failure
on an advertised supported path blocks that claim or the candidate until
resolved; it cannot be relabeled unavailable to avoid repair.

Keep historical observations dated. Do not rerun an unchanged comparison just
to refresh its date. Do repeat affected checks after repairs. Core acceptance
is mandatory even when S2 and C1 add nothing.

Useful existing commands, from the repository root:

```sh
uv run pytest
uv run python tools/build_payload.py
uv build --package apparatus-core --out-dir dist/packages
uv run python docs/certification/evidence/core-readiness-2026-10-12/verify_evidence.py
```

The last command checks historical capsule integrity only. A fresh candidate
needs its own captured results; passing that checker does not execute acceptance.

### S4 and S5 — Rehearse, publish and verify delivery

Follow the [release runbook](../release-runbook.md) without changing its order.
S4 manually dispatches an authorized dry-run for the frozen candidate. Verify
the dispatch's actual source SHA before accepting its results. With the current
default-branch dispatch path, start the run while main is still at the candidate
and before merging S4 receipts; do not assume a later dispatch uses older source.
Inspect the payload, sdist, wheel, two flat bootstrap scripts, Windows executable and
macOS package, plus notes/checksums. Record actual Windows signing and macOS
signing/notarization status, tool identities, source/version and coverage gaps.
Confirm the rehearsal changed neither PyPI nor GitHub Releases. Rehearsal
installers resolving PyPI do not establish installation of an unpublished wheel.

Present the exact candidate, checks, seven-artifact inventory and remaining gaps
for release approval. After approval, use a new matching tag and the protected
publish path; the tag targets the frozen candidate SHA, not the newer evidence
commit at main. After PyPI publication, run the existing acceptance-only workflow
against that same tagged run and published distribution. Require Windows x64
and macOS install-and-repair receipts, source/artifact identity, exact installed
version, shipped-file repair and preserved project content before approving
GitHub Release publication. If native acceptance fails, withhold GitHub Release;
the PyPI publication already exists and cannot be undone or its version reused.

Verify final public attachments, hashes and notes, then unset publish mode as
the runbook requires. If this sprint enabled publish mode, restoring it to unset
is also part of the authorized cleanup after failure, interruption or quota
wind-down, once safe for the active workflow. Do not approve a release gate to
achieve cleanup. If cleanup cannot safely complete, explicitly hand off the
outstanding variable change, exact workflow state and pending gates.
Record exact delivery evidence and update the support
matrix/README only as far as those results justify. Signed wrappers, runtime
acceptance and interactive installer presentation are separate claims. Close
the sprint with the release record, or a precise ready-but-unpublished handoff
when external approval/setup is the only remaining dependency.

## Economical execution and usage controls

Use a capable lead for product decisions and integration. Prefer GPT-6 Luna
medium for bounded source gathering, fixture preparation and mechanical work
against a written spec; GPT-6.1 Sol for harder ordinary implementation. Keep
independent review at least as capable as authorship. Release, privacy,
migration and conditional filesystem mutation work stay with authoring-grade
roles. Record requested and observed model/effort rather than inferring them
from role names.

Use at most two parallel workers plus the lead. Run an independent review after
a worker slot is free, with the prompt, governing ADR and complete diff/evidence.
Workers own disjoint files; one lead integrates. Classify rejections as ambiguous
spec, platform constraint or capability failure before retrying. Two repair
passes maximum; no recursive agents, parallel feature prototypes or repeated
reviews without new evidence.

At execution start, record actual used percentage, remaining percentage, bucket
duration, reset timestamp and observation time privately. Remaining is
`100 - usedPercent`. Check at phase boundaries, before costly new dispatches,
and roughly every 15 minutes during active long work. Shared account use counts;
the sprint does not own the whole balance or the reserved final 30 percentage
points. Preserve the planning/previous checkpoint observations across resumptions.
Name one target account/bucket/reset identity for the owner's reset stop; use
the longer account window observed during this planning session. Do not replace
it with a short-window reset. If several applicable windows exist, respect the
tightest capacity reserve and track their reset identities separately.

| Observation | Required response |
|---|---|
| 45% or less remaining | No new optional block; prioritize integration, verification and handoff. |
| 30% or less remaining | Stop new work and enter wind-down. Do not deliberately consume the reserve to finish a feature. |
| Confirmed target-bucket reset with 99–100% remaining | Enter wind-down immediately; the fresh allowance is not another sprint budget. |
| Lower usage without a reset signal | Recheck the same account/bucket identity and reset timestamp; do not infer a reset from the percentage alone. |
| Usage temporarily unavailable | Avoid new optional dispatches; retry once at the next checkpoint. If still unavailable, checkpoint and stop expanding work. |
| All admitted work complete | Close out; do not generate work or wait idle merely to reach a reset. |

Confirm a reset through a rollover/reset signal and the corresponding near-full
remaining reading for the designated target bucket. A shorter-window reset alone
does not trigger this stop. Prefer a second prompt reading before labeling
an ambiguous transition confirmed. Never redeem a reset credit or buy capacity
to satisfy the stopping rule. These are operator controls, not new product quota
enforcement or a background service.

On wind-down: stop new dispatches; interrupt discretionary drafting, allow only
a short necessary file operation to settle, preserve diffs and evidence, and
record unfinished tests honestly. Do not start a merge, signing run or publish
operation. Save the current branch/worktree, source identity, last passed checks,
active process IDs, remaining failures and one exact next action. Never label
partial changes landed or claim successful acceptance from an interrupted run.
An already-started external release workflow needs a truthful state and pending
gate handoff; do not approve its gates just to finish before stopping.
Complete the publish-mode cleanup above when authorized and safe; otherwise
include it explicitly among the outstanding release obligations.

## Deferrals and completion

Keep email campaigns, personal voice, automatic journal, shared/cloud Library,
scheduling, graph features, cross-CLI execution, general module catalog/update/
removal and a second optional module outside this sprint. A source-level gap is
not automatically a release blocker. Template handoffs largely overlap existing
goals/resume; reconsider only for observed user friction.

Done means the selected work is delivered and verified through its applicable
boundary, or the stop rule has produced a reviewable checkpoint. A checkpoint is
not product completion. The final report distinguishes source changes, installed
wheel evidence, app observations, signatures, native installer results and public
delivery, and lists omitted work with its reason.

## Planning evidence

Two bounded read-only scouts checked current App capabilities and developed
reference-workspace patterns. They confirmed that resume and basic module
deployment already exist; relinking and discovery adapters remain conditional.
The reference review supports explicit handoff/acceptance evidence and careful
Skill adoption, but provides no demonstrated meeting-notes advantage or relink
demand. Those absences remain visible in this plan. Private mappings stay outside
the repository. Independent senior review requested three changes: fix the
release source across rehearsal/tagging, designate the reset bucket, and require
publish-mode cleanup on failure/interruption. The lead applied all three and
the focused recheck approved the execution design on 2026-10-23. This is plan
review, not implementation or release acceptance. Local document checks cover
links, whitespace and private-reference hygiene; product tests remain future
execution work because this change contains only planning documents.
