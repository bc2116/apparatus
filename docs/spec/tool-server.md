# Optional Local Tool Server (`apparatus mcp serve`)

Status: Accepted (`ADR-0008`)

`apparatus mcp serve WORKSPACE` provides an optional local Model Context Protocol (MCP) server over standard input and standard output so compatible AI apps can call Apparatus retrieval, brief assembly, and—when explicitly enabled with `--memory-saves`—task-controlled Memory save tools directly. Without `--memory-saves`, the server is strictly read-only.

## Transport and Protocol

- **Protocol revision:** Stateful MCP stdio JSON-RPC 2.0 pinned to `2025-11-25`.
- **Framing:** Exact newline-delimited UTF-8 (`\n`, with optional `\r\n` tolerated on input and stripped); embedded `\r` or `\n` inside frames and JSON-RPC batch arrays are rejected (`-32600`).
- **Stream isolation:** Binary stdio mode (`O_BINARY` on Windows); `stdout` is strictly reserved for JSON-RPC 2.0 response frames, and any incidental `print` or diagnostic output is redirected to `stderr`.
- **No networking:** The server opens no sockets, HTTP/SSE endpoints, or background listeners and imports zero networking modules (`socket`, `http`, `urllib`, `ssl`, `asyncio`, `websockets`, or third-party HTTP/MCP packages).
- **Caps:**
  - `MAX_REQUEST_BYTES = 65536`: lines exceeding 65,536 bytes are drained to the next newline and answered with `-32600` (`Invalid Request`), leaving the session usable for subsequent frames.
  - `MAX_RESULT_BYTES = 524288`: serialized JSON-RPC responses exceeding 524,288 bytes are replaced with a bounded `isError: true` (`result_too_large`) tool result so the wire payload never exceeds the cap.

## Lifecycle Methods

- `ping`: Allowed before or after initialization; returns `{}`.
- `initialize`: Negotiates `protocolVersion: "2025-11-25"`, `capabilities: {"tools": {}}`, and `serverInfo: {"name": "apparatus", "version": "<version>"}`. Calling `initialize` a second time returns `-32600`.
- `notifications/initialized`: Notification without `id`; produces no response frame.
- `tools/list` and `tools/call`: Require prior `initialize` (`-32600` otherwise). Unknown methods return `-32601`. Unknown tool names or invalid outer `tools/call` params return `-32602`.

## Startup and Read-Only Guarantees

- `--task` is rejected with exit code `2` on `stderr` and zero bytes on `stdout` before task retention or project binding opens.
- Missing subcommand (`apparatus mcp` without `serve`) exits `2` on `stderr` with zero bytes on `stdout`.
- `WORKSPACE` may be a direct work area or a bound project directory resolved once at startup. Legacy work areas lacking `System/tasks` are refused with exit code `2` on `stderr` and guidance to rerun `apparatus init`.
- Root identity and project binding are re-validated before and after every tool invocation; mid-session drift returns a bounded `isError: true` (`execution_error`) tool response without serving stale or redirected data.
- Tool execution creates no files, receipts, task files, snapshots, or external cache entries for read tools or when `--memory-saves` is omitted. `library_recall` runs inside an explicit non-saving `TaskContext` (`save_memory=False`, `legacy=False`) even when `--memory-saves` is enabled and a saving task exists.
- With `--memory-saves`, only `task_start`, `task_no_memory`, and successful saves (`memory_save_fact`, `memory_save_person`, `memory_save_decision`) under a saving `task_id` modify the work area, producing the exact same record bytes and receipts as the corresponding CLI verbs. Suppressed saves (`no-save`), read calls, and rejected calls leave the work-area tree unchanged.

## Exposed Tools

The three default tools advertise MCP read-only annotations (`readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`, `openWorldHint: false`). All tools return both `content` (`[{"type": "text", "text": "<json>"}]`) and `structuredContent`. Without `--memory-saves`, only the three read tools below are listed in `tools/list`, and calling any opt-in save or task tool returns `-32602` (`unknown tool`).

### 1. `library_recall`

Arguments: `{"question": string (non-empty, required), "limit": integer (1..20, default 5)}`. Invalid arguments return `isError: true` (`invalid_arguments`).

Distinct non-error (`isError: false`) `status` outcomes:
- `grounded` / `abstained`: Normal recall envelope (`question`, `threshold`, `evidence`, `generated_at`, `coverage: {"status": "complete" | "partial", "sources": [...]}`, optional `ignored_summary`). Notice partial source coverage remains explicit in `coverage.status == "partial"` rather than collapsing into a generic complete miss.
- `feature_disabled`: `library_indexing` is off for the work area.
- `no_extractions`: No Library extractions have been ingested yet.
- `invalid_extractions`: Existing Library extraction evidence is corrupt and needs `apparatus library ingest`.
- `fts_unavailable`: Full-text search is unavailable in the local Python environment.

### 2. `memory_recall`

Arguments: `{"query": string (non-empty, required), "limit": integer (1..20, default 5)}`.

Distinct non-error (`isError: false`) `status` outcomes:
- `matched`: Contains matching durable Memory snippets (`results`, `truncated`).
- `no-match`: No durable Memory records matched `query` (`results: []`).
- `unavailable`: Memory records could not be read cleanly (for example, corrupt YAML frontmatter).

### 3. `resume_brief`

Arguments: `{}` (no parameters accepted).

Distinct non-error (`isError: false`) `status` outcomes:
- `complete`: All brief sections (`Goals`, `Library`, `Snapshots`) read cleanly; returns `text` matching `apparatus resume`, `selection`, and `partial: false`.
- `partial`: One or more sections degraded (such as unreadable goal records, incomplete Library sources, or missing/unreadable snapshot); returns `partial: true` and the degraded `text` brief.

## Opt-in Task and Memory Save Tools (`--memory-saves`)

When started with `apparatus mcp serve WORKSPACE --memory-saves`, the server additionally exposes five tools that invoke the existing task-retention controls and Memory writers directly without shell-command composition.

- **Explicit task identity:** The server keeps no current task across calls and starts none automatically. Each `memory_save_*` call requires an explicit `task_id` returned by `task_start`; missing, malformed, or unknown `task_id` values return `isError: true` with the existing bounded retention error message and write nothing.
- **Bound projects:** When `WORKSPACE` is a bound project, task controls and Memory records write into the linked work area and return work-area-relative `record_path` values.
- **Product-facing rules:** Tool descriptions follow `ADR-0001` (`AI app` / `assistant`) and carry the canon capture rule: use a save tool only when the user explicitly asks to remember, save, or keep something; save only the requested fact, person, or decision; take sources and reasons from the request or evidence; do not invent them or save unrelated conversation content.

### 4. `task_start`

Arguments: `{"memory": optional "save" | "no-save"}`. Omitted `memory` uses the work area's existing default (including `no-save` for a legacy `private` profile). Returns `{"task_id": "<uuid>", "memory": "save" | "no-save"}`.

### 5. `task_no_memory`

Arguments: `{"task_id": string (required)}`. Applies the one-way opt-out for that task and returns `{"task_id": "<uuid>", "memory": "no-save"}`.

### 6. `memory_save_fact`

Arguments: `{"task_id": string (required), "title": string (non-empty, required), "body": string (required)}`. Runs the `memory add-fact` writer.

### 7. `memory_save_person`

Arguments: `{"task_id": string (required), "name": string (non-empty, required), "body": string (required), "role": optional string}`. Runs the `memory add-person` writer.

### 8. `memory_save_decision`

Arguments: `{"task_id": string (required), "title": string (non-empty, required), "date": string (YYYY-MM-DD, required), "body": string (non-empty, required)}`. Runs the `memory add-decision` writer.

### Outcomes for `memory_save_*`

- `saved` (`isError: false`): Returned only after confirming the new record file exists on disk through the retained work-area root. Payload includes `record_path` (work-area-relative path with `/` separators) and `redactions` (`{"total": int, "classes": [...], "counts": {...}}`) reporting credential-floor redaction counts and classes only—never removed secret text.
- `not_saved` (`isError: false`): Returned under a `no-save` task (including after `task_no_memory` or a legacy `private` profile default) with `reason` (`"This task does not save new Memory or setup answers."`); writes nothing.
- Invalid inputs (such as missing/empty/malformed/unknown `task_id`, empty `title`/`name`, invalid `date`, or empty decision `body`) return `isError: true` with a bounded path-safe message and write nothing.
