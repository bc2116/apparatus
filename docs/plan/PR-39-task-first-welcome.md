# PR-39: Task-first welcome and everyday work

R5 implementation contract grounded in PR-38, ADR-0006 sections 5/9/10, the design brief sections 2/4/5, and `rework-sequence.md` R5. Integrate the verified merged PR-38 dependency before final delivery. Approved product choices require no new product interview.

## Small cut and dependency

Ship the task-first behavior as one portable payload/core-compatibility slice after R4a/PR38. Native discovery adapters are unnecessary: the existing canon index and direct reading of the five canonical `SKILL.md` files supply the complete required path. Claim tested files/commands and guidance behavior, not certified invocation by Codex, Claude, or Cursor.

Keep current command names, profile schema, task controls, work-area/project routing, recovery format, and five Skill names. Add no onboarding engine, model calls, scheduler, new setup command, native adapter, or learned-Skill capture. Library registration/cards and broad receipt-system reduction remain their later slices.

## Required behavior

1. Welcome starts from the user's actual request, selected project, and relevant existing context. If no task was supplied, ask what they want to accomplish. Otherwise ask only for information that prevents useful or correct work: for example a genuinely ambiguous destination, absent required source, or consequential unstated requirement. Do not re-ask facts already supplied. Use reversible reasonable assumptions for nonessential choices and proceed.
2. Remove the fixed questions, feature menu, setup-summary confirmation, configured-profile prerequisite, and automatic collection of People, efforts, source locations, review day, or spend preferences. Neither fresh `unconfigured` nor legacy `configured` status blocks work. Optional preferences may be changed when relevant or requested; completing work never depends on them.
3. Produce the requested work in its project, check against the request, fix correctable omissions, save, and report the file and material limitations. No mandatory agreement before drafting, acceptance before saving, or direction before routine corrections. Preserve explicit user review constraints and native authorization for actual external actions. A requested review alone does not authorize editing its subject.
4. Research uses relevant available sources, accurate nearby citations and honest uncertainty. Distinguish no match, unavailable retrieval, and unsupported claims. Choose the task's useful format; no mandatory facts/uncertainty/recommendations headings or durable research-notes file. Ask about missing evidence only when needed.
5. Checklist and weekly Skills run only when requested. A stored `review_day` is a preference for an explicitly requested review, never a schedule or trigger. Ask only for absent review essentials; preserve evidence-based goal completion and report incomplete coverage.
6. Use existing task enrollment/resumption and no-save controls without asking an extra per-task approval question. No-save permits the requested project deliverable but suppresses automatic profile answers, Memory/goal continuity records, activity notes, learned Skills, Library offers/cards and automatic snapshots. Separate requested exceptions remain limited to existing API scope; never turn one into permission for Memory. Existing correction/outdated/forgotten semantics and tombstone suppression remain binding.
7. Follow existing snapshot feature and task decisions at a meaningful completion boundary; report managed-state coverage truthfully. The command owns its receipt. Remove Skill directions to manufacture a second snapshot receipt or claim project-file recovery. Do not redesign core receipt events in R5. Credential redaction and source-as-data rules remain unchanged.

## Defaults and preference compatibility

Retain `balanced` spend and the three existing default-on features (`library_indexing`, `snapshots`, `ignore_rules`). Respect every existing explicit false/selection. Missing optional feature mappings already mean on; do not rewrite a valid profile merely to materialize defaults. Preserve `privacy_mode` compatibility and private-profile task defaults; introduce no replacement global privacy selector. Keep both profile statuses accepted, describing them as legacy setup metadata rather than a completion gate.

Retain `profile apply --stdin` for explicit preference changes and legacy import. The assistant reads existing valid configuration, merges only requested changes in memory, preserves other fields, and uses the existing credential-safe transactional write; no durable answer scratch file. Both schema-valid profile statuses must be accepted: a fresh user's one requested preference change succeeds without inventing setup answers or marking setup complete. Remove only the configured-status prerequisite, preserving schema validation, credential handling, task retention and absent-only seed behavior. Test that single-preference path with unchanged status and unrelated fields. `interview.py` remains a compatibility helper for redaction/seeding; update misleading descriptions without changing its APIs. Do not silently reseed forgotten records or rewrite user records.

Add a small editable shipped `System/ignore` starter list: `node_modules/`, `.venv/`, `__pycache__/`, `.pytest_cache/`. Existing immutable OS/Git exclusions remain. These patterns govern existing Apparatus machinery only, not native app access or credential detection. Preserve custom ignore bytes and explicit `ignore_rules: false`; do not expand to broad output/source exclusions. Update the ignore spec deliberately.

## Paths and migration

Payload: `starter/payload/.agents/skills/apparatus-*/SKILL.md`, `Welcome.md`, `AGENTS.md` if routing text needs adjustment, `System/profile.yaml`, `System/README.md`, `System/ignore`, and `starter/profiles/README.md`; synchronize embedded starter and goldens. Include exact-stock Welcome.md migration and a conformance assertion that human-facing orientation no longer directs users into a setup questionnaire. Keep shipped `profiles.yaml` mapping/default semantics: all five workflows are already available without a feature interview.

Core: narrowly update descriptions in `interview.py` and `commands/profile.py`; touch init/profile/default logic only if acceptance reveals a real barrier. Extend existing `instruction_updates.py`/overlay migration for exact PR38 stock bodies and stock ignore/orientation bytes. Current overlay preserves any valid differing native Skill, so replacing payload alone will not migrate the old welcome. Recognize exact reviewed prior bytes (including deliberate LF/CRLF handling); preserve valid custom Skills/canon, custom legacy procedures and unknown files. Keep old profile fields/records and legacy pointer stubs valid. Use existing preimage-bound deployment/rollback, not header-based ownership or a new publication framework. Repeated migration must be a no-op.

## Acceptance

- Fresh actual request yields checked, saved project output before optional setup, with no `profile apply` required; no questionnaire or unrequested review.
- Existing explicit preferences/profile bytes, custom Skills and dirty project Git state survive repair/migration; exact stock PR38 Skills upgrade and repeat without churn.
- Saving and no-save task stories cover real commands and persisted artifacts; no-save creates no task-content retention, while requested deliverable creation succeeds.
- Optional explicit profile change preserves unrelated preferences and existing/tombstoned records; credential floor, unsafe-path and rollback tests remain.
- Research fixtures retain supporting citations with a task-chosen format; checklist/weekly trigger assertions reject automatic invocation.
- Ignore fixtures prove generated dependency/cache paths excluded, ordinary sources retained, custom rules preserved and feature-off honored.
- Revise `conformance/test_welcome_e2e.py`, payload assertions, `test_interview_profiles.py`, `test_feature_selection.py`, ignore and migration tests deliberately. Preserve substantive source/credential/recovery evidence; subprocess orchestration proves persistence, not live assistant behavior. Run focused suites and full `uv run pytest`.

## Delivery and ownership

Use this focused PR branch, original product prose, DCO sign-off, independent
review and required actual Windows CI. Keep payload copies synchronized and
include the landed status row in the same PR. Do not claim live app certification.
The lead coordinates integration; the author owns this cut's payload, migration,
narrow profile adjustment, tests and docs. Other contributors are active: preserve
their work, make no unrelated edits and do not start further agents.
