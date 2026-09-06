# ADR-0002: Protocol and state format

- **Status:** Accepted, partially superseded by ADR-0006
- **Date:** 2026-08-08

> Read [ADR-0006](ADR-0006-lean-workspace-and-skills.md) first for the
> approved rework and its explicit supersession table. The text below records
> the original decisions; preserved provisions remain binding.

## Context

Workspace state must be legible to three readers at once: the human (in a file
explorer, with no tooling), the AI app (any certified one), and the validators.
Event streams, databases, and rich schemas favor the machine at the human's
expense and multiply the support surface. The audience for v0 is a single user
on a single machine.

## Decision

1. **Files first.** Every piece of workspace state is a file a human can open
   and read. No databases, no hidden stores, no state that exists only in an
   index. Derived caches (e.g., the Library search index) live outside the
   workspace, are rebuildable, and are never the source of truth.
2. **Markdown with YAML frontmatter, one record per file**, kebab-case
   filenames. `System/profile.yaml` is plain YAML. Machine-written records
   (receipts) are also Markdown with frontmatter. No JSON state inside the
   workspace in v0.
3. **Seven record kinds in v0**, each with a one-screen schema: procedure,
   goal, decision, fact, person, profile, receipt. Schemas live in
   `packages/apparatus-core` and are enforced by `check`; every schema beyond
   these seven needs an ADR.
4. **Goals carry verification oracles**: owner, status, done-when (how anyone
   could verify completion), and next action.
5. **Receipts** record what the machinery did — checks, redactions, snapshots,
   egress decisions — under `System/`, append-friendly, one file per event.
6. **Snapshots** use local git under the hood when available and degrade
   gracefully (explicit "snapshots unavailable" state reported by the machine
   report — never silent). The workspace is never presented to the user as a
   git repository.
7. **Sync-hostile by design, on purpose:** live state is documented to live
   outside file-sync engines; backup is a one-way snapshot export. State
   formats stay append-friendly so an accidental sync conflict damages one
   record, not the workspace.

## Consequences

- v0 forgoes event-stream memory (supersession chains, consolidation). If a
  pack later needs them, it builds them on top of the file records without
  replacing them.
- Validators must parse only Markdown frontmatter and YAML — no bespoke
  formats.
- Fixtures in `conformance/` pin the record schemas as they land (PR-04).
