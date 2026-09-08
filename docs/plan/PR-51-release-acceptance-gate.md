# PR-51 — Complete the first-publication acceptance gate

The production installer installs apparatus-core from PyPI, so actual install-and-repair acceptance requires that package to exist. Today the tagged publish workflow creates the public GitHub installer release immediately after PyPI publication. It also permits skipped signing jobs during assembly. Close this release-only gap without changing the installer, payload, core behavior, or app test target.

## Deliverables and acceptance

- In `.github/workflows/release.yml`, fail assembly explicitly in publish mode unless both platform signing jobs succeeded. Dry-run assembly must continue to permit skipped signers. Failed or cancelled signing must never permit publication. Retain all existing immutable action pins, permissions, tagged version checks, signing isolation, and checksum verification.
- Place the public GitHub Release job behind a dedicated GitHub `release` environment. Document that its required-reviewer protection must be configured before a publish run; an environment name alone is not evidence of protection. Manual workflow dispatch remains dry-run. All dry-run paths, including tag pushes, create workflow artifacts only and never a public Release. This closes the legacy unsigned dry-run prerelease path under ADR-0005.
- Update `docs/release-runbook.md` and relevant signing guidance with the exact first-project PyPI pending trusted-publisher route, protected pypi/signing/release environments, signed rehearsal, package publication, download of the same workflow's signed artifacts, actual per-OS install-and-repair validation, and only then release approval. State that PyPI publication itself is public and a package version cannot be reused. The public installer is still signed from its first release. No provider choice or account change is implied.
- Add focused meaningful workflow tests using existing repository patterns. Cover publish missing/one/both signatures, dry-run with skipped signers, the release environment and ordering, and unchanged manual no-publication behavior. Run these tests and the required full pytest once. CI provides Windows/platform coverage; do not rerun native app chats for this workflow/doc-only change.
- Add a concise verification note and this plan row as landed in the same PR. No real tag, publisher setup, credential access, package upload, GitHub Release, or Sites mutation in implementation work.

## Scope boundary

This prepares a reviewable release gate. Apple activation, signing credentials, Windows provider selection, protected-environment configuration, PyPI pending publisher setup and actual installer acceptance remain separately verified operator steps. The parent Astra agent retains review and merge judgment.
