# Installed Mailbox Survey — supplied sample, 2026-10-10

Two fresh native Codex subagent sessions passed this bounded exercise. The
first produced a useful report from the eight packaged synthetic messages;
the second used that report to write a requested note in a no-save task.
Neither required a correction. This is explicit Skill-file use in native
subagents, not top-level desktop-chat certification or automatic discovery.

## What the person received

The original [report](evidence/mailbox-supplied-sample-2026-10-10/survey.yaml)
proposes six categories: purchases, deliveries, editorial newsletters,
personal correspondence, project work and account notices. Purchases and
deliveries share the order and matching tracking notice. Nine category
memberships therefore cover seven distinct messages. The vague appointment
reminder remains uncategorized, accounting for all eight supplied records.

Independent comparison with the
[fixture](evidence/mailbox-supplied-sample-2026-10-10/sample-mailbox.yaml)
found the example links supported. The report distinguishes a planned carrier
label from reported delivery, leaves account authenticity and other absent
facts unresolved, and treats the embedded request to disclose/delete messages
as data. It states the supplied dates, excerpts and sample coverage without
claiming a complete mailbox. This small observation does not estimate
classification quality on other inputs.

The installed validator and read-only summary both returned zero. The
[summary](evidence/mailbox-supplied-sample-2026-10-10/summary.txt) accurately
reflects the report's counts and limits. This factual comparison is separate
from structural validity. Commands preserved the report's bytes and modification
time. The fresh continuation's
[note](evidence/mailbox-supplied-sample-2026-10-10/category-note.md) correctly
explains overlap, the unresolved reminder and the sample boundary. It explicitly
does not claim to have rechecked the underlying messages.

## Exact environment and method

The exercise began after PR-68 merged at
`625372abc4082675079d4b484fb20eb4d15bfd3e`. Its tree matched corrected source
`f4cb3ae03025849c84898f1571cdeb4e140305e5`. Wheels were built from
`c6947f4f44308c5617f7ad71a4cb33b7dc570ab2`; runtime code, package metadata,
resources and starter content were unchanged through the test-ID correction
and merge. The module wheel matches the
[PR-68 evidence](mailbox-release-recognition-2026-10-10.md).

- Mailbox Survey 0.1.4 wheel: `1eeedd2296771241a34b27c85984794d0482d927867f2a4ec8c55152d3ac6d06`.
- Core 0.0.2 **source-build** wheel: `9097bd7bc044fd383c30592707fdb00640e6ee606cbf58e60c9c3706ecb959e7`.
- Python 3.12.4; macOS 27.2, build 26B5101f, ARM64.
- Host app bundle `com.openai.codex`, version 26.1007.21159, build 20052.
- Native `spawn_agent`, `fork_context=false` for each session; inherited parent
  model with medium reasoning effort requested. Provider-side model identity
  was not independently attested. No model-switching or cost-saving claim.

All 81 installed Core package files and 11 module package files byte-matched
their wheels. The module was installed through its create-only command into
a new enrolled work area; status reported current with a complete 0.1.4 content
match. Its project had unrelated synthetic Memory and registered/extracted
Library content before the first baseline. No live connector was used.

The [prompts](evidence/mailbox-supplied-sample-2026-10-10/prompts/survey.txt)
supplied the canonical Skill and source/output paths explicitly, rather than
an example report or expected categories. The first
[tool trace](evidence/mailbox-supplied-sample-2026-10-10/survey-trace.json)
records Skill/reference/sample reads, report creation and installed validation
and summary commands. The second
[trace](evidence/mailbox-supplied-sample-2026-10-10/continuation-trace.json)
records only report/Skill reading and note creation. Source-read outputs in
these bounded traces are marked when truncated; the inputs and outputs have
separate complete artifacts and hashes. Local prefixes are normalized to
`$RUN` and `$REPO`; reasoning and unrelated session metadata are excluded.

## Retention and preservation

The first session added only the requested report: all 142 earlier entries,
including 73 files, remained unchanged. Starting the second no-save task then
added exactly one task-control file. That deliberate setup occurred before
the continuation baseline and is recorded separately.

The continuation added only `Projects/survey/category-note.md`. All 144 prior
entries, including 75 files, preserved their bytes, sizes, modes and file
modification times. This includes existing task controls, Memory, Library
records/cache, deployed Skills, project input and report. Directory presence
and modes were compared; directory modification times were excluded because
creating the requested child legitimately changes its parent's timestamp.

The [result record](evidence/mailbox-supplied-sample-2026-10-10/result.json)
contains counts, source assessments, hashes and inventory differences. The
four frozen inventories can be compared with the supplied read-only
`compare_inventories.py`. These observations concern this disposable work
area; they establish neither operating-system confinement nor the AI app's
own retention behavior.

## Validation and limits

Local full suite: 1,792 passed, 43 skipped on the wheel-source candidate. After
the upstream test-ID correction, its focused file passed 79 tests; runtime
and test cases were unchanged. PR-68's corrected-head Linux suite passed
1,785 tests with 50 platform-dependent skips, and all 11 checks passed before
its remote merge. The evidence PR separately requires current-head CI.

The first local full-suite invocation stopped during collection because the
fresh worktree's workspace packages had not been installed. Running
`uv sync --all-packages` resolved that setup error before the passing run;
it was not an assistant acceptance failure. Both assistant attempts passed
without repair. Independent review and evidence consistency checks accompany
this PR.

Automatic discovery, top-level desktop/CLI behavior, live-mailbox access,
general classification quality, module update/removal, native installer
upgrades and package publication remain unqualified. The ordinary Core release
and full module lifecycle retain their separate acceptance requirements.
