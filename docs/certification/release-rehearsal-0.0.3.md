# Signed core rehearsal 0.0.3 — 2026-10-23

The signed rehearsal passed. Both selected signing jobs succeeded, all seven
distributable checksums verified, and the final installers match the signed
job uploads exactly. **Publication is withheld at the owner's direction.**
No 0.0.3 tag, PyPI version or GitHub Release was created.

## Immutable candidate and run

The candidate is **`5890838696157a9139d91903f029b7114f1412b5`**, the verified
remote merge of [GitHub PR #74](https://github.com/bc2116/apparatus/pull/74)
(planned PR-73). Its reviewed head was `298232dd445cccbbac84f6a3b4a194ba6a66ef6b`;
all 263 recorded source-input hashes match the [accepted source](release-candidate-0.0.3.md).
Current-head CI was green before merge. This is the future tag target;
the later rehearsal-evidence commit must not replace it.

[Release run 39994962103, attempt 1](https://github.com/bc2116/apparatus/actions/runs/39994962103)
used `workflow_dispatch` on main at that exact SHA with an empty
`acceptance_run_id`. It was dispatched before any rehearsal-record merge.
The workflow hash is recorded in the capsule. macOS signing and Azure Windows
signing were enabled; the certificate-store path was skipped. Publish mode
was unset. The protected signing environment retained its required reviewer
and branch rules, and approval used the normal authorized reviewer path.

## Artifact and signature evidence

The [capsule](evidence/release-rehearsal-0.0.3/) records run/job identities,
artifact IDs/digests, source parity, selected verification output and tool
identities. Four downloaded artifact archives matched GitHub's SHA-256 digests:
release inputs, the two signed uploads, and the final release bundle.

The final bundle contains these seven files plus release notes and
[SHA256SUMS](evidence/release-rehearsal-0.0.3/SHA256SUMS):

| Distributable | Verification |
|---|---|
| `apparatus-payload-0.0.3.zip` | Matches the accepted candidate's exact archive hash. |
| `apparatus_core-0.0.3.tar.gz` | Matches the candidate's ordinary build hash. |
| `apparatus_core-0.0.3-py3-none-any.whl` | Matches the ordinary build hash; every member also matches the normalized acceptance wheel. |
| `bootstrap-apparatus.ps1` | Matches release-input bytes and the frozen source. |
| `bootstrap-apparatus.sh` | Matches release-input bytes and the frozen source. |
| `apparatus-installer.exe` | Matches the successful Azure signing upload exactly. |
| `apparatus-installer.pkg` | Matches the successful macOS signing/notarization upload exactly. |

All seven checksum entries were checked independently after download; no extra
distributables were present. Release notes identify this as an unpublished
dry-run. The manifest also hashes those notes, which SHA256SUMS itself excludes.
Binary files stay in workflow artifacts rather than this evidence capsule.

Windows `signtool verify /pa /tw` succeeded. The same successful verification
step required Valid Authenticode status, the protected publisher subject,
accepted code-signing EKU and current signer/timestamp certificates. The signed
installer's dry-run verified and executed its embedded bootstrap. These claims
derive from the exact workflow assertions and retained observed output;
certificate identities and credential-bearing setup logs are omitted.

macOS `productsign` completed, notarization reported **Accepted**, and stapling
and staple validation succeeded. `pkgutil --check-signature` reported an Apple
distribution certificate; `spctl` reported Notarized Developer ID. The signed
package's payload and launcher verification passed after signing.

Build observations include the Inno Setup 7 32-bit compiler banner, successful
verification of the pinned 7.0.2 download, macOS 15.7.9 build 24G830, and the
`pkgbuild`/`productbuild` executable hashes. Runner image identities are retained.
Exact signtool, productsign, notarytool and stapler versions were not emitted;
the record does not infer them from the runner labels.

## Validation and boundary

The offline checker validates captured job outcomes, artifact and source
relationships, signing observations, publication inventories and capsule
integrity. It does not rerun signing or substitute for native installation.
`uv run pytest` passed: **1,792 passed, 43 skipped**, 547.00 seconds. Independent
review approved the complete record without blockers and separately checked
the downloaded artifact bytes; details are in `validation.json`. The first local test invocation failed collection
because the new worktree lacked workspace packages; `uv sync --all-packages`,
the existing CI setup command, corrected that environment before rerunning.
No product source, workflow, fixture or dependency changed for this rehearsal.

The before/after GitHub Release and PyPI version inventories are unchanged.
PyPI lists only 0.0.2, no v0.0.3 tag exists, publish mode is still unset, and both
publication jobs were skipped. Existing app observations and unavailable
surfaces retain the limits in the candidate record.

This establishes signed rehearsal. Installing and repairing the published
0.0.3 package on Windows and macOS remains a later acceptance gate; the rehearsal
does not supply that evidence. Future publication will rebuild/sign artifacts,
so its hashes and native receipts must be checked against that tagged run.

## Publication handoff

Hold here until the owner explicitly approves release of the candidate above.
After approval, follow the [release runbook](../release-runbook.md): recheck
collisions/gates, enable publish mode, tag the immutable candidate, publish
through the protected package job, and perform native install-and-repair
acceptance against the same tagged run. Approve the GitHub Release only after
both platform receipts pass, then verify public assets and unset publish mode.
No publication step is authorized by this rehearsal record.
