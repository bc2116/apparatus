# PR-23: Code-signing and IT one-pager

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` — especially §7 (privacy), §9 (distribution),
  §14 (open questions: signing logistics)
- `docs/adr/ADR-0004-privacy-model.md` — the model the one-pager summarizes
- `docs/adr/ADR-0005-distribution-and-packaging.md` — signing and the
  one-pager are decided here
- `docs/adr/ADR-0001-vocabulary.md` — the one-pager is user-facing text
- `docs/plan/README.md`
- `.github/workflows/release.yml` (landed in PR-21)
- `installer/README.md` and the scripts under `installer/` (landed in PR-22)

## Objective

When this PR lands, the release pipeline has real integration points for
signing the Windows and macOS bootstrap artifacts — gated off until a
certificate exists, structured so enabling them is configuration, not
engineering — and the repository ships the two documents ADR-0005 requires
around them: an operator runbook for certificate acquisition and enablement
(including the SmartScreen and AppLocker realities that make signing the true
enterprise blocker), and `docs/it-onepager.md`, the honest one-page answer an
IT reviewer needs before approving Apparatus on a corporate machine. Actual
signing may remain pending the certificate; nothing in this PR pretends
otherwise.

## Deliverables

- `.github/workflows/release.yml` — modified; checksums plus gated signing
  jobs (criteria 1–3).
- `docs/signing-runbook.md` — new; operator runbook (criterion 4).
- `docs/it-onepager.md` — new; the IT reviewer one-pager (criteria 5–7).
- `installer/README.md` — modified; link the one-pager and state current
  signing status honestly (criterion 8).
- `docs/plan/README.md` — modified; status table row for PR-23.

## Acceptance criteria

1. The release workflow attaches the two bootstrap scripts
   (`installer/windows/bootstrap-apparatus.ps1`,
   `installer/macos/bootstrap-apparatus.sh`) to the GitHub Release — users
   never clone the repository (ADR-0005) — and always generates a
   `SHA256SUMS` file covering every release artifact (payload archive, sdist,
   wheel, both bootstrap scripts), attached to the Release in dry-run and
   publish modes alike.
2. Two signing jobs exist — Windows and macOS — each skipped unless the
   repository variable `APPARATUS_SIGN_WINDOWS` / `APPARATUS_SIGN_MACOS`
   equals `enabled`. Each contains the concrete step shape for its platform
   (Windows: Authenticode over the `.ps1` with a timestamp server; macOS:
   Developer ID signing and notarization slots for the future `.pkg`, plus
   what applies to the shell script today) with clearly marked
   `OPERATOR:` placeholders where certificate material is referenced. Signed
   outputs, when produced, replace the unsigned artifacts in the Release and
   are re-listed in `SHA256SUMS`.
3. No certificate, key, password, or secret value appears anywhere in the
   repository; signing secrets are referenced by name only, through a GitHub
   environment documented in the runbook. With both variables unset, a
   dry-run of the release workflow behaves exactly as it did after PR-21
   plus the checksum step.
4. `docs/signing-runbook.md` covers, as explicit operator steps: certificate
   options and trade-offs (standard vs EV code-signing and cloud signing
   services for Windows; Apple Developer ID plus notarization for macOS);
   acquisition and secure storage (GitHub environment secrets or a cloud
   signing service — never this repository); timestamping; the SmartScreen
   reality that a valid signature still accrues reputation over time (EV or
   established reputation shortens it); the AppLocker/WDAC reality that
   publisher rules need a stable certificate subject across releases;
   notarization stapling; and the exact procedure to flip each gating
   variable on and verify with a dry-run first.
5. `docs/it-onepager.md` is genuinely one page — objective check: at most
   600 words of body text — addressed to an IT reviewer, in ADR-0001
   vocabulary, naming no AI app brands. Sections, in order:
   what gets installed and where (user scope only: uv, a uv-managed Python,
   `apparatus-core` as a uv tool, git if already present, with the actual
   per-OS user-profile paths); where workspace data lives
   (`C:\Projects\Apparatus` / `~/Projects/Apparatus`, plain files, never
   inside sync-redirected folders); what leaves the machine and via what
   channel (Apparatus makes no post-install network calls; content leaves only
   through an explicit user-approved external channel, such as AI-app sharing,
   export/copy/publish/upload, send-shaped handoff, or one-way snapshot export;
   install-time downloads listed with their sources); the privacy model summary per
   ADR-0004 (label at write, enforce at egress, credential floor never
   relaxed, private mode, external actions are drafts until approved);
   receipts (`System/receipts/` — every check, redaction, snapshot, and
   egress decision is reviewable); and clean uninstall (remove the uv tool,
   remove uv, delete or archive the workspace folder — nothing system-wide
   to undo).
6. Every claim in the one-pager is true of the code as shipped at this PR;
   where a capability is pending (signing, installer executables), the
   one-pager says so rather than promising it.
7. The one-pager states exactly what the credential floor blocks and where
   receipts live, as ADR-0004 requires of it.
8. `installer/README.md` links `docs/it-onepager.md` and
   `docs/signing-runbook.md` and states current signing status (unsigned
   scripts, checksums published, signing pipeline gated off pending
   certificate).
9. The status table in `docs/plan/README.md` is updated in this PR.

## Conformance and tests

- No conformance fixtures are added or changed; workspace protocol behavior
  is untouched.
- `uv run pytest` green is required, including the PR-22 dry-run smoke test,
  which must be unaffected.
- Verification is by rehearsal and review: run the release workflow once via
  `workflow_dispatch` with both signing variables unset and record in the PR
  description that behavior matched PR-21 plus checksums; a reviewer checks
  the one-pager line-by-line against ADR-0004/0005 and the actual installer
  behavior.

## Out of scope

- No certificate purchase or enrollment; acquisition is an operator step in
  the runbook.
- No actual signing or notarization runs; jobs stay gated off in this PR.
- No `.exe`/`.pkg` wrapper builds (see Open decisions).
- No changes to bootstrap script behavior (PR-22 owns that).
- No certification matrix or per-app quickstarts (PR-24).

## Dependencies

- PR-22 (bootstrapper v1), per the status table in `docs/plan/README.md`.

## Open decisions

- **Specification ambiguity — outbound wording:** acceptance criterion 5's
  original “nothing except” wording conflicts with the landed one-way snapshot
  export. The smallest truthful default is: Apparatus makes no post-install
  network calls; content leaves only through an explicit user-approved external
  channel, such as AI-app sharing, export/copy/publish/upload, send-shaped
  handoff, or one-way snapshot export.
- **Specification ambiguity — Windows signing provider:** certificate vendor
  remains open while signing must be configuration rather than engineering.
  The smallest provider-neutral boundary is an operator-provisioned Windows
  runner with a hardware- or cloud-KSP-backed certificate in its CurrentUser
  certificate store. Job routing uses fixed repository-level self-hosted runner
  labels because environment variables are unavailable when GitHub schedules a
  job. Protected environment variables supply only certificate subject,
  thumbprint, and timestamp URL after the job reaches the gated environment;
  the workflow resolves native `signtool` below the trusted Windows SDK path.

- Installer-executable wrapping technology (`.exe`/`.pkg` around the
  scripts): genuinely undecided and entangled with certificate logistics
  (design brief §14). Smallest reversible default, taken here: sign the
  scripts themselves (Authenticode supports `.ps1` directly; macOS gets a
  signed `.pkg` only once wrapping is chosen) and keep the pipeline's signing
  jobs artifact-shaped so a wrapper step can be inserted before them later
  without restructuring. Record the wrapper question against §14 if it is
  not already listed there.
- Certificate vendor and timing remain operator decisions; the runbook
  documents options, not a choice.
