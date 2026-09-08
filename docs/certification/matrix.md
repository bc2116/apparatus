# Certification matrix — DRAFT

Updated 2026-09-07. **The focused app-chat gate passed for the three named
configurations below. The overall lean RC gate remains incomplete pending
signed installer install-and-repair acceptance.**
Codex CLI, Claude Code CLI, and the named Cursor/Luna variant passed two focused
chats on the candidate below. A separate Cursor/Grok run remains qualified after
an incorrect final timing phrase. These bounded observations establish neither
broad certification nor a signed public release. Held PR24 evidence stays
attached to its original payload.

## Current candidate — explicit Memory capture

- Source commit: `964d5a1738b2d8928ec85b964474bcc8e59b2316`; version `0.0.1`.
- Wheel SHA-256: `a15084de226bacfa9b0936f7417dff11c418f44decd948fa9bd26b00cfa5ac89`.
- Payload SHA-256: `9ef2a754346ace668ac1d64ff6bdfbeae354017dc4e26965f6f10cbfc7819c94`.
- Full exact-head Linux CI: 1266 passed, 45 skipped; focused local checks:
  39 passed, 1 skipped. A redundant local full run was canceled after CI passed.

| App / exact variant and model | Observed result | Remaining qualification |
| --- | --- | --- |
| [Codex CLI 0.153.4](evidence/codex-cli-2026-09-07-pr50/run.json), Terra Medium requested | Two passing chats: explicit sourced Fact, project plan, Library card, fresh cited recall, no-save and missing-duration abstention | Casual “remember” still omitted the Fact on this payload; explicit wording is required by the passing case. Desktop remains untested. |
| [Claude Code CLI 2.1.263](evidence/claude-code-cli-2026-09-07-pr50/run.json), Sonnet 5 Medium | Two passing chats with the same persisted outcomes; both results report no native permission denials | Native auto permission mode and restricted tool setup are specific to this run; earlier denied configuration remains separate. |
| [Cursor IDE 3.19.13](evidence/cursor-ide-2026-09-07-grok-isolated/run.json), Grok 4.6 High, Fast off | Persisted facilitator note was correct and existing files were preserved | Native final prose called the timing a “45-minute water break”; this remains qualified failure evidence. |
| [Cursor IDE 3.19.13](evidence/cursor-ide-2026-09-07-luna/run.json), GPT-5.6 Luna Medium | Two native chats passed: sourced plan, verified Memory fact, Library card, cited recall, accurate facilitator note, and 85 pre-existing files unchanged in no-save | Canonical Skill use was observed through the prompted path; automatic discovery, OS confinement, retention, signing, installer repair, and broad certification remain untested. |

The passing explicit request says “Save a Memory fact” and asks for verification.
Do not infer that the instruction repair alone fixed casual “remember” requests.
All runs use the same installed wheel and payload with the default work-area
cache. Their native configurations, permitted roots and tool-read observations
are recorded separately; these tests do not establish operating-system read
confinement, provider-retention controls, or another app variant's behavior.

The [unsigned release rehearsal](evidence/release-rehearsal-2026-09-07-pr50/run.json)
completed and all seven distributable checksums matched. Its wheel and payload
are byte-identical to the local test build. The Windows ARM64 VM wrapper dry run
exited 0 and left all 67 work-area files unchanged. A dry run is not full installer
acceptance and cannot replace required Windows x64 evidence. Signing and
publication were skipped; PyPI still needs its first package publication.

## Earlier September 7 build — focused observations

- Core commit: `8953d374ee5e6ce751ba2217aac24f5e6f2a7486`; version `0.0.1`.
- Wheel SHA-256: `33fc6440e63b03487370dd626426ca68ad37e1a866851cc279f4ccc5f3023ed8`.
- Payload SHA-256: `24e20f0cd31898e66887f21f95a4964fedd36d6f06a5205df14ce20a00b74851`.
- Integration commit `58507bfacf1b58492df9bcc249ae3832d1125607` has exactly the
  same Git tree (`251fa6d087b6f28a81e489bccdd0d3f2e5879ed1`).

Each app used a fresh synthetic bound project and the explicit isolated runtime,
with the default work-area cache. This is package-based app acceptance, not a
system-installer test. The final integrated core suite passed: 1269 tests passed,
38 skipped. Native Windows CI is recorded independently.

| Exact AI app / model | Saving chat | Fresh no-save chat | Bounded result |
| --- | --- | --- | --- |
| Cursor IDE 3.19.13, Grok 4.6 High, Fast off, macOS 27 | Pass: sourced plan, saved Memory fact, grounded Library card, canonical Skill verified in a same-chat follow-up | Qualified: saved note and recall passed; all 85 existing files unchanged; final reply mislabeled break timing as break length | Two chats recorded with final-reply qualification; [evidence](evidence/cursor-ide-2026-09-07-lean-rc/run.json) |
| Codex CLI 0.153.4, Terra Medium, macOS 27 | Fail: plan and Library card created, requested Memory fact omitted | Partial: no-save preservation passed, but Memory continuity could not be demonstrated | Required Memory capture missing; [evidence](evidence/codex-cli-2026-09-07-memory-gap/run.json) |
| Codex CLI 0.153.4, Terra High, macOS 27 | Fail: same Memory omission on one fresh bounded effort retry | Not run after saving-chat failure | Retry stopped; failure retained |
| Claude Code CLI 2.1.263, Sonnet 5 Medium, macOS 27 | Partial: plan and card created; Memory fact omitted; native helper-command denials and continued work prevent a clean permission result | Not run after saving-chat failure | Required Memory capture missing; [evidence](evidence/claude-code-cli-2026-09-07-memory-gap/run.json) |
| Codex desktop | Unavailable to native computer control | Not run | No desktop coverage inferred from CLI |

The Memory omissions prompted a focused instruction repair: the existing canon
explains retention and recall but does not explicitly map “remember this fact”
to durable fact capture. These failures remain attached to the original payload;
a revised payload requires fresh evidence for the changed behavior. Claude's
native permission denials are a separate test-configuration qualification.

The Windows ARM64 virtual machine installed this wheel with native Python
3.13.13 and prepared a bound synthetic work area. This is an ARM64 CLI setup
observation only; it does not establish installer-wrapper acceptance, x64
coverage, or a desktop assistant run.

## September 6 repaired build — historical first-task smokes

- Core commit: `1e50521f1aae41759123cc21f1a9f91c9f89a6a9`; version `0.0.1`.
- Wheel SHA-256: `84dea9eb17fcaea356013bb673dfbcc90677962eb2011c00815094327c71b956`.
- Payload ZIP SHA-256: `24e20f0cd31898e66887f21f95a4964fedd36d6f06a5205df14ce20a00b74851`.

This PR49 build was the September 6 checkpoint baseline. Only bounded shared-root
first-task smokes were completed before the checkpoint; no lean-RC result
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
Those September 6 runs stopped at this partial checkpoint. **These historical smokes certify no app and do not establish lean RC compatibility.**

## Sep 7 build — bounded Cursor fragments

- Core commit: `b1290082707322b1e1ab7ba77dda2ddff67f6224`; version `0.0.1`.
- Wheel SHA-256: `9971e54fd100d72b54e780215fa37b150a7ea1f1fce122923f1a6a2da744c054`.
- Payload SHA-256: `24e20f0cd31898e66887f21f95a4964fedd36d6f06a5205df14ce20a00b74851`.

A fresh [shared-root case](evidence/cursor-ide-2026-09-07-shared-root/run.json)
saved a reusable facilitator guide, preserved all 127 existing files and
demonstrated the canonical Humanizer body plus two selective edits. It offered
Library addition after completion. Declining the offer left all 128 files
unchanged. This used a facilitator-guide variant of the checklist's shared-root
task; retain it as a passing first-task fragment alongside the separately opened
bound-project case below. Later independent Skill and Library cases are recorded below; the original
fragment retains its stated scope.

Cursor IDE 3.19.13 on macOS 27.0 used Grok 4.6 High for these observations.
The separately opened bound-project and saving Memory cases used Fast mode;
the fresh no-save case had Fast off. Retention, sourced correction and current
recall passed. The bound case saved a sourced plan and a managed
snapshot; the no-save case added only its requested project-local note, with 140
preexisting files unchanged. See [bound evidence](evidence/cursor-ide-2026-09-07-bound-project/run.json)
and [no-save evidence](evidence/cursor-ide-2026-09-07-memory-controls/run.json).
Independent fresh no-save chats also passed the separately requested
[Library and snapshot exceptions](evidence/cursor-ide-2026-09-07-no-save-exceptions/run.json).
Library registration/extraction added no card or other automatic retention.
The requested snapshot preserved the live no-save flag and project files,
captured existing managed state only, and emitted one metadata-only receipt.
These observations cover the Memory step's listed cases on this Cursor build;
they do not supply the distinct full Library or recovery cases.

A later fresh [Library-acceptance case](evidence/cursor-ide-2026-09-07-library-acceptance/run.json)
saved the literal `project-a/workshop-plan.md` in 77 seconds, preserving all 95
existing files, and offered optional addition. Acceptance took 31 seconds and
created a reference and a current assistant-written card with hashes matching
the original. Project files and Git remained unchanged; the managed snapshot's
manifest and actual path inventory exclude originals. Semantic review qualified
the plan's unlabeled assumption that the break/resume template repeats in each
session. The card faithfully summarizes that plan and inherits this limitation;
this is not an unqualified source-only first-task pass.

In a separate [changed-original no-save case](evidence/cursor-ide-2026-09-07-library-stale/run.json),
the operator revised only the registered original before starting a fresh chat.
Actual recall returned `abstained`, no evidence and partial coverage with reason
`stale`. Cursor declined to name a venue, and all 109 work-area files remained
unchanged. Acceptance used Grok High with Fast on; the 32-second stale case used
Grok High with Fast off.

A [correction and card refresh](evidence/cursor-ide-2026-09-07-library-refresh/run.json)
explicitly labels the per-session schedule as a proposal and retains the operator
revision. The card matches the corrected plan. This saving task also created two
Memory records and an additional task record; it is not a plan-only edit or a
passing supplied-task continuity case. Earlier prompt annotations used unsupported
`APPARATUS_TASK_ID`; only an observed global `--task ID` establishes CLI selection.

Independent [missing-original](evidence/cursor-ide-2026-09-07-library-missing/run.json)
and [ignored-original](evidence/cursor-ide-2026-09-07-library-ignored/run.json)
no-save cases explicitly used their assigned task IDs. Both returned abstention,
empty evidence and the corresponding partial-coverage reason. All 126 and 128
work-area files respectively, plus all three isolated-cache files in each case,
remained unchanged. These took 29 and 23 seconds with Grok High and Fast off.
The operator restored the original and ignore rules only after freezing each
case. The remaining independent cases were subsequently exercised as follows.

### Remaining Cursor scenario inventory — completed on September 7

All cases below used the same explicit runtime and isolated cache above, Cursor
3.19.13, Grok 4.6 High, Fast off, and no delegation. Each command used an explicit
global `--task ID`. Full work-area/cache inventories were checked locally; public
records retain selected synthetic artifacts, hashes and compact change summaries.

| Scenario group | Result | Observed outcome |
| --- | --- | --- |
| [Partial PDF extraction](evidence/cursor-ide-2026-09-07-library-partial/run.json) | Qualified | Extracted text supported the card; recall abstained on the image-only venue. Cursor also inspected another Library card and broader searches, so selected-source-only browsing did not pass. |
| [Unsupported original](evidence/cursor-ide-2026-09-07-library-unsupported/run.json) | Pass | Registration succeeded; no usable extraction or card was invented. No recall was requested in this case. |
| [Learned Skill](evidence/cursor-ide-2026-09-07-learned-skill/run.json) | Pass | Inactive draft, exact-byte review/adoption, then native use of the canonical body in a fresh no-save chat. Only the requested project plan was added during use. |
| [Snapshot and restore](evidence/cursor-ide-2026-09-07-managed-recovery/run.json) | Pass | A deliberate managed change returned to exact saved bytes; project files and originals stayed unchanged. |
| [One-way backup](evidence/cursor-ide-2026-09-07-managed-backup/run.json) | Pass | The 149-entry archive matched its declared scope; project files, originals, caches and project Git were excluded. |
| [Restored catalog, missing original](evidence/cursor-ide-2026-09-07-restored-catalog-missing-original/run.json) | Pass | Registration returned, original stayed missing, and recall abstained with explicit coverage gaps. |
| [Unavailable Git](evidence/cursor-ide-2026-09-07-git-unavailable/run.json) | Pass | The command reported snapshots unavailable and suggested doctor; all 207 work-area and six cache files stayed unchanged. |
| [Routine maintenance](evidence/cursor-ide-2026-09-07-quiet-actions/run.json) | Pass | Check, requested ingest and recall added no receipts; all 208 work-area and six cache files stayed unchanged. The existing unsupported source remained visible. |
| [Meaningful repair](evidence/cursor-ide-2026-09-07-quiet-actions/run.json) | Pass | Init restored the exact missing stock Skill and wrote its repair receipt; custom work was preserved. |
| [Synthetic redaction](evidence/cursor-ide-2026-09-07-quiet-actions/run.json) | Pass | The stored fact replaced the fake password value; its receipt retained only class/count. The input value is excluded from public evidence. |
| [Ordinary local copy](evidence/cursor-ide-2026-09-07-quiet-actions/run.json) | Pass | The 880-byte copy matched its original outside the work area, with no Apparatus sharing review; all 231 work-area and six cache files stayed unchanged. |

The PDF recall envelope's `coverage: complete` describes its indexed extraction;
it does not establish complete page/image capture. Some native command outputs
were not expanded before leaving the viewport. Their records explicitly separate
observed final replies from independently verified persisted files and inventories.
Native permission settings, default-cache installation and provider retention were
not assessed. The earlier plan/refresh qualifications are preserved.

These earlier-build fragments do not themselves supply the two-chat Cursor row
or the combined named-app lean RC gate. Older common three-app observations at core `1e50521…` remain
historical evidence and are not relabeled as this build.

## Earlier PR48 build — dated partial observations

- Core commit: `7c0c6c4252bf948a0e4dd32decfb35cf308e963d`; version `0.0.1`.
- Payload ZIP SHA-256: `24e20f0cd31898e66887f21f95a4964fedd36d6f06a5205df14ce20a00b74851`.
- Isolated wheel SHA-256: `5b3f11834131f564d0c521d5dfb77a39c9da4d08d13dd50e11bd39c587c02936`.

This build includes PR48. A default-cache diagnostic defect observed during a
Codex run led to PR49. These observations remain attached to the exact earlier
build; successful fragments and workarounds are not relabeled as repaired runs.

## Earlier-build historical coverage

| AI app / exact variant | Inventory on macOS 27.0 | Observed fragments | Overall | Missing evidence |
| --- | --- | --- | --- | --- |
| Codex desktop, local folder | Version not recorded | Not run | Not certified | Actual session, version, and two RC chats on the final payload |
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

No RC-compatible row may omit dated app/variant, version, model, OS/version,
shared build identifiers, persisted artifacts, hashes, or a passing required
chat. Testing a variant does not cover its siblings. Scripts, metadata, menus,
and automated core/conformance results cannot establish assistant behavior.
Optional native discovery/delegation, installer install-and-repair evidence per
supported OS, package composition, publisher signatures, and live release
publication remain separate evidence. Windows ARM64 VM evidence must be labelled
and cannot replace required x64 evidence.

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
