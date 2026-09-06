# PR-35 shared interface and ownership

The lead owns workspace_layout.py, existing snapshot/backup/restore CLI routing,
normative specs/ADR/plan updates and cross-engine integration tests. Worker A
owns managed_state_recovery.py and focused store/capture/restore tests. Worker B
owns managed_state_backup.py and focused managed archive tests; coordinate any
narrow factoring/reuse of existing backup publication helpers with the lead.
Do not edit another role's files or revert their work. No recursive delegation.

## Layout control (lead)

workspace_layout.read_layout(workspace) -> ManagedLayout | None reads only the
explicit root; no ancestor/project discovery in this PR. ManagedLayout exposes
workspace: Path, workspace_id: str, and validate(anchor: WorkspaceAnchor), which
checks the root and exact captured marker bytes/identity. Its canonical_bytes()
serializes only validated fields for export, omitting comments. Marker is closed YAML
at System/workspace.yaml with schema: apparatus/workspace@v0, id: UUIDv4,
layout: sibling-projects, recovery: managed-state. LayoutError(ValueError)
reports invalid/unsafe/lost enrollment. Marker absence plus residual
System/recovery is an error, never legacy fallback. None means verified absence
of both. Re-read/validate before mutation, not just at initial dispatch.

## Managed capture paths (Worker A)

Named optional regular text files:
AGENTS.md, CLAUDE.md, Welcome.md, .cursor/rules/apparatus.mdc,
.github/copilot-instructions.md, System/profile.yaml, System/ignore,
System/README.md, System/guidance/model-guidance.md,
System/policy/standard.md, System/policy/private.md.
Validate profile.yaml with the current profile schema. Instruction/plain text
files must be UTF-8; preserve their bytes. Missing optional files are not added.

Record roots, recursively, with schema and filename validation:
Goals -> goal; Memory/People -> person; Memory/Facts -> fact;
Memory/Decisions and legacy Decisions -> decision;
System/procedures -> procedure; System/receipts -> receipt.
Skip dot placeholders and unrelated non-Markdown files; malformed expected .md
records report a coverage error. Do not follow symlink/reparse directories.
Skip receipt events snapshot, restore and backup-export entirely, so unchanged
saves do not retain their own bookkeeping or manufacture a change. Include no
other roots. Layout marker, project bindings, System/tasks, System/recovery,
Library sources, project data and caches remain outside snapshot contents.

Restore only declared saved files and preserve additions. Existing destinations
must still be valid for their declared kind, or exactly match a named optional
text path. Never replace a directory/link/special file or unrelated malformed
record. Validate the complete plan before any replacement; compare captured
preimages at commit and compensate only owned changes. Restored Memory has the
historical state represented by that snapshot, not an erasure guarantee.

## Store and recovery API (Worker A)

Module may reuse public Snapshot, SnapshotResult, SnapshotError,
UnknownSnapshotError, SnapshotReceiptError from snapshots.py; lead uses local
imports for routing to avoid a module-import cycle. Shared filesystem/receipt
primitives remain authoritative.

Provide take_snapshot(workspace, *, label=None, force=False, run=..., write=...,
clock=None, task_id=None, requested=False) -> SnapshotResult;
prepare_snapshot with the same core parameters -> ManagedSnapshotTransaction;
list_snapshots(workspace, *, run=...) -> list[Snapshot];
resolve_snapshot_id(workspace, identifier, *, run=...) -> str;
restore_snapshot(workspace, identifier, *, run=..., task_id=None, write=...) -> None;
preflight_restore(workspace, identifier, *, run=...) as a context manager.
Snapshot and BackupResult have an optional scope field defaulting to workspace;
managed results set managed-state so CLI messages identify coverage without a
post-publication metadata read. Managed restore writes its owned receipt inside
the restore transaction before compensation proofs are released; the CLI does
not write a second receipt. Commands otherwise use the existing result shapes; all managed APIs independently require
and validate the layout rather than silently operating on root Git.

ManagedSnapshotTransaction exposes result, commit(), rollback(), close(), and
validate() for the still-live owned ref/receipt and layout proof. A no-change
transaction must also validate its baseline ref/manifest before acceptance.
Do not irrevocably drop compensation proofs before export's final checkpoint.
If a richer settle/release/accept protocol is necessary to preserve existing
close-failure guarantees, agree it explicitly with Worker B before authoring.

For backup integration provide capture_state(workspace, *, run=...) returning
validated current declared files/bytes plus the layout and preimage proofs;
and stage_reachable_history(workspace, destination, *, run=...) creating a fresh
self-contained bare store below an invocation-owned staging directory, using
only all-validated reachable history, known config/refs and matching owner marker.
Returned capture object exposes files and validate(); keep reads bounded to
managed paths and exact store entries. Worker A and B may simplify these signatures
by agreement, but record the interface here before dependent implementation.

## Managed backup (Worker B)

export_backup(workspace, destination, *, available=..., write=..., clock=None,
task_id=None) -> existing BackupResult, with an optional injected prepare callable
for focused fault tests. It propagates explicit snapshot permission. Archive
contains declared current files, fresh reachable-only store, current validated
layout marker and task-control metadata, plus readable managed-scope note.
Reject invalid task controls; include no arbitrary source-root or store bytes.
Validate source/task/routing preimages and owned destination through publication.
Do not expose task paths/text in no-save operational receipts. Use existing
collision-safe archive allocation/cleanup and exact receipt ownership where
applicable; do not create a second weaker publication mechanism.

### Export transaction agreement

Worker A and B use `ManagedSnapshotTransaction.settle()` for all fallible receipt
publication/alias release while retaining independent exact ref and receipt
compensation proofs. `validate()` works before and after settlement. `rollback()`
remains effective until `accept()`, which performs only nonraising final acceptance
and proof teardown. `commit()` is the standalone settle/validate/accept sequence.
`close()` rolls back an unaccepted live transaction; after acceptance or rollback
it only tears down handles. Export settles first, performs its own fallible receipt
close and final source/task/layout/history/destination/archive checks, then accepts.

`capture_state()` returns a context-managed capture with `files: dict[str, bytes]`,
`layout`, `validate()` and `close()`. `stage_reachable_history()` receives the exact
fresh store-root destination; its owner marker is `apparatus-owner.json` inside
that store. Export prefixes these generated files with `System/recovery/store/`.

`HistoryProof.files: dict[str, bytes]` is the exact generated bare-store mapping
relative to the destination. Its `validate()` checks pinned source history/ref/
layout and staged file preimages/inventory; export archives only this mapping.
Task controls retain exact source preimages for concurrency checks and export
canonical closed-schema metadata; even an empty task directory preserves enrollment.
Without Git, current-state export is supported only when no System/recovery exists;
the result and scope note report unavailable history. Existing managed storage
requires Git validation and fails rather than silently omitting history.
