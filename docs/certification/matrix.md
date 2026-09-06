# Certification matrix — DRAFT

Updated 2026-09-06. **No reworked core app certification is complete.** These are
partial observations of named local builds, not a signed public release or a
support promise. Held PR24 results cover their original payload.

Release-candidate status: a local checkpoint with a working basic Cursor task,
not a signed public RC or completed app certification. Required Windows CI and
signing remain pending. Cursor is the priority app for remaining acceptance.

## Repaired build — bounded first-task smokes

- Core commit: `1e50521f1aae41759123cc21f1a9f91c9f89a6a9`; version `0.0.1`.
- Wheel SHA-256: `84dea9eb17fcaea356013bb673dfbcc90677962eb2011c00815094327c71b956`.
- Payload ZIP SHA-256: `24e20f0cd31898e66887f21f95a4964fedd36d6f06a5205df14ce20a00b74851`.

This PR49 build is the latest observed baseline. Only bounded shared-root
first-task smokes were completed before the checkpoint; no six-step result
is carried forward from earlier builds. Each app uses an explicit fixture cache,
so these smokes do not verify the default-cache environment.

Codex CLI completed its smoke in 47.91 seconds and saved a sourced plan with a
break after 45 minutes and explicit unknowns. Its final reply correctly stated
that managed snapshots exclude project files. Direct hashes verified all 67
preexisting work-area files and 28 preexisting project Git files unchanged.
The assistant offered Library addition; no acceptance is included in this smoke.
See [run record](evidence/codex-cli-2026-09-06-pr49/run.json) and
[normalized final reply](evidence/codex-cli-2026-09-06-pr49/assistant-final.md).
Claude Code CLI used the same restricted direct-file configuration and an
explicit fixture cache. Task start took 8.23 seconds and the shared-root task
43.08 seconds. Check passed; the final reply honestly reported no ingested
Library evidence and project files outside snapshot coverage. Five original
file hashes and all 28 project Git files stayed unchanged. Its saved **sample**
outline proposes a 15-minute break and another 45-minute block not supplied by
the source. The proposal label and unknown total length qualify those timings,
but break duration is not separately listed as unresolved. This remains a
qualified smoke, not an unqualified content pass. See [Claude record and saved
plan](evidence/claude-code-cli-2026-09-06-pr49/run.json).
Cursor IDE completed its shared-root smoke in 48 seconds with Sol Medium. The
saved 27-line plan explicitly leaves break duration and total session length
unknown and cites the source. The operator observed an explicit-cache snapshot
return no changes and a final optional Library offer; no acceptance followed.
Direct comparison verified all 67 preexisting work-area files and 28 project Git
files unchanged. Nine reads were observed, but the exact canonical Skill body
was not verified in this case. See [Cursor run record and artifact hashes](evidence/cursor-ide-2026-09-06-pr49/run.json).
All app runs have stopped at this partial checkpoint. **No app is certified.**

## Earlier PR48 build — dated partial observations

- Core commit: `7c0c6c4252bf948a0e4dd32decfb35cf308e963d`; version `0.0.1`.
- Payload ZIP SHA-256: `24e20f0cd31898e66887f21f95a4964fedd36d6f06a5205df14ce20a00b74851`.
- Isolated wheel SHA-256: `5b3f11834131f564d0c521d5dfb77a39c9da4d08d13dd50e11bd39c587c02936`.

This build includes PR48. A default-cache diagnostic defect observed during a
Codex run led to PR49. These observations remain attached to the exact earlier
build; successful fragments and workarounds are not relabeled as repaired runs.

## Earlier-build six-step coverage

| AI app / exact variant | Inventory on macOS 27.0 | Observed fragments | Overall | Missing evidence |
| --- | --- | --- | --- | --- |
| Codex desktop, local folder | Version not recorded | Not run | Not certified | Actual session, version and all six cases |
| Codex CLI | 0.153.4 | Shared-root and bound outputs; Fact/guide; Library card after cache workaround | Not certified | Correct final reporting, clean configuration, complete cases on final build |
| Claude Code terminal CLI | 2.1.263 | Root/bound outputs; no-save and requested exceptions; Library offer/decline/card/missing original | Not certified | Correct final reporting, Memory/Skills and complete final-build cases |
| Cursor IDE Agent | 3.18.25 | Shared-root plan; Fact/guide and accepted Library card | Not certified | Bound opening, negatives and complete cases on final build |
| Cursor CLI agent | 2026.09.02-c22c1a3 | Not run | Not certified | Actual CLI execution; no IDE inference |

Codex CLI used Terra Medium, workspace-write, approvals never, ignored user
configuration, ephemeral sessions and no delegation. The first launcher attempt
failed to resolve a native companion. The bundle launcher then saved the
shared-root plan in 43.59 seconds. A 67.25-second bound-project task saved a
correct plan, but its final reply incorrectly called a break **after 45 minutes**
a “45-minute water break.” The 89.69-second Fact/guide fragment saved a managed
snapshot and offered Library addition. Addition took 104.51 seconds and produced
a current card and snapshot after an outside-fixture temporary cache override.
The default-cache error was labelled as a symlink failure; the actual errno was
not retained. The final reply omitted the workaround. This is not a clean
configuration pass. See [run record](evidence/codex-cli-2026-09-06-pr48/run.json)
and [qualified final-reply excerpts](evidence/codex-cli-2026-09-06-pr48/assistant-excerpts.md).

Cursor IDE used Sol Medium with one assistant. The 50-second shared-root fragment
saved a grounded plan and preserved the operator's preexisting hash inventory.
The UI showed use of the canonical produce-deliverable Skill. The 97-second
Fact/guide fragment saved a sourced two-session Fact, edited a reusable guide,
saved a managed snapshot and offered Library addition. The operator accepted;
the 34-second addition kept the original project-local and produced a current
card and snapshot without an observed configuration change. Default product
cache may reside outside the fixture and was not inspected. The assistant's
claim of humanizing is not proof that it read the canonical Humanizer body.
See [run record and artifact hashes](evidence/cursor-ide-2026-09-06-pr48/run.json).
These are fragments, not passing complete Memory, Skill or recovery cases.

A later 46-second Cursor correction followed the operator changing the source
from two sessions to three. The assistant replaced the existing Fact, recalled
one current sourced Fact with three sessions, and saved a managed snapshot.
The original plan and guide remain byte-identical; corrected source/Fact copies
are stored separately. This does not complete the no-save or full Memory case.

Claude Code CLI 2.1.263 made ten bounded calls (407.95 seconds total) with Sonnet 5,
requested Medium effort, restricted safe mode, `dontAsk`, no MCP or delegation,
and portable file fallback. Root/bound outputs, no-save suppression, explicitly
requested Library/snapshot exceptions, offer/decline/accepted card and a missing
original abstention were observed. Three final replies failed semantic review:
one misstated the break duration, and two falsely described untracked files as
backed up by Git. No-save file comparison showed only the opaque task and
requested deliverable added; decline added only a different requested guide.
The first requested Library operation used default cache outside the fixture;
later calls used an operator-owned cache. Prior calls are not relabeled as fully
contained. Parent-directory searches were denied; no extra grant or bypass was
used. Memory creation/correction, learned adoption and full recovery were not
run. See [normalized CLI outcomes, claims and artifact hashes](evidence/claude-code-cli-2026-09-06-pr48/run.json).

No Windows app case has run. A native configuration parse warning in the Codex
lane is recorded only as a generalized diagnostic; no global configuration or
raw session transcript is included.

## Earlier PR46 Cursor diagnostic — preserved

This earlier run used core `78e09ece6225deef9f84e36f42eec3b451aeed84`, wheel
`04d6dfa6a26e513e5955c72d1d17465126d6797829f90300cf59fd5ae7f0dca1`
and the same payload hash above. It is not relabeled as a passing repaired run.

On 2026-09-06 at approximately 11:40 America/Los_Angeles, Cursor IDE ran a
45-second shared-root task with Sol Medium and no delegation. It saved a sourced
workshop plan with two sessions, 12 places each, a break after 45 minutes and unknown
venue; other activities were explicitly provisional. Source, local note, custom
project instructions, root canon and profile hashes remained unchanged. No setup
questionnaire or extra approval pause was observed. The separately opened bound
project case is unrun, so **step 1 remains partial**.

The UI linked “Used apparatus-produce-deliverable” to the exact canonical body.
That is a native usage observation, not completion of step 4. No Library offer
was observed; the short plan was not explicitly a reusable guide, so no offer
pass/failure is inferred. The snapshot attempt failed with a safe-profile-read
error, which the final reply reported honestly. An independent core reproduction
confirmed an external-ancestor alias defect against the same profile inode;
PR48 repaired that boundary. The failure is not an app permission diagnosis or a pass.

See [normalized run evidence](evidence/cursor-ide-2026-09-06-pr46/run.json),
[synthetic source](evidence/cursor-ide-2026-09-06-pr46/project-a/source.md) and
[actual saved plan](evidence/cursor-ide-2026-09-06-pr46/project-a/workshop-plan.md).
This earlier baseline remains diagnostic after repair; no app is certified.

No certified row may omit dated version/OS, shared build identifiers or a
passing required case. Testing a variant does not certify its siblings. Optional
native discovery/delegation, package composition, publisher signatures and live
release publication remain separate evidence.

## Existing metadata-only observations

The supplied records contain no observation timestamps; this is their review
date, not an invented run date. File timestamps do not establish run timing.
All observations are macOS-only. They predate final PR46 certification and used
synthetic probe Skills, not proof of running the final built-in bodies.

| Exact observed variant/version | Recorded condition and result | What remains unproved | Evidence |
| --- | --- | --- | --- |
| Codex CLI 0.153.4 | Project-local `.agents/skills` entry listed; shared work-area body outside independent repository absent. A relative directory symlink was listed; agents-plus-claude paths produced one row; claude-only link absent. | Body execution, pointer following, general precedence/deduplication, final payload and Windows behavior. | [Codex metadata](evidence/codex-discovery-metadata.json) |
| Claude Code CLI 2.1.261 | Project-local, thin-wrapper and directory-symlink cases listed one project row; shared-parent case reported no Skills. Duplicate-path case listed one row. | Restricted project-only settings apply. Thin-wrapper body was never invoked. One duplicate row does not prove deduplication because `.agents` was not independently established as a source. | [Native metadata](evidence/native-discovery-metadata.json) |
| Cursor CLI 2026.09.02-c22c1a3 | Unsent menu/echo observations were inconclusive; no positive synthetic Skill candidate established. | Both discovery and absence; body execution; all IDE behavior. No further support claim follows from the second terminal-menu probe. | [Native metadata](evidence/native-discovery-metadata.json) |

No model prompt or Skill invocation was submitted in those probes. Symlink
observations are diagnostics, not a shipped adapter recommendation. No Windows
link-privilege or native discovery result exists here. New app access and native
permissions must be verified when a run actually occurs.
