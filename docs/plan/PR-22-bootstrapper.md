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
signed installer executables is PR-26; this PR delivers the working scripts
and honest documentation of their limits.

## Deliverables

- `installer/windows/bootstrap-apparatus.ps1` — new.
- `installer/macos/bootstrap-apparatus.sh` — new.
- `installer/README.md` — new; how to run each script, what each step does,
  flags, idempotency, limitations (see criteria 9–10).
- `conformance/test_bootstrap_dry_run.py` — new dry-run smoke test.
- `conformance/windows_bootstrap_syscall_trace.ps1` — test-only built-in
  WPR/ETW controller for the Windows syscall boundary.
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
   persistent-filesystem mutation from interpreter entry, and exits 0.
   Mutation means creating, modifying, deleting, renaming, or changing the
   attributes of a persistent filesystem object: a file, directory, symbolic
   link, or extended attribute. Character-device I/O under `/dev` is outside
   this boundary, and the proof contract must not enumerate device names.
   Native CI must enforce the persistent-object boundary with non-vacuous
   metadata and identity canaries on Windows and mutation-denial canaries on
   macOS. The macOS sandbox retains its native network canary. Windows retains
   static exit-order and source checks in hosted CI and an optional ETW network
   witness where the platform can run it; static checks remain defense in
   depth rather than the primary persistent-object proof.
8. Both scripts fail loudly (nonzero, clear message) on unsupported OS,
   missing shell prerequisites, or a partially blocked chain — never a
   silent half-install; the message always says re-running is safe.
9. `installer/README.md` documents limitations honestly: unsigned scripts and
   how to run them anyway (`powershell -ExecutionPolicy Bypass -File …`;
   signing lands in PR-23 and signed wrappers land in PR-26); locked-down
   machines where the toolchain cannot
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
  Windows PowerShell 5.1 with `-NoProfile` and `macos-latest` running a
  controlled `/bin/bash` environment; both must pass without network installs.
- The macOS native proof launches `/bin/bash` from interpreter entry through
  `/usr/bin/sandbox-exec`, denies persistent-object mutation and `network*`
  with no logging and `SIGKILL`, closes every descriptor except standard
  input/output/error, and proves both denial categories with separate
  canaries. Its generic `/dev` allowance permits character-device data I/O
  only; creation, deletion, rename, metadata, and extended-attribute changes
  remain denied, and no device name is listed.
- The primary Windows native proof compares the filesystem before and after
  dry-run by name, size, modification time, and file identity across every
  named location: the workspace target, each user-scope install destination,
  `TEMP`, and the working directory. It covers absent and present roots and
  uses deterministic mutation canaries for every compared field. It needs no
  administrator access, global session, or timeout-prone trace lifecycle.
  The existing built-in WPR/ETW controller remains an optional stronger
  file/registry/network witness. Hosted runners skip that optional test with a
  reason recording the operator ruling; Windows environments with working ETW
  continue to run it.
- `uv run pytest` green is required.

## Out of scope

- No signed executables, no `.exe`/`.pkg` wrapping, no notarization (PR-23 and
  PR-26).
- No Linux bootstrapper in v0.
- No elevation/admin path beyond the honest failure message.
- No bundled MinGit or any vendored git (see Open decisions).
- No pack catalog UI on re-run (ADR-0005 §5 — later work).
- No general changes to `apparatus init`, `doctor`, or core behavior; the
  operator-authorized repair may harden only the init deployment transaction
  and machine-report publication by reusing the existing retained-root
  primitives.

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
- Operator ruling for the repair: retained-root hardening is authorized only
  for the core init deployment path, using the existing `WorkspaceAnchor`
  primitive family. Snapshot and receipt behavior remain outside this grant
  except exact cleanup fallout caused directly by the deployment transaction.
- Operator ruling for dry-run: zero mutation begins at interpreter entry. The
  pre-interpreter shell stage may only read state and write stdout/stderr; it
  runs no installer, network, or workspace command and leaves no persistent
  artifact.
- Operator ruling for UNC dry-run: Windows UNC targets remain lexical and
  uninspected before the dry-run exit. No existence, attribute, or SMB probe
  may touch the target.

## Authorized restart

The operator authorized a fresh two-pass restart after the prior blocked stop.
This branch records restart pass 2 of 2. The narrow core authorization,
interpreter-entry boundary, pre-interpreter promises, and UNC ruling above are
unchanged.

Before recounting failures, the operator refined the mutation boundary to the
persistent-filesystem definition in criterion 7. Under that definition, the
previous macOS interpreter-startup stop does not survive: character-device
data I/O under `/dev` is outside scope. The proof uses one generic subtree
allowance and names no device, while keeping every persistent-object mutation
and all network activity denied with non-vacuous canaries.

Two installer-harness failures from the prior exact-head Windows run do
survive the refined ruling: the controller's machine-scoped environment lookup
did not resolve the trusted Windows system directory, and a macOS-only native
path check was not platform-gated. Restart pass 1 repairs those proof defects
without weakening either boundary.

The same exact-head run had eleven init rollback failures: the
invocation-created-root case reported four incomplete cleanup operations, and
ten replacement, removal, or final-gate cases reported one each. Retained
Win32 file and parent handles outlived their exact rollback operations and
blocked later cleanup. Restart pass 1 releases each settled proof handle before
ancestor cleanup and adds a native Windows regression proving that a concurrent
foreign file is preserved and reported rather than removed. PR-22 stays blocked
and must not be marked landed or merged during this pass.

At restart-pass-1 head `f301bf6`, CI run `31509417123` closed all eleven core
rollback failures: Windows safety completed 381 tests with 69 skips before its
sole ETW failure. The remaining failures came from scheduling the same
machine-global WPR/ETW proof concurrently in both Windows jobs. The dedicated
bootstrap job timed out, while the safety job detected that the shared session
state was not restored exactly. This is a CI-topology capability shortfall, not
a contract ambiguity or permission to weaken the proof.

Restart pass 2 excludes the global test explicitly from `windows-safety`,
retains every other listed safety test there, and runs the ETW node exactly
once as a dedicated invocation in `bootstrap-windows` after the other bootstrap
checks. A static conformance regression pins that selection topology.

At restart-pass-2 implementation head
`cb9b66d61916cc29cd6c87bbdc73855c48492b8e`, CI run `31510839370` passed the
Linux, macOS bootstrap, and Windows safety jobs. Windows safety completed 382
tests with 69 skips and one intentional ETW deselection. The dedicated Windows
ETW invocation still failed because the traced cold process did not exit within
the controller's 30-second wait. The same timeout occurred in pass 1, so
removing concurrent execution did not close the native proof capability gap.

Both authorized repair passes were exhausted at administrative head `98d1851`,
and the PR entered a blocked stop for operator review.

## Authorized Windows proof-mechanism restart

The operator reclassified the repeatable hosted-runner ETW timeout as platform
infeasibility of that proof mechanism, not a capability shortfall and not a
specification ambiguity. The dry-run guarantee and refined persistent-object
definition are unchanged. Only the Windows evidence mechanism may change.

The operator authorized a fresh bounded restart at frontier/max author and
frontier/max reviewer, with the normal two-pass budget. Restart pass 1 replaces
hosted ETW as the primary Windows witness with the scoped filesystem comparison
specified above. The ETW controller remains available as an optional stronger
witness and is skipped on hosted runners with the ruling in its reason string.
USN-journal machinery is deliberately omitted because it is not needed for the
deterministic primary proof and must not become an ETW-equivalent subsystem.

Post-ruling recount: all eleven Windows init rollback findings, both earlier
proof portability findings, Linux CI, macOS native proof, and Windows safety
coverage remain closed. The sole reopened deliverable is the hosted Windows
dry-run evidence mechanism. PR-22 stays blocked with this restart in progress
until the new exact-head native CI evidence and independent review are green.

Restart pass 1 at exact head `98b0845` replaced the primary witness and removed
proof-level subprocess timeouts. CI run `31517125863` then exposed three scoped
test defects. Cached `DirEntry.stat` metadata returned zero file identities for
Windows files; the isolated `TEMP` root retained a modification-time change;
and the bootstrap job's final skipped optional-ETW invocation masked the broad
pytest failure. Windows safety failed and preserved the true run disposition;
Linux and macOS remained green.

Restart pass 2 uses path-based `os.stat` for the documented Windows file-index
identity, adds a cold interpreter baseline plus a git-suppressed diagnostic to
classify any surviving `TEMP` mutation without ignoring it, and propagates each
native pytest exit code before the optional ETW invocation. The root modification
time remains part of the comparison, and no warm-up or exclusion narrows the
interpreter-entry boundary. Native CI evidence remains pending.
