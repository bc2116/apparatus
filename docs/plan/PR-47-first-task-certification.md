# PR-47 — Prove the reworked first-task experience

R12 replaces PR-24's held checklist. Final certification depends on PR-49's
cache error diagnostic repair and PR-48's feature-profile external path alias
repair, following PR-46 and preceding rework. The first PR-46 Cursor run exposed
the alias defect. Later observations on the PR-48 build exposed misleading cache
error wording and a Codex cache workaround. Preserve these dated observations;
use one final common baseline for certification. Neither failed attempts nor
workaround runs become clean passes after a source repair. Preserve the held
PR-24 worktree and historical evidence; they establish only that earlier payload's
behavior. Unit tests and native metadata discovery do not satisfy app acceptance.

## Deliverables

- `docs/certification/checklist.md`: one portable, observable first-task script.
- `docs/certification/matrix.md`: dated core results and separate optional
  native Skill/delegation observations, with explicit unavailable coverage.
- `docs/quickstarts/codex.md`, `claude-code.md`, `cursor.md`: concise instructions
  for an actual task in a fresh work area or an explicitly bound project.
- `docs/certification/evidence/`: compact synthetic run evidence, identified by
  app/version/OS, final payload/core identifier and test case. No raw personal
  conversations, provider credentials, private app state or machine paths.
- README support link, current design/rework/status reconciliation, and a
  verification note that distinguishes implemented source from tested runtime.

Prioritize Codex, Claude Code and Cursor. Certify the same final payload across
at least three actually available AI apps, recording variants separately (a CLI
observation is not IDE evidence). An unavailable app gets a gap, not a fabricated
run or an assumption inferred from another app. The basic read/write/approved
commands contract remains available to new capable apps immediately; tested
support is a dated empirical claim.

## Portable checklist

Use synthetic project documents and fresh isolated state. Record actual file
outcomes and permitted command results, plus only the minimal assistant text
needed to demonstrate questions, offers or citations. A human-operated session
or explicit authorized agent-driven session can provide evidence, but a fake
assistant, scripted core-only run or model-free inventory cannot certify an
app's behavior. Never bypass native permissions or create new provider accounts.

1. **Start useful work.** Open the shared root and then an explicitly bound
   sibling project. Ask for a short concrete deliverable from a supplied local
   source. It is saved in that project with relevant evidence, no preliminary
   questionnaire, forced central folder or routine approval pause. Existing
   files/custom instructions survive. Native app permissions remain authoritative.
2. **Control Memory.** In a saving task, record a useful sourced fact/decision,
   correct it and prove recall no longer presents the obsolete version as
   current. In a separate don't-save task, produce the requested deliverable
   while preserving Memory/learned Skills/cards/activity notes. Verify the
   current explicit Library/snapshot exceptions separately; do not claim
   control over provider retention or deletion from historical backups.
3. **Keep one Library.** Finish a reusable deliverable, observe one brief
   optional addition offer, and test decline and acceptance in independent
   cases. Decline does not block completion. Acceptance registers the original
   and produces a supported card through the current assistant. No required
   copy or symlink is created. Inspect hashes, source-grounded wording, partial
   extraction and missing/stale/ignored-original outcomes. Unsupported answers
   abstain; cards never turn their own prose into original-source authority.
4. **Use Skills portably.** Invoke built-in research/deliverable guidance and
   the small humanizer with an actual task. Capture and review one learned
   Skill, adopt the reviewed bytes and demonstrate file-reading use. Drafts
   remain inactive. Record canonical source selection; do not infer body
   execution from a native menu entry. Native economizer guidance is advisory:
   if delegation tools exist, verify bounded roles/capability/effort with no
   cross-CLI executor. If absent, the single-assistant fallback is a core pass.
5. **Recover exactly what is covered.** Create a real managed snapshot, make
   a deliberate managed change, restore it, and show unaffected project
   deliverables/originals. Export a one-way backup and inspect its closed scope.
   Restoring catalog metadata cannot restore a deleted original. Exercise
   unavailable Git separately and show the concrete action, without claiming
   a recovery point from Git detection alone.
6. **Stay quiet and respect ordinary actions.** Ordinary check, recall and
   extraction create no routine receipts. Meaningful repair/redaction/recovery
   retains its required evidence. Make an authorized local move/copy/export of
   a synthetic deliverable and observe no added Apparatus sharing review.
   Do not send messages, upload or publish merely to test this condition.

For each step record setup, prompt/action, expected result, evidence paths and
pass/fail/partial/unavailable. No blank result means pass. Keep independent
negative cases rather than corrupting a passed baseline to imply wider coverage.

## Native observations and quickstarts

Separate native discovery, following the sole canonical body, precedence,
duplicate discovery, shared-root versus independent-project behavior and
delegation controls. Existing metadata-only probes may be retained as labeled
diagnostic evidence for their exact versions; they do not count as any of the
six core steps. Windows link privileges and IDE versus CLI remain distinct.
Optional adapter decisions follow evidence and cannot fork canonical bodies or
make an app-specific path necessary for core use. Do not add an adapter based
only on menu visibility.

Quickstarts fit one page each and lead with opening the selected folder and
asking for actual work. Use the tested installer/adoption paths from PR-46;
ask the assistant for command steps when needed. Explain fallback in one short
paragraph. Verify current native setup instructions from the app's official
documentation before publishing them; label any untested path honestly.

## Acceptance and stop conditions

Every certified row identifies the same final core/payload and supplies six
real passing cases. Partial or unavailable rows may ship as diagnostic evidence
but cannot satisfy the three-app release gate. Preserve signed first public
release requirements separately: native certification, package composition,
publisher signatures and live release publication are different evidence.

Review evidence semantically against actual synthetic source files, not just
table structure. A lightweight consistency check may validate links and prevent
"certified" rows with missing/nonpassing cases; it cannot assess or manufacture
the underlying behavior. Run required full pytest before delivering this PR,
without repeating platform safety suites for documentation-only edits unless a
new failure justifies them. No core or payload changes in this slice; defects
get concrete reports and separate focused repairs.

If an app, permission, signed artifact or operator action is unavailable,
complete all independent preparation and record the exact remaining evidence.
Do not mark this PR or the overall release complete merely because the test
plan and quickstarts exist. Do not overwrite the held PR-24 branch.
