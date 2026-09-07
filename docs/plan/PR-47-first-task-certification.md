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

Prioritize Cursor IDE, Codex desktop, and the actually available Claude Code
variant. The lean RC compatibility gate is two actual chats for each named
app/variant on the same final payload. Record variants separately: a CLI
observation is not IDE or desktop evidence. An unavailable app gets a gap, not
a fabricated run or an inference from another app. The basic read/write/approved
commands contract remains available to new capable apps immediately; tested
support is a dated empirical claim. Broader certification may be scheduled
later; it is not silently implied by this RC gate.

## Portable checklist

Use synthetic project documents and fresh isolated state. Record actual file
outcomes and permitted command results, plus only the minimal assistant text
needed to demonstrate questions, offers or citations. A human-operated session
or explicit authorized agent-driven session can provide evidence, but a fake
assistant, scripted core-only run or model-free inventory cannot certify an
app's behavior. Never bypass native permissions or create new provider accounts.

1. **Task-first chat.** In an explicitly bound synthetic project, ask for a
   sourced deliverable. It must be saved in that project, preserve sentinels,
   name uncertainty, record one sourced Memory fact, and use the canonical
   Skill body. A brief optional Library-registration offer is acceptable;
   accepted registration must keep the original in its project and produce a
   grounded card. Record
   the persisted artifact and hashes. Native permissions remain authoritative.
2. **Fresh recall chat.** Start a fresh conversation in the same bound project.
   Ask it to recall the prior context with citations and create the requested
   deliverable. Request no Memory saving and verify no automatic task-content
   capture in Memory, learned Skills, Library cards, or activity notes. Include
   deliberately missing evidence and require a truthful abstention. Record the
   persisted artifact, citations, inventories, and hashes. Do not claim control
   over provider retention or deletion from historical backups.

For each chat record setup, prompt/action, expected result, evidence paths and
pass/fail/partial/unavailable. A blank result is not a pass. Keep independent
negative cases rather than corrupting a passed baseline to imply wider coverage.

## Native observations and quickstarts

Separate native discovery, following the sole canonical body, precedence,
duplicate discovery, shared-root versus independent-project behavior and
delegation controls. Existing metadata-only probes may be retained as labeled
diagnostic evidence for their exact versions; they do not count as either
required chat. Windows link privileges and IDE versus CLI remain distinct.
Optional adapter decisions follow evidence and cannot fork canonical bodies or
make an app-specific path necessary for core use. Do not add an adapter based
only on menu visibility. Actual assistant behavior cannot be inferred from
scripts, metadata, menus, or automated core/conformance results.

Quickstarts fit one page each and lead with opening the selected folder and
asking for actual work. Use the tested installer/adoption paths from PR-46;
ask the assistant for command steps when needed. Explain fallback in one short
paragraph. Verify current native setup instructions from the app's official
documentation before publishing them; label any untested path honestly.

## Acceptance and stop conditions

Every RC-compatible row identifies the same final core/payload and supplies two
real passing chats. Each record includes exact app/variant, app version, model,
OS/version, persisted-artifact and hash oracles. Partial or unavailable rows
remain diagnostic evidence and cannot satisfy the named-app RC gate. Preserve
signed first public release requirements separately: native compatibility,
package composition, publisher signatures, and live release publication are
different evidence.

Review evidence semantically against actual synthetic source files, not just
table structure. A lightweight consistency check may validate links and prevent
an RC-compatible row with missing or nonpassing chats; it cannot assess or
manufacture assistant behavior. Keep deep deterministic mechanics in automated
core/conformance CI once. Run one installer install-and-repair pass per supported
OS; Windows ARM64 VM evidence must be labelled as such and cannot replace required
x64 evidence. Retest the changed layer after a change. `uv run pytest` must be
green before this PR is declared done; an unchanged, exactly identified validated
tree may reuse that evidence when appropriate. Documentation-only edits need
focused document validation, not a rerun of the app matrix or GUI/platform suite.
No core or payload changes in this slice; defects get concrete reports and separate
focused repairs.

If an app, permission, signed artifact or operator action is unavailable,
complete all independent preparation and record the exact remaining evidence.
Do not claim support certification, a full pass, or an RC merely because the
test plan and quickstarts exist. Keep this branch draft/incomplete until its
two-chat-per-app and installer acceptance evidence exists. Signing and
publication remain separate, accurately incomplete public-release gates; the
signed-first-public-release requirement is unchanged. Do not overwrite the held
PR-24 branch.
