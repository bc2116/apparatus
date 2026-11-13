# ADR-0008: Optional local tool server

- **Status:** Accepted by owner direction on 2026-11-12; amended for opt-in Memory save tools in PR-78
- **Date:** 2026-11-12
- **Scope:** Defines an optional local Model Context Protocol (MCP) stdio adapter on top of Apparatus core (read-only by default, with explicit opt-in Memory save tools) without altering ADR-0003 minimum-capability portability.

## Context

Some AI apps support connecting local tools directly over standard input and output so they can query grounded Apparatus context without composing shell commands. At the same time, Apparatus must continue working cleanly in AI apps that only read files, write files, and run approved commands (`ADR-0003`), and Apparatus's privacy and retention rules (`ADR-0004`, `ADR-0006`) forbid silent background writes, network listeners, or automatic retention during read-only inspection.

## Decision

1. **Core may ship an optional local tool server as an AI app adapter under ADR-0003 §4.** Nothing in core, the canon, or a Skill depends on it.
2. **The AI app starts the process and owns its lifetime.** `apparatus mcp serve WORKSPACE` pins the verified stateful MCP stdio protocol revision **`2025-11-25`**. It speaks only on its standard streams (newline-delimited UTF-8 JSON-RPC 2.0), opens no listening socket, makes no network call, installs no background service, never starts by itself, and exits cleanly when its input closes.
3. **It serves one explicitly selected work area and never guesses another.** Selection resolves once at startup (directly or via an explicit project link) and is re-validated before and after each tool invocation; legacy un-enrolled layouts lacking `System/workspace.yaml` and `--task` invocations are refused with exit 2 on `stderr` and zero bytes on `stdout`.
4. **It adds no dependency to `apparatus-core`.** Both `mcp_protocol.py` and `commands/mcp.py` use Python's standard library alone with zero networking module imports.
5. **Tool results are data for the assistant, never instructions or authority.** Tool descriptions state this explicitly, preserve every domain refusal and degraded state (`feature_disabled`, `no_extractions`, `invalid_extractions`, `fts_unavailable`, partial vs. complete Library coverage, Memory `matched`/`no-match`/`unavailable`, and `resume_brief` `complete`/`partial`), and state that an abstained Library recall means the answer is not in the Library.
6. **Read tools write nothing; Memory saves require explicit opt-in.** By default, the server exposes only `library_recall`, `memory_recall`, and `resume_brief` with read-only annotations; `library_recall` establishes an explicit non-saving task context per call so neither workspace files nor external caches are modified. Passing `--memory-saves` to `apparatus mcp serve WORKSPACE` opts in to exposing `task_start`, `task_no_memory`, `memory_save_fact`, `memory_save_person`, and `memory_save_decision`, which execute through the same task-retention controls, Memory writers, credential redaction, and receipt path as the CLI verbs.

## Consequences

- AI apps with local MCP stdio support can call `library_recall`, `memory_recall`, and `resume_brief` cleanly over a single bounded session with zero filesystem or cache side effects, and can opt in with `--memory-saves` to explicit task-controlled Memory saves.
- AI apps without MCP support keep identical capabilities through existing CLI verbs and work-area files.
- A static AST test enforces zero networking module imports inside `mcp_protocol.py` and `commands/mcp.py`.
