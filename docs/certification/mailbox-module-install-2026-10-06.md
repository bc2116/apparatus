# Mailbox Survey installation acceptance — 2026-10-06

This is source-build evidence for PR-64. It does not publish a package, install
into a user's work area, qualify automatic Skill discovery, or access mail.
The [synthetic evidence](evidence/mailbox-module-install-2026-10-06/verification.json)
records the implementation revision, isolated wheel digest and released-core
version. Later documentation-only commits do not change those tested bytes.

## Isolated package checks

The module 0.1.1 wheel was built with `uv build --package
apparatus-mailbox-survey --wheel`. A fresh environment containing only this
wheel and its required dependency validated the packaged example. Core and
provider SDKs were absent; deployment commands correctly reported unavailable.

A second isolated environment used the wheel's `lifecycle` extra and published
`apparatus-core==0.0.2`. In a disposable, explicitly enrolled work area it passed:

- Read-only absent status and installation of exactly the two released assets.
- Repeated installation without content changes.
- Repair after removal of the exact report-format reference.
- Preservation of module assets through repeated released-core initialization.
- An edited Skill plus missing reference blocked repair with no partial write.

The initial disposable path used a macOS system alias. The retained-root
boundary rejected that path; the acceptance run used its physical directory.
This is an explicit-path requirement, not automatic path resolution.

## Explicit native use

A native Codex worker was directed to read the deployed Skill and relative
reference, then produce a report from the packaged eight-message synthetic
sample. Requested routing was Luna with medium effort; provider-internal
runtime attribution was not available. No AI CLI or live connector was used.
The worker had earlier task context, so this is an integration exercise rather
than a blind quality benchmark.

The resulting [report](evidence/mailbox-module-install-2026-10-06/report.yaml)
passed structural validation and supervisor source readback. All eight items
are accounted for; the ambiguous appointment remains uncategorized; the
embedded source instruction is ignored. No unsupported weekly cadence is
inferred. Source and deployed-asset digests remained unchanged after the run.
The report is the only worker-created file.

## Limits

Module assets remain outside core managed recovery. These commands only create
missing released files; edited or foreign assets block repair. Update/removal,
deployed-version ownership, core-upgrade compatibility beyond the tested
version, automatic discovery and a real authorized connector path need later
qualification. The POSIX adapter bounds every retained file read; Windows uses
core's retained locking primitives and needs its platform CI. Full-suite and
exact-head CI results are recorded on the pull request.
