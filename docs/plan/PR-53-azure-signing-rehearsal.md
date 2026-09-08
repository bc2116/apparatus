# PR-53: Repair the Azure signing rehearsal

## Problem and scope

The first authenticated Azure rehearsal stopped before signing because the
pinned action requires an absolute file path. Repository action restrictions
and GitHub's newer immutable OIDC subjects also need explicit setup guidance.

Pass the exact installer under `github.workspace` to the existing signing
action. Update the two workflow assertions and the signing runbook. Keep all
input, signature, timestamp, dry-run, and publication checks intact. Core,
payload, installers, package versions, and provider selection do not change.

## Acceptance

- The action receives only the absolute path to the downloaded installer.
- Existing workflow tests pin the new input and retain verification ordering.
- Setup guidance obtains the current OIDC subject, accounts for custom
  templates, and permits only the exact reviewed Azure action commits.
- Run focused workflow tests, `uv run pytest`, and CI; record results in
  `docs/notes/pr-53-verification.md` and mark this plan row landed in this PR.
- After merge, an authorized artifact-only rehearsal must demonstrate actual
  signing, native verification, and signed bootstrap dry-run before reporting
  Windows signing as working. A code review or unit test cannot prove it.

This is a bounded release repair: frontier authorship and independent frontier
review at medium effort, with no nested delegation.
