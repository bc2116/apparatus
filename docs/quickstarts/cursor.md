# Apparatus with Cursor — pre-alpha quickstart

In Cursor, choose **File > Open Folder** and select your actual work-area root.
Open the Agent panel and ask for a concrete result. Cursor IDE 3.19.13 with
GPT-5.6 Luna Medium passed the focused two-chat gate; that result does not extend
to every Cursor model or the CLI.
[Open a project](https://cursor.com/help/getting-started/first-project),
[Cursor quickstart](https://cursor.com/docs/get-started/quickstart).

1. Start with the shared root, or use a sibling project that Apparatus has
   explicitly bound using `apparatus project bind PROJECT --workspace
   WORKAREA`. Ask for help with that command if needed; never infer a binding
   from a nearby folder. Honor Cursor's native access and command permissions.
2. In Agent, ask: “Read this work area's Apparatus instructions. From
   `project-a/source.md`, finish and save `project-a/workshop-plan.md`. Cite
   the original and identify missing information.” Use project-relative names
   when the bound project itself is open. You can use `@` to identify the
   actual file in the request. [Official file context](https://cursor.com/help/getting-started/first-project)
3. Review the saved file and its changes. Completion should not depend on an
   interview or optional Library addition. Say “Don't save this task to Memory”
   when desired; the requested deliverable can still be saved. This does not
   change provider retention or erase historical copies.

If Apparatus is not set up, consult the [dated matrix](../certification/matrix.md)
for current package publication and native installer acceptance, then follow
the [setup guide](../../installer/README.md) for the selected root. Apparatus
remains pre-alpha. Defaults are `~/Projects` or `C:\Projects`; an Apparatus
enclosure is not required. Existing nonempty unmarked folders need explicit adoption through
`--adopt` on the macOS script or `-Adopt` on the Windows script (`/ADOPT` for the
Windows wrapper). The macOS package cannot select a custom root or pass
adoption; use the flat script. Ask for the matching path option and command
rather than silently enrolling an existing folder.

In a bound project, `apparatus project bind` and `apparatus render` generate thin
pointer adapters under `PROJECT/.agents/skills/NAME/SKILL.md` pointing to the
canonical `.agents/skills/NAME/SKILL.md` files in the work area; whether Cursor
automatically discovers and follows those adapters remains unverified. For portable
Skill use, ask Agent to read the work-area `AGENTS.md` and relevant
canonical `.agents/skills/NAME/SKILL.md`. A native menu entry is not required;
no duplicate body or symlink is needed. Existing Cursor **CLI** metadata probes
were inconclusive and establish neither IDE discovery nor body execution.

## Optional read-only local tool server

You do not need a tool server to use Apparatus. If you want Cursor to query
Library evidence, Memory records, or your resume brief as native read-only tools
without changing work-area files, add an optional `.cursor/mcp.json` entry
pointing to a relative `WORKAREA` path (for example `.` from the work area):

```json
{
  "mcpServers": {
    "apparatus": {
      "command": "apparatus",
      "args": ["mcp", "serve", "."]
    }
  }
}
```

Cursor `.cursor/mcp.json` stdio schema checked against Cursor documentation on
2026-11-13 (note: Cursor IDE local MCP behavior remains unverified in headless
checks until tested interactively).

Official setup pages checked 2026-09-06. The Luna IDE run observed canonical
Skill use through the prompted path; automatic discovery remains unproven.
The separate Grok 4.6 High run retained a timing error in its final prose.
See the [dated matrix](../certification/matrix.md) for exact identifiers, preserved
failures, variant limits and current release/install gates. No CLI result or
broad support certification is inferred.
