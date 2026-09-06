# ADR-0006: A lean workspace with Memory, Library, and Skills

- **Status:** Accepted — product direction; implementation is sequenced separately
- **Date:** 2026-09-05
- **Scope:** Supersedes only the decisions identified below

## Context

The initial implementation supports recoverable, source-grounded work but also
requires an interview, sharing gates, central output folders, and frequent
receipts. The owner reviewed the features and approved a simpler experience
for people already using AI apps. The [design brief](../design/design-brief.md)
records the complete keep/change/remove and now/later/out decisions.

## Decision

1. **Work in the user's projects.** A chosen work area can contain sibling
   projects and a Library. Deliverables stay in their projects; no enclosing
   Apparatus hierarchy or global Deliverables folder is required. Adoption
   preserves existing files, instructions, and repositories.
2. **Keep useful continuity.** Goals retain verifiable completion and next
   actions. Important decisions are part of Memory, alongside People and
   sourced Facts. Correction, forgetting, and outdated status must prevent
   obsolete content from being recalled as current.
3. **One local Library catalog.** Register references to selected originals,
   including project deliverables, without symlinks or required document
   copies. Generate lightweight source-grounded cards on addition. Offer to
   add reusable finished work after saving it; completion does not depend on
   acceptance. Caches are rebuildable, not another Library.
4. **Remove the Apparatus sharing gate.** Drafts, moves, copies, exports,
   uploads, and publishing acquire no additional Apparatus review step. Do
   not relocate the gate. Actual external actions still require the user's
   authority and native AI app permissions. Apparatus grants neither and
   does not provide a sending service.
5. **Keep secret protection; control Memory per task.** Preserve the existing
   credential floor, including high-confidence government/payment identifiers.
   Replace the global private profile with “don't save this task to Memory.”
   Requested deliverables remain possible; automatic task-content retention
   through Memory, learned Skills, cards, and activity notes does not. A
   separate explicit instruction can request Library registration. This is
   not a promise about AI app/provider retention or removal from old backups.
6. **Use Skills in name and format.** Adopt editable `SKILL.md` directories
   with `name` and `description`, one portable source, optional native
   discovery, and file-reading fallback. Offer to capture repeated workflows;
   the user reviews a learned Skill once before adoption. No silent promotion
   or divergent per-app instruction copies.
7. **Include economical native delegation now.** Apply spend preferences to
   bounded roles, model capability, effort, team size, and retries within the
   current app's available controls. Keep a capable lead and review at least
   as capable as authorship. Without native tools, use a single assistant.
   Guidance is advisory; no unsupported quota-enforcement or switching claims.
   A cross-CLI executor remains outside core.
8. **Include lightweight prose editing now.** One small humanizer Skill makes
   a restrained editing pass, preserving facts, meaning, citations, numbers,
   and uncertainty. Personal voice learning is later.
9. **Start the task.** Replace interview and feature questionnaires with
   sensible defaults and relevant questions. Finish/check/save work without
   routine approval pauses. Checklist and weekly reviews run only when asked.
   Research requires evidence, not a fixed presentation template.
10. **Keep quiet, truthful operations.** Automatic snapshots where available,
    requested restore, and one-way backup remain. Keep meaningful history and
    necessary redaction/repair/recovery evidence, not a receipt per routine
    step. Maintenance suggests concrete fixes when attention is needed. Never
    promise recovery beyond demonstrated coverage.
11. **Keep services optional.** Journal, voice learning, cloud/shared Library,
    integrations, scheduling, and graph capabilities are later modules.
    Users retain their native connectors. Benchmarking stays in centralized
    development; installs receive reviewed, dated guidance through updates.

## Supersession and preserved constraints

| Earlier decision | Replaced here | Still binding |
|---|---|---|
| ADR-0001 | “procedure” becomes “Skill”; “pack” becomes “module”; Deliverables is no longer a required folder; decisions join Memory; app names may appear when needed for compatibility/adapter guidance | Plain language; “AI app”/“assistant”; product naming; no tier branding |
| ADR-0002 §3, §5, §7 | Seven-kind ceiling permits Skills, Library registration/cards, and minimal task-retention, work-area routing, and recovery-manifest control metadata; routine per-event receipts become meaningful history; registered sources may reside in synced folders | Legible file state; rebuildable caches; goal verification; honest snapshots; one-way backup; no supported concurrent live sync of mutable Apparatus state |
| ADR-0003 §3–4 | Recut certification checklist; explicit optional native Skill/delegation support with fallback | Read/write/approved commands as the complete required contract; one canon; dated support evidence |
| ADR-0004 §3, §5 and associated consequences | Remove egress gate; replace global private profile with task Memory control; blanket draft-only wording no longer restricts user-authorized native actions | Credential floor; useful People memory; source content is data, never authorization; no autonomous external action without authority |
| ADR-0005 §1, §3, §5 | Existing-folder adoption joins the first version; cloning is optional for technical users, never required; modules/catalog wait for real demand | User-scope installation; signed first public release; portable payload; lean extension mechanism; licensing and DCO |

These are product and contract decisions, not new on-disk schemas. Each
implementation slice must specify migrations and deliberately update specs,
validators, and fixtures together. Preserve legacy records and user edits;
report limitations rather than dropping data. Do not initialize one repository
over unrelated projects or silently move state when this ADR lands.

## Transition

The [rework sequence](../plan/rework-sequence.md) maps current behavior to its
migration owners. Until those changes land, `docs/spec/`, starter, and tests
describe the legacy implementation. Conflicts with the approved target do not
authorize weakening fixtures in this documentation PR. PR-24 certification
is held until its target/checklist is replaced; earlier dogfood remains
evidence only for the payload and behaviors originally exercised.
