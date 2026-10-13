# Supplied-document review comparison — 2026-10-12

## Decision

Retain the current built-in Skills for supplied-document review. Do not add a
new Skill, module or checklist delivery in this cycle. All three approaches
found every planted material problem; specialized guidance improved presentation
but did not establish a material advantage over current behavior. This is a
bounded result, not a claim that current behavior is universally reliable.

The owner delegated this placement choice under [the bounded plan](../plan/next-release-features.md).
A2 is omitted and Library relinking remains deferred: this supplied-file task
provides no evidence of moved-source demand. C, final core acceptance, remains
required. This preserves the default two-PR path and keeps email testing deferred.

## Source and method

Core/payload source: `1eee87a6e7a1104446099a023f1b93cd42819e07`, through PR-69.
PR-70 adds only planning and evaluation files; no active instruction, package or
runtime source changes. The [capsule](evidence/document-review-2026-10-12/)
contains frozen synthetic inputs, inactive guidance, all first reports and
independent claim-level scoring. Three cases cover numeric overstatement,
authority/conflicts, and an entirely supported clean control. Each has six claims;
the first two have four material defects each.

There were three arms, two fixed repetitions per case/arm, and 18 fresh native
Codex subagents requested as GPT-6 Luna at medium effort. The common request,
source files and existing Skill text were supplied explicitly. Arms differed by
no extra guidance, a generic checklist, or inactive specialized review guidance.
Every first output is preserved; there were no correction attempts or human
reminders. Initial dispatch wording was more verbose for runs 01–03 than later
runs, while preserving the same read/write and first-output constraints.

Cases and oracle were frozen before specialized guidance. The oracle was absent
from participant packets and outside the checkout until all runs completed.
Native tool-root isolation was unavailable: **enforced blinding is unavailable**.
Input hiding and instructions do not prove participants lacked filesystem access;
raw tool-access traces were not independently audited. This limits the comparison.

A separate GPT-6.1 reviewer, requested at high effort, scored all original reports
against the oracle and actual passages. Dispatch accepted the requested settings;
provider model identity and effective effort were not independently attested.

## Results

Each arm has 36 claim assessments, 16 material issues and two clean-control runs.
Citation counts are per claim, not per individual inline reference.

| Arm | Claims covered | Issues caught | Accurate claim citations | False material findings | Clean controls correct |
|---|---:|---:|---:|---:|---:|
| Current Skills | 36/36 | 16/16 | 36/36 | 0 | 2/2 |
| Generic checklist | 36/36 | 16/16 | 34/36 | 0 | 2/2 |
| Specialized guidance | 36/36 | 16/16 | 36/36 | 0 | 2/2 |

All arms preserved the unresolved retention/capacity proposals and correctly
applied the approved amendment. Each supplied usable corrections for 16/16
planted issues. The checklist's second authority/conflict report cited amendment
line 1 for values actually on line 2: correct conclusions, two wrong passage
locators. Current Skills labeled the already-correct percentage as needing
correction in both quantitative runs, while explicitly affirming its value.
These are preserved as two non-material labeling defects, not silently repaired.
Specialized guidance provided consistent dispositions and tables without those
label defects, but no added material detection or reduced reminders. A formatting
advantage on these small cases does not justify new product surface.

See [scores](evidence/document-review-2026-10-12/scores.json) and the
[independent assessment](evidence/document-review-2026-10-12/scoring-review.md)
for the rubric, per-claim excerpts, limitations and original outputs.

## No-save continuation

A fresh native continuation uses the first current-arm authority/conflict report
and its supplied sources in a disposable enrolled work area. Setup creates a
synthetic Memory sentinel and Library registration before the no-save task and
baseline inventory. The requested correction note is the only permitted addition.
The source environment is used here; isolated installed-wheel qualification is C.

The continuation passed: 143 pre-existing entries remained unchanged, one
requested correction note was added, and nothing was removed. The lead checked
that note against the supplied sources; all corrections and unresolved decisions
are accurate.

The [continuation capsule](evidence/document-review-2026-10-12/continuation/)
records the task, portable prompt, setup, inventories, output and result. File
bytes, size, mode and modification time, additions and removals include managed
content, task controls, receipts and recovery state. Directory modification times
are excluded because adding the requested deliverable changes its parent; directory
presence and modes are compared. This is work-area behavior, not AI-app/provider
retention or enforced filesystem confinement.

## Verification and limits

The offline checker verifies captured hashes, run/claim coverage, score arithmetic
and the exact continuation delta; it does not validate factual meaning by code.
`uv run pytest` passed: **1,792 passed, 43 skipped** in 560.99 seconds.
Platform-conditional skips do not qualify unavailable platforms. Independent
final review is recorded with the capsule.
Current-head CI and remote merge verification are delivery gates.

Only three short synthetic Markdown cases, one requested executor model/effort,
explicit file reading and no-save project output are covered. No PDF parsing,
Library retrieval, native discovery, customer demand, long-document review,
statistical generalization, live email or release publication is qualified here.
