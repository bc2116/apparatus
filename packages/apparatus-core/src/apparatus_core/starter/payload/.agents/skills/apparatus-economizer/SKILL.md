---
name: apparatus-economizer
description: Use when planning substantial work that could benefit from native delegation or choosing model capability and reasoning effort, or when the user asks to work economically. Keep simple tasks direct.
---

# Choose enough capability for the work

Follow the user's task and budget. Actual actions still require the user's
authority and native permissions. For a simple request,
work directly; this Skill needs no planning report. For larger work, read
`spend` in the selected work area's `System/profile.yaml`, defaulting to
`balanced` when absent. Leave the stored preference unchanged. Read the
starting table in `System/guidance/model-guidance.md` when choosing roles.

Check the current AI app's exposed models, supported effort settings and team
limits. Choose capability, effort and team size separately. `frontier` means
the most capable reasoning option, `strong` a capable workhorse, and `fast` a
small or latency-focused option. These relative labels do not certify models
or establish equivalence between vendors. Apply `low`, `medium` or `high`
effort only through a supported native control; prose cannot apply a missing
setting. If suitable controls or delegation are unavailable, the current
assistant works directly and mentions only limitations that affect the result.
Do not claim a setting took effect without confirmation from the native tool.

The capable lead owns scope, sources, decomposition, conflicts, synthesis and
acceptance. It must be able to evaluate every delegated result. Give a reviewer
the requirements, relevant evidence and finished artifact or diff; review must
be at least as capable as authorship. If available controls cannot establish
these conditions, retain the work at the capable lead. Never weaken review to
fit a cheaper author.

Delegate only an independent, bounded part whose benefit exceeds duplicated
discovery and coordination. Name its inputs, deliverable, ownership boundaries
and completion check. A fast worker may do only mechanical work whose entire
output can be checked. Keep incomplete-evidence interpretation, unresolved
design, safety/privacy policy, authority, migrations, deletion/recovery and
active instruction changes with capable authorship and equally capable review.
These restrictions add no approval step.

Use these ceilings for simultaneous delegated assistants, excluding the lead:

| Spend | Starting team | Ceiling |
|---|---|---|
| `frugal` | Lead does substantive work; delegate a mechanical part only when worthwhile. | 1 |
| `balanced` | Add one independent worker when useful; review can be sequential. | 1 |
| `thorough` | Improve verification first; add a second worker only for useful independent work. | 2 |

A ceiling is not a quota. Workers do not delegate further. Honor a different
explicit user limit and any stricter native limit. Consequential work can
require stronger authorship at any spend level. Choosing a cheaper model does
not establish savings.

Before delegating, define the completion check and repair allowance. Unless
the user specifies another budget, allow the initial authoring attempt plus
at most two delegated repair passes for the same deliverable; a stricter task
limit wins. Reassignment, escalation and a repeated delegated authoring attempt
consume the same remaining allowance. They do not reset it. Ordinary
deterministic verification commands do not consume this allowance.

When a result fails its check, distinguish unclear requirements, a tool or
platform constraint, an implementation defect and demonstrated capability
shortfall. Address the cause. Repeated capability failures can justify stronger
authorship or effort with equally capable review; elapsed time alone cannot.
Stop new delegation when the task is done, the repair allowance is exhausted,
or an explicit applicable budget is reached. Exhausted delegation allowance
does not pause authorized work the capable lead can finish within the user's
remaining budget. Respect an actual task-wide stop limit; if completion is
blocked, preserve the work and report the specific blocker and useful next step.

Treat unavailable token, money or quota data as unknown. Do not invent budget
enforcement, repeatedly seek unavailable telemetry, launch monitoring or add an
executor. Report material routing limits in the ordinary result, without an
economy receipt or task-content log. Follow the task's Memory choice: no-save
permits requested project work and reading generic guidance, but no automatic
Memory, cards, learned Skills, style profiles or snapshots derived from it.
