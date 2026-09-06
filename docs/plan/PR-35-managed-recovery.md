# PR-35: Isolated recovery for shared work areas

R3a backend first, after PR-34. R3b/PR-36 will publish the new layout and adopt
projects only after this backend is verified. The approved work-area shape keeps
Goals, Memory, System and one Library at the chosen root, with arbitrary sibling
project folders and project-local deliverables. No root Git repository may be
initialized or reused over these projects. This PR does not deploy the new layout
marker to users, move records or edit project instructions.

## Routing and scope

Add a closed, retained-root validated System/workspace.yaml control with schema
apparatus/workspace@v0, a random UUID id, layout: sibling-projects and recovery:
managed-state. Only synthetic fixtures create it in this PR. Marker absence uses
legacy behavior only when no managed-recovery evidence exists. If System/recovery
or another managed enrollment artifact exists without its marker, report a repair
error rather than falling back. Revalidate routing before mutation. Malformed,
unsafe, unknown or unsupported markers fail before any recovery mutation, never
fall back to root Git. Extend ADR-0006's minimal
control metadata allowance and add a normative recovery spec in this PR.

Every public snapshot/restore/backup engine boundary recognizes this marker,
including initialization/preparation/list/resolve helpers: no direct caller can
bypass the new scope. Existing legacy tests and APIs remain compatible. Retention
context resolves before all new capture/store writes; no-save automatic snapshots
stay suppressed, requested snapshot/backup retain their operation-only exception.

New recovery lives in a separate managed_state_recovery.py module backed by a
dedicated bare Git store under System/recovery/store. Do not deeply branch the
legacy root-.git implementation. Reuse filesystem transactions, ownership-bound
receipts, safe Git environment and narrowly factored archive publication. Never
run Git repository discovery, checkout, restore, clean, index or config mutation
against the work-area or a project. Every Git call targets the dedicated store
and any transient worktree/index explicitly. A known store must prove its UUID,
local object storage, regular endpoints and absence of redirect/alternate/linked
storage. Unknown existing content is a collision, not an adoptable repository.

Capture only declared managed state: valid Goals, People, Facts and decision
records (including legacy Decisions until R3b migration), named shipped canonical
instructions/pointers, profile and selected policy/procedure/guidance files, and
valid operational receipts except events snapshot, restore and backup-export.
Those recovery-generated receipts are never captured or used for change detection;
repeating an unchanged save creates neither a snapshot nor another receipt.
Do not traverse projects or Library originals.
Exclude caches, unknown files, task controls, layout/project bindings, the store
and its staging. List the exact allowed paths/kinds in the normative spec; do not
infer ownership merely from a directory prefix. Invalid expected records fail
with a coverage error rather than silently being called complete.

Each snapshot has a readable manifest naming its work-area UUID, schema, scope
and exact included relative paths/content hashes. Validate its paths, file kinds,
uniqueness/case collisions and hashes against stored blobs. Reject extra or
missing tree paths and symlink/gitlink modes. Tree equality can detect no-change
before publishing a new receipt; volatile timestamp data must not manufacture
changes. Capture uses safe retained reads and validates its preimages before
publishing a compare-and-swap reference and ownership-bound receipt. Failed
publication compensates only owned changes; preserve concurrent references and
files. Old root history stays untouched and is never offered as this area's
snapshots. Unreachable owned Git objects after a failed save are an honest limit.

## Restore and export

Restore saved files, preserving additions and unknown files. State this scope
plainly: it does not undo later additions or recover project/Library originals.
Reading target blobs and validating the entire plan happens before any change.
Use retained-root create/replace transactions with captured preimages, never Git
checkout/clean on the work area. Refuse unsafe paths and unrelated-file collisions
before publishing. Roll back only operation-owned replacements on failure; live
task controls and routing/enrollment metadata remain in place. Restoring old
Memory can revive older information; CLI output identifies the snapshot's date
and historical scope without inventing lifecycle erasure or adding an approval.

Backup exports the same declared managed state, validated reachable snapshot
history/manifests and current metadata-only task controls, with a small readable
scope note. Validate every reachable snapshot; do not silently omit an invalid
ancestor. Build a fresh self-contained bare store in private staging from the
validated reachable objects, known configuration/refs and matching ownership
marker. Do not copy arbitrary store files or unreachable objects left by failed
saves. Reject unexpected store files/configuration instead of archiving them. Project
files and Library originals are not included. Do not traverse projects to inspect
their repositories. Preserve destination containment, collision-safe names,
retained identities, exact archive ownership and receipt/snapshot compensation.
Re-use/factor existing publication primitives only where their proof applies;
never package an unrelated work-area .git. An extracted managed backup has the
same UUID/routing marker and usable managed recovery, while old controls know
only export-time restrictions. Legacy full-tree backups remain unchanged.

## Acceptance and delivery

Use real fixtures containing a dirty root Git repository and two dirty project
repositories. Prove unchanged HEAD, index, config, staged/unstaged/untracked bytes
through successful and failed new snapshots, restore, backup and init helpers.
Prove no-save suppression before Git/store creation; explicit exceptions do not
enable Memory; manifest and archive coverage exclude sentinel project/Library
content; task controls survive older-state restore and concurrent opt-out;
unknown additions remain; lost enrollment marker with residual recovery state
fails before legacy routing; repeated unchanged saves produce no new receipt;
planted store sentinels and unreachable objects do not enter archives; malformed
manifests, collisions and concurrent edits
fail without destroying other work; receipt/ref/archive failures compensate only
owned changes. Verify safe repeated use and extracted-backup recovery. Keep
existing legacy filesystem, credential, Windows and archive tests unchanged unless
a narrowly documented fixture adaptation is necessary.

Lead owns routing/contract/integration and restore tests. One authoring-tier worker
owns the isolated store/capture/restore module with explicit interfaces; another
owns managed export and the narrowly reused publication boundary. Independent
review reads contract + ADR + full diff, stays authoring-tier for this migration,
and permits at most two classified repair passes. No recursive delegation.
Run focused meaningful tests, full uv run pytest, actual Windows CI and normal
branch/PR/exact-head remote-merge verification. PR-36 handles payload/layout,
project bindings and adoption after this backend lands; no product survey needed.
