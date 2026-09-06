# PR47 preparation and evidence status

Updated 2026-09-06. **Incomplete: no app certification or public release claim.**
The plan was rebased onto PR46 `78e09ece6225deef9f84e36f42eec3b451aeed84`.
Final certification now depends on PR48. The PR47 branch has not yet rebased
onto that unfinished repair. Only documentation is changed here; held PR24 and its earlier results remain
untouched. This preparation does not run model prompts, install apps, change
runtime behavior, sign artifacts or publish anything.

## Prepared documents

- [Portable checklist](../certification/checklist.md): six observable steps with
  independent negative cases and minimal synthetic evidence.
- [Matrix](../certification/matrix.md): common local build, current app inventory,
  actual run status and historical metadata diagnostics kept separate.
- One-page quickstarts for [Codex](../quickstarts/codex.md),
  [Claude Code](../quickstarts/claude-code.md) and [Cursor](../quickstarts/cursor.md).
- Two supplied metadata JSON records, copied unchanged. They have no embedded
  observation dates and establish no body execution or core certification.

The baseline is the tested local version `0.0.1`, with payload SHA-256
`24e20f0cd31898e66887f21f95a4964fedd36d6f06a5205df14ce20a00b74851` and wheel
SHA-256 `04d6dfa6a26e513e5955c72d1d17465126d6797829f90300cf59fd5ae7f0dca1`.
[PR46 verification](pr-46-verification.md) records full-suite and package checks;
those are not app acceptance and do not establish what PyPI currently serves.
A signed public release is not established.

## Documentation sources

The approved PR47 plan and final PR46 setup semantics govern these documents.
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

Relative links resolve, both JSON records parse and match their supplied
originals byte for byte, and the new documents contain no private absolute
paths. The quickstarts are 354–387 words each. `git diff --check` passes.
No full pytest run was requested for this preparation stage.

## Remaining evidence

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
canonical path passed against the same profile inode. PR48 repairs that feature
boundary; the earlier failure remains diagnostic evidence. No Library offer was
observed, but the short plan was not explicitly a reusable guide, so this is not
an offer pass/failure. The native canonical Skill usage label is a fragment,
not a passing full Skill case.

Other app runs have not started. Complete all required cases against one repaired
common build before recording certification. The three-app gate, independent
semantic review and required PR47 full pytest remain pending. Native installer
CI/rehearsal, signatures and publication are separate. No raw conversation or
machine absolute path was copied into the normalized evidence.
