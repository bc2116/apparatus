# PR-52: Optional hosted Windows signing

## Problem

The Windows release job requires an operator-provisioned x64 signing machine.
An individual publisher using a hosted signing service should also be able to
sign on an ephemeral GitHub-hosted Windows runner. Enrollment remains an
operator decision; adding support must not enable a service or publish a release.

## Scope

Add an optional Microsoft Azure Artifact Signing path. Preserve the existing
certificate-store signing path, macOS signing, PyPI trusted publishing, and
the protected public-release acceptance gate. Do not change core, payload,
installer behavior, package version, or repository/cloud configuration.

## Contract

1. Read repository-level `APPARATUS_WINDOWS_SIGNING_PROVIDER` during the build
   configuration check. Empty means `certificate-store` for compatibility.
   Accept only that value or `azure-artifact-signing`; reject other values
   before signing. Pass the resolved selection as a build output so later
   jobs use the same selection.
2. Keep the existing fixed self-hosted Windows labels. Add a distinct Azure
   signer job with fixed `windows-2025`. Both require the existing
   `APPARATUS_SIGN_WINDOWS == enabled` switch and their matching provider.
   Both use the protected `signing` environment. Only the Azure signer gains
   `id-token: write`, alongside `contents: read`; never widen workflow-global
   token permissions or permit secret-based authentication fallback.
3. Validate Azure environment metadata before authentication: tenant, client,
   and subscription UUIDs; HTTPS regional `*.codesigning.azure.net` endpoint
   with no credentials, port, query, or additional path; nonempty service
   account and certificate-profile identifiers; and exact publisher subject.
   Reject control characters and malformed values; reject whitespace in machine
   identifiers and leading/trailing whitespace in the subject, while allowing
   ordinary spaces within a legal publisher subject. Feed validated
   values as action inputs through step outputs, not interpolated shell code.
4. Use immutable commits of official `Azure/login` and
   `Azure/artifact-signing-action`. Authenticate with GitHub OIDC and use only
   that Azure CLI credential in the signing action. Disable dependency caches
   and every other credential source. Limit signing to the exact downloaded
   `apparatus-installer.exe`, use SHA-256, and request Microsoft's RFC 3161
   timestamp. No arbitrary executable or signing-command configuration.
5. Verify the downloaded input is exactly one ordinary installer file. After
   signing, require valid native Authenticode verification, the exact protected
   publisher subject, Code Signing EKU, a valid signing-certificate validity
   interval, and a timestamp certificate. Run trusted SDK `signtool verify`
   with Authenticode policy and timestamp warning enabled, treating nonzero as
   failure. Resolve and validate the SDK tool as in the existing signing job.
   Reject test-profile lifetime-signing EKU. The Azure provider rotates
   short-lived certificates, so do not apply the certificate-store thumbprint
   pin to this path; record the observed thumbprint for the release receipt.
   The Azure trust contract is the protected account/profile selection, OIDC
   signer role on that profile, trusted public certificate chain, and exact
   publisher identity. Keep the store path's thumbprint check intact.
6. Exercise the signed wrapper's existing dry-run and embedded-bootstrap
   verification. Upload a distinctly named Azure signed artifact only after
   every check passes. Do not execute an unverified signed candidate.
7. Assembly must accept exactly one successful Windows signer with the other
   skipped. Fail for two successes, failures, cancellations, or an unexpected
   status, or a signer inconsistent with the resolved provider. Validate the
   dry-run mode as exactly `true` or `false`. A dry run may still have both Windows signers skipped; publication
   may not. Publication still requires successful macOS signing. Download only
   the selected verified artifact, replace the unsigned wrapper, then generate
   and check final checksums. All dry runs remain artifacts-only.

## Operator documentation

Document optional individual enrollment, Public Trust profile (not test/private),
profile-scoped Certificate Profile Signer role, exact GitHub environment
federated subject, and main/`v*` environment branch restrictions. Explain that
environment-scoped OIDC alone does not bind a specific workflow filename.
Describe metadata, enablement, disabled rollback, and the required signed
rehearsal. Do not promise SmartScreen bypass or corporate policy acceptance.
Correct the outdated suggestion that buying EV provides an immediate
SmartScreen advantage. Keep provider choice and paid enrollment separate.

## Acceptance

- Execute configuration validators for default/store/Azure/unknown providers,
  valid metadata, and missing/malformed metadata including hostile endpoint and
  newline cases. Validate before either Azure action can run.
- Exercise assembly's full result matrix, including both skipped in dry run,
  each single successful signer, duplicate success, failure/cancelled states,
  unknown statuses, and missing macOS signature for publication.
- Inspect immutable action pins, job permissions, protected environment,
  credential exclusions, exact input file, native signature/timestamp checks,
  and post-sign dry-run ordering.
- Preserve package/core/payload/installer byte identity. Run focused workflow
  tests, `uv run pytest`, and CI. Live Azure signing stays explicitly untested
  until the publisher enrolls and authorizes a rehearsal; simulated checks do
  not establish a real signature.
- Record validation in `docs/notes/pr-52-verification.md`; mark this plan row
  landed in the implementation PR only when implementation is complete.

## Verified vendor interfaces

- Azure login v2: `7184910d9eb2b1c5e48f7073824a90609bb9b6d6`.
- Artifact Signing v2: `c7ab2a863ab5f9a846ddb8265964877ef296ee82`.
- [Microsoft signing integration](https://learn.microsoft.com/en-us/azure/artifact-signing/how-to-signing-integrations)
- [OIDC integration](https://github.com/Azure/artifact-signing-action/blob/c7ab2a863ab5f9a846ddb8265964877ef296ee82/docs/OIDC.md)
- [Service roles and certificate profiles](https://learn.microsoft.com/en-us/azure/artifact-signing/concept-resources-roles)

These interfaces were inspected on September 8, 2026. Implement original
workflow steps against the documented interfaces; do not copy vendor prose or
implementation bodies.
