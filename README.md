# Apparatus

**The governed workspace for agentic knowledge work.**

Apparatus turns a folder on your computer into a workspace your AI app can operate
safely: goals, decisions, people, source documents, and deliverables — all plain
files — with guardrails that make agentic work inspectable, reversible, and safe
to share.

It is built for information workers first: analysts, quality engineers, project
managers, support engineers, writers. No GitHub account, no terminal, and no prior
IDE experience required. Developers get the same protocol through a second entry
path.

## The job statement

Every design decision is tested against one sentence:

> From a fresh install to a real deliverable produced inside a governed workspace —
> goals updated, sources cited, snapshot taken — in one sitting, with no terminal
> typed by the human and no accounts beyond their AI app.

## Principles

1. **Files first, tooling second.** The workspace is useful as plain files; the
   CLI is progressive enhancement, and its primary caller is the AI app, not the
   human.
2. **One canon, many renders.** Instructions and procedures are written once and
   rendered to every supported AI app. The workspace is portable across apps.
3. **Rails, not engine.** Apparatus never calls a model and never wraps an IDE.
   It is contracts, state, and gates that any app reads, writes, and operates.
4. **Safe by default.** Label sensitive content at write time; enforce at the
   workspace boundary. Credentials never persist. External actions are drafts
   until the human approves. Snapshots make everything reversible.
5. **Progressive disclosure.** Day 1 is a welcome conversation and a deliverable.
   Everything else reveals itself as it is needed.

Full detail: [docs/design/design-brief.md](docs/design/design-brief.md).

## Status

Pre-alpha. The protocol and development plan are documented; implementation is
underway. Current state: [docs/plan/README.md](docs/plan/README.md).

## Repository layout

| Path | Purpose |
|---|---|
| `packages/apparatus-core/` | The `apparatus` CLI: validators, gates, render, Library, snapshots |
| `starter/` | The universal workspace payload and profile overlays |
| `conformance/` | Golden fixtures — the executable specification |
| `docs/` | Design brief, ADRs, specs, and the development plan |
| `installer/` | Per-OS bootstrapper (planned, later phase) |

## Contributing

Human contributors: see [CONTRIBUTING.md](CONTRIBUTING.md). AI agents:
[AGENTS.md](AGENTS.md) is the canonical instruction file — app-specific files
such as CLAUDE.md are shims that point to it.

## License

Apache-2.0 — see [LICENSE](LICENSE). The Apparatus name and marks are not
licensed with the code; see [TRADEMARKS.md](TRADEMARKS.md).
