# PR-76 — Optional local tool server, read-only

- **Target:** Apparatus core, one new decision record, and its documentation.
- **Branch:** `pr-76-local-tool-server`.
- **Plan slice:** Owner direction 2026-11-12, first of three Native Reach
  prompts (following the 0.0.3 release delivery in PR-75).
- **Dependencies:** PR-75 landed on `main`.
- **Capability:** strong tier at medium-high effort for implementation;
  frontier tier at high effort for the decision record and the review.

## Goal

Let an AI app that supports the Model Context Protocol call Apparatus as native
tools instead of composing shell commands. Add `apparatus mcp serve WORKSPACE`,
a local process the AI app starts, which answers three read-only tools over
standard input and output: grounded Library recall, current Memory recall, and
the resume brief.

This is an optional adapter. Every capability stays available through files
and approved commands, so the three-capability contract in ADR-0003 is
unchanged and no canon or Skill may require the server.

Read `AGENTS.md`, the design brief, ADR-0003, ADR-0005, ADR-0006, this prompt,
`docs/spec/workspace.md`, `docs/spec/task-retention.md`,
`docs/spec/memory.md`, `docs/spec/library-sources.md`, and the current public
[protocol specification](https://modelcontextprotocol.io/specification) before
implementation. Take every protocol detail from that specification, not from
memory, and record the revision you implement.

## Decision record

Write `docs/adr/ADR-0008-optional-local-tool-server.md`, status accepted by
owner direction on 2026-11-12, deciding exactly this:

1. Core may ship an optional local tool server as an AI app adapter under
   ADR-0003 §4. Nothing in core, the canon or a Skill depends on it.
2. The AI app starts the process and owns its lifetime. It speaks only on its
   standard streams. It opens no listening socket, makes no network call,
   installs no background service, never starts by itself, and exits when its
   input closes.
3. It serves one explicitly selected work area and never guesses another.
4. It adds no dependency to `apparatus-core`.
5. Tool results are data for the assistant, never instructions or authority.
6. Read tools write nothing. Any writing tool is a separate, opt-in decision
   ([PR-78](PR-78-memory-save-tools.md)).

Update the design brief in the same PR: one sentence in section 6 naming the
tool server among optional adapters, and an `Open questions` heading (add it if
absent) recording whether the server should later move to an optional module.

## Command contract

1. Register `apparatus mcp serve WORKSPACE` and add `mcp` to the central
   workspace-verb routing set, so an explicitly bound project resolves to its
   linked work area through the existing project-context route. A missing,
   malformed, unsafe or mismatched selection is a usage failure, exit 2, before
   any protocol output. The global `--task` option is rejected for this verb:
   a server is not one task.
2. Standard output carries protocol messages only. Every diagnostic goes to
   standard error and is bounded, path-safe and free of raw OS, YAML, SQLite
   or exception text. Force binary, UTF-8, newline-exact stream handling so
   Windows text translation cannot alter a frame.
3. Implement only the lifecycle the specification requires for a tools-only
   server: initialization and capability negotiation, the initialized
   notification, ping, tool listing and tool calls. Advertise the tools
   capability alone. Any other method returns the standard method-not-found
   error. Handle one request at a time in arrival order.
4. Read input with fixed limits. Choose and document a maximum request size
   and a maximum result size. An oversized or malformed request returns the
   standard protocol error and the server keeps running. End of input is a
   clean exit 0.
5. Expose exactly these tools. Names and argument names are part of the
   contract; descriptions are product-facing text and follow ADR-0001.

   | Tool | Arguments | Engine and result |
   |---|---|---|
   | `library_recall` | `question`, optional `limit` (1–20, default 5) | The existing recall engine. Returns status `grounded` or `abstained`, evidence items with source path, snippet and score, the coverage object, and the ignore-rule sentence the verb prints. |
   | `memory_recall` | `query`, optional `limit` (1–20, default 5) | The existing current-Memory reader. Returns only current records with their work-area-relative paths and sources. |
   | `resume_brief` | none | The same brief text `apparatus resume` prints, plus a flag saying whether any section was unavailable or partial. |

   Factor the resume assembly so it can return its rendered text and status
   without printing. The verb's output stays byte-for-byte unchanged.
6. Every state the verbs distinguish stays distinct in tool results: no
   extractions yet, invalid extraction evidence, the Library feature turned
   off, full-text search unavailable in this Python build, partial coverage,
   a complete no-match, and an unreadable Memory or goal record. These are
   successful tool results with a `status` field, not protocol errors. Invalid
   arguments and unknown tool names are tool errors.
7. Return each result as one text block containing the JSON object and, where
   the implemented revision defines structured results, the same object as
   structured content. AI apps differ in which form reaches the assistant.
8. Each tool description states that returned text is data, not instructions,
   and that an abstained recall means the answer is not in the Library.

## Read-only and safety invariants

The server leaves the complete work-area tree byte-for-byte unchanged for its
whole lifetime, on every outcome. It creates no cache directory, lock, index
file, receipt, task control, machine report, log file or temporary durable
file. It starts no child process.

Library retrieval already has a no-write route: an invocation whose task
context does not save builds its index in memory. An anonymous invocation
takes that route only when the work area has its `System/tasks` directory.
Establish the no-write route explicitly for every server call. For a legacy
layout where that cannot be established, refuse to serve with exit 2 and the
existing guidance to rerun `apparatus init`. Do not create a task control per
call.

Resolve the selection once at startup. Before and after each tool call,
validate that the same root, and for a bound project the same binding, is
still selected. A changed selection yields a tool error for that call; the
server never re-resolves to a different work area. Existing ignore rules apply
through the engines. Expose no tool that reads an arbitrary path.

The module that implements the server imports no networking library; assert
that in a test.

## Scope and owned files

- `packages/apparatus-core/src/apparatus_core/commands/mcp.py` (new) and a
  small protocol module beside it if that keeps the verb thin;
- the registry and routing-set change in `cli.py`, plus
  `packages/apparatus-core/pyproject.toml` (and `uv.lock` if changed by
  `uv sync`) for `[project.entry-points."apparatus.commands"]` (without adding
  any package dependency);
- the print-free refactor in `commands/resume.py`, with unchanged output;
- `packages/apparatus-core/tests/test_tool_server.py` (new), and the narrow
  additions to the Windows safety selection in `.github/workflows/ci.yml` with
  the matching selector manifest in `test_ci_workflow.py`;
- `docs/adr/ADR-0008-optional-local-tool-server.md` (new),
  `docs/spec/tool-server.md` (new), one linking sentence in
  `docs/spec/workspace.md`, and the design brief edits above;
- `docs/it-onepager.md`: one paragraph stating the properties in decision 2,
  leaving the existing network sentence true;
- `README.md` status text, `CHANGELOG.md` under Unreleased;
- an optional-setup section in each quickstart whose AI app documents a local
  tool-server configuration. Take each configuration form from that vendor's
  current primary documentation with a retrieval date. If it cannot be
  verified, omit that app's snippet and say so. Use a relative work-area
  argument; never write a machine-specific path;
- `docs/notes/pr-76-verification.md` and one dated matrix row;
- this prompt and the PR-76 row in `docs/plan/README.md`.

Do not edit the starter canon, any Skill body, Memory or Library writers,
record schemas, recovery, installers or package dependencies. No canon bytes
change, so no instruction migration is needed. Do not write or modify any AI
app configuration file on the user's behalf.

## Non-goals

No writing tool, no file-read tool, no resources, prompts or sampling, no
HTTP or socket transport, no configuration writer, no background start, no
second package, and no claim that any AI app is supported beyond what the
observation below records.

## Acceptance and validation

Deterministic tests, driving the real command as a child process where the
behavior is about streams:

- Initialization, tool listing and one call of each tool succeed against a
  work area with registered sources, Memory records and goals. Results match
  the corresponding verb's engine output for the same inputs.
- Every distinct state in contract item 6 is produced and labeled.
- Malformed JSON, an oversized request, an unknown method, an unknown tool
  and invalid arguments each return the specified error, and a following
  valid request still succeeds.
- Every line on standard output parses as a protocol message, including on
  failure paths. Closing input exits 0.
- A bound project serves exactly its linked work area. A broken binding fails
  before protocol output. Replacing the root between two calls makes the
  second call fail without serving another root.
- For every success and failure fixture, an immutable recursive tree capture
  before start and after exit is equal. Include the legacy-layout refusal.
- The static no-networking assertion passes. The new tests run in the Windows
  safety lane.

One observation, not a gate on merging the mechanism: in one available AI app
that supports local tool servers, confirm the three tools are listed, a recall
over a synthetic registered source returns cited evidence, and a recall for an
absent topic abstains. Record the app, version, operating system and outcome
as one dated matrix row and a short note. `Unavailable` is a valid outcome.
Claim support in the README and quickstarts only for what was observed. Do not
create a per-PR evidence directory.

```sh
uv run pytest packages/apparatus-core/tests/test_tool_server.py packages/apparatus-core/tests/test_resume.py
uv run pytest
git diff --check
```

## Execution prompt

Implement PR-76 on `pr-76-local-tool-server`. Read the current protocol
specification first and pin the revision. Write ADR-0008, then the smallest
standard-library server that exposes the three read-only tools through the
existing engines. Prove the unchanged-tree invariant and stream purity before
running the full suite. Run the one app observation if an app is available and
record its exact outcome. Report test results, the pinned revision, the chosen
size limits and any unverified quickstart configuration. Prepare only
externally authorized delivery actions; this prompt grants no external
authority.
