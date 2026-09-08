# PR-52 verification

The final local macOS run passed in an isolated worktree environment:

```text
uv run pytest packages/apparatus-core/tests/test_release_workflow.py -q
17 passed

uv run pytest
1278 passed, 38 skipped in 546.24s
```

The focused suite executes provider resolution, metadata validation and output
framing, the signer-result publication gate, and each provider's signed-file
replacement followed by checksum verification. Static checks pin the Azure
job's runner, environment, permissions, actions, credential exclusions, and
signature-before-dry-run-before-upload ordering. Missing metadata, malformed
identifiers, endpoint injection, duplicate/mismatched signers, and failed,
cancelled or unknown results fail the applicable gate.

All three new PowerShell steps parsed successfully using Windows PowerShell on
an ARM64 Windows VM. An additional runtime input-fixture attempt was blocked by
that VM's existing script execution policy before the script ran. The policy
was left unchanged; syntax validation does not establish runtime signing.

Independent static inspection and root review were completed. Root review
corrected configuration output framing, input checks, embedded-bootstrap log
verification, and resource-name limits before the final full suite. Core,
starter, conformance fixtures, installer sources, and package version are
unchanged. CI supplies final-commit platform verification.

Live Azure signing remains untested pending publisher enrollment and an
approved signed rehearsal. No provider, credential, or publishing configuration
was enabled. Neither simulated checks nor workflow code establish a real
signature or a public release.
