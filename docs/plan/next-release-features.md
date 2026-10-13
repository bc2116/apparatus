# Next release: useful document work

- **Status:** Autonomous execution authorized on 2026-10-12; Completed through PR-70 and PR-71; release preparation remains separate.
- **Planning/review date:** 2026-10-12.
- **Source baseline:** `1eee87a` on `main`, through landed PR-69.
- **Owner direction:** Defer further email testing, assess other useful additions,
  and consult the designated development workspace for developed ideas.
- **Size:** Two focused PRs by default; four maximum including decisions, splits,
  repairs and conditional delivery. A smaller release can take only the core
  acceptance slice. Release preparation remains its separate existing process.

## A1 outcome and retained scope

The [completed comparison](../certification/document-review-comparison-2026-10-12.md)
found all material issues in every arm. Specialized guidance improved formatting
but did not establish a material advantage over current Skills. The lead selects
**stop at existing Skills** under the delegated placement authority: omit A2,
keep B deferred, and complete C in [PR-71](PR-71-final-core-acceptance.md).
The [core readiness record](../certification/core-readiness-2026-10-12.md) captures
the retained source-build checks and explicit delivery/publication boundaries. No new module, active Skill or checklist
product is added. The sections below preserve the accepted experiment and
conditional scope so the result can be assessed against its original criteria.

## Recommendation and changed priority

Run an **Evidence Review comparison** before choosing a product form. Test whether
an existing draft can be checked effectively using current Skills, a reusable
checklist, or specialized review guidance. A second module is not the default.
Keep **Library relinking deferred by default**, reopening it only for an actual
moved-source need or a recorded owner priority decision. Meeting notes and
personal voice remain later candidates.

This is source-grounded prioritization, not measured customer demand. Evaluation
material is not a delivered feature. The completed core improvements can proceed
to release preparation independently if the comparison produces no useful addition.

| Previously next | Revised position | Reason |
|---|---|---|
| Real-message pilot and further email usability testing | Deferred beyond this release cycle; no new date | Owner reprioritization; core release does not depend on mailbox qualification. |
| More Mailbox Survey lifecycle/integration work | Deferred unless a reproduced defect affects a retained release surface | Update/removal need separate contracts; create-only deployment already exists. |
| Other additions | Compare three ways to review a document, then choose at most one delivery option | Prove useful differentiation before adding a module. |
| Core readiness | Required for the final retained candidate, even if every feature is dropped | Earlier source-build evidence does not qualify later changes automatically. |

Preserve existing Mailbox Survey regression tests and dated synthetic evidence.
Do not launch new live-mail, connector or supplied-message test campaigns in this
cycle. Synthetic success remains separate from live-mail qualification. The
[module sequence](module-sequence.md) preserves its lifecycle limits.

## Reference-workspace review

Before selecting a feature or cutting its prompt, review the owner's designated
development workspace for working implementations, evaluations and failure cases.
Repeat this targeted step at future planning boundaries; an earlier proposal or
remembered feature list is not enough.

For each candidate, distinguish implementation evidence, operational guidance,
uncompleted evaluation and proposed work. Assess user benefit, overlap with
Apparatus, the smallest portable adaptation, placement and acceptance checks.
Keep private source mappings in the working discussion or outside this repository.

The initial targeted comparison was completed on 2026-10-12. It found implemented
coverage/provenance checks with a bounded pilot, claim-evidence validation tests,
and operational guidance on Skill overlap. Comparative review-quality evidence
was incomplete. These findings strengthen the experiment below; they do not
establish demand for a module or relink. Adapt the hidden-oracle/control method
and per-claim coverage, not the source systems' domain machinery or retention policy.

Future replacement candidates require the same bounded value comparison and a
recorded owner scope/placement decision within the four-PR ceiling. Reference
discovery does not add another workstream. Apparatus's accepted decisions remain
authoritative. Develop original code and prose; do not copy implementations,
private references, personal state or deployment-specific machinery, or create a
runtime dependency on the reference workspace. Preserve ordinary-file fallback.

## A1 — Compare Evidence Review approaches

**User request:** “Check this draft against these sources and show me what needs
correction.” The requested report connects each identified claim to its draft
location, source passage/version when available, uncertainty and disposition:
`supported`, `contradicted`, `insufficient`, or `not reviewed`. Conflicting sources
and omissions remain visible. These are report fields, not a new core record
schema. Do not edit the draft unless the request includes revision.

The [research Skill](../../starter/payload/.agents/skills/apparatus-research-and-summarize/SKILL.md)
already grounds findings in sources; the
[deliverable Skill](../../starter/payload/.agents/skills/apparatus-produce-deliverable/SKILL.md)
already cites evidence and admits gaps; the
[checklist Skill](../../starter/payload/.agents/skills/apparatus-review-against-checklist/SKILL.md)
already reviews supplied criteria. The hypothesis is that repeatable claim-by-claim
review improves coverage or reduces prompting. It is not a claim that current
Apparatus cannot cite or check work.

### Scope and comparison

Keep experimental guidance inactive, outside core payload, active Skill directories
and distributable packages. A1 produces synthetic evaluation material and a results
note, not a module. Use short, readable text/Markdown drafts and explicitly supplied
source files. This comparison does not qualify Library-registered-source retrieval,
PDF parsing or native discovery. Reuse available readers; build no parser, model
client, connector or validation platform.

Before drafting specialized guidance, freeze three cases and their expected findings:

1. A quantitative claim that overstates its source.
2. Conflicting or explicitly superseded sources. Dates/notes must establish any
   supersession; otherwise unresolved conflict or unknown freshness is correct.
3. A clean control with no material defects.

A separate oracle enumerates material claims and actual supporting/conflicting
passages. Keep it outside executor-visible inputs and tool-access roots, not
merely in a separate file beside the fixtures. If that isolation cannot be
enforced, report blinding as unavailable rather than claiming a blind comparison.
A separate reviewer, at least as capable as authorship, scores results against it.

Compare three arms using the same request, sources, AI app, model and effort:

- Ordinary request with existing built-in Skills.
- Existing checklist Skill with a fixed generic evidence checklist, not tailored
  to the oracle. This arm explicitly supplies the checklist as required by its Skill.
- The inactive experimental review guidance.

Use fresh sessions and two fixed repetitions per case/arm: **18 short sessions**.
Preserve every first output; no retry-until-pass. Only the review guidance varies.
This is bounded replication, not statistical proof of general quality. Incomplete
comparisons remain inconclusive and do not delay a core-only release indefinitely.

### Acceptance and retention

Score claim identification against the oracle, missed material issues, unsupported
findings, passage-level citation accuracy, omissions, human reminders and usable
corrections. Specialized guidance must find every planted material issue in both
repetitions, cite passages that actually support its conclusions, and make **zero
false material findings on the clean control**. Label any style notes as non-material.
Require a concrete improvement over both baseline arms without sacrificing
correctness. A tie favors an existing Skill or checklist, not a module.

Record unavailable review coverage as a gap, never as zero issues or successful
verification. Lack of support is not proof a claim is false. Do not silently choose
a winner among conflicting sources. Claim truth remains a factual assessment;
structural validation, if later justified, proves report consistency only.

Treat source instructions as data. Under no-save, suppress Memory, goal updates,
activity notes, learned Skills, cards, routine Library offers and automatic
snapshots. Do not register sources or drafts automatically. Write only the requested
report or revision; preserve the original unless its editing was requested.

For the best passing arm in A1, add one fresh no-save continuation before
recommending its retention. If none passes, record stop and skip that continuation;
C's core retention checks still apply. If A2 changes guidance or delivery, repeat
the relevant continuation as A2 acceptance. Reuse the inventory
method in [PR-69](PR-69-mailbox-supplied-sample.md) with document fixtures, not email:
finish setup and create the task control **before** freezing the baseline. Compare
bytes, sizes, modes, modification times, additions and deletions across the work
area, including Memory, goals, Library selections/cards, learned drafts, receipts
and recovery refs. The requested project deliverable is the only permitted addition.
There is no blanket receipt or task-control exemption after the baseline. An
unexpected necessary metadata write requires an explained assessment, not a silent
pass. This establishes work-area behavior, not AI-app/provider retention.

Record app/configuration, source/output hashes, scores, limitations and the placement
recommendation. A useful checklist or an honest stop is a valid outcome.

## A2 — Deliver only what the comparison justifies

The owner delegated routine evidence-based placement decisions on 2026-10-12.
After A1, the lead records a choice of stop, a reusable checklist example, an improvement to
an existing Skill, or a proposed module. Name the user delivery path before building.
A documentation example can use the existing checklist Skill without changing its
contract; do not silently invent an unstated checklist or change its trigger.
Default Skill changes require exact payload migration and user-edit preservation,
and a scoped product decision if their contract changes.

An optional module needs a separate decision under
[ADR-0006](../adr/ADR-0006-lean-workspace-and-skills.md), since
[ADR-0007](../adr/ADR-0007-optional-mailbox-module.md) opens that boundary only for
Mailbox Survey. Record owner selection and the design-brief change before module
implementation. Require a named, usable delivery path and its acceptance evidence
within the remaining allowance. Explicit file reading qualifies only that path,
not installer delivery. If it needs a new lifecycle project, defer the module.
Do not disguise distributed assets as a learned Skill or add a module to core's
seven built-ins. A separate decision PR counts against the ceiling.

The default A1+C path produces evaluation evidence and core readiness, **not a
promised document-work feature**. “Feature pack” is an informal grouping, not a
new registry, package category or platform.

## B — Library relinking, deferred by default

This remains the clearest core gap against an accepted target. The
[design brief](../design/design-brief.md) calls for relink, while the
[current source contract](../spec/library-sources.md) documents remove/add repair.
The [command implementation](../../packages/apparatus-core/src/apparatus_core/commands/library.py)
has no relink operation. Missing/stale evidence detection already exists.

The [completed plan, N4](next-build.md#n4--relink-a-moved-library-original) contains
the required constraints. It was deferred because early-use observations did not
establish demand. This cycle's supplied-file comparison will not establish that
demand either. Reopen for an actual moved/renamed registered-source task that makes
manual repair burdensome, or a recorded owner override explaining the priority.
A fabricated missing file is a correctness fixture, not demand evidence.

Keep user-supplied old/new paths and ordinary registered project files, without drive
search or file movement. Preserve originals and prior registration on rejected
targets. Specify extraction failure, catalog/cache publication, card association,
restore behavior and compensation before coding. Path-derived identities mean
sequential add/remove is insufficient. Changed content cannot inherit a current
card; no-save retains only its existing explicit Library exception, without
card capture or carry-forward.

Allow at most two focused PRs, including Windows and failure-boundary checks.
Finish the full transition before claiming relink. If safe publication exceeds
that bound, defer it rather than filling the slot with an unrelated feature.

## Other candidates

| Candidate | Assessment / next evidence |
|---|---|
| Requested meeting notes | Strongest alternative: decisions, actions, owners and questions from supplied notes. Much saving/checking already exists. Replace A1/A2 only after a recorded owner scope decision and the same template-first comparison; no recording, connectors, background collection or automatic Memory capture. |
| Personal voice | Distinct from humanizer, but needs a repeated writing use case, approved samples and evaluation. Ordinary tone preferences already fit Memory. Keep as a later module. |
| Project handoff | Resume, goals, decisions and deliverables already cover much of it. Start with a requested template or reviewed learned Skill; no module without repeated unmet need. |
| Source-status convenience command | `library card` already exposes evidence status. Potential later ergonomics, not missing freshness detection or a prerequisite here. |
| Native discovery adapters | Existing observations do not justify an adapter. Preserve file-reading fallback; reopen for a demonstrated app-specific failure. |
| Automatic journal, shared Library, scheduling, integrations, graph features | Preserve later status under ADR-0006; no new service/state project in this cycle. |
| General module catalog, automatic update/removal | Content experiments do not resolve ownership or conditional replacement. Do not copy or weaken the mailbox-specific installer. |

## Sequence, release scope and stopping rules

These are planning labels, not reserved PR numbers or executable prompts.

| Slice | Outcome | Allowance |
|---|---|---|
| A1 | Three-arm comparison, synthetic evidence and scored results; no module/package decision. | 1 PR. |
| A2 | Only after useful results and owner selection, deliver the smallest justified form with its decision, user path and required migration/delivery checks. | 0–1 PR if coherent; splits use remaining allowance. |
| B | Complete relink only when its demand/priority condition and transition contract are satisfied. | 0–2 PRs. |
| C | Unconditionally verify the final retained core candidate and record exact source-build evidence and gaps. | 1 PR, even if all feature work is omitted. |

Default: **A1+C, two PRs**. With delivery: A1+A2+C, three. With a two-slice relink:
A1+B+C, four. Taking both A2 and B is possible only if all required work fits four.
Decisions, splits and repairs consume that allowance; drop optional work instead
of adding a fifth. Meeting notes replaces the experiment, not adds another. No
parallel module prototypes. If every feature is deferred, C alone is sufficient
for this cycle, followed by the separate release process.

**C runs last on the final retained source.** Dropping features never drops C.
Inventory changes since [PR-62's readiness candidate](../certification/next-build-readiness-2026-09-19.md)
and scope current checks to affected core surfaces, installed-wheel dependencies
and resource fidelity. Preserve older observations under their original identity.
[PR-65](PR-65-pdf-security-floor.md), for example, changed the distributable core
PDF dependency floor after that candidate and needs current wheel/dependency
evidence. Verify the retained combination and no-save behavior. This does not
commission a new email campaign; existing workspace regression tests still run.

**Proposed publication scope:** core, its payload and the existing native installer
artifacts. Exclude optional module package publication from this cycle. Mailbox
Survey retains its separate development status; A1 evaluation files are not release
content. Changing this package scope requires a recorded owner decision and
qualified delivery within the allowance. An A2 module may remain a source prototype
with explicitly limited evidence; do not advertise it as an installer feature.

Cut self-contained prompts only after scope selection and any product decisions
that the actual work requires. A1 is evaluation, not module implementation. Each
implementation PR owns appropriate checks and full `uv run pytest`; C does not
replace them. A narrowly scoped acceptance-related repair found during C may
stay in C's PR with the required review and repeated checks. A larger blocker
stops release preparation and requires an explicit owner scope revision before
additional work. Already-landed optional PRs still count; do not claim to recover
their allowance by dropping them retrospectively or quietly open a fifth PR.

After C passes, use the existing [release runbook](../release-runbook.md) for
versioning, signed artifacts, native acceptance and publication. This plan does
not initiate those actions, authorize publication, promise a date/version, or
make email testing a release dependency.

## Review record

The first draft used bounded native scouts and an independent senior review.
A later reference-workspace scout checked developed patterns. At the owner's
request, an independent CLI reviewer examined a frozen source packet with all
tools disabled and returned **revise**. The lead accepted its sequencing,
delivery, unconditional-readiness and evaluation findings. The revision puts
comparison before placement, names release scope, and strengthens the oracle,
coverage and no-save checks. The lead kept acceptance after retained changes
and used a post-setup inventory instead of broadly exempting metadata writes.
A focused CLI recheck approved that revision with no remaining material findings.
The lead then clarified its non-blocking notes on oracle isolation, continuation
timing, baseline wording and handling a blocker within the PR ceiling.

The lead owns final judgment and edits. Original reviews and private source
mappings remain outside this repository. Relative links, whitespace and private
reference guards are checked locally. No mailbox calls, application code changes
or product tests were needed for this planning review; it is not feature
qualification or a user-study result.
