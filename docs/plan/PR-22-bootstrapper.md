# PR-22: Bootstrapper v1

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` — especially §2 (audience), §5 (default
  locations), §9 (distribution), §14 (open questions: portable git)
- `docs/adr/ADR-0005-distribution-and-packaging.md` — the binding decision
- `docs/adr/ADR-0003-harness-agnostic-contract.md`
- `docs/adr/ADR-0001-vocabulary.md` — all text a user might see
- `docs/plan/README.md`
- `docs/spec/workspace.md` — "Placement on disk" (sync-redirection rules)
- `conformance/README.md`
- `.github/workflows/ci.yml`

## Objective

When this PR lands, a person with no terminal skills can get from a bare
machine to a working, doctor-verified workspace by running one script per OS.
The Windows PowerShell script and the macOS shell script each perform the
ADR-0005 user-scope chain — uv, a uv-managed Python, git detection,
`apparatus-core` via `uv tool`, then `apparatus init` at the default location
and `apparatus doctor` — with no admin rights on a typical machine. Both are
idempotent: re-running is the repair tool. Dry-run flags make both scripts
smoke-testable in CI without installing anything. Wrapping these scripts into
signed installer executables is PR-23; this PR delivers the working scripts
and honest documentation of their limits.

## Deliverables

- `installer/windows/bootstrap-apparatus.ps1` — new.
- `installer/macos/bootstrap-apparatus.sh` — new.
- `installer/README.md` — new; how to run each script, what each step does,
  flags, idempotency, limitations (see criteria 9–10).
- `conformance/test_bootstrap_dry_run.py` — new dry-run smoke test.
- `conformance/README.md` — modified; register the new test.
- `.github/workflows/ci.yml` — modified; dry-run smoke jobs on
  `windows-latest` and `macos-latest`.
- `docs/design/design-brief.md` — modified; §14 records the interim git
  default chosen here (see Open decisions).
- `docs/plan/README.md` — modified; status table row for PR-22.

## Acceptance criteria

1. Each script performs, in order, skipping any step already satisfied:
   install uv user-scope (official installer); ensure a uv-managed Python;
   detect git (criterion 5); `uv tool install apparatus-core` (or upgrade if
   present); `apparatus init` at the default location; `apparatus doctor`.
2. User scope only: no `sudo`, no elevation prompts, no writes outside the
   user profile and the workspace target. If a step fails for policy reasons
   (blocked downloads, execution policy), the script stops with a plain-
   language message pointing at `installer/README.md` — it never retries with
   elevation.
3. Default workspace locations: `C:\Projects\Apparatus` on Windows,
   `~/Projects/Apparatus` on macOS, overridable via `-Path` / `--path`. The
   Windows script refuses a target inside a OneDrive-managed or
   folder-redirected location (detects `OneDrive` path components and the
   known redirection registry state for Documents/Desktop); the macOS script
   refuses a target whose resolved path lies under `~/Library/Mobile
   Documents` (iCloud Drive). Both explain why: live workspace state must not
   sit in a sync engine (`docs/spec/workspace.md`, "Placement on disk");
   backup is a one-way snapshot export.
4. Idempotent: re-running a completed install changes nothing, repairs any
   missing component, never overwrites an existing workspace (an existing
   target is left intact and `init` is skipped or run in its non-destructive
   mode per PR-11), and always finishes with a fresh `apparatus doctor` run.
5. Git strategy (interim default, see Open decisions): detect git on `PATH`
   and use it; when absent, continue without failing — `doctor` reports
   snapshots unavailable per ADR-0002, and `installer/README.md` tells the
   user (or their IT) how to install git user-scope later and re-run the
   script to repair.
6. AI apps are detected and recorded, never selected: the scripts present no
   app choice and name no app brands in output; detection and the machine
   report in `System/` happen through `apparatus doctor` (PR-08). Script
   output uses ADR-0001 vocabulary (workspace, snapshot, check, AI app).
7. Dry-run: `-DryRun` / `--dry-run` prints the full plan with the detected
   state of every step (present/missing), performs no network access and no
   writes, and exits 0.
8. Both scripts fail loudly (nonzero, clear message) on unsupported OS,
   missing shell prerequisites, or a partially blocked chain — never a
   silent half-install; the message always says re-running is safe.
9. `installer/README.md` documents limitations honestly: unsigned scripts and
   how to run them anyway (`powershell -ExecutionPolicy Bypass -File …`;
   signing lands in PR-23); locked-down machines where the toolchain cannot
   install fall back to the degraded files-only workspace mode that `doctor`
   reports — a fallback, not a design center (ADR-0005). The README is
   user-facing text: ADR-0001 vocabulary throughout, no AI app brand names.
10. No secrets, no telemetry, no machine-specific absolute paths in any file;
    downloads come only from the official uv install endpoints and PyPI.
11. The status table in `docs/plan/README.md` is updated in this PR.

## Conformance and tests

- New `conformance/test_bootstrap_dry_run.py`: runs the platform-appropriate
  script with its dry-run flag under a temporary HOME/working directory,
  asserts exit code 0 and that no files were created outside the temp area.
  Skips cleanly when the required interpreter (pwsh/bash) is unavailable on
  the host. Register it in `conformance/README.md`.
- `.github/workflows/ci.yml` gains two smoke jobs: `windows-latest` running
  `pwsh -File installer/windows/bootstrap-apparatus.ps1 -DryRun` and
  `macos-latest` running `bash installer/macos/bootstrap-apparatus.sh
  --dry-run`; both must pass without network installs.
- `uv run pytest` green is required.

## Out of scope

- No signed executables, no `.exe`/`.pkg` wrapping, no notarization (PR-23).
- No Linux bootstrapper in v0.
- No elevation/admin path beyond the honest failure message.
- No bundled MinGit or any vendored git (see Open decisions).
- No pack catalog UI on re-run (ADR-0005 §5 — later work).
- No changes to `apparatus init`, `doctor`, or core behavior; the scripts
  only orchestrate existing verbs.

## Dependencies

- PR-21 (release pipeline) and PR-30 (embedded universal payload), per the
  status table in `docs/plan/README.md`.

## Open decisions

- Windows portable-git strategy (design brief §14: bundled MinGit vs
  detect-and-skip). Smallest reversible default, taken in this PR:
  **detect-and-skip** (criterion 5). It ships nothing extra, degrades to the
  doctor-reported files-only mode ADR-0002 already defines, and a later PR
  can add MinGit bundling without changing the script's interface. Record
  this interim default against the open question in design brief §14; the
  question stays open until real locked-down-machine data decides it.
- Idempotency and the required fresh doctor run leave one narrow tension:
  doctor timestamps the current machine report, so a completed re-run cannot
  be byte-identical at that one generated file. The smallest reversible
  default is that bootstrap and tool repair are idempotent and existing user
  files are preserved, while doctor intentionally refreshes
  `System/machine-report.md`; byte-identical no-op behavior is not promised for
  that report. This records the existing behavior without expanding core.
