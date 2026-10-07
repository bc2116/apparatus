# PR-64 — Install and repair the Mailbox Survey Skill

## Outcome

Make the first optional module usable in an enrolled work area through its
existing separate package. Add `status`, `install`, and `repair` to
`python -m apparatus_mailbox_survey ACTION WORKAREA`. Keep `validate REPORT`
unchanged. Package presence and deployed Skill state remain distinct.

This focused slice only creates missing, exact released assets and reports
existing state. It never overwrites or removes an existing file. Update/removal
with old-version ownership and installer-environment qualification belong in
the next slice. Do not describe this as a complete lifecycle yet.

## Minimal contract

The module owns exactly these two candidate paths when their content matches
its packaged release bytes:

- `.agents/skills/apparatus-mailbox-survey/SKILL.md`
- `.agents/skills/apparatus-mailbox-survey/references/report-format.md`

Use the corresponding packaged resources; validate their portable Skill format
before deployment. Do not copy synthetic samples or example reports into the
work area. No source bodies, user configuration, Memory, Library, ownership
markers, snapshots or receipts are created. No new managed record kind or
generic core registry is introduced.

`status` is read-only and reports package ID/version, each fixed relative asset
path and missing/current/modified state; aggregate absent/current/partial/
conflict. Unsafe or invalid work areas are failures, not empty installations.
Package version is not asserted to be a durable deployed-version record.

`install` and `repair` share idempotent behavior: preflight every destination;
exact current bytes remain untouched, missing files are created, any modified,
foreign, malformed or unsafe occupant stops before writes. Preserve unrelated
files and directories. A partial installation with one exact current file can
be repaired; a partial installation containing edited bytes is a conflict.

Require an explicitly enrolled work-area root and reject a bound-project root
with a clear work-area instruction. Reuse the installed core's retained-root
filesystem and layout primitives; do not add a weaker pathname-only writer.
Use a module-local bounded, nonblocking POSIX reader for retained anchors:
the released core reader alone can block on a substituted FIFO. Keep the
shared core package unchanged and qualify the adapter against released core.
The compatible core dependency is optional for standalone report validation,
but required for these deployment commands. Missing core means unavailable;
never silently install a dependency or choose a different work area.

Retain root/enrollment and immediate parent identities throughout preflight,
creation and validation. Do not follow symlinks/junctions or unsafe final files.
Validate all fixed sources/destinations before any publication. On error,
compensate only exact files/directories created by this invocation, preserve
concurrent substitutions, and report the failure honestly. No success if
enrollment, root or retained parent changed before completion.

This deploys generic shipped guidance on an explicit request; it creates no
task-derived content and is permitted under no-save. Module assets remain
outside core managed recovery. Native automatic discovery remains unqualified;
the assistant can read the deployed canonical body explicitly.

Exit 0 means status or deployment completed; 1 means an actionable content
conflict; 2 means invalid invocation, missing dependency or unsafe/unavailable
work area. Output fixed relative paths and bounded repair guidance, not source
content or machine-specific absolute paths. No external calls.

## Ownership and validation

Own new package deployment code/tests, the module command dispatcher, optional
dependency declaration, package README, this prompt, module specification,
sequence and plan index. Bump the module to 0.1.1; core and starter stay unchanged.
Keep the validator usable without core installed.

Tests must cover absent/current/partial/conflict, repeated install, exact
missing-file repair, user-edit/foreign preservation with no partial writes,
invalid enrollment, bound project, no-save-safe generic content, symlink and
Windows junction boundaries, parent/enrollment substitution and injected
failure compensation. Verify no provider/network calls, core init preservation
of these unowned module files, and honest lack of snapshot coverage.

Run focused package tests, `uv run pytest`, and Windows CI. Build and test the
wheel in isolation, both validator-only and with compatible published core.
Demonstrate explicit Skill use from a disposable enrolled work area. Set the
plan row to `✅ landed` in this PR and follow normal remote delivery.
