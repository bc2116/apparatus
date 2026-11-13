# Optional Local Tool Server (`apparatus mcp serve`)

Status: Accepted (`ADR-0008`)

`apparatus mcp serve WORKSPACE` provides an optional, read-only local Model Context Protocol (MCP) server over standard input and standard output so compatible AI apps can call Apparatus retrieval and brief assembly directly without modifying the work area.

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
- Tool execution creates no files, receipts, task files, snapshots, or external cache entries. `library_recall` runs inside an explicit non-saving `TaskContext` (`save_memory=False`, `legacy=False`).

## Exposed Tools

All three tools advertise MCP read-only annotations (`readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`, `openWorldHint: false`) and return both `content` (`[{"type": "text", "text": "<json>"}]`) and `structuredContent`.

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
