# PR-34 shared implementation interface

This note pins the worker interface for the execution contract. The lead owns
`retention.py`, `commands/task.py`, root CLI dispatch, receipts, and payload/spec changes. Worker B also owns
snapshots/restore and backup integration under the execution contract.

`retention.py` provides:

- `TaskRetentionError(ValueError)` for invalid/missing context.
- `RetentionSuppressed(TaskRetentionError)` for a valid no-save task blocking
  automatic persistence. CLI adapters report this as a calm skip, not success
  claiming a write. Do not catch the base error as suppression.
- Frozen `TaskContext`: `workspace: Path`, `task_id: str | None`,
  `save_memory: bool`, `legacy: bool`, `requested: frozenset[str]`.
- `context_for(workspace, *, task_id=None, require_task=False) -> TaskContext`:
  inherits the same-workspace invocation context; otherwise reads metadata.
  No task directory + no ID is legacy. Existing task directory + no ID is
  anonymous no-save for maintenance; `require_task=True` rejects it.
  Unsafe/invalid state always errors. Supplying an explicit other task ID
  resolves that ID, never silently inherits the current task's decision.
- `operation(workspace, *, task_id=None, require_task=False, requested=())`:
  context manager yielding the context and propagating it to nested calls via
  `ContextVar`, reset in `finally`. Contexts cannot cross workspace boundaries.
- `TaskContext.require_memory_write()` rejects anonymous task-enabled calls
  and no-save. For a valid saving task, use standard labeling/redaction rules
  even when a legacy profile still says private; only `legacy=True` uses the
  old mode. Forget/outdated/label/read do not call this write guard.
- `TaskContext.require_library_write()` rejects anonymous task-enabled calls;
  no-save requires `"library" in requested`. No other capture is enabled.
- `TaskContext.require_snapshot()` has the analogous `"snapshot"` exception.
- `metadata_fields(workspace, event, fields)` returns original fields when
  saving; otherwise returns a narrow metadata-only mapping before receipt
  preparation. The lead owns its whitelist and transaction tests.

Public engine entry points may accept `task_id: str | None = None` and
`requested: bool = False` where applicable, wrapping their existing operation
in this context. A CLI global `--task ID` propagates context to current handlers;
existing direct Python callers remain compatible only on legacy workspaces.
CLI `--requested` is scoped to the Library or snapshot operation by its adapter,
not a global context permission. No free-form user text enters task controls.

Worker A owns `commands/memory.py`, `commands/profile.py`, and new targeted
task-retention Memory/profile tests. Worker B owns `snapshots.py`, `backup.py`, their CLI adapters and recovery tests,
plus `cache.py`, `library/`,
`recall.py`, `commands/library.py`, `commands/recall.py`, and targeted Library
retention tests. Both coordinate signature needs with the lead and preserve
other edits. Existing baseline tests should remain; dedicated new tests activate
the task protocol and prove missing-ID rejection and no-save behavior.
