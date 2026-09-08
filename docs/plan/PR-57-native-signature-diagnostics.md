# PR-57 — Diagnose native Windows signature checks

Published 0.0.2 has successful signing-job verification and a passing real Mac
install-and-repair result. Two fresh Windows acceptance runs stopped before
installation at the combined signature/timestamp check. Their generic exit
code does not distinguish a verifier error from an invalid signature. The same
installer also verifies on a separate Windows VM. Preserve these observations
without inferring a cause or weakening the public-release gate.

## Deliverables and acceptance

- Keep the signed release, package, starter and installer bytes unchanged.
  This is an acceptance-tool correction, not a new package version.
- Remove `PSModulePath` case-insensitively from the Windows subprocess
  environment, including the native installer and its descendants. The runner
  starts Python from PowerShell 7; Microsoft's documented intermediate-process
  behavior can otherwise pass incompatible module paths to Windows PowerShell.
  Preserve the actual user profile and every other environment value. Do not
  change global/user settings or switch signature policy.
- Record bounded structured signature diagnostics: engine version, signature
  status, signer/timestamp presence and a safe fixed failure category. Do not
  expose raw command output, paths, environment values, certificates or
  exception messages. Reject malformed diagnostics. Require valid signature,
  signer and timestamp before invoking the installer, as before. Never add
  trust roots, disable revocation or accept an invalid status to make CI pass.
- Add an optional manual-dispatch platform choice, defaulting to both, so one
  failed platform can be checked without repeating an unchanged passing Mac
  test. Empty source-run input retains ordinary rehearsal behavior. Preserve
  read-only permissions, exact source/tag/artifact/PyPI validation, protected
  release approval and immutable action pins. Include the run attempt in
  receipt artifact names so a future job retry does not collide with evidence.
- Retain both failed Windows observations and the successful Mac receipt.
  Run one focused native Windows install/repair after the correction; only
  passing native evidence for the same published bytes permits release.
- Exercise fail-closed diagnostic parsing and platform selection, run focused
  existing acceptance/workflow tests, and use final CI for full pytest.
  Update the plan row and verification note in this PR. Do not rerun app chats.
