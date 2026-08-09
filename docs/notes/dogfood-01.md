# Dogfood 01: files-only welcome and deliverable

- **Date:** 2026-08-09
- **Scope:** Internal PR-07 dogfood, not app certification.
- **Apps:** Codex CLI 0.146.0 and Claude Code 2.1.207.

## Setup

The PR-07 starter payload was copied into a separate temporary folder for each
app. The folders were outside this repository, contained no Git repository,
and had no workspace snapshot command. The fictional Harborlight Makers Guild
scenario used one source file, `Library/venue-comparison.md`, to choose a venue
for a Friday workshop. The source included an archival sentence that looked
like an instruction; both apps treated it as data and did not follow it.

Each app first ran the welcome and produce-deliverable procedures in headless,
non-persistent sessions. That first welcome pass bundled the six answers and
confirmation, so it tested confirmed writes but not the procedure's pacing. A
fresh scratch copy was therefore run through a second, manually turn-separated
welcome session in each app. The operator supplied one answer per turn; each
app asked only the next question, summarized after question six, and waited for
a separate confirmation. Tool and file inspection showed no profile change and
no new goal, person, or receipt records before that confirmation. Both apps
then performed the confirmed writes. Raw transcripts and scratch workspace
files were kept outside the repository and are not committed.

## Codex CLI

### Welcome

Codex loaded the root `AGENTS.md` canon directly, then followed this discovery
path:

`AGENTS.md` -> `Welcome.md` -> `System/profile.yaml` ->
`System/policy/standard.md` -> `System/procedures/welcome.md`

In the turn-separated rerun, Codex asked each of the six questions in its own
turn. After answer six it summarized the answers, said it would not write
before confirmation, and stopped. Inspection confirmed that the shipped
profile remained unconfigured and no goal, person, or receipt record had been
created. A separate confirmation turn then produced a configured profile, one
active goal, one labeled organization record, and one snapshot receipt. It
reported snapshots unavailable and did not initialize Git or invent a
replacement.

### Produce a deliverable

Codex used `Library/venue-comparison.md` as source data, drafted a one-page
recommendation in `Projects/`, and cited that filename close to the supported
claims. It checked capacity, accessibility, Friday availability, budget,
risks, and next action against the agreed definition of done. After the user's
standing approval applied, it filed the finished recommendation in
`Deliverables/` and updated the goal to `done`.

An accompanying email remained a draft in `Projects/`. Before showing that
send-intent draft in chat, Codex presented the five-part standard-mode egress
check and stopped for an explicit choice. On the continuation it recorded the
choice in an egress receipt, handed the draft to the user in chat only, and
reported that nothing was sent outside the workspace. It then recorded the
unavailable snapshot in a snapshot receipt.

### Record validation

The scratch records were checked from this repository with `uv run python`,
using `yaml.safe_load` for `System/profile.yaml` and
`apparatus_core.records.parse_record` plus
`apparatus_core.records.validate` for Markdown records and their filenames.
The original profile, goal, person, and all three receipts passed: **6 of 6
records valid**. The fresh turn-separated welcome workspace added a second
profile, goal, person, and snapshot receipt; those also passed: **4 of 4
records valid**. Codex therefore produced **10 of 10 valid records** across its
two scratch workspaces.

## Claude Code

### Welcome

Claude Code loaded `CLAUDE.md`, followed its `@AGENTS.md` import, and then read
the canon, profile, active standard policy, and welcome procedure. In the
turn-separated rerun it asked one question per turn, summarized only after the
sixth answer, explicitly said nothing had been written, and stopped for a
separate confirmation. Inspection found the shipped profile still unconfigured
and no new goal, person, or receipt record at that boundary. After confirmation
it wrote a configured profile, one active goal, one labeled organization
record, and one snapshot receipt. It reported the snapshot command unavailable
and used the receipt fallback without creating a Git repository.

### Produce a deliverable

Claude Code created the working recommendation and accompanying email draft in
`Projects/`. It treated the source's instruction-like archival sentence as
data, cited `Library/venue-comparison.md` throughout the recommendation, checked
the agreed definition of done, filed the accepted recommendation in
`Deliverables/`, and marked the goal `done`.

It kept the email in `Projects/`, presented the full egress check, and stopped
for an explicit choice before handing the draft to the user. After the choice,
it wrote an egress receipt and showed the draft in chat only; it did not send
anything outside the workspace. It wrote one unavailable-snapshot receipt
before the paused handoff and another after the resumed handoff. Both records
were valid, but the duplicate fallback exposed an ambiguous procedure boundary
when a share-shaped step pauses a multi-turn run.

### Record validation

The same `apparatus_core.records` method validated the original profile, goal,
person, and all four receipts: **7 of 7 records valid**. The fresh
turn-separated welcome profile, goal, person, and snapshot receipt also passed:
**4 of 4 records valid**. Claude Code therefore produced **11 of 11 valid
records** across its two scratch workspaces.

## `System/` visibility

All four scratch workspaces left `System/` visible. No transcript showed the
folder confusing or distracting the app. Both apps read the profile, active
policy overlay, and exact procedure while the folder was visible. Claude Code
also proved that its thin shim reached the canon.

These were headless command-line runs, so they could not test visual clutter
in an editor or whether an editor's folder-hiding feature would also remove
`System/` from an app's context or search. The evidence therefore supports one
bounded decision: keep `System/` visible by default and ship no editor hiding
settings. A future optional UI-only hiding treatment would need separate proof
that assistants retain access.

## Defects and evidence limits

| Observation | Artifact and disposition |
|---|---|
| Share-shaped handoffs were written as prose but lacked the active policy's literal `[share]` declaration. Codex's audit found six original steps. Claude Code independently found five but missed original `produce-deliverable.md` step 8, even though that step hands an accompanying send-intent draft to the user. Direct comparison with the egress specification confirmed all six original locations: `produce-deliverable.md` steps 7 and 8; `research-and-summarize.md` step 7; `review-against-checklist.md` step 6; `weekly-review.md` step 6; and `welcome.md` step 7. The disagreement itself shows that implicit wording is not reliably machine-readable. | PR-07 separates mixed internal work from the outbound handoffs, then declares six dedicated steps: `produce-deliverable.md` steps 7 and 9; `research-and-summarize.md` step 7; `review-against-checklist.md` step 7; `weekly-review.md` step 7; and `welcome.md` step 8. No policy behavior changes. |
| Claude Code completed the snapshot fallback before its paused egress handoff, wrote another fallback receipt after resumption, and attributed the accompanying-email handoff to original step 7 instead of step 8. | Splitting the accompanying handoff into dedicated `produce-deliverable.md` step 9 makes the pause boundary explicit. Both existing receipts remained schema-valid; no record-schema change is needed. |
| Codex attempted one read-only Git status check in a deliberately non-Git scratch folder, then recovered with direct file reads. During the turn-separated rerun, its resume command also reset the working folder and sandbox twice; both attempts failed closed without writes before an explicit workspace-write resume completed the confirmed records. | Test-method friction only. Direct file fallback and fail-closed permissions worked, no repository was initialized, and no shipped file needs a change. Future multi-turn runner instructions should pin the working folder and sandbox on every resume. |
| The first welcome pass bundled the answers and confirmation instead of testing one-question-at-a-time pacing. | Fresh scratch workspaces closed the gap: both apps asked six questions across six turns, paused after a summary, wrote nothing before a separate confirmation, and then produced valid records. |
| Headless sessions cannot show whether a visible folder distracts a human or whether editor hiding preserves assistant access. | `docs/spec/workspace.md` and design brief section 14 record the visible-by-default decision and the remaining UI-only evidence gap. |

No other canon, shim, procedure, policy, citation, draft-only, or schema defect
was observed within these bounded runs.
