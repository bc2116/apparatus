# PR-78 Verification Note: Opt-in Memory Save Tools (`--memory-saves`)

- **Date**: 2026-11-13
- **Platform**: macOS ARM64 (`codex-cli 0.166.0`)
- **Isolation**: Scratch work area under `/tmp/apparatus-pr78-obs/workarea` with
  `APPARATUS_HOME=/tmp/apparatus-pr78-obs-home` and `codex exec --ephemeral
  --ignore-user-config --ignore-rules -s workspace-write`; user home app
  configurations (`~/.codex`, `~/.claude`, `~/.cursor`) were left untouched.
- **MCP server invocation**: `apparatus mcp serve . --memory-saves`

## 1. Tool discovery check

In a dedicated isolated `codex exec --ephemeral` probe asking Codex CLI to
list available Apparatus MCP tools without shell commands, Codex reported all
eight tools exposed by `apparatus mcp serve . --memory-saves`: `library_recall`,
`memory_recall`, `resume_brief`, `task_start`, `task_no_memory`,
`memory_save_fact`, `memory_save_person`, and `memory_save_decision`.

## 2. Three-session live Codex CLI observation

1. **Remember synthetic fact** (`"Please remember that the release freeze
   window starts every Thursday at 17:00 UTC."`):
   - **Observed tool path**: Codex read `Welcome.md`, `System/workspace.yaml`,
     `System/policy/`, and `System/profile.yaml`, then located a local `.venv`
     CLI binary on the machine instead of calling the `task_start` /
     `memory_save_fact` MCP tools, and ran `apparatus task start` followed by
     `apparatus --task e956f02e-894b-4e48-8892-04ca845c5d4e memory add-fact`.
   - **Saved record path**: `Memory/Facts/release-freeze-window.md` (with
     `schema: apparatus/fact@v0` and `title: Release freeze window`).
   - **Note**: Prompt wording was not retried to force MCP tool selection; the
     MCP save path itself is covered deterministically by
     `packages/apparatus-core/tests/test_tool_server_saves.py`.
2. **Fresh-conversation recall** (`"What was saved about the release freeze
   window?"`):
   - **Observed tool path**: `apparatus` was not on `PATH`, so Codex invoked
     MCP `task_start` (`{}` -> `{"task_id":
     "e1571c6e-04c5-43fd-8cc7-98fc92e2b40f", "memory": "save"}`) and MCP
     `memory_recall` (`{"query": "release freeze window", "limit": 5}`), which
     matched `Memory/Facts/release-freeze-window.md`.
   - **Outcome**: Recalled `"The release freeze window starts every Thursday at
     17:00 UTC."`
3. **Fresh-conversation no-save opt-out** (`"Don't save this task to Memory.
   Also note that the backup cutoff is 02:00 UTC."`):
   - **Observed tool path**: After `command -v apparatus` was unavailable on
     `PATH`, Codex called MCP `task_start`. Its initial guess (`{"workspace":
     ..., "no_memory": true}`) was rejected with `status: "invalid_arguments"`
     (`unknown argument(s): no_memory, workspace`); Codex immediately retried
     with `{"memory": "no-save"}`, receiving `{"task_id":
     "ab6332bb-66aa-46a7-b5a1-a74e48958ac7", "memory": "no-save"}`, and did
     not call any `memory_save_*` tool.
   - **Filesystem diff**: Zero new files under `Memory/` or
     `System/receipts/`; only `System/tasks/ab6332bb-66aa-46a7-b5a1-a74e48958ac7.yaml`
     (`memory: no-save`) was added.
