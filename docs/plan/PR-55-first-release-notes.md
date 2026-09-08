# PR-55 — Prepare the first release notes

The package is still version `0.0.1`, but the changelog has no matching version
heading. The release workflow would publish its generic fallback text rather
than a useful description of the implemented product.

## Deliverables and acceptance

- Add an exact `## v0.0.1` changelog section with concise, source-grounded
  features and practical limitations. Preserve the current pre-alpha status;
  this change does not advance certification or publish a release.
- Cover the implemented work area, Memory, local Library, seven Skills,
  managed recovery, packaging, and removal of the sharing gate. Preserve the
  security dependency floor without adding new upstream security claims.
- Exercise the existing release-note extraction against this exact changelog
  in both manual rehearsal and tagged publish modes. The notes must use the
  intended section and contain no fallback reminder. Existing release metadata
  tests must pass. Final CI supplies the required full `uv run pytest` check.
- Keep core, starter, installer, package version, dependency lock, workflows,
  and conformance fixtures unchanged. Reuse their existing acceptance evidence;
  do not repeat native AI-app chats or installer tests for this prose change.
- Record focused verification and mark this plan row landed in the same PR.

## Scope

No tag creation, package publication, signing enablement, credential handling,
or public-site mutation is part of this PR. Release execution remains subject
to the separate signing, package, installer-acceptance, and publication gates.
