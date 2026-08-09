# PR-26: Installer wrapper and signed artifacts

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` — especially §2 (audience), §9
  (distribution), §14 (open questions: signing logistics, wrapper technology)
- `docs/adr/ADR-0005-distribution-and-packaging.md` — §3 promises a signed
  exe on Windows and a signed pkg on macOS; this PR closes that promise
- `docs/adr/ADR-0001-vocabulary.md` — installer output and docs are
  user-facing text
- `docs/plan/README.md`
- `docs/plan/PR-22-bootstrapper.md` — the scripts being wrapped
- `docs/plan/PR-23-signing-it-onepager.md` — the gated signing jobs, runbook,
  and one-pager this PR builds on
- `installer/README.md` and the scripts under `installer/` (landed in PR-22)
- `docs/signing-runbook.md`, `docs/it-onepager.md`, and
  `.github/workflows/release.yml` (landed in PR-23)

## Objective

ADR-0005 §3 promises installers a person can double-click: a signed `.exe` on
Windows and a signed `.pkg` on macOS. PR-22 delivered the working bootstrap
scripts; PR-23 delivered checksums, gated signing jobs, and honest docs — but
left the artifacts unwrapped, and left macOS integrity resting on checksums
alone because a shell script gave Developer ID signing nothing to sign. This
PR closes both gaps. Each bootstrap script is wrapped in a native installer
artifact whose only job is to carry the already-tested script unchanged and
launch it; the release pipeline builds the wrappers and feeds them through
PR-23's signing jobs so releases attach signed wrapped installers. When this
lands, the ADR-0005 end state is real: one signed artifact per OS, from a bare
machine to a doctor-verified workspace with no terminal.

## Deliverables

- `installer/windows/` wrapper build definition — new files as the chosen
  technology requires (see Open decisions), producing an `.exe` that carries
  and runs `bootstrap-apparatus.ps1`.
- `installer/macos/` package build definition — new, producing a `.pkg` that
  carries and runs `bootstrap-apparatus.sh`.
- `.github/workflows/release.yml` — modified: build both wrapper artifacts on
  their native runners, route them through the PR-23 signing jobs, attach
  them to the Release, and list them in `SHA256SUMS`.
- `installer/README.md` — modified: the wrapped installers become the primary
  install path; the bare scripts remain documented as the fallback.
- `docs/signing-runbook.md` — modified: the `.pkg` notarization slots become
  concrete operator steps now that a real `.pkg` exists.
- `docs/it-onepager.md` — modified only where a claim changes (installer
  artifacts now exist; signing status stated honestly).
- `docs/design/design-brief.md` — modified: §14 records the wrapper
  technology defaults chosen here.
- `docs/plan/README.md` — modified: PR-26 status row only.

## Acceptance criteria

1. The Windows artifact is a single `.exe` that embeds
   `installer/windows/bootstrap-apparatus.ps1` byte-for-byte and executes it.
   All install logic stays in the script; the wrapper adds none. The PR-22
   flags remain reachable through the wrapper (at minimum `-DryRun` and
   `-Path`), and `installer/README.md` documents how.
2. The macOS artifact is a `.pkg` that carries
   `installer/macos/bootstrap-apparatus.sh` and runs the bootstrap chain as
   the logged-in user, preserving the user-scope guarantee: no step of the
   chain runs as root. If the OS package-install flow itself forces an
   authentication prompt, `installer/README.md` states that reality plainly
   instead of hiding it — the chain's writes still land only in the user
   profile and the workspace target.
3. Wrapped artifacts preserve every PR-22 guarantee: user scope, idempotent
   re-run as the repair tool, refusal of sync-redirected targets, loud
   plain-language failures, ADR-0001 vocabulary, and no AI app brand names
   in any output.
4. Release integration: with the PR-23 signing variables enabled, the
   Windows job Authenticode-signs the `.exe` and the macOS job Developer
   ID-signs, notarizes, and staples the `.pkg`; signed artifacts are attached
   to the Release and listed in `SHA256SUMS`. With the variables unset, the
   unsigned wrapped artifacts are still built, attached, and checksummed, and
   the workflow stays green — wrapping never blocks on certificate
   logistics.
5. The macOS checksum-only integrity gap from PR-23 is closed: once signing
   is enabled, the primary macOS install path is a signed, notarized `.pkg`
   that Gatekeeper verifies, so integrity no longer depends on a user
   comparing checksums by hand.
6. The bootstrap scripts remain directly runnable and byte-identical to the
   repository copies; CI fails the wrapper build if the embedded script
   drifts from the script in the repository (byte comparison).
7. Wrapper builds are reproducible in CI from repository content plus
   version-pinned tooling; no unpinned downloads in the build jobs.
8. No certificate, key, password, or secret value appears anywhere in the
   repository; signing secrets stay referenced by name only, exactly as
   PR-23 established.
9. Every claim in `docs/it-onepager.md` and `installer/README.md` is true of
   the artifacts as shipped at this PR; anything still pending (an unsigned
   interim release, unflipped signing gates) is stated, not promised.
10. `uv run pytest` is green, including the PR-22 dry-run smoke tests, which
    must be unaffected.

## Conformance and tests

- No conformance fixture changes; workspace protocol behavior is untouched.
- CI gains wrapper build jobs on `windows-latest` and `macos-latest` in the
  release workflow's dry-run mode, including the embedded-script byte
  comparison of criterion 6.
- The PR-22 dry-run smoke tests keep passing unchanged.
- Verification is by rehearsal and review: run the release workflow via
  `workflow_dispatch` with signing variables unset and record in the PR
  description that both unsigned wrapped artifacts appear in the artifact
  list with checksums; when certificates exist, an operator follows
  `docs/signing-runbook.md` to flip the gates and verifies a signed install
  on a clean machine — recorded when it happens, never claimed early.

## Out of scope

- Certificate purchase or enrollment — operator steps per
  `docs/signing-runbook.md` (PR-23).
- No Linux installer in v0.
- No pack capability catalog on installer re-run (ADR-0005 §5 — post-alpha,
  tracked in the development plan's post-alpha section).
- No changes to bootstrap script logic — PR-22 owns behavior; this PR wraps
  what exists.
- No per-machine MSI, Intune, or other enterprise deployment formats; note
  demand for them to the plan owner instead.
- No auto-update mechanism for installed toolchains; re-running the
  installer remains the repair and upgrade path.

## Dependencies

- PR-22 (bootstrapper v1) and PR-23 (code-signing and IT one-pager), per the
  status table in `docs/plan/README.md`.

## Open decisions

- **Wrapper technology per OS — the central decision of this PR.** Genuinely
  undecided (design brief §14). Constraints: the wrapper carries the tested
  script unchanged and adds no logic; it builds headlessly in CI from pinned
  tooling; and it yields exactly the artifact its OS signing chain expects
  (Authenticode for the `.exe`; Developer ID plus notarization for the
  `.pkg`).
  - Windows candidates: Inno Setup, NSIS, WiX (Burn bundle), a minimal
    compiled launcher stub. Smallest reversible default: **Inno Setup** —
    mature, scriptable, and produces a single user-scope `.exe` that
    extracts and runs the script; swapping later changes only the build
    definition, not the script or the pipeline shape.
  - macOS candidates: native `pkgbuild`/`productbuild`, munkipkg, Packages.
    Smallest reversible default: **native `pkgbuild` + `productbuild`** —
    ships with the Xcode command line tools, fully scriptable, no
    third-party dependency, and emits exactly what `productsign` and
    `notarytool` expect.
  Record whichever defaults survive implementation against design brief §14
  in this PR.
- Whether the Windows `.exe` presents an installer UI or runs as a console
  launcher. Smallest reversible default: console launcher — it matches the
  script's own interaction model, and a graphical flow can wrap the same
  artifact later without changing the signing or release contract.
