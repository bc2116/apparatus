# First-task certification checklist — certification incomplete

Prepared 2026-09-07 for PR47. The latest integrated build observed in Cursor is commit
`b1290082707322b1e1ab7ba77dda2ddff67f6224`, version `0.0.1`, payload SHA-256
`24e20f0cd31898e66887f21f95a4964fedd36d6f06a5205df14ce20a00b74851`, and
wheel SHA-256 `9971e54fd100d72b54e780215fa37b150a7ea1f1fce122923f1a6a2da744c054`.
The shared-root, bound-project, Memory-correction/retention and no-save Cursor observations
are passing fragments on this build; they do not complete certification. Earlier
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

| Step | Future action and observable pass condition | Evidence to retain |
| --- | --- | --- |
| 1. Finish useful work | Open the shared root, then an explicitly bound sibling project in a separate case. Ask for `project-a/workshop-plan.md` from the supplied source, with source references and unknowns. It lands in that project, respects the two-session/12-place/break constraints, identifies the undecided venue, and preserves sentinels. No setup interview, forced central folder or added Apparatus approval interrupts completion; native permission prompts remain valid. | Source/output bytes and hashes, selected root/binding, actual command results, minimal assistant text needed to show questions or completion. |
| 2. Control Memory | In a saving task, retain the sourced session count, then explicitly correct it to three using an updated synthetic source. Recall must not present two as current. In a fresh don't-save task, request another project deliverable and prove Memory, learned Skills, cards and activity notes unchanged. Test explicit Library and snapshot exceptions in separate cases; permission for one does not authorize other automatic retention. | Record before/after and recall citations; separate task controls; before/after file inventory for no-save; actual exception results. No provider-retention or historical-erasure claim. |
| 3. Keep one Library | Complete reusable work and observe one brief optional addition offer. Independent decline case: completion stands and nothing is added. Acceptance case: register original and have the current assistant supply a grounded card through current commands; no copied original or symlink. Independently change, remove and ignore an original, plus test partial/unsupported extraction. Stale/missing/ignored content supplies no current snippets or unsupported answer. Card prose never becomes its own evidence. | Original/registration/card paths and hashes; minimal offer/reply; extraction/status/coverage results; grounded claims checked against original bytes. |
| 4. Use portable Skills | Ask for real research/deliverable work and a small prose edit. Identify the sole canonical Skill body actually read. Offer one learned draft, review its exact bytes once, adopt them and demonstrate later file-reading use; draft alone stays inactive. If native delegation exists, observe bounded roles, capability/effort and stopping; otherwise use one assistant successfully. No cross-CLI executor. | Body identifier/hash, concrete output satisfying instructions, reviewed/adopted digest and ownership, optional native controls actually used. Menu visibility alone proves none of this. |
| 5. Recover covered state | Save a real managed snapshot, alter a managed synthetic record, restore it and verify the exact record plus unchanged ordinary project files/originals. Export one-way backup and inspect declared coverage. In a separate case remove an original and restore its catalog: original stays missing and retrieval reports the gap. Exercise unavailable Git separately with an actionable outcome. | Actual snapshot/restore/export IDs, commands, hashes and archive inventory; surviving live task flags; recovery receipts; unavailable-case result. Git presence alone is not a saved point. |
| 6. Stay quiet | Run ordinary check, recall and extraction; no new routine receipts. Perform a real repair and synthetic credential-redacting managed write; retain required redaction/repair/recovery evidence without the credential value. Make an authorized local copy/move/export of the synthetic deliverable with no extra Apparatus sharing review. No sending, upload or publication is needed. | Before/after receipt inventory, existing history hashes, safe diagnostic/action, changed files and minimal interaction evidence. |

The Sep 7 Cursor no-save fragment is recorded in
[`cursor-ide-2026-09-07-memory-controls`](evidence/cursor-ide-2026-09-07-memory-controls/run.json):
the requested `project-b/private-workshop-note.md` was the only added file and
all 140 preexisting files were unchanged. The separately opened bound-project
fragment is recorded in
[`cursor-ide-2026-09-07-bound-project`](evidence/cursor-ide-2026-09-07-bound-project/run.json).
Neither record supplies the remaining Library, Skill, recovery, quiet-action or
negative cases required for a six-step pass.
The separately requested [no-save Library and snapshot exceptions](evidence/cursor-ide-2026-09-07-no-save-exceptions/run.json)
also passed in independent fresh chats; their scope does not complete the
distinct full Library or recovery steps.
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
every work-area and isolated-cache file. Partial/unsupported extraction,
learned Skills and remaining recovery/quiet cases are still required.

The [plan correction and card refresh](evidence/cursor-ide-2026-09-07-library-refresh/run.json)
separates source facts from proposed timing, but also created two Memory records
and an additional saving task. Preserve that qualified result. Earlier prompts
mentioned unsupported `APPARATUS_TASK_ID`; task binding requires the global
`--task ID` option. An environment annotation alone proves no binding. Later
missing/ignored commands explicitly used the assigned task option.

For every step and independent case, record setup, exact action/prompt, expected
result, actual result, relative evidence paths, and **pass / fail / partial /
unavailable / not run**. Use only the minimal synthetic assistant excerpts needed
to establish behavior; do not export raw conversations or private app state.
A step passes only when all its required cases have evidence. A partial or
unavailable required case cannot silently become a pass. Full certification
requires six passing steps for the same final payload in at least three actual
AI apps. Separate desktop, CLI and IDE variants; optional discovery/delegation
observations do not substitute for these steps. Defects get concrete reports
and separate repairs; this checklist does not change core or payload behavior.
