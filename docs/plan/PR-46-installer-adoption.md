# PR-46 — Install into a chosen work area

R11 implementation contract under ADR-0006. Final delivery follows PR-45 with
PR-44 cards and all earlier rework integrated. Installer source and isolated
tests may be authored against integrated PR-43; integrate the final dependency
before documentation reconciliation, independent review and acceptance.

## Outcome and scope

Setup uses the chosen work area directly, with ordinary projects beside its
Library and Memory. Fresh setup and explicit adoption reach the same current
core. Rerunning repairs recognized shipped content and preserves custom work.
No setup wizard, folder migration service, global configuration, signing-policy
change or new filesystem enrollment implementation.

Own the two flat bootstrap scripts, Windows wrapper option handling, installer
and release tests, CI coverage for these tests, installer README, IT onepager,
current delivery/status docs and a verification note. Coordinate the IT
onepager and machine-report contract with PR-45. Core init already implements
enrollment and `--adopt`; do not duplicate its ownership decisions in shell.

## Selected root and explicit adoption

- Default to `C:\Projects` on Windows and `~/Projects` on macOS, as a convenience
  only. `-Path`/`--path` selects the actual root; never append an Apparatus
  enclosure. A nonempty unmarked default is subject to the same explicit
  adoption rule as every other selected root.
- Add `-Adopt` and `--adopt`, passing core `--adopt` only when explicitly
  supplied. Do not infer consent from legacy files or automatically retry a
  failed init with adoption. Preserve core rejection of bound projects, invalid
  markers, collisions and unsafe roots.
- Remove the obsolete `Test-WorkspacePresent`/`workspace_present` completeness
  inventory. Every normal setup invokes the installed core's init for current
  validation, stock migration and repair. No new profile selectors, task
  changes, forced snapshots or Git initialization in the installer.
- Missing permissions, an unavailable drive or unsafe target must stop with a
  concrete correction. Never silently elevate, relocate or delete existing
  state. Successful deployment and subsequent snapshot/report failures are
  distinct; do not claim all setup succeeded when a required later step failed.
- Explain stock updates accurately: recognized shipped text may update;
  custom files and ordinary projects survive or cause an explicit conflict.

## Native wrappers and dry-run

Extend the Windows wrapper's strict parser with `/ADOPT` to `-Adopt`. Reject
duplicates and arbitrary options; preserve argument-as-data quoting, exact
embedded-script hash, synchronous exit propagation and cleanup. Test spaces
and hostile arguments against the actual compiled wrapper on Windows CI.

The macOS package has no custom-option channel. Keep its identity drop and
closed script archive. Document the released flat script for custom roots and
explicit adoption. Do not invent a root environment/config-file transport or
claim the package can select an existing root. Its default route may stop with
an adoption instruction when the default already contains work; that is honest
limited convenience, not permission to adopt silently.

Dry-run remains read-only from interpreter entry. Print core validation/repair
as planned; never call core init/help/check/doctor, import Python, invoke a new
helper or use the network to classify a target. Remove the obsolete "init skip"
claim. Preserve bounded detection, the existing Git version probe, hostile
environment protections and Windows UNC lexical-only handling. Native wrapper
temporary extraction and OS Installer records remain separate from script
dry-run's no-effects claim.

## Recovery, uninstall and distribution wording

Use PR-45's stable report fields while distinguishing tool detection from
verified recovery. No Git is a documented degraded outcome, not evidence of a
usable snapshot store. Managed snapshots and one-way backups cover the exact
current managed record/instruction/catalog/card scope; they do not back up
ordinary projects, registered originals, derived caches or excluded task state.
Restoring a catalog does not recreate a deleted original.

Remove old private-mode and routine receipt promises. Document task Memory
control and its explicit operation exceptions from the final specs. Uninstall
the tool separately; never tell users to delete their shared projects root as
a routine uninstall step. Retained files can remain usable through the file
contract. No automatic state removal or cleanup command is added.

Keep signed first public release requirements. Distinguish implemented signing
gates from observed signatures; do not claim a gate is currently off, a release
is signed or an AI app is certified without evidence. Enumerate all seven
distributables and checksums in the release rehearsal instructions. Record
tested commit/version, platform/build tools, artifact/hash/signing observations
and explicit gaps. No certificate, device policy, release publication or live
user toolchain mutation is part of this slice.

The bootstrap still installs/updates from PyPI. Demonstrate this source's normal
flow with controlled tool/download collaborators and the actual built wheel;
do not call a local rehearsal wheel the currently published package. Report the
resolved test version. Do not add a new version distribution policy here.

## Acceptance

1. Fresh/empty, ordinary nonempty, complete and partial legacy, enrolled, invalid
   marker and bound-project targets behave as core specifies. Only explicit
   adoption is forwarded. Repeating setup preserves UUID, custom instructions,
   profile/task choices, ordinary files, Git state and selected originals.
2. Isolated normal-flow tests execute the real current core, prove every rerun
   reaches init, and inject failure to forbid false ready or fallback adoption.
   Tool/download collaborators may be controlled; enrollment is not mocked.
3. Existing dry-run before/after, no-network and hostile-input witnesses still
   pass, with adoption/default-root cases and no new external detection calls.
   Preserve actual Windows drive/UNC/reparse and native wrapper coverage.
4. Built wheel and payload contain current Skills, learned fallback, cards and
   schemas; installed init exposes adoption. Validate builders, exact embedding,
   archive composition, checksums, focused tests, full pytest and actual Windows
   and macOS CI. Packaging is not native AI-app certification.
5. Independent review accepts the final integrated diff. Update this PR's status
   row and verification evidence; preserve historical plans and held PR-24 work.

Use frontier/high for the hostile-environment installer and ownership-sensitive
tests, with equally capable independent review. Keep the bounded existing team;
no recursive fanout or repeated broad runs without a new failure/change.
