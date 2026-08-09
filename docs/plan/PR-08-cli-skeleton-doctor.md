# PR-08: CLI skeleton and doctor

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` — especially §5 (default locations), §8, §9
- `docs/adr/ADR-0001-vocabulary.md`
- `docs/adr/ADR-0002-protocol-and-state.md`
- `docs/adr/ADR-0003-harness-agnostic-contract.md`
- `docs/adr/ADR-0005-distribution-and-packaging.md`
- `docs/plan/README.md`
- `docs/spec/workspace.md` — the `System/` table (machine report row) and "Placement on disk"
- `packages/apparatus-core/README.md` and `packages/apparatus-core/pyproject.toml` — current stub state

## Objective

`apparatus` becomes a real command. This PR lands the console entry point, the
exit-code convention, and the subcommand registry that packs plug into per
ADR-0005 — plus the first verb, `doctor`, which inspects the machine (OS,
Python, git, uv, installed AI apps, sync-redirection risk for a path) and
writes `System/machine-report.md` so the assistant knows its environment from
its first turn. Every later verb (`check`, `snapshot`, `restore`, `init`, `memory`,
`render`) hangs off this skeleton, so the registry contract defined here is
load-bearing for the rest of Phase 2 and for every future pack.

## Deliverables

- `packages/apparatus-core/pyproject.toml` — modified: add
  `[project.scripts]` with both `apparatus = "apparatus_core.cli:main"` and
  `ap = "apparatus_core.cli:main"` — two names, one entry point, per ADR-0005
  §2 (`ap.exe` on Windows falls out of the console-scripts mechanism) — and
  register the built-in `doctor` verb under
  `[project.entry-points."apparatus.commands"]` so the plugin path is
  exercised from day one.
- `packages/apparatus-core/src/apparatus_core/cli.py` — root argparse parser
  (`--version`, help), the registry that discovers the `apparatus.commands`
  entry-point group via `importlib.metadata`, and `main() -> int`.
- `packages/apparatus-core/src/apparatus_core/commands/__init__.py` — empty
  package marker for built-in verbs.
- `packages/apparatus-core/src/apparatus_core/commands/doctor.py` — the verb:
  `register(subparsers)` wiring plus `run(args) -> int`.
- `packages/apparatus-core/src/apparatus_core/detect.py` — pure detection
  functions with injectable collaborators (see acceptance criteria 7–9).
- `packages/apparatus-core/src/apparatus_core/machine_report.py` — renders and
  writes `System/machine-report.md`.
- `packages/apparatus-core/README.md` — modified: document the plugin
  mechanism (group name, entry-point signature, exit-code convention, how a
  pack adds a verb).
- `packages/apparatus-core/tests/test_cli.py`
- `packages/apparatus-core/tests/test_detect.py`
- `packages/apparatus-core/tests/test_machine_report.py`
- `docs/plan/README.md` — modified: PR-08 status row only.

## Acceptance criteria

1. `uv run apparatus --version` prints the `apparatus-core` version and exits
   0; `uv run apparatus` with no verb prints help and exits 2.
2. Alias parity per ADR-0005 §2: `[project.scripts]` installs both `apparatus`
   and `ap` pointing at the same `main`, and the two commands behave
   identically — same verbs, same output, same exit codes. A test proves it
   (e.g. by asserting both console scripts resolve to the same callable and
   exercising `--version` through each). The alias is a typing convenience for
   humans only: no code, documentation, procedure, or receipt references
   `ap` — every written artifact, including help text and the machine report,
   writes `apparatus`, and nothing may depend on the alias existing.
3. Registry contract: an entry point in group `apparatus.commands` resolves to
   a callable `register(subparsers)` that adds one argparse subparser and sets
   `func` to a `run(args) -> int` handler. Built-in verbs register through the
   same group — no second registration path. Document this contract in the
   package README exactly as implemented.
4. Duplicate verb names are deterministic: first registration (sorted by entry
   point name) wins; the loser is skipped with a warning on stderr, never a
   crash. A test proves it with a fake entry point.
5. Exit-code convention, applied CLI-wide and documented in the README:
   `0` success, `1` findings or degraded result, `2` usage error or unexpected
   internal failure. `doctor` returns 0 only when Python, git, and uv are all
   present and no sync-redirection risk was found; otherwise 1.
6. `apparatus doctor [WORKSPACE]` always prints a human-readable report to
   stdout. With a workspace path it also evaluates that path for
   sync-redirection risk and writes `System/machine-report.md` inside it
   (creating `System/` if absent). Without one, it evaluates the OS default
   workspace location from `docs/spec/workspace.md` and writes nothing.
7. Detections: OS name and version; Python version and executable; git
   presence and version; uv presence and version; installed AI apps via a
   best-effort, table-driven scan of well-known per-OS install/config
   locations — seed the table with the three app families the shim set
   targets (ADR-0003 §2) and make adding an app a data change, not code.
8. Sync-redirection risk is deterministic: path components and environment
   markers for the common sync engines (OneDrive including redirected
   Documents/Desktop, Dropbox, iCloud Drive, Google Drive). The result carries
   a human-readable reason.
9. Every detection function accepts injectable collaborators (e.g. `which`,
   `run`, `env`, `home`) so tests exercise all branches with fakes. No
   detection touches the network.
10. `System/machine-report.md` is Markdown with YAML frontmatter: generated
    timestamp (UTC ISO-8601), generator name and version, OS, Python, git and
    uv versions or `null`, `snapshots: available` or `unavailable` (driven by
    git presence, per ADR-0002 §6), detected AI apps, and the sync-redirection
    result with reason. The body restates the same facts in plain language
    using ADR-0001 vocabulary; the workspace is never called a repository.
11. Re-running `doctor` overwrites the machine report idempotently (stable
    content except the timestamp).
12. Stdlib only — argparse, platform, shutil, subprocess, importlib.metadata.
    No new runtime dependencies; if one seems needed, stop and justify it in
    the PR description instead.
13. `uv run pytest` is green.

## Conformance and tests

- No conformance fixture changes: the starter payload and golden manifest are
  untouched (the machine report is written only into deployed workspaces).
- Unit tests use monkeypatching and temp dirs throughout: fake `which`/`run`
  for git and uv, fake home directories for AI-app scans, synthetic paths for
  redirection cases (positive and negative per engine), report writing into a
  temp workspace. No test invokes real git, uv, network, or installers.
- `test_cli.py` covers: version, help, unknown verb (exit 2), duplicate-verb
  handling, and that a fake entry-point-registered verb is dispatched.

## Out of scope

- All other verbs (`check`, `snapshot`, `restore`, `init`, `memory`,
  `render`) — later PRs.
- The bootstrapper and installer (PR-22) — `doctor` is the in-CLI half only.
- Any change to `starter/payload/` or the golden manifest.
- Repairing or installing anything `doctor` finds missing; it reports only.
- Machine-readable output flags (`--json`); telemetry; any network access.

## Dependencies

- PR-07 (per `docs/plan/README.md`). Phase 1 content (schemas, procedures,
  policy, canon and shims) is present transitively.

## Open decisions

- Is `machine-report.md` a schema'd record? ADR-0002 fixes seven record kinds
  and requires an ADR for more. Smallest reversible default, used here: it is
  a well-known file, not a record kind — frontmatter must parse as YAML, but
  no kind schema applies and `check` (PR-09) validates only parseability.
- Exact AI-app detection locations are an engineering judgment; keep the table
  small, commented, and data-only so corrections are trivial follow-ups.
