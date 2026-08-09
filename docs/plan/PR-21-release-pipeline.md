# PR-21: Release pipeline

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` — especially §9 (distribution), §12 (method)
- `docs/adr/ADR-0005-distribution-and-packaging.md`
- `docs/adr/ADR-0001-vocabulary.md` — for any user-facing wording in docs
- `docs/plan/README.md`
- `CONTRIBUTING.md`
- `.github/workflows/ci.yml`
- `tools/build_payload.py` and `tools/README.md` (landed in PR-20)

## Objective

When this PR lands, cutting a release is a mechanical act: push a `v<version>`
tag and a GitHub Actions pipeline builds the universal payload archive and the
`apparatus-core` distribution, publishes to PyPI via trusted publishing (no
long-lived tokens anywhere), and attaches all artifacts to a GitHub Release
with a changelog stub. Until the first real release, the same pipeline runs
end-to-end in dry-run mode — everything built, the GitHub Release created as a
clearly labeled prerelease, nothing sent to PyPI — so the machinery is proven
before it matters. Version-bump discipline is
written down in `CONTRIBUTING.md`, and every operator-side step (PyPI trusted
publisher configuration, flipping dry-run off) is documented rather than
assumed.

## Deliverables

- `.github/workflows/release.yml` — new; the tag-triggered release workflow.
- `CHANGELOG.md` — new; Keep-a-Changelog-style skeleton with an `Unreleased`
  section and instructions comment at the top.
- `CONTRIBUTING.md` — modified; add a "Releases and versioning" section.
- `docs/release-runbook.md` — new; operator runbook for configuring and
  running releases.
- `docs/plan/README.md` — modified; status table row for PR-21.

## Acceptance criteria

1. `release.yml` triggers on tag pushes matching `v*` and on
   `workflow_dispatch`. Dispatch runs are always dry-run regardless of any
   variable, and upload their outputs as workflow artifacts (no Release, no
   PyPI) so the pipeline is smoke-testable from any branch.
2. Build jobs produce, from the tagged commit: the payload archive via
   `uv run python tools/build_payload.py`, and the `apparatus-core` sdist and
   wheel via `uv build --package apparatus-core`.
3. A consistency gate fails the tag-triggered run with a clear message when
   the tag (`v1.2.3`) does not equal the `version` in
   `packages/apparatus-core/pyproject.toml`.
4. PyPI publishing uses trusted publishing only: the publish job uses
   `pypa/gh-action-pypi-publish`, declares `permissions: id-token: write`,
   runs in a GitHub environment named `pypi`, and references no API token,
   password, or secret value. A repository secret scan of the diff shows no
   credentials of any kind.
5. Dry-run is the default: the publish job runs only when the repository
   variable `APPARATUS_RELEASE_MODE` equals `publish`. In any other state a
   tag push still builds everything and creates the GitHub Release, marked as
   a prerelease and clearly labeled dry-run in its notes.
6. The GitHub Release attaches: the payload archive, the sdist, the wheel,
   and release notes containing a changelog stub — the matching
   `## v<version>` section extracted from `CHANGELOG.md` when present,
   otherwise a generated stub (version, date, artifact list) plus a pointer
   to update `CHANGELOG.md`.
7. `CONTRIBUTING.md` documents version-bump discipline: the single source of
   version truth is `packages/apparatus-core/pyproject.toml`; the payload
   archive shares that version (PR-20 builder behavior); the bump, the
   `CHANGELOG.md` section, and the tag `v<version>` land together; tags are
   never moved or reused.
8. `docs/release-runbook.md` documents, as explicit operator steps performed
   outside this repository: creating the PyPI project and trusted publisher
   (owner, repository, workflow filename, environment name `pypi`), creating
   the `pypi` GitHub environment, setting `APPARATUS_RELEASE_MODE=publish`
   for the first real release, and the dry-run rehearsal checklist to run
   first. No secrets or account identifiers appear in the file.
9. The status table in `docs/plan/README.md` is updated in this PR.

## Conformance and tests

- No conformance fixtures are added or changed: the pipeline's observable
  contract lives in GitHub Actions, not in the workspace protocol.
- `uv run pytest` green is required (nothing in this PR may break it).
- Verification is by rehearsal: run the workflow once via
  `workflow_dispatch` from the PR branch and once from a throwaway tag if
  practical, and record in the PR description what ran, what was attached,
  and that PyPI was not touched.
- `uv build --package apparatus-core` must succeed locally; state its output
  filenames in the PR description.

## Out of scope

- No actual PyPI publication and no first release — the pipeline stays in
  dry-run until an operator flips `APPARATUS_RELEASE_MODE`.
- No pack packages; `apparatus-core` is the only published distribution.
- No bootstrapper build or download-page work (PR-22).
- No code-signing, checksums-as-signing, or notarization steps (PR-23 extends
  this workflow; keep it structured so jobs can be appended).
- No version-bump automation (release-please and similar); discipline is
  documented, not automated, in v0.
- No changes to `tools/build_payload.py` beyond what a build failure on the
  runner strictly requires — and none silently.

## Dependencies

- PR-20 (universal payload builder), per the status table in
  `docs/plan/README.md`.

## Open decisions

- Exact PyPI project ownership and account logistics are operator matters
  outside the repository; the runbook documents the steps generically. The
  smallest reversible default taken here: keep the pipeline fully functional
  in dry-run mode with `APPARATUS_RELEASE_MODE` unset, so nothing irreversible
  happens until an operator acts.
