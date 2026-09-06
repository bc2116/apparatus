# Certification matrix — DRAFT

Updated 2026-09-06. **No reworked core app certification is complete.** This is
pre-alpha source/runtime evidence, not a signed public release or a promise of
support across untested variants. Held PR24 results cover their original payload.

## Diagnostic local build — final baseline awaits PR48

- Core commit: `78e09ece6225deef9f84e36f42eec3b451aeed84`; version `0.0.1`.
- Payload ZIP SHA-256: `24e20f0cd31898e66887f21f95a4964fedd36d6f06a5205df14ce20a00b74851`.
- Isolated wheel SHA-256: `04d6dfa6a26e513e5955c72d1d17465126d6797829f90300cf59fd5ae7f0dca1`.
- Local integration: 1,247 tests passed, 38 skipped; source/package parity passed.
  These checks do not certify an AI app. See [build evidence](../notes/pr-46-verification.md).

## Six-step core certification

Rows below record the PR46 diagnostic build above. Final certification requires
a common build containing PR48; its identifiers are pending. Versions are
operator inventory, not proof of completing any checklist case.

| AI app / exact variant | Current inventory on macOS 27.0 | Steps 1–6 | Overall | Missing evidence |
| --- | --- | --- | --- | --- |
| Codex desktop, local folder | Version not recorded | All not run | Not certified | Actual session, version and all six cases |
| Codex CLI | 0.153.4 | All not run | Not certified | Actual execution; prior CLI metadata is insufficient |
| Claude Code terminal CLI | 2.1.263 | All not run | Not certified | Actual execution using common build |
| Cursor IDE Agent | 3.18.25 | Step 1 partial; snapshot attempt failed; other cases not run | Not certified | PR48 repair, new common baseline and all required cases |
| Cursor CLI agent | 2026.09.02-c22c1a3 | All not run | Not certified | Actual CLI execution; no IDE inference |

On 2026-09-06 at approximately 11:40 America/Los_Angeles, Cursor IDE ran a
45-second shared-root task with Sol Medium and no delegation. It saved a sourced
workshop plan with two sessions, 12 places each, the 45-minute break and unknown
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
PR48 is repairing it. The failure is not an app permission diagnosis or a pass.

See [normalized run evidence](evidence/cursor-ide-2026-09-06-pr46/run.json),
[synthetic source](evidence/cursor-ide-2026-09-06-pr46/project-a/source.md) and
[actual saved plan](evidence/cursor-ide-2026-09-06-pr46/project-a/workshop-plan.md).
Other app runs have not started. No Windows app case has run. This earlier
baseline remains diagnostic after repair; no app is certified.

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
