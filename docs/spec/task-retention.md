# Task Memory decisions

A task is one coherent assistant request. `apparatus task start WORKSPACE`
returns JSON with an opaque UUID `task_id` and `memory: save` or `no-save`.
The assistant keeps that ID in its conversation and passes global `--task ID`
before subsequent managed commands. `task show WORKSPACE ID` reads the decision
on resumption. Lost context starts a no-save continuation; no shared active-task
file or title/query/transcript storage is introduced.

Commands can take an explicitly bound project as `WORKSPACE`. Its relative
binding and work-area UUID resolve before task enforcement, including task
start/show/no-memory and commands without global `--task`. The selected work area
owns the task control. A missing or invalid link is never repaired by ancestor
search, and a later link edit cannot redirect an in-flight command. See the
[workspace contract](workspace.md#context-selection) for command scope.

The user can say "don't remember this task." Start it with `--no-memory`, or
use `task no-memory WORKSPACE ID` to change an existing decision one way. Opt-out
affects subsequent invocations; an in-flight invocation freezes its entry
decision. It does not erase completed saves. A new explicitly saving task is
needed to opt back in. Direct assistant writes follow the same instructions;
core cannot intercept an AI app's native file writes or conversation history.

## Control and compatibility

`System/tasks/UUID.yaml` is closed operational YAML with exactly `schema:
apparatus/task@v0`, `id: UUID`, and `memory: save | no-save`. It contains no task
content. UUIDs are canonical random version 4 identifiers. Safe retained-root
reads and replacements reject unsafe paths and invalid state. Concurrent tasks
have separate controls; invocation context cannot implicitly cross workspaces.

New tasks default to save. A legacy private profile defaults to no-save unless
`--save-memory` is explicit. The profile field stays readable but is no longer a
setup question. Explicit saving tasks use ordinary labeling and credential
redaction, even if that compatibility field still says private. Before the task
directory exists, legacy commands keep their existing behavior. Afterwards,
new content requires a valid task ID; anonymous maintenance uses metadata-only
receipts and cannot silently save new content.

## No-save behavior

No-save suppresses new Memory, content-bearing corrections, profile answers and
their People/Goal seeds before reading task input. Reads, forgetting, outdated
status and labeling remain available. Requested output files save normally.
Automatic Library extraction, refresh, rebuild, Library cards and learned Skills,
activity notes and snapshots are suppressed. Routine Library offers are skipped.

Library retrieval compares existing extraction evidence with each selected
original's current bytes and searches only validated text in a temporary
in-memory index. A no-save query creates no cache directories, locks, files,
database repair or receipts. Missing, changed or unusable sources produce
partial coverage, distinct from a complete no-match. It does not re-extract
changed content during retrieval. A separate explicit Library add, remove,
ingest or rebuild uses its command's `--requested`; this does not enable Memory.

Automatic snapshots stop before Git initialization or object capture. A separate
explicit `snapshot --requested` or requested backup export remains available.
Managed work-area backup includes declared Apparatus state and its existing
history; legacy backup retains its full-workspace scope. Neither sanitizes old
data. Requested exceptions are scoped to that operation and do not
enable general capture.

Necessary receipts are shaped before exact-byte ownership binding: fixed event,
summary/status, opaque task/recovery identifiers and numeric counts. Queries,
paths, labels, snippets, bodies and free-form errors are omitted. Routine
retrieval produces no routine receipt for either saving or no-save tasks.
Queries and evidence paths are returned without a durable activity log; this does
not relax redaction obligations on actual managed mutations.

## Recovery and migration

New snapshots exclude `System/tasks`, including previously tracked entries.
Controls-only changes do not trigger snapshots. Restore preserves live controls
in place, including concurrent no-save updates, and cannot reinstate older task
flags. Incompatible snapshot ancestors are rejected before pre-restore capture
or mutation. Other restored Memory can still be older than current Memory.

Explicit backups may contain current metadata-only controls. Extracting an old
ZIP into a fresh folder knows only restrictions present at export time; it does
not import later opt-outs. This is not secure erasure or provider-retention
control.

Init recognizes known shipped instruction bytes, including CRLF variants, and
updates them with retained-root preimage checks. Custom conflicting guidance is
preserved with instructions to reconcile it before rerunning init. Existing
profile answers and historical files are not rewritten into new task controls.

Learned Skill draft and adoption commands require an explicit saving task before
reading candidate text or creating files. Snapshot and Library requested
exceptions never enable learned capture. New capture also requires managed
work-area enrollment, ensuring drafts stay outside managed recovery. These
controls do not block reading previously adopted Skills or erase older copies.

Library card publication requires an explicit saving task. The requested Library
exception permits registration/extraction only; it never permits card capture.
Routine completion offers are suppressed in no-save tasks.
