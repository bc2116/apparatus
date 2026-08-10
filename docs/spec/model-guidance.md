# Model and Spend Guidance (v1)

- **Status:** Normative for workspace model-capability and effort guidance.
- Governing decisions: ADR-0001 (vocabulary) and ADR-0003
  (AI-app-independent contract).

## Purpose and boundary

This guidance tells an assistant how much model capability and effort to apply
to a piece of work. Apparatus supplies the guidance as data. It does not call,
select, or switch models. The assistant applies the guidance using the controls
its AI app provides.

The stable rules below use roles, capability tiers, and effort settings rather
than model names. Concrete names belong only in the dated roster described at
the end of this specification.

## Stable terms

### Roles

- **lead:** orchestrates the work, synthesizes results, and verifies the final
  deliverable.
- **worker:** completes a bounded, delegated subtask.
- **reviewer:** checks finished work against its stated requirements.

One assistant may perform more than one role. Roles describe responsibilities,
not a requirement to delegate.

### Spend levels

- **frugal:** minimize cost by doing more work directly and delegating less.
- **balanced:** use capable defaults for ordinary work. This is the default.
- **thorough:** strengthen verification first, then authorship where warranted.

The spend level chooses starting settings. Evidence from the current piece of
work may justify a temporary escalation under the policy below.

### Capability tiers

- **frontier:** the provider's most capable reasoning model.
- **strong:** the provider's main workhorse.
- **fast:** a small or latency-optimized model.

The `fast` tier is permitted only for mechanical transformations whose complete
output the lead checks. It is not suitable for interpretation, judgment, or
independent verification.

### Effort

Effort is `low`, `medium`, or `high`. Apply it when the AI app exposes an effort
control; otherwise treat it as advice about the care and checking the role
requires.

## Stable starting mapping

The lead is never weaker than a worker whose work it verifies. A reviewer is at
least as capable as the author it checks. In `frugal`, the lead handles
substantive work directly; any worker assignment at the mapped `fast` tier is
therefore limited to a fully checked mechanical transformation. In `thorough`,
the reviewer and lead move to `frontier` before the drafting worker does.

```yaml
frugal:
  lead: {tier: strong, effort: medium}
  worker: {tier: fast, effort: low}
  reviewer: {tier: strong, effort: high}
balanced:
  lead: {tier: strong, effort: high}
  worker: {tier: strong, effort: medium}
  reviewer: {tier: strong, effort: high}
thorough:
  lead: {tier: frontier, effort: high}
  worker: {tier: strong, effort: high}
  reviewer: {tier: frontier, effort: high}
```

## Reactive escalation

The primary signal is a second blocking review cycle on the same deliverable.
Run time beyond roughly twice the stated expectation is secondary,
corroborating evidence only; elapsed time never triggers escalation by itself.
These triggers are identical at every spend level: the spend level sets the
starting point, while evidence adjusts it.

Before escalating, classify the blocking findings:

1. **Ambiguity:** if the task contract is unclear, fix the contract before
   continuing. A stronger model cannot repair an unclear ask, and using one
   hides the actual defect.
2. **Capability:** if the contract is clear and the author cannot satisfy it,
   raise the worker by one capability tier, one effort step, or both.

When the author rises, the reviewer rises with it so the reviewer is never
weaker than the author, and the re-review uses high effort. The escalation is
sticky for the remainder of that piece of work and is noted in its receipt.
Reset to the workspace spend level for the next piece of work; escalation never
permanently ratchets the user's setting.

Escalation is an economizing response. A lower-capability authorship pass
followed by two rework cycles and repeated reviews costs more than one stronger
authorship pass.

## Roster contract

A workspace guidance file may include a roster that maps the three capability
tiers to models available in the user's AI app. Concrete model names may appear
only in that roster. The roster must:

- carry a last-reviewed date;
- be marked advisory and replaceable;
- list one current app choice for each tier where available; and
- use a 90-day staleness window.

Once the last-reviewed date is more than 90 days old, every roster entry is a
hint rather than an instruction. The assistant then prefers the AI app's
current equivalent for each tier. Editing or replacing the roster never changes
the stable mapping or escalation policy.
