# Release runbook

This runbook is for a repository operator. It describes release preparation;
it does not store credentials or account identifiers.

## One-time operator setup

1. Before the first package exists, use PyPI's account-sidebar **Publishing**
   page to add a **pending** GitHub Actions trusted publisher for
   `apparatus-core`. Set its project name, this repository's GitHub **Owner**
   and **Repository**, workflow filename `release.yml`, and environment `pypi`.
   PyPI creates the project and converts the pending publisher on its first
   successful publication. A pending publisher neither reserves the name nor
   creates a project before that publication.
2. In GitHub, verify or create protected `pypi`, `signing`, and `release`
   environments with the required reviewers for their respective gates. The `release`
   environment protects the public GitHub Release job; creating an environment
   name alone is not evidence that protection is configured. Permit the
   protected default branch for signed manual rehearsals and `v*` tags for
   releases in the signing environment's deployment-branch policy.
3. Leave the repository variable `APPARATUS_RELEASE_MODE` unset. An unset value
   is dry-run mode. Only set it to exactly `publish` after a successful
   rehearsal and explicit release approval.

Trusted publishing uses GitHub's short-lived identity token. Do not add a PyPI
token, password, or other publishing credential to this repository, its
secrets, or its variables.

## Dry-run rehearsal

1. Confirm the planned version in
   `packages/apparatus-core/pyproject.toml` and the matching changelog heading
   `## v<version>`.
2. From the branch containing `release.yml`, run the **Release** workflow with
   **Run workflow**. A manually dispatched run is always dry-run, even if the
   repository variable says `publish`.
3. Run the rehearsal with macOS signing and exactly one selected Windows
   signing provider enabled and approved through the protected `signing`
   environment. Download the
   `apparatus-release-<version>` workflow artifact. Confirm it
   includes all seven distributables: payload ZIP, `apparatus-core` source
   distribution, wheel, both flat bootstrap scripts, Windows `.exe` and macOS
   `.pkg`, plus release notes and `SHA256SUMS`. Verify the checksums and record
   each wrapper's observed signing status; a skipped signing job is not a signature.
   Record the tested commit/version, native build tools and remaining coverage
   gaps. The bootstrap resolves PyPI independently; a rehearsal wheel is not
   evidence of the currently published package.
4. Confirm that no GitHub Release was created and that PyPI was not changed.
5. A tag pushed in dry-run mode also produces workflow artifacts only. It must
   not create a public GitHub Release or change PyPI. Use manual dispatch for
   rehearsals; never reuse or move a release tag.

## Publish a release

1. Land the version bump, `CHANGELOG.md` section, and release changes.
2. Confirm checks are green and the release branch is the intended commit.
3. Confirm the protected `pypi`, `signing`, and `release` environments have
   their required-reviewer rules in place. The publish path requires macOS and
   exactly one Windows signing provider to succeed; it cannot assemble a
   publish release from skipped, failed, cancelled, duplicated, or unexpected
   signing results.
4. Set `APPARATUS_RELEASE_MODE` to exactly `publish` in the repository
   variables. This is the only state that allows the trusted-publishing job to
   run for a tag push.
5. Push a new, never-before-used `v<version>` tag matching the package version.
   The pipeline rejects a mismatched tag. PyPI publication is public, and a
   published package version cannot be reused.
6. After PyPI accepts the package, download the signed artifacts from that same
   workflow run. On each supported OS, perform actual install-and-repair
   validation against the published package. Record the results before
   approving the protected `release` environment.
7. Approve the `release` environment only after those validations pass, then
   verify the GitHub Release attachments and release notes. The public
   installer is signed from this first release.
8. Return `APPARATUS_RELEASE_MODE` to an unset value after the release unless a
   subsequent approved release is immediately pending.

## Native install-and-repair acceptance

After the tagged workflow's PyPI job succeeds, manually dispatch **Release**
with `acceptance_run_id` set to that workflow's numeric run ID. This selects
acceptance only: no build, signing, package publication or public Release runs.
Leave the input empty for an ordinary signed rehearsal.
The optional platform choice defaults to both; choose Windows or macOS to
repeat only an unresolved platform while preserving the other platform's
passing receipt for the same source and artifact hashes.

The acceptance path checks the same repository, version tag, source commit,
successful signing/publication jobs, final artifact and PyPI distribution hashes.
It then runs the unchanged signed installers twice on fresh Windows x64 and Mac
runners, verifies the installed version, restores one removed shipped file and
checks that a synthetic project file survives. The Mac test requires an actual
console session and clean owned home; it never redirects the install into an
artificial profile. A missing session or preexisting workspace stops the check.

Download the two `apparatus-native-acceptance-*` receipts. Both must report
success with the intended source run and version before approving the original
tagged workflow's protected `release` environment. These checks cover real native
command-line installer execution; interactive installer presentation remains a
separate observation. Preserve any unavailable platform result as a coverage gap.

Windows acceptance removes an inherited `PSModulePath` from child processes so
PowerShell 7's workflow host cannot pass incompatible modules through Python
to Windows PowerShell. This changes only the test process environment. Signature
status, signer and timestamp checks remain required before installer execution;
fixed diagnostic fields identify a verification failure without raw command
output. Receipt artifact names include the run attempt to preserve retry evidence.
