# Release runbook

This runbook is for a repository operator. It describes release preparation;
it does not store credentials or account identifiers.

## One-time operator setup

1. Create the `apparatus-core` project on PyPI.
2. In PyPI, add a trusted publisher for this repository. Populate its **Owner**
   and **Repository** fields with this repository's GitHub owner and name, then
   set its workflow filename to `release.yml` and its environment name to
   `pypi`.
3. In GitHub, create the repository environment named `pypi`. Apply the
   approval rules appropriate for releases.
4. Leave the repository variable `APPARATUS_RELEASE_MODE` unset. An unset value
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
3. Download the `apparatus-release-<version>` workflow artifact. Confirm it
   includes the payload ZIP, `apparatus-core` source distribution, wheel, and
   release notes.
4. Confirm that no GitHub Release was created and that PyPI was not changed.
5. If practical in an operator-approved setting, use a dedicated rehearsal
   version and matching tag while `APPARATUS_RELEASE_MODE` is unset. Confirm the
   resulting GitHub Release is marked prerelease and begins with the dry-run
   notice. The rehearsal tag permanently consumes that version; never reuse or
   move it.

## Publish a release

1. Land the version bump, `CHANGELOG.md` section, and release changes.
2. Confirm checks are green and the release branch is the intended commit.
3. Set `APPARATUS_RELEASE_MODE` to exactly `publish` in the repository
   variables. This is the only state that allows the trusted-publishing job to
   run for a tag push.
4. Push a new, never-before-used `v<version>` tag matching the package version.
   The pipeline rejects a mismatched tag.
5. Verify the GitHub Release attachments, release notes, and PyPI publication.
6. Return `APPARATUS_RELEASE_MODE` to an unset value after the release unless a
   subsequent approved release is immediately pending.
