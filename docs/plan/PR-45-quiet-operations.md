# PR-45 — Quiet operations and concrete repair guidance

Implementation contract for R10, grounded in ADR-0006 §10 and the approved
rework sequence. Final delivery depends on PR-44 cards/offers, PR-43 references
and all intervening fixes. Runtime changes may be authored against integrated
PR-43 while PR-44 is in progress; integrate and inspect the completed PR-44
source before final guidance migration, review and validation. No new product
choices are needed.

## Outcome

Routine checks, retrieval and cache maintenance should return useful results
without leaving activity logs. Actual repairs, credential redaction and recovery
keep the evidence that makes them understandable and safe to undo. Existing
history remains byte-identical and readable. No scheduler, background service,
new receipt framework, cleanup command, quota dashboard or approval step.

Change conditions at individual producers. Do not filter events inside the
shared receipt writer: its identity, invocation digest, publication and rollback
contracts remain intact. Keep every historical event accepted by the record
schema and recovery readers, including retired sharing events.

## Receipt policy

- Stop new `check`, `recall` and `library-ingest` receipts, including unchanged,
  empty, abstained, flagged and feature-disabled outcomes. Preserve command
  output, exit codes, extraction metadata, citations, coverage and ignore counts.
  Keep `check --no-receipt` accepted as a compatibility no-op.
- Remove disabled-feature and unavailable-capability snapshot/restore receipts.
  Keep truthful notices and the existing explicitly invoked machine-report
  behavior. A missing receipts directory must not make these outcomes fail.
- Keep changed `init` and `profile-apply` history. Init already distinguishes
  changed deployments. Profile apply must emit history only for actual changes
  to profile bytes, overlays or seeded records; skipped seeds are not changes.
- Keep actual credential-redaction, snapshot, restore and backup-export evidence
  with all existing exact publication, final validation and compensation.
  Unchanged managed snapshots already produce no new record. Existing durable
  lifecycle records, Library registrations/cards, task flags and learned Skill
  ownership are product state, not disposable receipts.

Saving-task recall must stop persisting queries and evidence paths. A query that
would have been redacted in a retired log does not need a replacement log.
Credential-redacting mutations retain their existing obligation. No-save guards,
scoped Library/snapshot exceptions and metadata-only necessary receipts remain
unchanged. R9 card/offer operations add no routine event.

## Profile no-op correctness

Current `plan_overlay` can include same-byte policy writes, and `_apply_changes`
replaces every planned write. Do not infer change merely from plan length.
Compare actual safe preimages and avoid same-byte replacements, retaining exact
unchanged-file/root proofs through the existing final validation. Do not return
early before checking stale plans or bypass credential handling. Compute the
history condition from byte changes, actual removals and new seeds. Freeze one
exact file preimage set before receipt publication, including unchanged profile
and overlays plus removal targets; reuse it through apply and final validation.
A competing same-byte inode or callback edit must not become a new baseline. Redaction
findings remain meaningful even when sanitized candidate bytes equal existing
state. An ordinary repeat apply with no findings must preserve the whole tree.

## Actionable maintenance

Check remains read-only and must work when receipts cannot be written. Preserve
finding codes and bounded paths; improve generic hints with the missing field,
record kind or a concrete supported repair command. Use safe schema field/rule
descriptions, never raw validator strings containing rejected values; test a
synthetic credential-like rejected value for non-echo. Never advise creating an
empty invalid file. Use `apparatus init WORKSPACE` for shipped-content repair,
preserving custom conflicts; do not promise reconstruction of lost user records.

Doctor should distinguish detecting Git from proving a usable recovery store.
Give conditional next actions: make the missing tool available to the AI app,
rerun doctor, run `apparatus check WORKSPACE`, or list known points with
`apparatus restore WORKSPACE --list`. Keep current capability/report keys and
exit semantics unless a tested wording correction requires otherwise. Existing
sync warnings should suggest an explicit supported move/rebind, never perform it.

Library diagnostics distinguish an intentionally ignored source from a missing
original or invalid registration. Preserve PR-43's current-source/partial
coverage and PR-44 card boundaries. Learned Skill repair hints may suggest
inspecting/restoring the named registered pair; do not invent a repair verb or
silently adopt replacement instructions.

## Scope, migration and acceptance

Owned paths: receipt-producing command modules for check, Library, recall,
init, profile, snapshot and restore; recall/ingest producers; check/doctor and
machine-report wording; corresponding specs, IT onepager and starter guidance;
focused tests and exact-stock migration witnesses. Keep shared filesystem,
receipt, retention, snapshot and backup transaction machinery unchanged unless
an independently demonstrated defect requires a separate repair.

Replace the starter's blanket receipt instruction with this policy. Capture
exact final PR-44 stock bytes before editing guidance; preserve all custom text,
historical five/seven-Skill evidence, learned fallback, cards, preferences and
task controls. Regenerate shims/goldens and synchronize the embedded payload.
Do not rewrite old plans or historical fixtures to pretend the policy always
existed. Update current receipt/ignore/retention/recovery/IT descriptions.

Acceptance requires no publication for ordinary check/recall/ingest, feature-off
and unavailable operations, including an unwritable receipts destination;
correct outputs and all prior history unchanged; whole-tree equality for true
profile no-op; stale no-op rejection; and preserved late-failure compensation
for meaningful profile/redaction/recovery writes. Adapt fault fixtures to perform
an actual changed operation when they test a required receipt failure. Prove a
synthetic repair → check → snapshot/restore sequence retains sufficient history
without routine check logs. Preserve source freshness, no-save, original-file
exclusion and card/learned ownership tests. Run full pytest, payload/package
parity, independent review and actual Windows safety CI before acceptance.
