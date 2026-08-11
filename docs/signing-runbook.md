# Signing runbook

This runbook enables release signing after the operator has acquired the
required identities. It does not put certificates, keys, passwords, or
notarization credentials in this repository.

## 1. Choose the signing service

For Windows, choose either a standard code-signing certificate, an EV
code-signing certificate, or a cloud-signing service. A standard certificate
usually costs less but may have less initial SmartScreen reputation. EV and an
established publisher reputation can shorten that warning period, but neither
removes it by promise: a valid signature still accrues reputation over time.
Cloud signing can keep the private key in the provider's service instead of in
GitHub.

For macOS, enroll in the Apple Developer Program and obtain a Developer ID
Installer identity. A future `.pkg` must be signed, submitted for Apple
notarization, and stapled before release. The current macOS bootstrapper is a
shell script; Developer ID signing does not apply to it, so it remains unsigned
until the package wrapper exists.

## 2. Store the material outside this repository

Create a protected GitHub environment named `signing` with required reviewers.
For Windows, provision an operator-controlled signing runner whose CurrentUser
certificate store exposes the public code-signing certificate through its
hardware- or cloud-backed key provider. Configure the protected environment
with its runner label, certificate thumbprint, certificate subject, and
timestamp URL. The workflow invokes native `signtool` against that provisioned
key; no PFX, key, password, or provider-specific action is stored here. Store
the macOS signing
identity and its password there, plus the Apple ID, team ID, and app-specific
password used to create the ephemeral notarization profile on the runner when a
package is available. The workflow refers only to named secrets. Do not add
certificate files, keys, passwords, notarization credentials, or copied secret
values to a branch, issue, pull request, or release notes.

## 3. Enable Windows signing

1. Confirm that the certificate's subject is the publisher identity intended
   for all releases. AppLocker and WDAC publisher rules depend on that stable
   subject; changing it can require IT to create new allow rules.
2. Configure the timestamp server approved by the certificate provider. A
   timestamp lets a validly signed historical release remain verifiable after
   the certificate expires.
3. Provision the operator-controlled runner with a hardware- or cloud-KSP
   backed key in `Cert:\CurrentUser\My`. In the protected environment set
   `APPARATUS_WINDOWS_SIGNING_RUNNER`,
   `APPARATUS_WINDOWS_SIGNING_CERTIFICATE_THUMBPRINT`,
   `APPARATUS_WINDOWS_SIGNING_CERTIFICATE_SUBJECT`, and
   `APPARATUS_WINDOWS_SIGNING_TIMESTAMP_URL`.
4. Set repository variable `APPARATUS_SIGN_WINDOWS` to `enabled`.
5. Run a release `workflow_dispatch` dry-run first. Verify that the signed
   PowerShell script has a valid Authenticode signature, replaces the unsigned
   release copy, and has a new entry in `SHA256SUMS`. Only then use the normal
   tagged release path.

## 4. Enable macOS package signing

1. Do not set `APPARATUS_SIGN_MACOS` until a packaged installer exists. The
   current script-only release has no macOS signing output.
2. Add the Developer ID identity plus the Apple ID, team ID, and app-specific
   password for notarization to `signing`. The workflow creates its
   `apparatus-notary` keychain profile on the fresh runner.
3. Set repository variable `APPARATUS_SIGN_MACOS` to `enabled` and run a
   `workflow_dispatch` dry-run. Verify the package is Developer ID signed,
   notarized, stapled, replaces the unsigned package, and is re-listed in
   `SHA256SUMS`.
4. Keep the certificate subject stable across releases so IT can use durable
   publisher rules where its macOS controls require them.

## 5. Record the result

Record the dry-run URL, signing-variable state, signature-verification result,
notarization result when applicable, and checksum verification in the release
review. Leave either gate unset to keep its signing job skipped. A skipped job
is expected before certificates exist; it is not evidence that signing occurred.
