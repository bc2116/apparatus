# System

This folder is the machinery of your workspace. Your assistant uses it to do
its job well; you're welcome to look around, but nothing here needs your
attention day to day.

What lives here:

- `profile.yaml` — your preferences and useful defaults. Change a preference
  any time by asking your assistant; setup never blocks the requested work.
- `policy/` — the privacy and safety rules currently in force.
- `receipts/` — a record of what the machinery did on your behalf: checks,
  snapshots, and anything sensitive that was flagged or cleaned. If you ever
  wonder "what did it actually do?", the answer is here.
- `machine-report.md` — what tools are available on this computer, so your
  assistant never suggests something that can't work here.

Some of these appear only after setup completes.

Work-area enrollment is recorded in `workspace.yaml`. Managed recovery uses its
own store under `recovery/`; it never uses root or project Git repositories. A
project's `.apparatus/workspace.yaml` selects this work area explicitly. Its files
and Library originals are outside managed snapshot and backup coverage. Task
controls remain in place during restore.

Reusable workflows live in `.agents/skills/` at the work-area root. The Skill
index in `AGENTS.md` tells your assistant which canonical `SKILL.md` to read.
Legacy `procedures/` files may remain after an upgrade as compatibility pointers.
