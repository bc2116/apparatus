# PR-34: Task-specific Memory retention

Implement R2b of ADR-0006 after PR-33 on `pr-34-task-retention`. Keep the
product small: readable control files, one task context, no daemon, account,
model call, task dashboard, conversation import, or cross-app coordinator.

## Task contract

- `apparatus task start WORKSPACE [--no-memory | --save-memory]` creates an
  opaque random UUID and a minimal YAML record at `System/tasks/UUID.yaml`.
  The closed record contains only schema, UUID, and a save/no-save decision;
  never a title, query, summary, transcript, source path, or personal data.
- Ordinary new tasks save useful Memory by default. Existing private-profile
  workspaces default new tasks to no-save unless `--save-memory` is explicit.
  The legacy field is compatibility input, not a new global privacy selector.
- `task show WORKSPACE UUID` resumes/inspects the same decision. `task no-memory
  WORKSPACE UUID` changes it one way to no-save using retained-root replacement;
  repeat is safe. A new explicitly saving task is needed to opt back in.
  Opt-out governs subsequent operations; it does not undo already completed or
  in-flight saves. Existing Memory can be corrected/forgotten with PR-33 commands.
- The assistant starts one task for a coherent request, keeps the returned ID
  in that conversation, and passes global `--task UUID` to managed operations.
  Resuming uses that ID. Lost/ambiguous context never silently chooses a saving
  task; start a no-save continuation if the original ID cannot be established.
- Before the first task control exists, legacy commands remain compatible.
  Once `System/tasks/` exists, content-retaining operations require a valid
  explicit task or the same validated context supplied by an enclosing caller.
  Missing, malformed, unknown, cross-workspace, or unsafe task state fails
  before content writes. Concurrent tasks have separate IDs; no shared active
  task pointer or process-global mutable mode. Use one scoped context mechanism.

## Retention behavior

Resolve task context at public engine boundaries before any content persistence,
not only in the CLI. Freeze the decision for that invocation; later opt-out
  changes apply to subsequent invocations. No native permission or user authority
  is granted by a task record. Direct native writes remain instruction-governed.

1. No-save blocks new Memory, corrections containing new information, profile
   answer persistence, and profile-derived People/Goals before reading or writing
   task content. Forget/outdated/label maintenance and Memory reads still work.
   Saving tasks use the ordinary credential floor and labeling; the retired
   global private-mode write rule applies only to unconverted legacy calls.
2. No-save blocks automatic Library ingest/refresh/rebuild, future cards and
   learned Skills, and automatic activity notes. An invocation-scoped
   `--requested` flag on Library write commands records a separate explicit
   user request; it permits only those Library writes, not Memory or other
   capture. This is assistant plumbing, not another user approval prompt.
3. No-save Library search/recall uses existing validated extraction pairs and
   current ignore rules in an in-memory index. It creates no cache directory,
   lock, temporary file, database, journal, repair, or extraction. Missing or
   invalid cache state is unavailable, not a false no-match. Normal retrieval
   behavior remains compatible. Do not claim improved source freshness beyond
   existing extraction validation. Use the same retrieval helper for both CLIs.
4. Automatic snapshots are suppressed before Git initialization/tree/object
   capture for no-save tasks. Explicit `snapshot --requested` and requested
   backup export remain possible with honest whole-workspace/history scope.
   Backup propagates its explicit export intent to its snapshot preparation;
   this must not enable general Memory retention or add a sharing gate.
5. Routine no-save retrieval emits no receipt. Any necessary operational
   receipt is shaped before ownership binding to metadata only: fixed event/
   summary/status, opaque task/recovery identifiers and numeric counts. Drop
   queries, labels, source/destination paths, snippets, bodies and free-form
   error messages. Preserve transaction/publication proofs and required schema.
   Unscoped maintenance in a task-enabled workspace uses this same metadata
   rule; it does not silently gain permission to retain task content.
6. Requested deliverables saved by the assistant remain possible in the existing
   project layout. Suppress routine Library offers and automatic derivative
   capture for no-save tasks. No new provider-chat retention claim, retrospective
   deletion engine, or promise of erasure from snapshots/exports is introduced.
7. `System/tasks` is live operational control state. New snapshots exclude it,
   including previously tracked entries; controls-only changes do not trigger
   snapshots. Restore preserves the live subtree in place, excludes it from
   both tracked-file restoration and untracked cleanup, and never reinstates
   old task flags. Preflight incompatible target ancestors (a file, symlink or
   gitlink at `System`) before any pre-restore snapshot/mutation. Retain current
   workspace/System/task-directory identities; failures and concurrent no-save
   updates must not overwrite live controls. Explicit backup may include current
   metadata-only controls; extracting an old ZIP into a fresh folder preserves
   only restrictions known at export time, not later changes.

## Migration and instructions

Remove the privacy-mode question from the current welcome procedure and direct
users to the task instruction. Remaining interview ceremony waits for R5.
Keep old profile data readable; never silently enable Memory in a private
workspace. Deprecate selecting global private mode in fresh setup guidance;
compatibility fields/overlay plumbing may remain until the later setup cleanup.
Explain which behavior is legacy compatibility and which is current task policy.
Explicitly add the minimal task-control schema to ADR-0006's protocol
supersession; it is control metadata, not another user-maintained record.

Update known shipped instructions through the existing byte-recognition and
retained-root migration, including PR-33 canon/shims and affected procedures/
policies. Preserve custom content with actionable reconciliation. Keep canonical
and embedded payload, manifest, golden shims and normative specs synchronized.

## Ownership and acceptance

- Lead: shared task context/control CLI and tests, integration, specs/plan/payload
  migration, final verification/delivery.
- Worker A: Memory/profile entry-point enforcement and targeted tests.
- Worker B: cache/index/read-only Library operations, snapshots/backup/receipt
  enforcement and targeted tests, split further only for a distinct need.
- Independent authoring-tier reviewer: contract before implementation, then
  contract + ADR + full diff; no edits. Privacy/migration work is not tiered down.

Tests must cover task identity and resumption, one-way opt-out, legacy private
defaults, wrong/missing/unsafe IDs, separate simultaneous contexts, no-save
Memory/profile suppression, requested deliverable preservation, no derived
cache/index/receipt content, forced legacy SQLite read path, explicit Library/
snapshot/backup intent without general retention, malformed state fail-before-
write, and preservation of existing transaction/credential/platform protections.
Use synthetic sentinel content and compare workspace/cache trees for zero
unintended persistence. No automatic Memory/Skill/card capture may bypass this
same contract in later slices.

Run meaningful targeted checks, `uv sync --all-packages`, required `uv run pytest`,
payload build and diff checks. Verify actual Windows CI before merge. Record
platform and review repairs, use at most two review repair passes, preserve the
held certification worktree, and continue the sequence from remote merged main.
