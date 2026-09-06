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
extraction/search/citations, snapshots, backup, profiles, seven portable Skills,
and packaging machinery. The sharing gate has been removed. Fresh setup creates
a shared work area; `apparatus init WORKAREA --adopt` enrolls an existing folder
while preserving project files and custom instructions. Finished work stays in
its project. Welcome starts the actual request with useful defaults and only missing essential
questions; checklist and weekly reviews run only when requested.

People, Facts and Decisions support [correction, outdated status, and forgetting](docs/spec/memory.md).
`apparatus memory recall WORKSPACE QUERY` returns current Memory with sources.
Forgetting clears record content, with a filename marker to prevent automatic
re-seeding; it does not erase historical copies. [Task Memory controls](docs/spec/task-retention.md)
let a request opt out of new Memory and automatic capture while requested work
files remain available. Live task choices survive snapshot restore.

An enrolled [work area](docs/spec/workspace.md) keeps one Library, goals and Memory
beside existing project folders. `apparatus project bind PROJECT --workspace WORKAREA`
adds a relative link and instruction pointer, preserving project instructions.
Commands then use that explicit area's context. Moving a linked project requires
an explicit rebind; Apparatus never guesses another area.

The [local Library catalog](docs/spec/library-sources.md) can reference selected
project files in place. Add registers and extracts one original; existing files
under `Library/` remain compatible. Search and recall cite original paths and
report partial coverage when selected sources have changed or become unavailable.

[Managed recovery](docs/spec/managed-recovery.md) snapshots and backs up declared
Apparatus records and settings, excluding project files and Library originals.
It leaves root and project Git repositories untouched. Unconverted workspaces keep
their legacy recovery behavior until explicit adoption.

The seven built-in [Skills](docs/spec/skills.md) have one editable body each under
`.agents/skills/`. Init migrates recognized older procedures to small pointers
and preserves valid custom Skills. Checks and managed recovery understand these
files. Plain file reading works through the work-area link; native discovery
adapters and app-version probes remain the next compatibility step.

Economizer supplies bounded native delegation and model/effort guidance;
humanizer provides a selective prose pass. Both preserve task authority and
Memory controls. These instructions do not establish measured savings or prose
quality, and unsupported native controls remain unavailable.

After useful repetition, the assistant can offer an editable learned Skill draft.
The user reviews it once before adoption; no-save tasks do not capture drafts.
Adopted bodies stay editable and are covered by managed recovery through their
explicit ownership records. Drafts remain inactive and outside that coverage.

The [approved rework](docs/design/design-brief.md) adds native discovery adapters
and lightweight Library cards and completion offers. **The remaining rework is planned,
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
