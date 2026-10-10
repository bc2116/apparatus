# PR-68 — Recognize released module content

## Outcome

Make the installed module's status distinguish exact known release content from
unrecognized edits, without replacing or deleting any deployed file. Give fresh
Mailbox Survey installations concise guidance for the existing read-only report
summary. This is the recognition portion of the next module-lifecycle slice;
automatic update and removal remain separate work.

## Contract

Keep existing `status`, `install` and `repair` action semantics and JSON keys.
`version` remains the executing package version. Existing asset states remain
`missing`, `current` and `modified`; old recognized bytes are still `modified`
when different from the executing package, so install/repair still refuse to
overwrite them. Keep aggregate absent/current/partial/conflict semantics.

Add two fields to successful lifecycle output:

- `release_matches`: a mapping from each of the two fixed asset paths to a
  sorted list of module versions whose exact expected length and SHA-256 match
  the bytes read through the retained filesystem proofs. Missing and unknown
  content yield empty lists.
- `complete_release_matches`: the sorted intersection of the per-asset lists,
  requiring both assets to exist. It may name several versions with identical
  resources. An empty intersection must never be represented as one complete
  version assembled from different releases.

These fields establish content matches only, never a durable installed-version
record, origin, authenticity or current package presence. Existing state and
return-code behavior stay authoritative for create-only repair. Old recognized
assets remain unchanged and need the later update workflow. No new commands,
network access, discovery, workspace records, receipts or recovery coverage.

## Historical evidence and boundaries

Ship one small package-resource manifest for the fixed assets in versions
0.1.0, 0.1.1, 0.1.2 and 0.1.3. Derive digests and lengths from the accepted
source commits for those versions, and record full source commit identifiers
with the historical entries. Validate that the source package version agrees
before recording each entry. Identical assets legitimately match multiple
versions. Describe these as accepted source versions, not published packages.

The current package version is derived from the running module and the already
validated packaged assets; do not try to embed its own eventual commit hash.
Validate the entire historical manifest before any lifecycle mutation: closed
format, unique versions/keys, exact two-path allowlist, bounded entries, valid
version strings and source identifiers, lowercase SHA-256 values, and positive
non-boolean integer lengths within the existing asset size limit. A malformed
manifest returns a bounded content-free package diagnostic, exit 2. It cannot
add paths to read or write. Validation and summary of reports remain independent
of lifecycle/Core and of this manifest.

Use the existing captured asset bytes and identity validation; no additional
pathname read and no weakening of the retained root, enrollment, parent,
nonregular-file, size, symlink or Windows boundaries. A completed install or
repair reports matches for its final validated state. Partial publication
errors retain the PR-66 preservation-first behavior and are not successful
recognition results.

## Guidance and version

After the existing validation instruction in the portable Skill, add a short
optional instruction for the existing `summary REPORT` command when available.
The command summarizes declared claims and does not verify evidence, authority,
category quality or actual mailbox coverage. Preserve the file-reading fallback
when the package or command is unavailable. Do not extend source acquisition,
mail actions or retention. Keep the report-format reference and report schema
unchanged. Bump only this module to 0.1.4; Core and its starter stay unchanged.

## Ownership and acceptance

Own the module's deployment/classification helper, fixed historical manifest,
Skill resource, package version/lock entry, focused tests, README, module spec,
module sequence, this prompt and plan status row. No general plugin registry or
replacement primitive is included.

Test current and historical complete matches, several identical versions,
missing and unknown files, mixed known per-file content with no complete match,
malformed/oversized manifest and unknown paths. Prove status leaves bytes and
mtimes unchanged, and install/repair still block old/edited content before any
creation. Preserve existing boundary and failure-preservation tests. Exercise
the public CLI output and verify current matches after install and repair.

Build and inspect the wheel with its historical manifest. Exercise report
validation/summary without Core and lifecycle status against published Core
0.0.2 in an isolated environment. Use synthetic input only. Run focused tests
and full `uv run pytest`; current-head Windows CI remains necessary before
remote merge. Record source-build evidence without claiming package publication
or broader app certification. Set the plan row to `✅ landed` in the proposed
PR change; it describes landed state only after that branch reaches main.
