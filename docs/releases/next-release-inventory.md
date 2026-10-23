# Next core release inventory

Observed 2026-10-23. This is release preparation, not release acceptance.

## Identity and selected scope

The public GitHub release and PyPI package are **0.0.2**. The annotated Git tag
object is `85b3d0a753f6ff35915b9ce8b62bcfb420a357a3`; its source commit is
`7a1b0cda634f5d44ff100f83b72fe5e3cc3a4d25`. The inventory target is main at
`1e8df7debc0aeb25062ad74fa13b54efe5591568` (GitHub PR #72).

Public package identities from PyPI:

| File | SHA-256 |
|---|---|
| `apparatus_core-0.0.2-py3-none-any.whl` | `4192852c4ce46e9e2abceef989e0ee9ff708e695a0052d8258355bff35aca517` |
| `apparatus_core-0.0.2.tar.gz` | `5276b33b8a33e74d41a9082f352d4e9cf4b9e0f075ca790b9c736ee7ae9ed7e7` |

Sources: [GitHub release](https://github.com/bc2116/apparatus/releases/tag/v0.0.2),
[package metadata](https://pypi.org/pypi/apparatus-core/json), and the local Git
comparison `git diff v0.0.2..1e8df7d`. PyPI listed only 0.0.2; Git tags listed
0.0.1 and 0.0.2. **0.0.3 is the proposed next version**, subject to another
collision check before the candidate/tag is created.

Scope is core, its portable payload, and existing native installers. Optional
Mailbox Survey publication is excluded. S2's proposed meeting-notes example and
C1's conditional improvements are omitted at scope selection under the sprint's
capacity policy. No meeting-notes comparison was run and no efficacy conclusion
is drawn. Existing Skills remain the delivery path. This admission decision is
included in S1; no separate S2 experiment PR is consumed. Four required PRs
remain: inventory, candidate, rehearsal record and delivery record, within the
original eight-PR ceiling.

## Classified delta from 0.0.2

Paths in this table are relative to the repository root.

| Class | Retained change | Implementation and evidence |
|---|---|---|
| Core behavior | Explicit Decision capture; successful Fact, Person and Decision creation returns the exact record path. Input reads and final record publication are checked. | `b006a96`; `packages/apparatus-core/src/apparatus_core/commands/memory.py`; `tests/test_verifiable_memory_saves.py` under the same package; [Memory specification](../spec/memory.md). |
| Core behavior | Read-only `resume` brief resolves an explicitly linked project, lists bounded active/waiting goals and next actions, source availability and snapshot coverage. Reports partial/invalid state without repairing it. | `06444fe`; `packages/apparatus-core/src/apparatus_core/commands/resume.py`, `snapshots.py`, `cli.py`, package entry point; `tests/test_resume.py`; [workspace specification](../spec/workspace.md). |
| Core repair | POSIX backup accepts safe aliases in destination ancestors while retaining final-link and inside-work-area rejection. Windows normalization is unchanged. | `6d05582`; `packages/apparatus-core/src/apparatus_core/backup.py`, `managed_state_backup.py`; corresponding backup tests; [recovery specification](../spec/managed-recovery.md). |
| Payload | Guidance verifies and reports Memory saves, uses current source-backed recall and runs resume for continuation. Recognized older stock instructions can migrate; custom content remains protected. | `b006a96`, `06444fe`; `starter/payload/AGENTS.md`, generated shims, embedded counterparts and `instruction_updates.py`; PR-58/60 guidance tests. |
| Dependency | Declared PDF dependency floor changes from `pypdf>=6.16.1` to `pypdf>=6.19.0`; lock metadata follows. | `dbde171`, `890a7b1`; core `pyproject.toml`, `uv.lock`; [dependency record](../plan/PR-65-pdf-security-floor.md). This is not a universal PDF safety claim. |
| Release machinery | Native acceptance can rerun one platform; receipt artifact names include the attempt. Windows subprocesses isolate inherited module paths and signature checks report bounded diagnostics. | `3071735`; `.github/workflows/release.yml`, `tools/installer_acceptance/acceptance.py`; `packages/apparatus-core/tests/test_installer_acceptance.py`. |
| Optional module | Separate Mailbox Survey prototype, deployment/repair, failure preservation, summaries and historical-content recognition. | `packages/apparatus-mailbox-survey/`; [module sequence](../plan/module-sequence.md). Not a core feature or included release package. |
| Evidence and docs | Dated discovery observations, integrated source acceptance, mailbox sample evidence, document-review comparison, plans and quickstarts. | [matrix](../certification/matrix.md), [retained acceptance](../certification/core-readiness-2026-10-12.md), [comparison](../certification/document-review-comparison-2026-10-12.md). These do not add runtime capability or refresh support claims. |

The entire `installer/` tree and seven built-in Skill bodies are unchanged in
this comparison. No native discovery adapter was added. Resume reports source
availability; it does not reconstruct task history or certify extraction
freshness. Existing source acceptance does not qualify a newly versioned wheel.

## Operator observations

Read-only GitHub inspection found required-reviewer rules on `pypi`, `signing`
and `release`. Signing permits branch `main` and tags `v*`; publication
environments permit tags `v*`. These observations must be refreshed before
dispatch/publication.

`APPARATUS_RELEASE_MODE` was absent. Both signing switches were `enabled`, and
the selected Windows provider was `azure-artifact-signing`. Thus hosted Windows
is the selected signing route; lack of an online certificate-store runner is
not a blocker for that route. The workflow names Ubuntu build, Windows 2025,
and macOS 15 hosted surfaces. Their availability and signing-provider operation
are not established until the candidate rehearsal succeeds.

The first variable read lacked repository permissions; selecting the existing
repository-authorized CLI account allowed the bounded read, after which the
previous account selection was restored. No configuration or credential changed.
Current PyPI trusted-publisher configuration was not independently visible;
prior publication is historical evidence only. Publication requires its live
protected workflow to succeed. No secrets or signing material were inspected.

## Release checklist

- [x] Inventory source/public identities and classify the delta.
- [x] Select core-only scope and omit optional experiments.
- [x] Draft Unreleased notes and focused implementation prompts.
- [x] PR-73: recheck version availability, version the candidate, verify package
  and payload parity, run full tests/current CI and isolated installed checks.
- [x] PR-73: refresh affected first-task/continuation checks on actual available
  AI-app surfaces; record unavailable variants without claiming their support.
- [x] Nominate the exact merged PR-73 commit as immutable candidate. Later
  documentation commits must not move the release source.
- [x] PR-74: dispatch a signed dry-run while main still names that candidate;
  verify source SHA, seven distributables, notes, checksums and both signatures.
- [x] Confirm rehearsal changed neither PyPI nor GitHub Releases.
- [ ] Present exact candidate/evidence for final publication approval.
- [ ] PR-75 operational delivery: publish the new candidate tag through the
  protected package job, then run native install/repair on Windows and macOS.
- [ ] Approve GitHub Release only after native acceptance succeeds; verify
  attachments/hashes/notes and return publish mode to unset.
- [ ] Record final delivery and support limits, or a precise unpublished handoff.

The [release runbook](../release-runbook.md) controls sequencing and cleanup.
The [signed rehearsal](../certification/release-rehearsal-0.0.3.md) fixes the
candidate at `5890838696157a9139d91903f029b7114f1412b5` and records the verified
artifact/signature results. Publication is explicitly withheld.
The [0.0.3 source qualification](../certification/release-candidate-0.0.3.md)
records PR-73's bounded results and remaining native-surface gaps; the checked
PR-73 rows take effect with its green, verified remote merge.
If candidate inputs change, repeat affected acceptance and rehearsal. A package
version published to PyPI cannot be removed from history or reused.
