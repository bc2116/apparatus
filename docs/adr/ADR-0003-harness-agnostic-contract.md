# ADR-0003: Harness-agnostic contract

- **Status:** Accepted, partially superseded by ADR-0006
- **Date:** 2026-08-08

> Read [ADR-0006](ADR-0006-lean-workspace-and-skills.md) first for the
> approved rework and its explicit supersession table. The text below records
> the original decisions; preserved provisions remain binding.

## Context

Users will run Apparatus under whichever AI app their organization provides,
and organizations change AI vendors. Binding the workspace to one app's
features would strand users at every tool change and shrink the addressable
audience. "Harness-agnostic" must be enforceable in review, not aspirational.

## Decision

1. **Minimum agent capabilities.** Core workspace content and procedures may
   assume exactly three things of the AI app: it can **read files**, **write
   files**, and **run approved commands**. Nothing else — no subagents, no
   app-specific context or rule syntax, no model assumptions. Packs are bound
   by the same contract.
2. **One canon, shims around it.** Canonical workspace instructions live in
   `AGENTS.md` at the workspace root. The universal payload also carries thin
   shims for apps that read their own files, all coexisting:
   - `CLAUDE.md` — import shim pointing at `AGENTS.md`
   - `.cursor/rules/` — rules shim
   - `.github/copilot-instructions.md` — shim
   The shim set is extensible; adding a shim type is a small PR. `render`
   regenerates all shims from canon; `check` fails on canon/shim drift. Shims
   are generated artifacts and never hand-edited.
3. **Certification, not per-app builds.** Supporting an app means running the
   certification checklist against the same universal payload — welcome flow,
   produce a deliverable, snapshot and restore, recall with citation, egress
   check — and recording results in a published support matrix. Adding app
   N+1 is a documentation-and-testing task.
4. **App-specific enhancements** (e.g., an app's parallel-agent features) may
   be documented per app as optional adapters, clearly marked, never required
   by any core or pack procedure.
5. This repository dogfoods the pattern: `AGENTS.md` is canon for contributors;
   `CLAUDE.md` here is a shim.

## Consequences

- A procedure that needs more than the three capabilities is misdesigned or
  belongs in an app-specific adapter note.
- The payload is built once; profiles vary content, apps do not.
- Certification results are honest and dated; an uncertified app may work but
  is not claimed.
