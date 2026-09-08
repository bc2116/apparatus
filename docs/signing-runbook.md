# Signing runbook

This runbook covers identity acquisition, enrollment, and release enablement.
It does not put certificates, keys, passwords, or notarization credentials in
this repository.

## 1. Choose and enroll with a signing service

For Windows, choose either a standard code-signing certificate, an EV
code-signing certificate, or a cloud-signing service. [Microsoft states](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)
that EV certificates no longer receive immediate SmartScreen reputation. A valid
signature still accrues reputation over time; do not buy an enrollment on a
promise to bypass SmartScreen or corporate policy.
Cloud signing can keep the private key in the provider's service instead of in
GitHub.

Windows procurement and enrollment are explicit operator steps:

1. Compare public certificate authorities and cloud-signing services for
   platform support, identity-validation requirements, hardware or cloud KSP
   integration, renewal, timestamp service, and stable-subject renewal.
2. Apply for a public code-signing identity in the legal publisher name that
   IT should see.
3. Complete the CA or service's organization or individual identity checks,
   including its required registration records and independently verified
   contact details, then accept its subscriber agreement.
4. Complete the hardware-token or cloud-KSP enrollment ceremony. Do not export
   the resulting private key.
5. Use the provider console and Windows certificate tools to confirm the issued
   certificate has the approved subject, the Code Signing EKU, a current
   validity window, and a working private-key association.

For macOS, enroll in the Apple Developer Program and obtain a Developer ID
Installer identity. The release `.pkg` is the signed macOS artifact. The flat
shell-script fallback remains unsigned and is covered by `SHA256SUMS`.

## 2. Store the material outside this repository

Create protected GitHub environments named `signing` and `release` with
required reviewers. `signing` protects access to signing material; `release`
protects creation of the public GitHub Release after PyPI publication. An
environment name alone is not evidence that required-reviewer protection is
configured.
Configure the `signing` environment's deployment-branch policy to allow the
protected default branch for signed `workflow_dispatch` rehearsals and `v*`
tags for approved releases. Do not broaden that policy to pull requests, forks,
or unrelated branches.
For the certificate-store provider, register a dedicated x64 Windows runner to this repository with
the fixed labels `self-hosted`, `Windows`, `X64`, and
`apparatus-signing-windows`. Environment-level variables cannot select a runner
because GitHub resolves `runs-on` before opening the environment. Restrict the
runner to this repository and reviewed releases from the protected default
branch; never route pull requests, fork code, or unrelated workloads to it.
Keep its service account and workspace isolated, and take the runner offline
outside reviewed release windows. Its CurrentUser certificate store exposes
the public code-signing certificate through its hardware- or cloud-backed KSP.
The workflow resolves the validly signed x64 `signtool.exe` from the
administrator-controlled Windows SDK directory and never executes a configured
command path.

Set protected environment variables
`APPARATUS_WINDOWS_SIGNING_CERTIFICATE_THUMBPRINT`,
`APPARATUS_WINDOWS_SIGNING_CERTIFICATE_SUBJECT`, and
`APPARATUS_WINDOWS_SIGNING_TIMESTAMP_URL`. These are certificate metadata, not
private material. The certificate-store workflow invokes native `signtool`
against the certificate store; no PFX, key, password, or arbitrary command
path is stored here.

Store macOS signing and notarization values under these six exact `signing`
environment secret names:
`APPARATUS_MACOS_SIGNING_CERTIFICATE_BASE64`,
`APPARATUS_MACOS_SIGNING_CERTIFICATE_PASSWORD`,
`APPARATUS_MACOS_SIGNING_IDENTITY`, `APPARATUS_MACOS_NOTARY_APPLE_ID`,
`APPARATUS_MACOS_NOTARY_TEAM_ID`, and
`APPARATUS_MACOS_NOTARY_APP_PASSWORD`. Do not add certificate files, keys,
passwords, notarization credentials, or copied secret values to a branch,
issue, pull request, or release notes.

## 3. Enable Windows signing

1. Confirm that the certificate's subject is the publisher identity intended
   for all releases. AppLocker and WDAC publisher rules depend on that stable
   subject; changing it can require IT to create new allow rules.
2. Configure the timestamp server approved by the certificate provider. A
   timestamp lets a validly signed historical release remain verifiable after
   the certificate expires.
3. Provision the dedicated, isolated runner with a hardware- or cloud-KSP
   backed key in `Cert:\CurrentUser\My`. Confirm its fixed repository-level
   runner labels and Windows SDK installation. In the protected environment set
   `APPARATUS_WINDOWS_SIGNING_CERTIFICATE_THUMBPRINT`,
   `APPARATUS_WINDOWS_SIGNING_CERTIFICATE_SUBJECT`, and
   `APPARATUS_WINDOWS_SIGNING_TIMESTAMP_URL`.
4. Set repository variable `APPARATUS_SIGN_WINDOWS` to `enabled`.
5. Run a release `workflow_dispatch` dry-run first and approve the protected
   `signing` environment. Verify that
   `apparatus-installer.exe` has a valid Authenticode signature, still passes
   the embedded-script integrity and dry-run checks, replaces the unsigned
   release copy, and has the matching entry in `SHA256SUMS`. The flat
   PowerShell script remains an unsigned, checksummed fallback. Only then use
   the normal tagged release path.

### Optional Azure Artifact Signing enrollment

Azure Artifact Signing is an alternative for an individual publisher who does
not want a dedicated signing runner. Enrollment, pricing, and the provider's
availability rules are separate operator decisions; consult current Microsoft
documentation before proceeding. Review Microsoft's [signing integration](https://learn.microsoft.com/en-us/azure/artifact-signing/how-to-signing-integrations)
and [OIDC integration](https://github.com/Azure/artifact-signing-action/blob/c7ab2a863ab5f9a846ddb8265964877ef296ee82/docs/OIDC.md)
before proceeding. Choose a **Public Trust** certificate profile,
never a test or private profile. Grant the GitHub OIDC application only the
**Artifact Signing Certificate Profile Signer** role scoped to that profile.

Create a federated credential whose subject is exactly
`repo:OWNER/REPO:environment:signing`. Separately configure the protected
default branch and `v*` tags in the environment deployment-branch policy.
Environment-scoped OIDC approval does not by itself
bind the identity to a particular workflow filename, so restrict the release
workflow through repository review and branch protection.

Set these protected `signing` environment variables:
`APPARATUS_AZURE_SIGNING_TENANT_ID`, `APPARATUS_AZURE_SIGNING_CLIENT_ID`,
`APPARATUS_AZURE_SIGNING_SUBSCRIPTION_ID`, `APPARATUS_AZURE_SIGNING_ENDPOINT`,
`APPARATUS_AZURE_SIGNING_ACCOUNT_NAME`,
`APPARATUS_AZURE_SIGNING_CERTIFICATE_PROFILE_NAME`, and the existing exact
`APPARATUS_WINDOWS_SIGNING_CERTIFICATE_SUBJECT`. Set repository variable
`APPARATUS_WINDOWS_SIGNING_PROVIDER` to `azure-artifact-signing`, then enable
`APPARATUS_SIGN_WINDOWS` and run an approved signed rehearsal. Confirm native
Authenticode and timestamp verification, exact publisher identity, the observed
rotating certificate thumbprint, embedded-bootstrap dry-run, and `SHA256SUMS`.

Use an account name of 3–24 characters and a profile name of 5–100 characters:
start with a letter and use letters, digits, and single internal hyphens.
See Microsoft's [account](https://learn.microsoft.com/en-us/azure/templates/microsoft.codesigning/codesigningaccounts)
and [profile](https://learn.microsoft.com/en-us/azure/templates/microsoft.codesigning/codesigningaccounts/certificateprofiles)
resource constraints. Copy the publisher subject exactly from the enrolled
certificate, including internal spaces.

To roll back, unset `APPARATUS_SIGN_WINDOWS` or set the provider to
`certificate-store`; leaving it unset also selects the certificate-store path.
No simulated workflow check is evidence of a live Azure signature.

## 4. Enable macOS package signing

1. Add the Developer ID Installer identity plus the Apple ID, team ID, and app-specific
   password for notarization to `signing`. The workflow creates its
   `apparatus-notary` keychain profile on the fresh runner.
2. Set repository variable `APPARATUS_SIGN_MACOS` to `enabled` and run a
   `workflow_dispatch` dry-run through the protected `signing` environment.
   Verify the package is Developer ID signed,
   notarized, stapled, still contains the exact repository bootstrap script,
   replaces the unsigned package, and has the matching entry in `SHA256SUMS`.
   Verify with `pkgutil --check-signature`, `spctl --assess --type install`,
   and `xcrun stapler validate` before a tagged release.
3. Keep the certificate subject stable across releases so IT can use durable
   publisher rules where its macOS controls require them.

## 5. Record the result

Record the dry-run URL, signing-variable state, signature-verification result,
notarization result when applicable, and checksum verification in the release
review. Leave either gate unset to keep its signing job skipped. A skipped job
is expected before certificates exist; it is not evidence that signing occurred.
