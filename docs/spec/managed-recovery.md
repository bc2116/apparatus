# Recovery for shared work areas

Fresh initialization and explicit existing-folder adoption enroll the shared
work-area layout and select this backend. Existing workspaces without a marker
or residual managed-recovery state retain their legacy recovery behavior until
adoption. See the [workspace specification](workspace.md) for enrollment and
project links; engine calls here receive the already selected explicit work area.

## Explicit routing

`System/workspace.yaml` is closed YAML: `schema: apparatus/workspace@v0`, a
canonical random version-4 UUID `id`, `layout: sibling-projects`, and
`recovery: managed-state`. No other fields are permitted. It identifies one
work area; no ancestor search or project-binding inference happens here.

A malformed, unsupported or unsafe marker is an error. Missing enrollment with
remaining `System/recovery` state is also an error, never permission to use the
work area's own Git repository. Recovery revalidates the marker and root identity
before mutation. Routing, project bindings and live task controls are not restored
from historical snapshots.

## Snapshot coverage

Snapshots cover these declared records, with current schema and filename
validation: Goals, Memory/People, Memory/Facts, Memory/Decisions, legacy Decisions,
System/procedures and System/receipts. Recovery-generated receipt events
`snapshot`, `restore` and `backup-export` are excluded, so a save does not generate
its own next change. Dot placeholders and unrelated non-Markdown files are skipped;
malformed expected records produce a coverage error.

The following named UTF-8 files are included when present:

- `AGENTS.md`, `CLAUDE.md`, `Welcome.md`, `.cursor/rules/apparatus.mdc`, and
  `.github/copilot-instructions.md`.
- `System/profile.yaml` (validated against the profile schema), `System/ignore`,
  `System/README.md`, and `System/guidance/model-guidance.md`.
- `System/policy/standard.md` and `System/policy/private.md`.

The seven exact built-in `.agents/skills/NAME/SKILL.md` paths listed in the
[Skill specification](skills.md) are also included when present. They use
portable Skill validation, not the legacy procedure schema. Capture, manifest
membership and every reachable historical tree apply the same validation.
Historical five-Skill and procedure snapshots remain valid without requiring
later additions. Restore retains files absent from an older snapshot, including
new or customized Skills. Init can then upgrade exact old stock guidance again;
it preserves valid custom bodies. Missing new bodies remain actionable in check.
Third-party Skills, optional resources beside a built-in body and project native
adapters are outside coverage; `.agents/skills` is never recursively captured.

The closed [Library source registrations](library-sources.md) under
`System/library/sources/` are included. Capture validates the exact catalog;
historical manifests validate records without requiring their originals to be
available. Closed [Library card records](library-cards.md) directly under
`System/library/cards/` are also covered and validated offline. No paired
registration is required: implicit and removed-source cards remain recoverable.
Restored cards require current matching source evidence before use. Originals
and extraction/index caches remain outside coverage.

No other paths are inferred to be managed. Project files, Library originals,
caches, unknown files, task controls, routing/bindings and recovery storage are
outside snapshot contents. Filesystem traversal does not follow links or reparse
points. Capture validates its file preimages before publishing.

The dedicated bare store is `System/recovery/store`, identified by a closed
`apparatus-owner.json` with schema `apparatus/recovery-store@v0` and matching
`workspace_id`. Its sole branch is `refs/heads/managed`. Every Git operation targets
this store explicitly. Recovery does not initialize, configure, stage, commit,
checkout, restore or clean a work-area or project repository.

Every snapshot tree contains `recovery-manifest.json` plus exactly its declared
files. The closed manifest has `schema: apparatus/recovery-manifest@v0`, matching
`workspace_id`, `scope: managed-state`, and `files` entries containing `path` and
`sha256`. Paths, uniqueness/case collisions, kinds, hashes, and the exact tree file
set are validated. Unchanged state creates neither a snapshot nor a receipt.
Failed saves compensate only owned references and receipts; unreachable Git
objects may remain, and are not treated as valid history or exported.

## Restore

Restore replaces saved files and preserves additions and unknown files. It is
not an exact rewind of the entire work area. Target manifests and all destination
paths are validated before any replacement. Retained-root create/replace
transactions compare preimages, preserve concurrent edits and compensate only
their own changes. Task and routing controls stay in place, including later
no-save choices.

Restoring a Library registration preserves later registrations. The combined
historical/current catalog must remain free of portable path collisions at every
publication boundary. A conflicting restore stops with the existing state intact.
Restoring a registration cannot restore a missing original or freshen an old cache.

The CLI identifies the snapshot date and scope. Restored Memory reflects that
historical saved state and can revive older information, including content that
was subsequently corrected or forgotten. It does not promise secure erasure,
provider-retention control or recovery of project files and Library originals.

An older snapshot may restore full legacy procedures beside surviving new Skill
bodies. Check reports the mixed workflow state and suggests init migration.
Restore does not silently remove those old records. Re-migration preserves valid
custom canonical bodies and stops before writing if an old procedure is custom.

## Backup

A managed backup contains current declared state, valid reachable snapshot
history, the current layout marker and task-control metadata, and a readable
scope note. Project files and Library originals are not included. Control YAML
is serialized from validated fields without comments; exact source preimages
remain part of publication validation. Empty task enrollment is preserved.

History is rebuilt into a fresh self-contained store from validated reachable
snapshots and known configuration. Unexpected store files/configuration are
rejected. Unreachable objects from failed operations are not exported. Every
reachable ancestor must validate; missing coverage is not silently omitted.

When Git is unavailable and there is no managed store, current-state export is
still possible and explicitly reports unavailable history. Existing history
requires validation; it is not silently omitted when Git is unavailable.
Destination containment, collision-safe allocation and exact archive/receipt
ownership apply throughout export, with compensation until the final checkpoint.

Extract a backup into a fresh folder. It retains only restrictions known when it
was exported; later task choices cannot be inferred from an old archive. Legacy
full-workspace exports remain a distinct compatibility path.

## Task retention

The [task contract](task-retention.md) applies before store creation or capture.
Automatic no-save snapshots are suppressed. Separately requested snapshots and
backups are scoped exceptions; neither enables general Memory capture. Necessary
no-save receipts contain fixed operational metadata rather than task content.

Learned Skill recovery includes the closed per-Skill ownership records under
`System/skills/adopted/` and exactly their named `.agents/skills/NAME/SKILL.md`
bodies. Current capture and historical manifests must contain matching valid
pairs. Drafts under `System/skill-drafts/` and unregistered native Skills are
excluded. Restore keeps later individual adoption records as later additions;
restoring an older adopted body may revive an older workflow. No live task
control or native action authority is restored by adoption metadata.
