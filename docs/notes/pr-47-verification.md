# PR47 preparation and evidence status

## September 8 release closeout

The current release and named app outcomes are in the
[matrix](../certification/matrix.md). Version `0.0.2` is on PyPI, both native
wrappers are signed, and Mac ARM64 and Windows x64 native install and repair
passed. GitHub installer publication remains pending. The app-tested
`0.0.1` source differs from the release in the core version constant only across
core source, starter content and installers. Earlier observations below retain
their original build identities and failures.

## September 7 checkpoint — historical

Updated 2026-09-07. The current candidate is source
`964d5a1738b2d8928ec85b964474bcc8e59b2316`; its wheel and payload identifiers
and current app outcomes are in the [matrix](../certification/matrix.md).
Codex CLI and Claude Code CLI passed the focused pair with explicit Memory-fact
wording. The named Cursor IDE 3.19.13 / GPT-5.6 Luna Medium pair also passed on
this candidate, with prompted canonical Skill use observed and no-save inventory
independently verified. The separate Grok isolated rerun remains qualified
failure evidence because its native final prose called the timing a “45-minute
water break,” although the source says only “after 45 minutes.” The focused app-chat gate is complete for these named configurations. Signed
installer install-and-repair acceptance and the overall RC gate remain incomplete. Earlier observations below retain
their original build identities.

The exact candidate's full Linux CI passed (1266 passed, 45 skipped); focused
local checks passed (39 passed, 1 skipped). The redundant local full run was
canceled after CI passed. Release rehearsal built all seven distributables,
verified checksums, and skipped signing/publication. The Windows ARM64 wrapper
dry run passed with 67 existing files unchanged; actual installer acceptance
still requires package publication. Held PR24 remains untouched.

## Prepared documents

- [Portable checklist](../certification/checklist.md): two actual chats per named
  app/variant, with minimal synthetic evidence.
- [Matrix](../certification/matrix.md): common local build, current app inventory,
  actual run status and historical metadata diagnostics kept separate.
- One-page quickstarts for [Codex](../quickstarts/codex.md),
  [Claude Code](../quickstarts/claude-code.md) and [Cursor](../quickstarts/cursor.md).
- Two supplied metadata JSON records, copied unchanged. They have no embedded
  observation dates and establish no body execution or core certification.

The earlier PR48 observed baseline is local version `0.0.1`, with payload SHA-256
`24e20f0cd31898e66887f21f95a4964fedd36d6f06a5205df14ce20a00b74851` and wheel
SHA-256 `5b3f11834131f564d0c521d5dfb77a39c9da4d08d13dd50e11bd39c587c02936`.
[PR46 verification](pr-46-verification.md) records earlier full-suite and package
checks, not verification of this newer wheel; those are not app acceptance and do not establish what PyPI currently serves.
A signed public release is not established.

## Documentation sources

The approved PR47 plan and integrated setup semantics govern these documents.
Official pages fetched and checked on 2026-09-06:

- [OpenAI projects and local folders](https://learn.chatgpt.com/docs/projects).
- [Claude Code quickstart](https://code.claude.com/docs/en/quickstart).
- [Cursor quickstart](https://cursor.com/docs/get-started/quickstart).
- [Cursor opening and file context](https://cursor.com/help/getting-started/first-project).

Official instructions describe supported opening routes; they do not prove
Apparatus behavior. Codex/Claude/Cursor variants are recorded independently.
Historical Claude Code 2.1.261 metadata is not relabeled as the current 2.1.263
inventory. Cursor CLI metadata does not certify Cursor IDE 3.18.25.

## Local documentation checks

The two historical metadata records remain unchanged. The latest curation adds
eight run records and 76 verified artifact hashes (84 files total), with
exact normalized prompts, source/record bytes and explicit observation limits.
All run JSON parses, each artifact set matches its manifest, hashes match, relative
links resolve, and private machine paths/raw credential fixtures are absent.
The runtime, starter, conformance, installer and workflow trees match tested
`833eb398`; its full-suite result is reused for this documentation-only batch.
Generated evidence bytes retain their original trailing blank lines; the staged
whitespace check excludes only that category. Earlier evidence is unchanged.

## Earlier diagnostic evidence

The first actual Cursor IDE run is retained as [normalized synthetic evidence](../certification/evidence/cursor-ide-2026-09-06-pr46/run.json),
with exact source and output bytes. On 2026-09-06 at approximately 11:40
America/Los_Angeles, Cursor IDE 3.18.25 on macOS 27.0 used Sol Medium without
delegation. The 45-second shared-root fragment saved a grounded plan and kept
the checked source, local note, custom instructions, root canon and profile
unchanged. The output SHA-256 is
`bec91a250cfd1f49c88a3bb2dc9b4307cff52ddb5c45d965b0147e7957de6206`.
The separate bound-project opening case is unrun; step 1 is partial.

The snapshot attempt returned exactly:

> snapshot: System/profile.yaml could not be read safely; repair the workspace profile before using this feature

The assistant reported that failure honestly. The operator independently
reproduced the failure outside Cursor through an external path alias, while the
canonical path passed against the same profile inode. PR48 repaired that feature
boundary; the earlier failure remains diagnostic evidence. No Library offer was
observed, but the short plan was not explicitly a reusable guide, so this is not
an offer pass/failure. The native canonical Skill usage label is a fragment,
not a passing full Skill case.

## PR48 observations and limits

[Codex CLI evidence](../certification/evidence/codex-cli-2026-09-06-pr48/run.json)
records a failed launcher attempt, successful shared-root output, correct bound
output with an inaccurate final reply, a sourced Fact/reusable guide, and Library
addition following an outside-fixture cache override. The actual default-cache
errno was not retained. PR49 addresses the misleading generic symlink diagnostic;
this evidence does not establish which underlying error occurred in that run.

[Cursor IDE evidence](../certification/evidence/cursor-ide-2026-09-06-pr48/run.json)
records a new shared-root plan, sourced Fact/guide and explicit Library acceptance
with current card and managed snapshots. No configuration override was observed;
the default cache may be outside the fixture and is not part of the copied
inventory. Source, guide, Fact and card bytes were captured before correction. Separate
after-correction copies record three sessions and a current Fact; plan and guide
bytes remain identical. The operator observed current Memory recall and snapshot
`482d2f527d2a48ac490d7b03aa61ee94bd1f4199`. Canonical Humanizer reading is not
established by final claims.

Both sets distinguish directly inspected artifacts from operator observations
and assistant claims. The first shared-root preservation inventory was supplied
by the operator; later additions are expected. Raw JSONL, global state, hooks,
private machine paths and provider data are excluded.

[Claude CLI evidence](../certification/evidence/claude-code-cli-2026-09-06-pr48/run.json)
contains ten bounded calls and eight exact synthetic artifacts. It preserves the
incorrect break-duration reply and two false Git backup claims alongside actual
CLI outcomes. No-save inventory, explicit requested exceptions, offer/decline,
grounded card creation and missing-original abstention are recorded separately.
The first Library cache was outside the fixture; later calls used an owned cache.
No full Memory, learned Skill or recovery case is inferred.

Complete all required cases against one final common build
before recording certification. The complete three-app gate and its independent
semantic acceptance remain pending. Native installer
CI/rehearsal, signatures and publication are separate. No raw conversation or
machine absolute path was copied into the normalized evidence.

## PR49 checkpoint smokes

The September 6 smoke version `0.0.1` uses wheel SHA-256
`84dea9eb17fcaea356013bb673dfbcc90677962eb2011c00815094327c71b956`
and the same payload hash above. Each app uses an explicit per-app fixture cache;
default-cache behavior is outside these smokes. No broader matrix was started.

[Codex CLI smoke](../certification/evidence/codex-cli-2026-09-06-pr49/run.json)
completed in 47.91 seconds. The saved plan and final reply preserve break timing
and recovery scope. Direct comparison verified all 67 preexisting work-area
files and 28 preexisting project Git files unchanged.

[Claude CLI smoke](../certification/evidence/claude-code-cli-2026-09-06-pr49/run.json)
contains an 8.23-second task start and 43.08-second shared-root task. It preserves
correct command outcomes and project snapshot scope. Its sample outline proposes
unsupported break/block durations, qualified as a sample with total duration
unknown; break duration is not separately listed as unresolved. Five original
hashes and all 28 project Git files are unchanged.

[Cursor IDE smoke](../certification/evidence/cursor-ide-2026-09-06-pr49/run.json)
completed in 48 seconds with explicit fixture cache, a sourced 27-line plan,
unknown break duration/total length, no-change snapshot and an optional Library
offer. Direct comparison verified all 67 preexisting work-area files and 28
project Git files unchanged. Exact canonical Skill body reading was not verified.
No acceptance or further app cases followed. All app runs stopped at this partial
checkpoint on September 6; no app is certified.

The PR49 branch later recorded its verification note at
`3d940a45af75cbbd190a1fa2279fdf340c6f9918`; the tested artifact source remains
`1e50521f1aae41759123cc21f1a9f91c9f89a6a9`. PR49's operator-reported full result
is 1,265 passed and 38 skipped. That source test result does not certify apps;
PR47's own integrated full-suite result follows.

## September 7 bounded native evidence

The earlier integrated build observed in Cursor was `b1290082707322b1e1ab7ba77dda2ddff67f6224`, with
wheel SHA-256 `9971e54fd100d72b54e780215fa37b150a7ea1f1fce122923f1a6a2da744c054`
and payload SHA-256 `24e20f0cd31898e66887f21f95a4964fedd36d6f06a5205df14ce20a00b74851`.
Cursor IDE 3.19.13 on macOS 27.0 completed a separately opened bound-project
first-task fragment, a Memory correction/retention follow-up fragment, and a
fresh no-save fragment using Grok 4.6 High. Fast was on for the bound/saving
cases and off for no-save. The bound and no-save records
are [curated separately](../certification/matrix.md#sep-7-build--bounded-cursor-fragments);
they are not a complete six-step or three-app certification. Existing historical
PR49 three-app observations at core `1e50521…` remain unchanged and historical.
The [independent no-save exceptions](../certification/evidence/cursor-ide-2026-09-07-no-save-exceptions/run.json)
also passed: Library registration/extraction without a card or other capture,
and a separately requested managed snapshot with unchanged project files and
live task controls. Only the expected recovery reference, ten object files and
one metadata-only receipt changed or appeared during the snapshot case.
The later [shared-root guide and Library decline](../certification/evidence/cursor-ide-2026-09-07-shared-root/run.json)
completed in 48 seconds and one second respectively. The canonical Humanizer
body and two selective edits were observed. The guide was the only addition
to a fresh 127-file work area; declining Library addition left all 128 files
unchanged. Bound-project snapshot evidence now includes its actual receipt,
manifest and path inventory as requested by independent evidence review.
Four new run records and all 24 copied artifact hashes, relative links and
private-path checks pass. The exact copied no-save snapshot receipt retains
its generated trailing blank line; the staged whitespace check passes with
only the blank-at-EOF check excluded. Artifact bytes were not trimmed to make
that check pass. Production source remains identical to the tested build.

The integrated full suite passed **1,266 tests, 38 skipped in 527.58 seconds**;
the retained log and XML are `apparatus-integrated-full-sep7.log` and its
corresponding XML artifact. Those results are historical. Later Windows bootstrap attempts timed out in
complete-legacy adoption; current exact-head CI must be checked separately. Signing is still unconfigured. No release or
certification claim follows from these results.

## September 7 Library acceptance and stale-source follow-up

Two additional Cursor run records retain 15 exact artifact hashes. The fresh
shared-root workshop plan was the only addition to a 95-file baseline. Library
acceptance registered the original, wrote a current card matching its exact
source/extracted text hash, and saved managed snapshot
`2ab2645233793fdca7eed92ed0dec21ddf3845ad`. Project files and project Git remained
unchanged. The record includes actual snapshot receipt, manifest and path list.
Independent packet-based semantic review qualified the plan's unlabeled
per-session break/resume assumption; the card accurately inherits the saved
plan. That qualification remains visible rather than becoming a clean pass.

After an operator-only original revision, a fresh no-save chat ran actual recall
and returned `abstained`, empty evidence and partial coverage with reason `stale`.
Cursor declined to name a venue. All 109 work-area files remained unchanged;
the operator did not capture a full before/after external-cache inventory.
See the [matrix](../certification/matrix.md#sep-7-build--bounded-cursor-fragments)
for the separate records and remaining cases. No app is certified.

After integration of the two reviewed Windows test-fixture repairs, full
`uv run pytest` at `833eb39893f96f074324ef007ef90efacaaac2b5` passed **1,266 tests,
38 skipped in 533.82 seconds**, exit 0. Production source and payload remain
identical to the observed `b129008` build. The new evidence changes documentation
only; no additional full suite was run for this curation. Required exact-head
platform CI and signing remain separate gates.

## September 7 correction, missing and ignored originals

The [qualified plan correction](../certification/evidence/cursor-ide-2026-09-07-library-refresh/run.json)
took 227 seconds. The saved plan separates the per-session schedule proposal
from source facts and unknowns; its refreshed card matches the revised bytes.
Two Memory records, a snapshot receipt, an additional saving task and managed
Git objects also appeared. Existing source, note, instructions and project Git
remained unchanged. Saving-task guidance permits automatic Memory, but the
extra task is not a supplied-task continuity pass. The operator's earlier
`APPARATUS_TASK_ID` annotation is unsupported; only global `--task ID` selects
a task. The exact native command creating the extra record was not correlated,
so this observation does not establish a core defect.

The independently observed [missing-original](../certification/evidence/cursor-ide-2026-09-07-library-missing/run.json)
and [ignored-original](../certification/evidence/cursor-ide-2026-09-07-library-ignored/run.json)
cases explicitly used assigned no-save task IDs. Actual native recall commands
and JSON were expanded and observed. Both abstained with no evidence and their
correct partial-coverage reason. All 126 and 128 work-area files respectively,
plus all three isolated-cache files in each case, remained unchanged. The
operator restored fixture state only after freezing each outcome. These cases
took 29 and 23 seconds; full Library and app certification remain incomplete.

This curation batch contains five run records and 33 artifact hashes, including
the earlier acceptance/stale records. Hashes, exact copied native outputs,
relative links and private-path checks passed. Assistant reply summaries are
labeled paraphrases. Generated artifacts retain their exact trailing blank
lines; only that whitespace category is excluded for the artifact diff check.
No runtime, payload, test or workflow changes are included.

At head `833eb398`, native Windows safety passed on September 7 at 16:44:40 UTC.
Windows bootstrap failed because the complete-legacy adoption subprocess
exceeded its 90-second limit; 22 other cases passed and one skipped. The same
fixture/bootstrap/workflow bytes passed on another integrated branch, which
does not establish the cause or satisfy this head's failed check. No timeout
or assertion was relaxed. Required platform CI and signing remain gates.

## September 7 finite Cursor acceptance block

The [remaining scenario inventory](../certification/matrix.md#remaining-cursor-scenario-inventory--completed-on-september-7)
now records all eleven planned groups. Ten passed; the PDF case retained honest
extraction limits and abstention but also broader Library browsing. The learned
Skill draft stayed inactive until exact-digest review, then the adopted canonical
body was used in a fresh no-save chat. Recovery restored exact managed bytes,
backup matched its closed scope, and catalog recovery did not recreate an original.
Routine operations stayed quiet; meaningful repair/redaction retained receipts;
an ordinary byte-identical local copy had no Apparatus sharing review.

Eight new run records retain selected synthetic artifacts and compact verified
deltas. Full inventories, raw recovery objects, the backup ZIP, raw provider logs
and the fake redaction input value remain outside public evidence. Exact prompts
use a consistent fixture placeholder, preserving the sibling work-area/runtime/cache
layout. Command outputs that were not expanded are explicitly distinguished from
observed final replies and persisted artifact checks. Missing exact UI timing is
marked unavailable. Earlier evidence and qualifications remain unchanged.

This batch changes documentation/evidence only. It reuses the full integrated
`833eb398` result above after checking the unchanged runtime, starter, conformance,
installer and workflow trees. Independent PR46 test diagnostics do not certify a
new installer: the timed-out Windows process can leave children writing during
output cleanup, so untimed late traces cannot establish pre-deadline completion.
No timeout or safety assertion has been relaxed. Current platform CI, final-build
three-app acceptance, signing and publication remain separate gates.

## September 6 local integration — historical

The evidence commit was rebased from PR48 onto PR49
`3d940a45af75cbbd190a1fa2279fdf340c6f9918`. The resulting checkout before final
documentation reconciliation was `9e7a6df1eeb1298750342540bac9e44e62e82995`.
Compared with pre-rebase PR47, only exact inherited PR49 files and the intentional
plan dependency reconciliation changed. PR48 and PR49 remain marked landed;
PR47 remains in progress with dependency PR49.

- `uv sync --all-packages`: passed.
- `uv run pytest`: **1,265 passed, 38 skipped in 550.91 seconds**; exit 0.
  The operator retained the local log as `apparatus-pr47-final-full.log`.
- Core source, starter and conformance Git trees match smoke artifact source
  `1e50521f1aae41759123cc21f1a9f91c9f89a6a9` exactly. Core source tree:
  `f057a93f1fb4a9bfdb8afea0553002642291d4af`; starter tree:
  `af709c9bc3520ffa27d134b6ada98ffa553be5ac`.
- The observed wheel and payload identities above remain unchanged; no new
  package or app run is claimed from the documentation-only reconciliation.
- Final relative links, evidence hashes, private-path scan and diff whitespace
  checks pass. No additional platform suite was run.

This is a local RC checkpoint with basic Cursor use demonstrated. Remaining
full app cases, required Windows CI and signing are incomplete. No push, public
RC publication or completed app certification is established by this note.
