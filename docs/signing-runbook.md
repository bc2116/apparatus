# Signing runbook

This runbook covers identity acquisition, enrollment, and release enablement.
It does not put certificates, keys, passwords, or notarization credentials in
this repository.

## 1. Choose and enroll with a signing service

For Windows, choose either a standard code-signing certificate, an EV
code-signing certificate, or a cloud-signing service. A standard certificate
usually costs less but may have less initial SmartScreen reputation. EV and an
established publisher reputation can shorten that warning period, but neither
removes it by promise: a valid signature still accrues reputation over time.
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

Create a protected GitHub environment named `signing` with required reviewers.
For Windows, register a dedicated x64 Windows runner to this repository with
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
private material. The workflow invokes native `signtool` against the
certificate store; no PFX, key, password, provider-specific action, public
cloud identity token, or arbitrary command path is stored here.

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
5. Run a release `workflow_dispatch` dry-run first. Verify that
   `apparatus-installer.exe` has a valid Authenticode signature, still passes
   the embedded-script integrity and dry-run checks, replaces the unsigned
   release copy, and has the matching entry in `SHA256SUMS`. The flat
   PowerShell script remains an unsigned, checksummed fallback. Only then use
   the normal tagged release path.

## 4. Enable macOS package signing

1. Add the Developer ID Installer identity plus the Apple ID, team ID, and app-specific
   password for notarization to `signing`. The workflow creates its
   `apparatus-notary` keychain profile on the fresh runner.
2. Set repository variable `APPARATUS_SIGN_MACOS` to `enabled` and run a
   `workflow_dispatch` dry-run. Verify the package is Developer ID signed,
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
