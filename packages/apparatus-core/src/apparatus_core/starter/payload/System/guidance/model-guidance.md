# Model and spend guidance

Use this guidance to choose how much model capability and effort to apply to a
piece of work. Apparatus never switches models itself. You, the assistant,
apply this guidance using the models and controls available in your AI app.

## The spend level

Read `spend` in `System/profile.yaml`. If it is absent, use `balanced`.

- `frugal`: keep cost down. The lead does substantive work directly and uses
  fewer delegated tasks.
- `balanced`: use capable defaults for ordinary work.
- `thorough`: strengthen verification first, then drafting when needed.

The spend level sets the starting point. Evidence from the current work can
temporarily raise it under the escalation rule below.

## Roles and capability tiers

- The `lead` organizes, combines, and verifies the work.
- A `worker` completes a bounded delegated task.
- A `reviewer` checks finished work against its requirements.

Capability tiers are `frontier` (the most capable reasoning option), `strong`
(the main workhorse), and `fast` (a small or latency-optimized option). Use a
`fast` option only for a mechanical transformation whose complete result the
lead checks. Effort is `low`, `medium`, or `high`; where the AI app has no such
control, treat the setting as advice about the care and checking required.

## Starting settings

| Spend level | Lead | Worker | Reviewer |
|---|---|---|---|
| `frugal` | `strong`, medium effort | `fast`, low effort; mechanical and fully checked only | `strong`, high effort |
| `balanced` | `strong`, high effort | `strong`, medium effort | `strong`, high effort |
| `thorough` | `frontier`, high effort | `strong`, high effort | `frontier`, high effort |

The lead must never be weaker than a worker it verifies. The reviewer must
never be weaker than the author it checks. One assistant may fill several
roles; delegation is optional.

## When work comes back for rework

Use a second blocking review cycle on the same deliverable as the primary
signal. Run time beyond roughly twice the stated expectation can support that
signal, but elapsed time alone never triggers escalation. Use the same trigger
at every spend level.

Before spending more, decide what the findings mean. If the task is ambiguous,
fix its requirements first. If the requirements are clear and capability is the
problem, step the worker up by one capability tier, one effort step, or both.
Step the reviewer up with the author so the reviewer is never weaker, and use
high effort for the next review.

Keep that escalation for the rest of this piece of work and note it in the
work's receipt. Reset to the profile's spend level when the piece is done.
Repeated rework and repeated reviews usually cost more than one stronger pass,
so this escalation avoids waste rather than creating it.

## Advisory model roster

- Last reviewed: 2026-08-10
- Staleness window: 90 days
- Status: fictional placeholders; replace these entries with models actually
  available in the user's AI app.

| Capability tier | Model available in this AI app |
|---|---|
| `frontier` | `example-frontier-model` |
| `strong` | `example-strong-model` |
| `fast` | `example-fast-model` |

This roster is advisory and replaceable. If its last-reviewed date is more than
90 days old, treat its entries as hints and prefer the AI app's current
equivalents for the tiers. Keep concrete model names in this roster only; do
not add them to the stable settings or escalation rule.
