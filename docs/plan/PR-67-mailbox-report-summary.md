# PR-67 — Read a concise Mailbox Survey summary

## Outcome

Add `python -m apparatus_mailbox_survey summary REPORT` to make an existing
requested report easy to review. It reads one supplied local report and writes
only its summary to standard output. It does not survey mail, run a model,
deploy a Skill, or save workspace content. Keep report validation independent
of Apparatus Core and preserve the report v1 schema.

## Contract

Read the same bounded regular-file input as `validate`. Reuse the strict YAML
loader, limits and validation. Invalid reports produce the existing bounded,
value-free findings and exit 1, with no partial summary. Read failures and
invalid command usage exit 2; valid summaries exit 0. Existing validate output
and status/install/repair behavior remain unchanged.

Produce deterministic, human-readable plain text containing:

- The report's declared source, scope description and coverage claim.
- Known total or `unknown`, reviewed, unavailable, skipped and unassessed counts.
- Category names with their reviewed example counts, and the uncategorized
  reviewed-item count. State that categories can overlap: do not sum them as
  distinct messages or extrapolate to the whole mailbox.
- The reported coverage gaps, including an explicit none-reported case.
- A clear statement that the summary reflects report claims and does not verify
  evidence, authority or actual mailbox coverage.

Do not include message IDs, source locators, item summaries, category
descriptions or proposed next actions. Treat strings as untrusted display data:
escape control characters, line breaks and Unicode bidirectional/formatting
controls so they cannot inject terminal commands, extra headings or fake status
lines. Keep each displayed input string to at most 240 characters before
escaping, with explicit truncation; show at most 20 categories and 20 gaps, with
exact omitted-entry counts. The complete original report remains unchanged.
Do not silently treat missing coverage as zero or report complete coverage as
verified. Preserve intentional non-ASCII names where safely displayable.

## Scope and acceptance

Own the module report parser/summary helper, command dispatcher, focused tests,
package README, module spec, plan/sequence and concise synthetic acceptance.
Bump only the module package to 0.1.3 after PR-66; core/starter and deployed Skill
resources stay unchanged. No lifecycle mutation or external calls are added.

Tests cover a representative valid supplied sample, overlapping categories,
unknown totals and partial coverage, empty complete scopes, no categories,
all-invalid report behavior, read limits/nonregular files, output truncation,
terminal/control-character escaping, unchanged bytes/mtime and no network or
Core dependency. Existing validation tests must pass unchanged.

Build a wheel and exercise summary in isolation without Core. Run focused module
tests, full `uv run pytest` and current-head cross-platform CI before remote
merge. Record limitations, update the plan row to `✅ landed` in the same PR,
and retain the separate future update/removal qualification boundaries.
