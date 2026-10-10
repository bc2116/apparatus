# PR-69 — Exercise the installed Mailbox Survey with supplied messages

## Outcome

Record one bounded user experience against the integrated PR-68 source: a
fresh assistant reads the installed Skill and supplied synthetic messages,
produces its own useful report, validates it, and reads its summary. A second
fresh assistant uses that report in a no-save task and writes one requested
project note while preserving existing work-area content.

## Scope and prerequisites

Start the assistant exercise after PR-68 is merged and its source identity is
verified. Use an isolated wheel installation, disposable enrolled work area,
and only the packaged eight-message sample. Seed unrelated synthetic Memory
and Library content before the baseline. State the actual AI app, version,
session surface, model configuration, operating system, package versions,
source identities and wheel/resource hashes.

Use explicit Skill file reading. A native subagent session is a valid bounded
surface when identified as such; it must not be described as a top-level
desktop chat, CLI run, automatic discovery or live connector test. Fresh means
the second session receives no prior conversation history. Record what it was
explicitly supplied.

## Procedure

1. Install the current module's canonical Skill in the disposable work area.
   Confirm current status; create the first task control, then freeze the
   work-area inventory. Keep setup writes separate from assistant behavior.
2. Ask a fresh assistant to use the explicit Skill, review only the supplied
   sample, propose supported overlapping categories, leave unsupported items
   uncategorized, state coverage limits and save the report in the project.
   Do not supply or allow copying the packaged example report.
3. Run installed validation and summary commands. Independently compare every
   category/example link and summary with the source. Structural validity alone
   does not establish factual support. Preserve the first output and any
   bounded correction as distinct attempts, with at most two repairs.
4. Create a separate no-save task and freeze its baseline after that control
   exists. Ask a fresh assistant to read the existing report, explain the
   categories and write one short requested project note. Compare all existing
   file bytes, sizes, modes and modification times, and detect additions and
   deletions. The requested note is the only permitted content addition.
5. Independently review both outputs and the evidence. Retain failures and
   limitations. Do not broaden scope to obtain a pass.

## Ownership and completion

Own this prompt, one dated certification note, its compact synthetic evidence
directory and the minimal plan/matrix/module-sequence links. No product code,
resource changes, new model provider, mailbox access, lifecycle update/removal,
release publication or new certification framework belongs here.

Record the supplied prompt text, original assistant outputs, fixture/report
hashes, command results, before/after inventories and independent factual
assessment without private sources or machine-specific absolute paths. State
whether the original attempts passed, needed assistance or failed. No-save
observations cover the disposable work area, not the AI app's own retention.

Run repository `uv run pytest` after installing the workspace packages,
validate evidence and local links, obtain independent review and require
current-head CI before merge. Set the plan row to `✅ landed` in the proposed
change. An honest partial result is acceptable evidence; unsupported claims of
native discovery, live-mailbox quality or complete lifecycle support are not.
