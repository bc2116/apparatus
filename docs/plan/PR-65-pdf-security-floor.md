# PR-65 — Require the patched PDF dependency

## Outcome

Complete the existing dependency update PR by requiring `pypdf>=6.19.0` in
the distributable core package as well as resolving 6.19.0 in `uv.lock`.
A repository lockfile alone does not constrain an installed wheel's dependency
resolver. Preserve existing extraction behavior, package version and payload.

The eight open PDF dependency alerts reported for this repository on
2026-10-06 are fixed across releases 6.17.0 through 6.19.0. This is the
repository's observed alert set, not the total upstream advisory count.
Relevant maintainer sources are the
[release notes](https://github.com/py-pdf/pypdf/releases/tag/6.19.0) and
[security advisories](https://github.com/py-pdf/pypdf/security/advisories).
Apparatus uses the reader, pages and text extraction APIs; it does not override
parser configuration or invoke writer, page-label or attachment APIs. A fixed
dependency version does not establish that arbitrary PDFs are safe to parse.

## Scope

Update core's declared minimum and lock metadata. Continue the existing
Dependabot PR instead of opening a duplicate; use a local `pr-65-pdf-security`
branch and push the reviewed continuation to its existing remote head.
Add this prompt and the plan status row. Do not copy advisory payloads,
change source extraction, publish a package, or revise native installers.

## Acceptance

- Review the complete dependency diff and preserve unrelated resolutions.
- Existing Library ingestion, citation and cache tests pass with 6.19.0.
- Build a core wheel and inspect `Requires-Dist`: versions below 6.19.0 are
  excluded. Exercise its PDF extraction with generated synthetic input in an
  isolated environment and verify extraction errors remain content-free.
- `uv run pytest` passes; current-head cross-platform CI is green before merge.
- Verify remote main after merge and read back the relevant alert states.
  Do not claim an alert is resolved merely because a new version was selected.
- Set this plan row to `✅ landed` in the same PR. The existing public 0.0.2
  artifacts are unchanged; a later release is needed to distribute this floor.
