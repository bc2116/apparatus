# PR-30: Embed payload in apparatus-core

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` — especially §9 (distribution) and §10 (architecture)
- `docs/adr/ADR-0003-harness-agnostic-contract.md`
- `docs/adr/ADR-0005-distribution-and-packaging.md`
- `docs/plan/README.md`
- `docs/plan/PR-20-payload-builder.md`
- `docs/plan/PR-21-release-pipeline.md`
- `docs/plan/PR-22-bootstrapper.md`
- `packages/apparatus-core/pyproject.toml`
- `packages/apparatus-core/src/apparatus_core/payload.py`
- `packages/apparatus-core/src/apparatus_core/commands/init.py`
- `packages/apparatus-core/tests/test_init.py`
- `tools/build_payload.py`
- `conformance/test_payload.py`, `conformance/test_payload_archive.py`, and
  `conformance/golden/payload-manifest.txt`
- `.github/workflows/release.yml`

## Objective

When this PR lands, `apparatus init` works from an installed
`apparatus-core` wheel without a repository checkout. The wheel and source
distribution carry a committed copy of the universal starter payload and its
profiles. A conformance gate prevents that copy, the files-only release
archive, and the golden payload contract from drifting. Both artifacts remain
two forms of one versioned payload, produced from the same builder contract.

## Deliverables

- `packages/apparatus-core/src/apparatus_core/starter/` — committed payload and
  profiles, including freshly rendered shims.
- `packages/apparatus-core/pyproject.toml` — Hatch configuration that includes
  all embedded starter data in wheels and source distributions.
- `packages/apparatus-core/src/apparatus_core/payload.py` — package-resource
  discovery for default payload and profile resolution.
- `conformance/test_payload_archive.py` — byte equality, distribution-content,
  and installed-wheel smoke coverage.
- `docs/adr/ADR-0005-distribution-and-packaging.md` and
  `docs/design/design-brief.md` — binding dual-artifact rule.
- `docs/plan/README.md` — PR-30 status and PR-22 dependency update.

## Acceptance criteria

1. The full universal payload and `starter/profiles/` are committed beneath
   `apparatus_core`, including empty placeholders, hidden app shims, and fresh
   rendered-shim bytes.
2. Hatch includes the embedded tree in both the `apparatus-core` wheel and
   source distribution. Packaging tests inspect both archives and require the
   exact embedded path and byte set.
3. With no `--payload`, `apparatus init` resolves only installed package data;
   it never derives a path from a repository checkout. A normal filesystem
   install receives the existing symlink and containment checks, and a
   non-filesystem or absent resource fails with a clear usage error.
4. Explicit `--payload PATH` remains available for development and retains its
   existing sibling-profile behavior. Starter behavior and profile selection
   do not change.
5. One conformance gate builds the payload archive and proves that every
   `payload/` and `profiles/` byte equals the committed package data. Its
   payload path set equals `conformance/golden/payload-manifest.txt`; shims
   equal a fresh render; profiles are present; and the archive version equals
   the `apparatus-core` project version.
6. The GitHub Release payload archive remains the files-only distribution. It
   is still produced by `uv run python tools/build_payload.py` at the package
   version and has byte-identical payload/profile content to the wheel.
7. A test builds the wheel and source distribution, installs the wheel into an
   isolated temporary environment, changes to a directory outside the
   checkout, runs default `apparatus init`, and verifies the resulting
   workspace.
8. Two consecutive payload-builder runs remain byte-identical. No source mtime,
   owner, checkout path, wall-clock value, or umask enters the existing archive
   contract.
9. ADR-0005 §1 and design brief §9 each record the dual-artifact rule, and the
   plan marks PR-30 landed while PR-22 depends on PR-21 and PR-30.

## Conformance and tests

- Run `uv sync --all-packages` before trusting results.
- Run focused init, payload/archive, packaging, and release-workflow tests.
- Run `uv run pytest` and `python3 conformance/payload_check.py`.
- Build the payload twice and compare the archive bytes.
- Run `uv build --package apparatus-core`, inspect the wheel and source
  distribution, and smoke-test the installed wheel outside the checkout.
- Run Python compilation, `git diff --check`, the DCO check, and the tracked
  fingerprint scan before delivery.

## Out of scope

- No bootstrapper scripts, installer wrappers, signing, or notarization.
- No new distribution or payload endpoint.
- No starter-content, render, profile, or unrelated core behavior changes.
- No loosening or replacement of golden fixtures.
- No changes to how the files-only release archive is published.

## Dependencies

- PR-20 (universal payload builder), per the status table in
  `docs/plan/README.md`.

## Open decisions

- None. ADR-0003 still requires one universal payload, while ADR-0005 binds
  the package-embedded and files-only forms to identical content and version.
