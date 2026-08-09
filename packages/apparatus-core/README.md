# apparatus-core

Core package for [Apparatus](https://github.com/bc2116/apparatus) — the governed
workspace for agentic knowledge work.

This package provides the `apparatus` command. It starts with `doctor`, which
reports the local environment and can write `System/machine-report.md` in a
workspace. Later planned changes add workspace scaffolding, checks, rendering,
Memory and Library operations, and snapshots.

## Command packs

Packs add commands through the `apparatus.commands` Python entry-point group.
An entry point's name is its command verb and its target is a callable with this
signature:

```python
def register(subparsers) -> None:
    command = subparsers.add_parser("example")
    command.set_defaults(func=run)


def run(args) -> int:
    return 0
```

The core command discovers every entry point in that group, sorted by entry
point name and then by target value as a deterministic tie-breaker. The first
registration for a verb wins; a later duplicate is skipped with a warning. A
pack therefore adds its verb by declaring an entry point in its own package
metadata, for example:

```toml
[project.entry-points."apparatus.commands"]
example = "apparatus_example.commands:register"
```

Command handlers return these process codes: `0` for success, `1` for findings
or a degraded result, and `2` for usage errors or unexpected internal failures.
All written command output uses the canonical `apparatus` name.
