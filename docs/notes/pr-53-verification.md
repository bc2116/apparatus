# PR-53 verification

The authenticated artifact-only rehearsal
[34229109350](https://github.com/bc2116/apparatus/actions/runs/34229109350)
passed Azure OIDC login, then rejected the relative installer path before
signing. The action now receives the exact installer under `github.workspace`,
as required by its pinned input contract. Existing checks remain unchanged.

The runbook now covers the effective OIDC subject and selected-actions policy.
It retains profile-scoped access, protected environment branches, and exact
issuer/audience matching. It contains no publisher configuration or secrets.

Focused workflow tests passed (17 tests) after `uv sync --all-packages`.
Independent frontier review found no actionable issues. `git diff --check`
passed, and product, payload, conformance fixtures, installer sources, and
package version are unchanged.

The required `uv run pytest` completed with **1278 passed, 38 skipped in
549.41s** on macOS. CI supplies final-commit platform verification. Live signing
will be retried after the reviewed fix lands; this repair alone does not
establish a signature or public release.
