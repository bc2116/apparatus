# PR-76 Verification Note: Optional Local Tool Server (`apparatus mcp serve`)

Date: 2026-11-13
Target: `apparatus-core` (`apparatus mcp serve WORKAREA`, MCP stdio JSON-RPC `2025-11-25`)
Environment: macOS ARM64, isolated temporary work areas and `APPARATUS_HOME` directories (user home configurations in `~/.claude`, `~/.codex`, and `~/.cursor` were never read or modified).

## Automated Protocol & Core Verification

- `packages/apparatus-core/tests/test_tool_server.py` exercises `apparatus mcp serve WORKAREA` over real subprocess stdio and in-process streams:
  - Stateful MCP `2025-11-25` lifecycle (`initialize`, `notifications/initialized`, `ping`, `tools/list`, `tools/call`).
  - Exact three read-only tools (`library_recall`, `memory_recall`, `resume_brief`) with read-only annotations and ADR-0001 data-not-instructions descriptions.
  - Stream isolation (`stdout` emits only newline-delimited UTF-8 JSON-RPC 2.0 responses; incidental `print` output redirects to `stderr`), `--task` exit 2 refusal with zero `stdout`, missing subcommand exit 2 with zero `stdout`, and legacy un-enrolled work-area refusal with `apparatus init` guidance.
  - Bounded frames (`MAX_REQUEST_BYTES = 65536`, `MAX_RESULT_BYTES = 524288`) and clean recovery after malformed JSON, invalid UTF-8, batch arrays, uninitialized calls, unknown methods, unknown tools, and invalid arguments.
  - All seven domain states preserved (`feature_disabled`, `no_extractions`, `invalid_extractions`, `fts_unavailable`, partial vs. complete Library coverage, unreadable Memory `unavailable`, and `resume_brief` `complete` vs. `partial`).
  - Byte-for-byte work-area and `APPARATUS_HOME` SHA-256 snapshot invariance across all three tool calls, plus mid-session bound-project drift rejection (`isError: true`).
  - Static AST check confirming zero networking imports in `mcp_protocol.py` and `commands/mcp.py`.

## Live AI-App Observations (2026-11-13)

| App & Version | Probe Scope & Isolation | Observed Result | Limits |
|---|---|---|---|
| Codex CLI `0.166.0` | Ephemeral `codex exec --ephemeral --skip-git-repo-check --ignore-user-config --ignore-rules -s read-only -c mcp_servers.apparatus=...` against a seeded isolated temporary work area (`Library/calibration.md`, `Memory/Facts/release-freeze-window.md`, `Goals/obs-goal.md`, `obs-seed` snapshot). | **Passed:** Connected to `apparatus mcp serve .` over stdio and called `resume_brief`, `memory_recall` (`matched`), and `library_recall` (`abstained` for `"quantum marsupials"`; `grounded` for `"cobalt calibration"` citing `Library/calibration.md`). Post-probe SHA-256 snapshot across all 152 work-area and `APPARATUS_HOME` entries was byte-for-byte unchanged. | Natural-language question `"What is the cobalt calibration constant?"` abstained under FTS5 all-term matching before keyword query `"cobalt calibration"` matched; default model inherited from Codex auth config. |
| Claude Code CLI `2.1.321` | Non-interactive `claude -p --strict-mcp-config --mcp-config ... --tools "" --permission-mode bypassPermissions` against the same isolated temporary work area. | **Blocked on local auth:** Exited with code 1 (`Failed to authenticate: OAuth session expired and could not be refreshed`). Registration CLI flags verified via `claude mcp add --help`. | No live Claude model turn or tool-call round-trip completed in this environment. |
| Cursor IDE | GUI desktop IDE. | **Unavailable:** No headless GUI execution available in this environment; `.cursor/mcp.json` stdio configuration schema checked against Cursor docs on 2026-11-13. | Interactive Cursor IDE MCP registration and tool-call execution remain unverified. |
