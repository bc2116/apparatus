# ADR-0005: Distribution and packaging

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

The primary audience will not clone repositories, run pip, or open a terminal.
Many are on corporate Windows machines where admin rights are uncertain but
per-user installation usually works. The product must nevertheless deliver a
real toolchain (Python-based CLI, git-backed snapshots) so that checks and
gates are deterministic from the first session. Optional capabilities must be
deliverable to these same users without tier branding.

## Decision

1. **Monorepo, multiple artifacts.** This repository is a uv workspace.
   Releases produce: PyPI packages (`apparatus-core`, later packs), the
   universal starter payload, and a per-OS bootstrapper. Users never interact
   with the repository. `apparatus-core` embeds that same payload and its
   profiles byte-for-byte; the separate release archive is the files-only form.
2. **Plugin CLI.** `apparatus-core` ships lean and owns the `apparatus`
   command. Packs register subcommands via Python entry points; a verb exists
   on a machine only when its pack is installed. No dormant capability code in
   shipped binaries — better for security review, size, and honesty. The
   command installs under two names pointing at the same entry point:
   `apparatus` (canonical — the only form used in documentation, procedures,
   and receipts) and `ap` (a typing convenience for humans; `ap.exe` on
   Windows). Nothing may depend on the alias.
3. **Bootstrapper, user-scope first.** The installer (signed exe on Windows,
   signed pkg on macOS) installs in user scope by default: uv → uv-managed
   Python → portable git → `apparatus-core` → workspace creation at the default
   location (design brief §5). Elevation is the exception path, triggered by
   policy failures, not the default. It detects installed AI apps (recording
   them in the machine report — no app selection step), writes the machine
   report into `System/`, and is idempotent: re-running it is the repair tool.
4. **Code-signing from the first public release.** The realistic enterprise
   blocker is unsigned-executable policy (SmartScreen/AppLocker), not admin
   rights. The IT one-pager ships alongside the installer: what gets installed
   and where, where data lives, what leaves the machine and via what channel.
5. **Pack delivery, no tiers.** Two paths, same packages underneath:
   re-running the bootstrapper shows a capability catalog (checkboxes with
   one-line descriptions); or the assistant runs `apparatus add <pack>`
   in-session with the user's click-approval, installing the package and
   depositing the pack's workspace overlay. The catalog is a manifest the
   assistant can read and explain.
6. **Licensing.** Core is Apache-2.0 with DCO; the name is protected by the
   trademark policy. A pack may adopt a different license only from its own
   repository; the monorepo stays uniformly Apache-2.0.

## Consequences

- The release pipeline (payload builder, package publishing, installer build,
  signing) is first-class engineering, planned as its own phase.
- A zero-toolchain workspace (files only, no CLI) remains possible on locked
  machines and is reported honestly by the machine report as a degraded mode —
  it is a fallback, not a design center.
- Windows portable-git strategy is an open question tracked in the design
  brief (§14).
