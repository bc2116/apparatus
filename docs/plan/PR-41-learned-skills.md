# PR-41 — Capture a learned Skill after review

Implementation contract on `pr-41-learned-skills`, grounded in ADR-0006 §6, design brief §5, rework-sequence R7, and current PR39 Skill/retention/recovery code. This focused cut may be authored on PR-39, then must integrate PR-40 before final review, validation and merge. No further product-choice interview is needed.

## Scope and dependency

After useful repetition, the current assistant may offer to turn the reusable workflow into an editable draft. It contains instructions for doing work, not a transcript, factual Memory dump, or copied source authority. The user reviews the concrete draft once before adoption. Declining or ignoring the offer never blocks the original task. No silent promotion, automatic canon rewriting, per-use approval, evaluation service, or model runner.

R4a's portable format and file-reading fallback are sufficient. R6's economy/humanizer additions may land first or independently; native adapters and R8 Library registration are unnecessary dependencies.

## Small file model

Use a validated portable Skill name prefixed `learned-`, within the existing 64-character limit. Never overwrite a built-in or existing native Skill merely because its name looks familiar.

- Draft: `System/skill-drafts/NAME.md`, containing standard `name`/`description` frontmatter and an editable instruction body. This location is outside native Skill discovery. Drafts are excluded from automatic managed snapshots and backup coverage in this cut; report that limit. Existing exports of unrelated legacy whole workspaces are not retroactively sanitized.
- Adopted body: `.agents/skills/NAME/SKILL.md`, one canonical regular-file body. Initially support that file only, with no scripts, assets or reference-file copying.
- Adoption ownership: `System/skills/adopted/NAME.yaml`, a small closed control record: `schema: apparatus/learned-skill@v0` and `name: NAME`. The path to the body is derived, never an arbitrary path supplied in metadata. Reject duplicate keys, aliases/unsafe structure, invalid names and filename disagreement.

Use one ownership record per Skill rather than a mutable shared catalog. Existing recovery preserves later file additions: an old snapshot can restore an earlier adopted Skill without deleting ownership records for Skills adopted afterward. This avoids a restored shared catalog silently hiding newer adoptions. The record establishes managed coverage and fallback listing; it grants no native action authority.

Leave all existing third-party Skills and drafts untouched. Prefixes, directory presence and frontmatter alone do not establish recovery ownership. Reading a draft for review does not authorize using it as instructions.

## Two commands, one review

Proposed minimal command surface:

1. `apparatus --task ID skill draft WORKSPACE NAME --stdin`: require a saving task before reading candidate text or creating directories. Redact with the existing credential floor, validate the resulting portable Skill, and create the draft without replacing an occupant. Return its path and SHA-256 of the exact stored bytes. The assistant shows that actual sanitized draft for review. The command does not generate the workflow.
2. `apparatus --task ID skill adopt WORKSPACE NAME --digest SHA256`: use only after the user's explicit adoption instruction for the reviewed draft. The digest binds adoption to those exact bytes; a changed draft fails unchanged and must be reviewed again. Validate/redact-check the draft without changing the reviewed bytes. If further redaction would be needed, reject adoption and return to draft review; never sanitize into unreviewed bytes. Ensure neither destination is occupied, then publish body and ownership record as one retained-root transaction with exact compensation through its final checkpoint. Do not modify `AGENTS.md` or other native Skills.

A repeat adoption is a no-op only when both registered destination and draft still match the reviewed bytes; all partial/colliding states fail with an actionable preservation message. Do not add force overwrite or a promotion-policy engine. Leave the draft as an inactive review copy after successful adoption; it is not another active body. A user may delete a rejected/inactive draft explicitly with ordinary file tools. Once adopted, the user may edit its body normally; no immutable adoption hash prevents future edits or demands approval on each use. Replacing an adopted workflow with a materially new generated workflow still needs a new concrete review, rather than silently editing it through this capture path.

The shipped canon points once to `System/skills/adopted/`: read those small records and the referenced Skill descriptions to find relevant learned workflows, then open only relevant bodies. Unreviewed drafts are never in this fallback inventory. Future native discovery consumes the same canonical files; no new adapters are required here.

## Retention, checking and recovery

New learned capture requires an enrolled work area before input is read. Missing enrollment returns the existing `apparatus init WORKSPACE --adopt` repair action, with no new setup question. This makes draft exclusion enforceable; legacy read/use and whole-workspace recovery remain unchanged and may contain historical drafts.

Both commands use `operation(...)` and `require_memory_write()` before candidate persistence; no-save has no learned-Skill exception, even when snapshot or Library exceptions were requested. Do not offer capture or store draft text during a no-save task. Existing adopted Skills remain readable. Content already saved in earlier tasks/backups is not erased by a later opt-out.

Reuse credential handling, retained parent proofs, absent-only publication, exact-byte/identity validation and receipt compensation. Neither command creates a routine adoption receipt: its result and the durable adoption record provide the small lifecycle proof. Existing redaction evidence remains mandatory when credentials are removed, with its exact compensation retained through the final checkpoint. Add no new receipt event or task-prose audit log.

Extend check and recovery with the same closed adoption-record parser. Capture only registered exact bodies and their matching records; never scan/capture all `.agents/skills`. Validate each pair during live capture and from the files in each historical manifest, independently of current registration. Missing/malformed registered bodies fail truthfully. Unknown files remain outside managed coverage. Restore and export retain the existing manifest boundaries, rollback and reachable-history proofs. Restoring an older adopted body may revive older workflow instructions; requested restore is the existing authority, not a fresh capture review. Live task controls remain excluded from restore.

## Source ownership and acceptance

Likely paths: new `commands/skill.py` and a small learned-Skill helper; shared `skills.py`, `check.py`, `managed_state_recovery.py`, CLI registration, record/workspace/Skill specs, canon and embedded payload; focused command, retention, migration and real-Git recovery/export tests. Reuse existing mechanisms rather than refactoring them.

Accept with a synthetic repeated workflow: exact sanitized draft remains inactive; explicit digest-bound adoption exposes one body through fallback; rejection and stale digest cannot activate; repeated adoption is safe; occupied/custom paths survive; concurrent edits and late publication/receipt failures preserve competitors and roll back only owned files. Prove no-save guards before input reads and filesystem writes, credential handling, unsafe/duplicate control rejection, editable adopted bodies, missing-body diagnostics, and snapshot/export/restore round-trip including a later adoption surviving an older restore. Run focused and full suites plus actual Windows proof checks. Describe subprocess tests as persistence evidence, not live-app invocation certification.

R6 overlap is confined to the built-in registry/index, payload synchronization, source-completeness rules and recovery allowlist. Do not hardcode five or seven in learned-Skill logic: built-ins remain their explicit registry; learned ownership is separate. R8 changes selected source registration/search, not this workflow store; learned capture must not register Library files or create cards.
