# PR-78 — Opt-in Memory save tools for the local tool server

- **Target:** Apparatus core tool server and its specification.
- **Branch:** `pr-78-memory-save-tools`.
- **Plan slice:** Owner direction 2026-11-12, third of three Native Reach
  prompts (following the 0.0.3 release delivery in PR-75).
- **Dependencies:** PR-76 landed, including ADR-0008.
- **Capability:** frontier tier at high effort for implementation and review.
  This is a retention and privacy surface.

## Goal

Let an assistant that reaches Apparatus through the local tool server save an
explicitly requested fact, person or decision, with the same task Memory
control, redaction and confirmation as the existing verbs. Certification
recorded that casual “remember this” wording sometimes saved nothing when the
assistant had to compose a shell command. A named save tool that returns the
saved record's path makes the outcome explicit.

Read `AGENTS.md`, the design brief, ADR-0004, ADR-0006, ADR-0008, this prompt,
[PR-76](PR-76-local-tool-server.md), `docs/spec/tool-server.md`,
`docs/spec/task-retention.md` and `docs/spec/memory.md` first. The task
retention spec is binding for every sentence below.

## Contract

1. Add `--memory-saves` to `apparatus mcp serve WORKSPACE`. Without it the
   server is exactly the read-only server from PR-76: the tools below are not
   listed and a call to one is an unknown-tool error. Amend ADR-0008's
   decision 6 in this PR to record the flag as the opt-in.
2. With the flag, list these additional tools. Arguments mirror the existing
   verbs exactly; add no field a verb does not accept.

   | Tool | Arguments | Behavior |
   |---|---|---|
   | `task_start` | optional `memory`: `save` or `no-save` | The existing task start. Omitted `memory` uses the existing default, including the legacy private-profile default. Returns the opaque task ID and the decision. |
   | `task_no_memory` | `task_id` | The existing one-way opt-out for that task. |
   | `memory_save_fact` | `task_id`, `title`, `body` | The `memory add-fact` writer. |
   | `memory_save_person` | `task_id`, `name`, `body`, optional `role` | The `memory add-person` writer. |
   | `memory_save_decision` | `task_id`, `title`, `date` (`YYYY-MM-DD`), `body` | The `memory add-decision` writer. |

3. **One writer.** Each save runs through the same code path as its verb:
   the same retention gate, labeling, credential redaction, collision
   handling, transaction and receipts. Do not add a parallel writer or a
   second redaction pass. For equal inputs and task, a tool save and a verb
   save produce the same record bytes and the same receipts.
4. **Task identity is required and never inferred.** A save needs a
   `task_id` from `task_start` in the same conversation. A missing, malformed
   or unknown ID is a tool error with the existing bounded message. The
   server keeps no current task, starts none on its own, and never reuses an
   ID across calls on the caller's behalf.
5. **Outcomes are explicit.** A save returns status `saved` with the
   work-area-relative record path only after the server has confirmed that
   file exists. Under a no-save task it returns status `not_saved` with the
   existing reason; that is a successful result, not an error, and writes
   nothing. A redaction is reported as a count and class, never the removed
   text.
6. Tool descriptions are product-facing text under ADR-0001 and carry the
   canon's capture rule: use a save tool only when the user explicitly asks to
   remember, save or keep something; save only the requested fact, person or
   decision; take sources and reasons from the request or evidence; do not
   invent them or save unrelated conversation content.
7. The read tools from PR-76 keep their no-write behavior with or without the
   flag, whatever task exists.
8. The server's unchanged-tree invariant from PR-76 now holds for the server
   without the flag, and for every call other than a successful save or task
   change with it. A successful save changes exactly the files its verb
   changes.

## Non-goals

No correct, outdated or forget tools. No Library add, ingest, card, snapshot,
backup, profile, goal or learned-Skill tools. No file-based body input. No
automatic capture, no save without a request, and no change to the default
Memory decision. No canon edit: the verbs remain the documented fallback.

## Scope and owned files

- `packages/apparatus-core/src/apparatus_core/commands/mcp.py` and its
  protocol module;
- the smallest refactor in `commands/memory.py` and `commands/task.py` that
  lets the server call the existing writers and receive their outcome without
  parsing printed text. Verb output stays byte-for-byte unchanged;
- `packages/apparatus-core/tests/test_tool_server_saves.py` (new), narrow
  additions to existing Memory and retention tests where they prove shared
  behavior, and the Windows safety selection with its selector manifest;
- `docs/adr/ADR-0008-optional-local-tool-server.md`,
  `docs/spec/tool-server.md`, one linking sentence each in
  `docs/spec/memory.md` and `docs/spec/task-retention.md`;
- `docs/it-onepager.md`: one sentence that the server can write Memory
  records only when started with the flag;
- `README.md` status text, `CHANGELOG.md` under Unreleased, and the
  quickstart optional-setup sections, showing the flag as a choice;
- `docs/notes/pr-78-verification.md` and one dated matrix row;
- this prompt and the PR-78 row in `docs/plan/README.md`.

Do not edit record schemas, the credential floor's patterns, the retention
contract, the starter canon, Skills, recovery or installers.

## Acceptance and validation

Deterministic tests:

- Without the flag, the five tools are absent from the listing and rejected
  when called, and the PR-76 unchanged-tree tests still pass.
- With the flag, each save under a saving task writes one record at the
  returned path. The record bytes and receipts equal those of the matching
  verb for the same inputs.
- Under a no-save task, including one changed by `task_no_memory`, each save
  returns `not_saved` and the tree is unchanged.
- A body containing a credential is redacted exactly as the verb redacts it,
  with the required receipt and a count-only result.
- A missing, malformed or unknown task ID, an invalid date and an empty title
  each return a tool error and write nothing.
- A legacy private profile yields the existing no-save default from
  `task_start`.
- Two servers on one work area saving concurrently use the existing
  transaction and neither loses a record.
- A bound project saves into exactly its linked work area.
- Read tools write nothing while a saving task exists.

One observation, not a gate on merging the mechanism: in one available AI app,
with the flag set, ask in ordinary words to remember one synthetic fact, then
ask in a fresh conversation what was saved. Record whether the save tool was
called, the returned path, and whether the second conversation recalled it,
as one dated matrix row and a short note. Repeat once with “don't save this
task to Memory” and record that nothing was written. `Unavailable` is a valid
outcome. Do not retry wording to force a pass, and do not create a per-PR
evidence directory.

```sh
uv run pytest packages/apparatus-core/tests/test_tool_server_saves.py packages/apparatus-core/tests/test_tool_server.py
uv run pytest
git diff --check
```

## Execution prompt

Implement PR-78 on `pr-78-memory-save-tools`. Expose the five tools only
behind `--memory-saves`, each calling the existing writer or task function.
Prove byte equality with the verbs, no-save suppression and the absent-flag
behavior before the full suite. Run the one app observation if an app is
available and record its exact outcome. Report test results and any
difference you found between a tool save and its verb. Prepare only
externally authorized delivery actions; this prompt grants no external
authority.
