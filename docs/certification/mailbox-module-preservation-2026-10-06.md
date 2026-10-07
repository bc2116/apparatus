# Mailbox Survey failure preservation — 2026-10-06

PR-66 supersedes the failed-install compensation contract in PR-64. A failed
publication retains partial module files and directories for inspection instead
of deleting their pathnames after an ownership check. An incomplete Skill may
remain discoverable; do not use it until module `status` reports current.

## Installed package evidence

The [verification record](evidence/mailbox-module-preservation-2026-10-06/verification.json)
binds the implementation revision, module 0.1.2 wheel digest and resource hashes.
An isolated environment imported that wheel and published Core 0.0.2 from
installed packages. It passed all 231 module tests, with the Windows junction
case skipped on macOS.

A separate disposable enrolled work area verified that an injected second-file
failure retained the first exact asset and reported failure. Read-only status
reported partial; explicit repair completed the installation. An edited first
asset plus missing companion reported conflict, blocked repair and preserved
the edit without creating the missing companion. The packaged report remained
structurally valid. No mailbox, provider or personal content was used.

Six new focused regressions failed when run against the previous deployment
implementation and passed with this change. They cover the former final-unlink
boundary, partial and zero writes, synchronization failure, detached file parent
and failed child handoff. Native independent review found no actionable issue.

## Coverage limits

This qualifies the module adapter against the named Core release. It does not
change shared Core deletion behavior, create an atomic directory-creation
primitive, guarantee rollback, or establish process-interruption recovery.
Windows retains Core's exact-handle low-level creation protections; the module
performs no outer compensation on either platform. Cross-platform CI and full
suite results are recorded on the pull request.

The deployed Skill and reference bytes are unchanged. Module update, removal,
historical release recognition, automatic discovery, managed snapshot recovery
and live mailbox qualification remain separate work. No public package or
installer is published by this evidence.
