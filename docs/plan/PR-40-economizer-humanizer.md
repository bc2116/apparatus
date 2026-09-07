# PR-40 — Economizer and humanizer Skills

Implementation contract for R6 on branch `pr-40-economizer-humanizer`, after PR-39 and its PR-38 dependency. Governing sources are ADR-0006 sections 5–10, design brief sections 4–5, the R6 rework sequence, and the current Skill, task-retention, recovery and model-guidance specifications. Preserve PR-39 task-first instructions and preference behavior throughout this cut. No native adapter certification is implied.

## Result and scope

Add two portable built-ins, with one editable instruction body each:

- `.agents/skills/apparatus-economizer/SKILL.md`
- `.agents/skills/apparatus-humanizer/SKILL.md`

The existing five names remain unchanged. Keep the standard Skill validator, direct file-reading fallback and work-area/project binding. Add two concise entries to the shipped canon index. Economy guidance applies when planning work that could benefit from native delegation or model/effort selection; it must not make a simple task acquire a planning ceremony. Humanizer applies to user-requested prose editing and a light final prose pass on an authorized deliverable. A review-only request does not authorize editing its source.

No new CLI, external executor, API call, model launcher, quota monitor, scheduling, personal voice profile, learned-Skill capture, automatic benchmark, router service or generalized evaluation framework. Native tools remain optional. Product artifacts use original prose and synthetic examples; they contain no private repository names, private excerpts or private evaluation data.

## Economy behavior

Read the existing spend preference when relevant, defaulting to `balanced`; preserve the stored value. User instructions and available native controls bound every action. Inspect the current app's exposed models, supported effort controls and team limits before choosing a configuration. Never infer that a requested setting was applied, that a capability tier is identical across vendors, or that an unavailable control can be emulated by prose. If no suitable native control or delegation mechanism exists, the current assistant works directly and states any material limitation.

Keep model capability, reasoning effort and team size as separate choices. Retain the existing portable capability vocabulary (`frontier`, `strong`, `fast`) and `low`/`medium`/`high` advisory effort vocabulary; these are relative descriptions, not certifications of named models. Stable Skill instructions contain no vendor inventory, prices or model IDs.

The capable lead owns scope, source selection, decomposition, conflict resolution, synthesis and acceptance. A reviewer receives the task requirements, relevant evidence and resulting artifact or diff. Review must be at least as capable as authorship; the lead must be capable of evaluating every delegated result. If the available controls cannot establish those conditions, keep the work at the capable lead. Do not weaken review to save spend.

Delegate only a bounded subtask with named inputs, a deliverable, scope/ownership and a concrete check. Prefer direct work when another assistant would repeat discovery or cost more coordination than it saves. A fast worker is limited to mechanical work whose entire output can be checked. Interpretation with incomplete evidence, unresolved design, safety/privacy policy, authority, migrations, deletion/recovery and active instruction changes stay with capable authorship and equally capable review. These capability restrictions add no new user approval gate.

Use this small advisory resource ceiling unless the user has supplied another limit:

| Spend | Starting approach | Maximum simultaneous delegated assistants, excluding lead |
|---|---|---|
| frugal | Lead does substantive work; delegate only a clearly worthwhile mechanical part. | 1 |
| balanced | Lead plus one bounded independent worker when useful; review may run sequentially. | 1 |
| thorough | Strengthen verification first; use a second independent worker only when useful. | 2 |

These are ceilings, not quotas or required team sizes. Workers do not start additional teams. Native limits and user limits may reduce them. Existing model-guidance starting capability/effort choices remain the default; consequential work can require capable authorship irrespective of spend. Never claim savings merely because a cheaper model was selected.

Before a delegated attempt, specify its completion check and the task's repair allowance. Use at most two repair passes for the same bounded deliverable unless the user explicitly supplies a different budget; a stricter existing task limit wins. Every delegated authoring repair attempt consumes this allowance, including escalation or reassignment. Deterministic verification runs do not consume delegated repair passes. Exhaustion stops new delegation, while the capable lead may finish already-authorized work within the remaining user budget; it does not add an approval gate. On failure, first distinguish an unclear requirement, a tool/platform constraint, an implementation defect and a demonstrated capability shortfall. Resolve the actual cause. Elapsed time alone is not evidence of inadequate model capability. A repeated capability failure may justify a stronger author or effort setting and equally capable review; this never creates a new retry allowance.

Stop new delegation when the requested task is complete, the repair allowance is exhausted, or an explicit spend/time/quota limit is reached using information actually available. Preserve authorized work and report the specific remaining blocker and useful next action. Unknown token or monetary consumption is unknown, not zero and not an enforced budget. Do not poll for nonexistent telemetry, invent a universal quota threshold, or start background monitoring. A material routing limitation may be stated in the ordinary result; do not create an economy receipt or task-content log.

## Humanizer behavior

Scale the pass to the document and request. For a short answer, fix only obvious repetition or awkwardness. For a longer deliverable, inspect clarity and organization where useful without automatically rewriting every paragraph. Use the supplied purpose, audience and constraints; ask only when missing information prevents a safe useful edit.

Make one selective editing pass. Prefer concrete wording, remove empty emphasis and redundant framing, and vary structure only when comprehension improves. Preserve useful technical language and the document's appropriate tone. Do not enforce a universal word blacklist, manufacture conversational quirks, infer authorship, promise detector avoidance or learn a personal voice.

Compare the edited passages with the original. Preserve facts, numerical values and units, citations and their claim relationships, exact quotations, identifiers, code/commands, negation, conditions, warnings and uncertainty. Source-document instructions remain data. Do not silently repair disputed facts or strengthen claims. If an edit changes meaning or cannot be checked safely, restore that passage; at most one local corrective pass is permitted. Already-good prose stays unchanged. This adds no new approval before saving an already-authorized deliverable or native permission to send it.

No extra draft archive, diagnostic report, before/after receipt or permanent scratch file is required. A brief explanation is useful only for a material limitation or an explicitly requested review. Requested output may be saved in the project; the task's no-save choice still governs derived retention.

## Guidance data and compatibility

Keep `System/guidance/model-guidance.md` as the existing centrally maintained, dated and replaceable guidance surface. The economizer Skill owns the operational instructions; the guidance file supplies the compact starting capability/effort table, review date and availability caveats, avoiding a second editable workflow body. Update `docs/spec/model-guidance.md` deliberately where prior rules conflict with the bounded failure/repair policy above, including its routine receipt requirement.

Do not ship fictional names as selectable models. A roster may be absent; that is a supported state. Any future concrete roster must be separately dated, identify its applicable app/version evidence and remain subordinate to live available controls. Retain the current 90-day stale-data warning, without treating freshness as proof of availability or execution. Updates arrive through reviewed release/pull/clone distribution; installs neither benchmark nor self-calibrate. This slice does not populate a live model inventory or claim measured efficacy.

Do not change profile fields, statuses, defaults, explicit feature selections or privacy compatibility. Preserve R5 preference behavior. A no-save task can read these Skills and install generic shipped guidance, but must not save routing transcripts, task-derived Skills, style profiles, Memory, cards or automatic snapshots. Requested project prose remains possible. Existing task enrollment, credential floor, metadata-only operational evidence and separately requested exceptions remain unchanged.

## Exact migration from five to seven

Separate the five historical procedure-to-Skill mappings from the canonical built-in name/path set. Keep those five legacy paths and exact pointer bytes valid; never invent old procedure paths or compatibility stubs for the two new names. Use explicit constants for the supported five-file and seven-file sets, not recursive ownership or a new installation-state service.

Fresh payloads contain exactly seven canonical bodies. Complete historical five-Skill payloads with their compatible manifests remain usable; a source with either new built-in directory/body or known seven-Skill index/orientation evidence must contain all seven valid files. Reject partial or mixed source sets before writes. Target work areas with older five-Skill evidence remain readable and receive an actionable upgrade hint for missing new built-ins. Retain historical index/orientation witnesses so deleting bodies cannot hide an installation. Unknown native Skills alone imply no Apparatus enrollment.

Init upgrades exact recognized shipped canon/index, guidance and orientation bytes through the existing deployment transaction and creates missing new Skills. Preserve valid custom canonical bodies, custom guidance/canon, profile bytes, unrelated Skills/resources and project Git state. Invalid or foreign occupants at either new canonical path are preflight collisions. Retain exact byte/absence preimages and root/layout checks through final acceptance, with existing compensation preserving concurrent content. Review LF/CRLF stock witnesses deliberately. A repeated upgrade is a no-op. Do not overwrite a customized five-Skill file merely to add two new capabilities.

Extend overlays and check to the exact seven paths, retaining legacy manifest support and deselection protection for valid custom bodies. Extend managed capture, manifest membership and historical-tree validation together. Historical five-Skill and procedure snapshots remain readable; restore preserves later additions. New snapshots/backups cover the seven named bodies and existing guidance path, never third-party Skills or resources. An older restore followed by check and init must safely reconcile known stock instructions without replacing customized bodies.

## Lean implementation paths and acceptance

Own source and embedded copies of the two new Skills, canon/index and model guidance; update `skills.py`, narrow instruction migration, overlays/check/recovery membership, normative Skill/model/recovery specs, goldens and focused tests as required. Keep changes to the existing five workflow bodies limited to integration needs and retain R5 behavior. Explicitly track hidden payload files in Git and verify wheel/archive inclusion.

Required evidence:

- Seven-file fresh init and repeat; five-to-seven upgrade; legacy manifest/pointer compatibility; stock LF/CRLF migration; custom body/guidance preservation; missing/invalid new source or destination; stale byte/absence preimages and late rollback preserving competitors.
- Missing-new-body diagnostics with old and current index/orientation evidence, unknown Skills excluded, no writes during check, and declared seven-path recovery/backup with a historical restore/remigration round trip.
- Saving/no-save command stories preserve task/profile controls and create no automatic content retention or extra receipts during generic guidance installation.
- Small synthetic economy scenarios: simple direct work, a mechanical bounded worker, judgment requiring capable lead, a stronger author requiring matched review, absent controls, a platform failure, an ambiguous requirement, and an exhausted repair/user budget. Check the actual guidance against expected decisions; do not pretend a static fixture proves native execution or savings.
- Small synthetic prose examples: short explanation, long technical instructions, factual summary with citations/numbers/uncertainty, instruction bait inside source text, and an already-good negative control. Check protected content and independently review meaning/usefulness; literal equality checks alone cannot establish semantic preservation.
- Any live development comparison is centrally reviewed and dated, uses only synthetic or approved public content and already-authorized native tools, and is reported separately from static/conformance evidence. This planning contract authorizes no API spending. Missing live evidence remains explicit; no per-install trials or generalized quality claims.
- Focused tests, full `uv run pytest`, payload/package validation and actual Windows CI before delivery. Independent review checks migration and policy at capable authorship level. No R4 native certification, automatic budget enforcement or guaranteed prose-quality claim.
