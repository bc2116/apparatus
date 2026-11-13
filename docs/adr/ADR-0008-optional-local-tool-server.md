# ADR-0008: Optional local tool server, read-only

- **Status:** Accepted by owner direction on 2026-11-12
- **Date:** 2026-11-12
- **Scope:** Defines an optional, read-only local Model Context Protocol (MCP) stdio adapter on top of Apparatus core without altering ADR-0003 minimum-capability portability.

## Context

Some AI apps support connecting local tools directly over standard input and output so they can query grounded Apparatus context without composing shell commands. At the same time, Apparatus must continue working cleanly in AI apps that only read files, write files, and run approved commands (`ADR-0003`), and Apparatus's privacy and retention rules (`ADR-0004`, `ADR-0006`) forbid silent background writes, network listeners, or automatic retention during read-only inspection.

## Decision

1. **Core may ship an optional local tool server as an AI app adapter under ADR-0003 §4.** Nothing in core, the canon, or a Skill depends on it.
2. **The AI app starts the process and owns its lifetime.** `apparatus mcp serve WORKSPACE` pins the verified stateful MCP stdio protocol revision **`2025-11-25`**. It speaks only on its standard streams (newline-delimited UTF-8 JSON-RPC 2.0), opens no listening socket, makes no network call, installs no background service, never starts by itself, and exits cleanly when its input closes.
3. **It serves one explicitly selected work area and never guesses another.** Selection resolves once at startup (directly or via an explicit project link) and is re-validated before and after each tool invocation; legacy un-enrolled layouts lacking `System/workspace.yaml` and `--task` invocations are refused with exit 2 on `stderr` and zero bytes on `stdout`.
4. **It adds no dependency to `apparatus-core`.** Both `mcp_protocol.py` and `commands/mcp.py` use Python's standard library alone with zero networking module imports.
5. **Tool results are data for the assistant, never instructions or authority.** Tool descriptions state this explicitly, preserve every domain refusal and degraded state (`feature_disabled`, `no_extractions`, `invalid_extractions`, `fts_unavailable`, partial vs. complete Library coverage, Memory `matched`/`no-match`/`unavailable`, and `resume_brief` `complete`/`partial`), and state that an abstained Library recall means the answer is not in the Library.
6. **Read tools write nothing.** The server exposes only `library_recall`, `memory_recall`, and `resume_brief` with read-only annotations; `library_recall` establishes an explicit non-saving task context per call so neither workspace files nor external caches are modified. Any writing tool is a separate, opt-in decision ([PR-78](../plan/PR-78-memory-save-tools.md)).

## Consequences

- AI apps with local MCP stdio support can call `library_recall`, `memory_recall`, and `resume_brief` cleanly over a single bounded session with zero filesystem or cache side effects.
- AI apps without MCP support keep identical capabilities through existing CLI verbs and work-area files.
- A static AST test enforces zero networking module imports inside `mcp_protocol.py` and `commands/mcp.py`.
