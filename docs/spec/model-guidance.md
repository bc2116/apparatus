# Model and spend guidance

Normative under ADR-0006. Apparatus supplies portable instructions and dated
starting data. It does not call, select or switch models, enforce quotas, or
supply a separate executor.

## One operational body

`.agents/skills/apparatus-economizer/SKILL.md` owns the operational instructions.
`System/guidance/model-guidance.md` contains only the dated starting table and
availability caveats. Neither a roster nor delegation is required. Simple work
stays direct; one assistant can perform several roles.

The existing profile values `frugal`, `balanced` and `thorough` are unchanged;
absence defaults to `balanced`. Applying guidance does not rewrite a preference.
Capability (`frontier`, `strong`, `fast`), effort (`low`, `medium`, `high`) and
team size are separate choices. Capability labels describe relative options,
not certified equivalents across providers. Unsupported effort controls remain
unapplied; prose cannot emulate them. Use the AI app's exposed controls and
report material limitations truthfully.

The retained starting table is:

| Spend | Lead | Optional worker | Reviewer |
|---|---|---|---|
| frugal | strong, medium | fast, low; fully checked mechanical work | strong, high |
| balanced | strong, high | strong, medium | strong, high |
| thorough | frontier, high | strong, high | frontier, high |

A capable lead owns judgment and acceptance. It can evaluate every delegated
result; review is at least as capable as authorship. Capability restrictions for
policy, authority, migrations, recovery and active instructions apply regardless
of spend and create no new approval gate. Small-team ceilings are one delegated
assistant for frugal/balanced and two for thorough, excluding the lead; user and
native limits take precedence. Workers do not start further teams.

## Bounded repair and truthful limits

A delegated deliverable has a named completion check and, by default, an initial
authoring attempt plus at most two delegated repair passes. A different explicit
user budget or stricter task limit takes precedence. Reassignment and escalation
consume the existing repair allowance. Deterministic verification commands do
not consume delegated repair passes. Exhaustion stops new delegation; a capable
lead may finish authorized work within the remaining user budget without a new
approval question.

Classify failures as ambiguity, platform/tool constraints, implementation defects
or demonstrated capability shortfalls. Address the cause. Repeated capability
failure may justify stronger authorship and matched review, without resetting
the allowance. Time alone does not establish inadequate capability. Known explicit
limits govern stopping; unknown usage is not zero or enforced. No background
monitoring, automatic benchmark or claim of savings follows from this guidance.
Routine routing produces no extra receipt or task-content log.

## Dated data and migration

The replaceable guidance carries a review date and a 90-day staleness window.
Warn when data is stale; freshness proves neither availability nor execution.
A concrete roster may be absent. Any future roster identifies applicable AI app,
version evidence and its own review date; fictional selectable models are not
shipped. Reviewed releases and optional pull/clone updates distribute changes;
installs do not benchmark or self-calibrate.

Init upgrades only exact recognized shipped guidance and instruction bytes,
including deliberate LF/CRLF variants, through retained preimage checks. Custom
guidance and profile choices remain unchanged. Generic shipped guidance may be
installed during no-save; routing transcripts, task-derived Skills, Memory,
cards, style profiles and automatic snapshots remain suppressed. Requested
project output is still possible. Existing necessary operational evidence and
native authority are unchanged.
