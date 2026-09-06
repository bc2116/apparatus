# PR47 preparation and evidence status

Updated 2026-09-06. **Local RC checkpoint: basic Cursor task works; certification,
required Windows CI and signing remain incomplete. No signed public RC claim.**
PR47 documentation is based on PR48 and is being curated to retain both its
partial app observations and bounded PR49 first-task smokes. Latest observed
source is `1e50521f1aae41759123cc21f1a9f91c9f89a6a9`; earlier multi-case fragments
used `7c0c6c4252bf948a0e4dd32decfb35cf308e963d`. These are exact-build evidence,
not claims about a release. Only documentation and synthetic evidence are
curated here; held PR24 evidence remains untouched.

## Prepared documents

- [Portable checklist](../certification/checklist.md): six observable steps with
  independent negative cases and minimal synthetic evidence.
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

The two historical metadata records remain unchanged. Current evidence includes
byte-for-byte synthetic source, plans, guides, Facts and cards, with SHA-256
checks in each run record. Final curation checks passed: six new run JSON records parse, all 27 copied
artifact hashes match, relative links resolve, no private absolute paths were
found, and historical evidence is unchanged. `git diff --check` passes. No full pytest or additional app run is performed by this
documentation curation task.

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
before recording certification. The three-app gate, independent
semantic review and required PR47 full pytest remain pending. Native installer
CI/rehearsal, signatures and publication are separate. No raw conversation or
machine absolute path was copied into the normalized evidence.

## PR49 checkpoint smokes

Latest observed version `0.0.1` uses wheel SHA-256
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
checkpoint; no app is certified.

The PR49 branch later recorded its verification note at
`3d940a45af75cbbd190a1fa2279fdf340c6f9918`; the tested artifact source remains
`1e50521f1aae41759123cc21f1a9f91c9f89a6a9`. PR49's operator-reported full result
is 1,265 passed and 38 skipped. That source test result does not certify apps;
PR47's required full suite is still pending integration by the owner.
