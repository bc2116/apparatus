# First-task certification checklist — certification incomplete

Prepared 2026-09-07 for PR47. The latest integrated build observed in Cursor is commit
`b1290082707322b1e1ab7ba77dda2ddff67f6224`, version `0.0.1`, payload SHA-256
`24e20f0cd31898e66887f21f95a4964fedd36d6f06a5205df14ce20a00b74851`, and
wheel SHA-256 `9971e54fd100d72b54e780215fa37b150a7ea1f1fce122923f1a6a2da744c054`.
Fourteen Cursor runs exercised eleven remaining scenario groups on this build:
ten passed and the partial-PDF case retains its browsing qualification. Earlier
plan/refresh observations retain their qualifications; certification is incomplete. Earlier
PR46 and PR48 failures, fragments and cache workarounds remain dated observations;
they do not complete this checklist. No signed release or app certification is
established. Preserve held PR24 separately. The [matrix](matrix.md) records
actual progress; checklist instructions alone prove no result.

Use the same final core version, commit and payload SHA-256 in every app run.
Record app **and variant**, exact version, OS/version, date, native permission
mode and permitted roots. Use fresh isolated synthetic work areas for each app;
never reuse live projects or provider account data. Run each step through the
actual assistant, then inspect saved files and command outcomes. Record only actually observed actions and outcomes.

Minimal source: `project-a/source.md` says “The practice workshop has two
sessions with 12 places each. Allow a water break after 45 minutes. The venue
is undecided.” Add an existing `project-a/local-note.md` and a custom instruction
sentinel to prove preservation. Keep a sibling `project-b/` and one `Library/`.
Prepare enrollment/adoption and explicit project binding with current core;
retain relative paths only in shared evidence. Cases below are instructions
for future authorized execution, not recorded results.

| Chat | Future action and observable pass condition | Evidence to retain |
| --- | --- | --- |
| 1. Task-first | In an explicitly bound project, ask for `project-a/workshop-plan.md` from the supplied source, with source references and unknowns. It must preserve sentinels, record one sourced Memory fact, and use the canonical Skill body. A Library-registration offer is optional; if accepted, the original stays project-local and its card is grounded. No setup interview, forced central folder, or added Apparatus approval interrupts completion. | Exact app/variant, version, model, OS/version, root/binding, actual prompt, source/output/Skill bytes and hashes, Memory citation, optional registration/card hashes, and minimal assistant text. |
| 2. Fresh recall | In a fresh conversation for the same bound project, ask for a requested deliverable that recalls the first chat's context with citations. Set no-save and prove no automatic Memory, learned-Skill, Library-card, or activity-note capture. Deliberately omit one fact and require abstention rather than invention. | Exact environment identity; fresh-chat proof; cited recall and saved output; before/after retention inventory; missing-evidence prompt and abstention; persisted-artifact and hash oracles. |

The Sep 7 Cursor no-save fragment is recorded in
[`cursor-ide-2026-09-07-memory-controls`](evidence/cursor-ide-2026-09-07-memory-controls/run.json):
the requested `project-b/private-workshop-note.md` was the only added file and
all 140 preexisting files were unchanged. The separately opened bound-project
fragment is recorded in
[`cursor-ide-2026-09-07-bound-project`](evidence/cursor-ide-2026-09-07-bound-project/run.json).
Neither record supplies the two complete lean-RC chats required for a compatible
app/variant row.
The separately requested [no-save Library and snapshot exceptions](evidence/cursor-ide-2026-09-07-no-save-exceptions/run.json)
also passed in independent fresh chats; their scope does not complete the
older full Library or recovery checklist. Those older steps are historical
coverage categories, not additional chats required by the lean RC gate.
The [shared-root guide and Library decline](evidence/cursor-ide-2026-09-07-shared-root/run.json)
also passed, including observed canonical Humanizer use. A later independent
[Library acceptance](evidence/cursor-ide-2026-09-07-library-acceptance/run.json)
kept the original in its project and created a current card with matching hashes;
semantic review preserves a qualification in the generated plan's session
template. A fresh [changed-original case](evidence/cursor-ide-2026-09-07-library-stale/run.json)
returned no evidence and reported stale partial coverage without changing any
work-area files. Separate [missing-original](evidence/cursor-ide-2026-09-07-library-missing/run.json)
and [ignored-original](evidence/cursor-ide-2026-09-07-library-ignored/run.json)
cases also abstained with the correct partial-coverage reason and preserved
every work-area and isolated-cache file. The later [completed scenario inventory](matrix.md#remaining-cursor-scenario-inventory--completed-on-september-7)
records partial/unsupported extraction, learned Skill review/adoption/use, managed
recovery and backup, missing-original restoration, unavailable Git, and all four
quiet-action cases. It preserves the PDF browsing qualification and the limits
of each observation; these are not unrun cases.

The [plan correction and card refresh](evidence/cursor-ide-2026-09-07-library-refresh/run.json)
separates source facts from proposed timing, but also created two Memory records
and an additional saving task. Preserve that qualified result. Earlier prompts
mentioned unsupported `APPARATUS_TASK_ID`; task binding requires the global
`--task ID` option. An environment annotation alone proves no binding. Later
missing/ignored commands explicitly used the assigned task option.

For every chat and independent case, record setup, exact action/prompt, expected
result, actual result, relative evidence paths, and **pass / fail / partial /
unavailable / not run**. Use only the minimal synthetic assistant excerpts needed
to establish behavior; do not export raw conversations or private app state.
A chat passes only when its required outcomes have evidence. A partial or
unavailable requirement cannot silently become a pass. The lean RC gate requires
two passing chats on the same final payload for each named app/variant: Cursor
IDE, Codex desktop, and the actually available Claude Code variant. Separate
desktop, CLI, and IDE variants; optional discovery/delegation observations do
not substitute for actual chats. Automated core/conformance mechanics run once;
each supported OS also needs one installer install-and-repair pass. Label Windows
ARM64 VM evidence explicitly; it cannot replace required x64 evidence. Actual assistant
behavior cannot be inferred from scripts. Defects get concrete reports and
separate repairs; this checklist does not change core or payload behavior.
