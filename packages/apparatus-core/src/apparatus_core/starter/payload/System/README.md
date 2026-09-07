# System

This folder is the machinery of your workspace. Your assistant uses it to do
its job well; you're welcome to look around, but nothing here needs your
attention day to day.

What lives here:

- `profile.yaml` — your preferences and useful defaults. Change a preference
  any time by asking your assistant; setup never blocks the requested work.
- `policy/` — the privacy and safety rules currently in force.
- `receipts/` — meaningful init/profile changes, credential redaction,
  snapshots, restores and exports. Routine checks, retrieval, ingest and
  unchanged operations leave no activity log. Existing history stays readable.
- `machine-report.md` — detected tools and suggested next steps. Git detection
  alone does not prove a usable recovery store or an existing saved point.

Some of these appear only after setup completes.

Work-area enrollment is recorded in `workspace.yaml`. Managed recovery uses its
own store under `recovery/`; it never uses root or project Git repositories. A
project's `.apparatus/workspace.yaml` selects this work area explicitly. Its files
and Library originals are outside managed snapshot and backup coverage. Task
controls remain in place during restore.

Reusable workflows live in `.agents/skills/` at the work-area root. The Skill
index in `AGENTS.md` tells your assistant which canonical `SKILL.md` to read.
Legacy `procedures/` files may remain after an upgrade as compatibility pointers.

`guidance/model-guidance.md` holds dated starting choices. The economizer Skill
owns the delegation and repair guidance; the humanizer Skill provides one
selective prose pass. Both live in the canonical Skill directory above.

Learned workflow drafts live in `skill-drafts/` for review, outside native
discovery and managed recovery coverage. `skills/adopted/` holds small ownership
records pointing to the canonical adopted `.agents/skills/NAME/SKILL.md` bodies.

`library/sources/` selects project originals without copying them. `library/cards/`
holds small assistant-written summaries with exact source/extraction provenance.
Cards aid discovery; originals remain authoritative. Removed or ignored sources
keep their cards inactive; leave them inactive when that choice is intentional.
For a missing or changed original, repair the source first and request refreshed
evidence and a grounded summary if the card is still useful.
