# Core release delivery 0.0.3 — 2026-10-23

**Version 0.0.3 is public on PyPI and GitHub.** Both native installers passed
signature checks, real installation and repair. Public files match the verified
release bundle; publish mode is unset again. The GitHub Release was published
at 2026-10-24 03:20:58 UTC (October 23, 20:20:58 America/Los_Angeles).

## Source and authorization

The owner approved staged publication after reviewing the signed rehearsal and
the sequence in which PyPI becomes public before native acceptance. The
immutable `v0.0.3` tag names **`5890838696157a9139d91903f029b7114f1412b5`**,
the candidate accepted in [PR-73](release-candidate-0.0.3.md) and exercised by the
[signed rehearsal](release-rehearsal-0.0.3.md). The later documentation merge
`55d5f7123ee78276c69dd87b862729f41d634b2d` is not the tag target. All 263
recorded candidate inputs match both the tag and delivery checkout.

[Tagged Release run 40057337396, attempt 1](https://github.com/bc2116/apparatus/actions/runs/40057337396)
rebuilt and signed the release. Its successful protected PyPI job published
[apparatus-core 0.0.3](https://pypi.org/project/apparatus-core/0.0.3/).
The existing required-reviewer and tag policies remain in place; approvals use
the normal reviewer path. No secrets or signing material are retained here.
Operations use October 24 UTC timestamps, corresponding to October 23 in
America/Los_Angeles.

## Artifacts and signatures

The [delivery capsule](evidence/release-delivery-0.0.3/) preserves the exact
run/job identities, artifact IDs/digests, seven distributable hashes and
source comparisons. All four downloaded workflow archives matched GitHub's
digests. Every final distributable passed [SHA-256 verification](evidence/release-delivery-0.0.3/SHA256SUMS).
The final installers byte-match the corresponding signed uploads. The wheel,
source distribution and payload archive retain the accepted ordinary-build
hashes; all wheel members also match the normalized acceptance build.

| File | Integrity and signing claim |
|---|---|
| `apparatus-installer.exe` | Azure Authenticode signing; valid signer and timestamp verified. |
| `apparatus-installer.pkg` | Developer ID Installer signature, accepted Apple notarization, stapling and Gatekeeper verification passed. |
| Wheel, source distribution, payload ZIP and both bootstrap scripts | Checksums verified; these files do not carry the native installer signatures. |

The publish path requires exactly one successful Windows signer and a successful
Mac signer. Rebuilt native installer hashes differ from the rehearsal, so its
signatures and receipts are not reused as publication evidence. Signed wrappers
do not establish SmartScreen reputation, corporate policy approval, or signatures
on every dependency the installer retrieves.

## Native installation and repair

[Acceptance run 40057627691](https://github.com/bc2116/apparatus/actions/runs/40057627691)
was dispatched on `v0.0.3`, with `acceptance_run_id=40057337396` and both
platforms selected. Windows x64 passed. The first Mac check passed package
signature and Gatekeeper assessment, then stopped before installation when
`stapler validate` returned 68. The exact downloaded package passed the same
ticket check on the operator Mac. A fresh [Mac-only run 40057773383](https://github.com/bc2116/apparatus/actions/runs/40057773383)
then passed without changing source, workflow or artifact bytes. A transient
verification issue is consistent with these observations; its root cause was
not established. Both the failed first receipt and successful retry are retained.

| Platform | Observed result | Limits |
|---|---|---|
| Windows Server 2025 hosted x64 | Valid Authenticode signer/timestamp; native EXE installation and repair, version 0.0.3, workspace checks and project preservation passed. | Hosted runner; standard-user corporate policy and interactive installer UI remain untested. |
| macOS 15.7.9 hosted ARM64 | Developer ID Installer signature, Gatekeeper and ticket validation; native package installation and repair, version 0.0.3 and project preservation passed on retry. | Actual console session; Mac Intel and interactive installer UI remain untested. |

Both receipts identify release run `40057337396`, final artifact `12546007689`
and its exact archive digest. Both restore the removed shipped welcome Skill to
its original bytes and preserve the synthetic project sentinel. All seven
hashes match the verified release bundle, including the published wheel and
source distribution. The first workflow's overall failure remains a failure;
its passing Windows job is reconciled with the separate passing Mac run.

## Public delivery and cleanup

After independent receipt review, the normal protected release gate was
approved. The [GitHub Release](https://github.com/bc2116/apparatus/releases/tag/v0.0.3)
completed successfully. All eight attachments and both PyPI distributions were
downloaded anonymously and their bytes verified against the tagged bundle;
release notes also match. This includes both native installers and SHA256SUMS.
The signature observations were captured from the actual publication run.

Publish mode was returned to unset, its absence verified, and all three
required-reviewer rules rechecked. The immutable tag still names the candidate.
The [offline checker](evidence/release-delivery-0.0.3/verify_evidence.py) checks
source/artifact relationships, native receipts, approval ordering, public hashes
and capsule integrity. It does not repeat native installation or independently
attest a remote runner.

## Validation and limits

`uv sync --all-packages` followed by `uv run pytest` passed: **1,792 passed,
43 skipped**, 556.95 seconds. Independent native-gate review confirmed both
receipts before release approval. Independent final review approved the delivery record without blockers and
verified the downloaded archives, source parity, public-hash records and native
receipts. Current-head CI and verified remote merge complete this documentation
slice.
This slice changes release records and documentation, not product source,
installer behavior, workflow configuration, conformance fixtures or dependencies.

Native installer execution is separate from interactive installer presentation
and AI-app behavior. The [candidate record](release-candidate-0.0.3.md) retains
the four focused Codex CLI/Claude Code CLI conversations, the Claude wording
qualification, unavailable Cursor IDE and untested Codex desktop. This release
does not convert those observations into broad app certification. Optional
Mailbox Survey publication and deferred meeting-notes/relinking/email work are
outside this release.
