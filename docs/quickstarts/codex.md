# Apparatus with Codex — pre-alpha quickstart

Open your chosen local work area and ask for useful work. Codex CLI 0.153.4
with Terra Medium requested passed the focused two-chat gate. The desktop route
below is documented separately and remains untested; Apparatus stays pre-alpha.

1. In the desktop app, use a local project with the work-area folder attached.
   Under **Edit project**, **Add folder** attaches a folder and **Make primary**
   chooses the default context. Make the work area primary for the initial
   task. Codex discovers its instructions and Skills from the primary folder;
   secondary folders remain available for file access but are not automatically
   equivalent discovery roots. [Official projects documentation](https://learn.chatgpt.com/docs/projects)
2. Start a new Codex chat in that local project. For a CLI session instead,
   start `codex` from the chosen directory or use `codex --cd WORKAREA` after
   replacing the placeholder. Record CLI and desktop results separately.
   [Official directory setup](https://learn.chatgpt.com/docs/projects)
3. Ask: “Use this work area's Apparatus instructions. From `project-a/source.md`,
   finish and save a short workshop plan as `project-a/workshop-plan.md`. Cite
   the source and identify what it does not establish.” Supply your actual
   source/task when using this outside the synthetic checklist.
4. Check the saved project file and citations. To work from a sibling project
   later, first ask for explicit `apparatus project bind PROJECT --workspace
   WORKAREA`, then open that project and follow its pointer. Honor native access
   controls if the work area is outside the selected readable/writable roots.

If setup is needed, consult the [dated matrix](../certification/matrix.md) for
current package publication and native installer acceptance, then follow the
[setup guide](../../installer/README.md).
The installer uses the chosen root directly: fresh/empty roots use normal setup; existing
nonempty roots need explicit `--adopt` (macOS script) or `-Adopt` (Windows script;
wrapper `/ADOPT`). Defaults are `~/Projects` and `C:\Projects`, without a required
Apparatus subfolder. The macOS package cannot forward custom-path/adoption flags;
use its flat script. Do not silently adopt an existing folder.

If no native Skill entry appears, ask Codex to read the selected work area's
`AGENTS.md` and the relevant canonical `.agents/skills/NAME/SKILL.md` directly.
Keep one body; do not create duplicate Skills or infer execution from a menu.
For a task you do not want retained, say “Don't save this task to Memory”; this
still allows its requested deliverable and does not control provider retention.

Official setup pages checked 2026-09-06. The passing CLI case explicitly asked
“Save a Memory fact”; casual “remember” still omitted the Fact. See the
[dated matrix](../certification/matrix.md) for exact build/configuration evidence,
preserved failures and current release/install gates. No desktop result or broad
support certification is inferred.
