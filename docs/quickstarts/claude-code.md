# Apparatus with Claude Code — pre-alpha quickstart

Open a terminal in your chosen work-area folder and start `claude`. Start with
an actual task. Claude Code CLI 2.1.263 with Sonnet 5 Medium passed the focused
two-chat gate; its IDE/desktop variants remain untested. The official quickstart documents project-directory launch and the
normal sign-in flow. Use an already authorized account and follow native
permissions. [Claude Code quickstart](https://code.claude.com/docs/en/quickstart)

1. Use the shared work-area root for your first session. If you prefer a sibling
   project, have Apparatus explicitly bind it first with `apparatus project
   bind PROJECT --workspace WORKAREA`, replacing both placeholders, and start
   Claude Code from that bound project. Confirm the selected directory.
2. Ask: “Read the Apparatus instructions for this selected work area. Use
   `project-a/source.md` to finish and save `project-a/workshop-plan.md`, with
   source references and unresolved details.” From inside `project-a`, use
   `source.md` and `workshop-plan.md` instead. Work should finish in the project
   without a setup interview; native permission prompts still apply.
3. Inspect the saved file, its evidence and the preserved original. A brief
   offer to add reusable finished work to the Library is optional; declining
   should not block completion. State “Don't save this task to Memory” when
   desired; requested work files remain possible, with no provider-retention
   or historical-backup-erasure promise.

Need Apparatus first? Consult the [dated matrix](../certification/matrix.md) for
current package publication and native installer acceptance, then follow the
[setup guide](../../installer/README.md) and choose the actual work area.
Apparatus remains pre-alpha. Fresh/empty roots use ordinary init; existing
nonempty folders need explicit adoption. The scripts accept `--path WORKAREA --adopt` on macOS and
`-Path WORKAREA -Adopt` on Windows; the Windows wrapper uses `/WORKSPACEPATH=`
and `/ADOPT`. Omit adoption for fresh setup. Defaults are `~/Projects` and
`C:\Projects`. The macOS package has no custom-root/adoption option; use the
flat script. Existing projects and custom instructions stay in place or produce
a conflict requiring reconciliation.

If a native Skill is not listed, ask Claude Code to read `AGENTS.md` through
its existing instruction pointer and the chosen canonical
`.agents/skills/NAME/SKILL.md`. This file-reading route does not require a copied
body, symlink or successful menu discovery. A listed thin wrapper has not yet
proved that its body pointer is followed.

Official launch instructions checked 2026-09-06. The passing CLI configuration
used native auto permission mode and a restricted tool setup. Earlier permission
denials, semantic failures and the earlier sample-timing caveat remain attached
to their original runs in the [dated matrix](../certification/matrix.md), alongside
current release/install gates. No IDE result or broad support certification is
inferred.
