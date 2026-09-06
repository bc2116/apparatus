# Apparatus

**Help your AI app remember, find sources, and finish work in your projects.**

Apparatus adds portable files and a small toolchain to your workspace: goals,
Memory, a source Library, reusable Skills, snapshots, and backup. Your AI app
does the work. Apparatus does not wrap it or call model APIs.

The approved direction is task-first: finish and save real work in its project,
retain useful context, and offer reuse when it helps. A simple installer and
assistant-guided adoption of existing folders are both part of that direction.
Core needs only file reading, file writing, and approved commands; native AI
app features are optional enhancements.

## Status

Pre-alpha. The existing implementation includes Memory, local Library
extraction/search/citations, snapshots, backup, profiles, five procedure files,
and packaging machinery. It still has the old interview, sharing gate, and
central Deliverables folder.

The [approved rework](docs/design/design-brief.md) replaces that ceremony and
adds native Skills, economical subagent guidance, lightweight prose editing,
and a Library catalog referencing project files. **Those changes are planned,
not yet implemented.** Existing specs and conformance tests describe the
baseline until their migration PRs land. Formal app certification is held
while the target changes; packaging code alone does not establish a signed
public release or certified support.

Read the [decisions](docs/adr/ADR-0006-lean-workspace-and-skills.md),
[refactor sequence](docs/plan/rework-sequence.md), and
[development status](docs/plan/README.md).

## Repository layout

| Path | Purpose |
|---|---|
| `packages/apparatus-core/` | CLI, file validation, Memory, Library, recovery, and embedded payload |
| `starter/` | Canonical workspace payload and current profile overlays |
| `conformance/` | Fixtures and tests pinning implemented behavior |
| `docs/` | Design, ADRs, implementation specs, and focused PR plans |
| `installer/` | Platform bootstrap and installer machinery |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). [AGENTS.md](AGENTS.md) is canonical
for AI contributors; app-specific instruction files point to it.

## License

Apache-2.0 — see [LICENSE](LICENSE). The name and marks are covered separately
by [TRADEMARKS.md](TRADEMARKS.md).
