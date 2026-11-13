# PR-77 verification: Native Skill pointer adapters

Isolated verification of generated native Skill pointer adapters on macOS
27.2.1 (`arm64`) in a fresh bound project (`demo-project` linked to its parent
work area) using an adopted learned Skill (`learned-marker-probe`) whose
canonical body contained an out-of-band verification token.

## Automated tests

- `packages/apparatus-core/tests/test_skill_adapters.py`: deterministic adapter
  rendering, verbatim YAML description preservation (quotes, colons, multiline,
  non-ASCII), LF/CRLF full-byte ownership, bound-project and work-area render
  sync, `skill adopt` JSON stdout + stderr render notice, non-qualifying
  exclusions, unrecognized occupant preservation + exit codes,
  `--remove-skill-adapters` cleanup, `check` gated `skill-adapter-drift` /
  `skill-adapter-missing` / `skill-adapter-orphan` findings, parent symlink /
  Windows-reserved / case-collision safety, rollback compensation, and snapshot
  exclusion.
- `conformance/test_render.py` and `packages/apparatus-core/tests/test_ci_workflow.py`.

## Isolated AI-app observations

| AI app | Observed result | Limits |
| --- | --- | --- |
| Codex CLI (`codex-cli 0.166.0`, macOS 27.2.1 `arm64`, `--ephemeral --sandbox read-only`) | **Pass** — discovered `learned-marker-probe` from `PROJECT/.agents/skills/learned-marker-probe/SKILL.md`, read `../.agents/skills/learned-marker-probe/SKILL.md`, and returned the canonical verification token verbatim. | Non-interactive CLI run in a bound project; no desktop GUI or cross-CLI coverage. |
| Claude Code CLI (`2.1.321`, macOS 27.2.1 `arm64`, `claude -p`) | **Unavailable** — `claude auth status` reported `"loggedIn": false` and `claude -p` exited 1 with `Failed to authenticate: OAuth session expired and could not be refreshed`. | Local CLI OAuth session expired/not logged in; adapter following in Claude Code remains unverified here. |
| Cursor IDE | **Unavailable** — GUI-only desktop app; not probed headlessly. | Recorded as unavailable rather than extrapolated from CLI or older IDE runs. |
