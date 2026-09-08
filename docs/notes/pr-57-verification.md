# PR-57 verification

Two fresh Windows x64 acceptance attempts stopped at signature verification
before native installation. Their generic exit code did not retain the exact
cause. The same signed executable passed verification in the signing workflow
and an independent Windows PowerShell 5.1 VM probe. The Mac native install,
version check, workspace check, managed-file repair and project-preservation
checks passed against published 0.0.2 in run `34273605918`.

Microsoft documents the workflow's `pwsh` to Python to Windows PowerShell
[module-path inheritance failure](https://raw.githubusercontent.com/MicrosoftDocs/PowerShell-Docs/main/reference/7.4/Microsoft.PowerShell.Core/About/about_PSModulePath.md).
Windows child processes now omit only the case-insensitive `PSModulePath`
variable. Actual profile, identity and all other environment values remain.
The unchanged installer and its Windows PowerShell descendant receive this
neutral environment too. No trust store, revocation setting, certificate or
signed artifact changes.

Structured diagnostics retain only engine version, signature status,
signer/timestamp booleans and a fixed failure category. A successful probe
process is not acceptance: the parser still requires valid trust, signer and
timestamp before native installation. It rejects malformed, extra, duplicate
and unknown fields without retaining raw output. Platform selection uses a
fixed allowlist and defaults to both; receipts include the workflow attempt.

The focused acceptance and release-workflow suites passed: **105 tests**.
Tests cover child-environment preservation, invalid or malformed signature
results stopping before installer execution, and selected-platform routing.
Independent review found no blockers; `git diff --check` passed. Final CI
supplies full repository pytest. The native Windows rerun must establish the
runtime result; the original failures are retained, and their precise exception
remains unavailable. A local dirty-versus-clean reproduction was unavailable
because that VM has no PowerShell 7.
