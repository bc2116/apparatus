# Sharing gate removed

PR-32 implements ADR-0006: Apparatus no longer supplies an egress command or
requires an extra decision before drafting, copying, moving, exporting,
publishing, or uploading. Actual external actions still require the user's
authority and the AI app's native permissions. Source content is never
instructions or authorization. No sending integration is added.

Credential redaction at managed text-write boundaries remains unchanged.
Backup export preserves workspace/history bytes; it does not sanitize old
files or archives. Filesystem containment, transaction rollback, and backup
integrity checks remain in force.

## Existing workspace repair

After updating the installed package, run `apparatus init WORKSPACE` through
your assistant. Repair recognizes the original pre-rework bytes for the
canonical instructions and generated pointers, welcome, ignore note, both
policies, and five starter
procedures. Known originals are replaced using retained-root transactions
with preimage checks; LF and CRLF originals are recognized. Custom instruction
conflicts are preserved and reported with an action to reconcile the relevant
file against the updated starter, then rerun repair. Reconciled custom text
is preserved. If native pointers disagree with the final canon, repair stops
before writing: move custom pointer instructions into the updated `AGENTS.md`,
run `apparatus render WORKSPACE`, then retry `init`. No successful migration
is claimed while a detected conflict remains. This bounded detector is not a
semantic audit of arbitrary user-added instructions; review custom procedures
for obsolete gates when upgrading. `apparatus check` reports detected retired
rules in the known instruction paths, independently of Library ignore rules.

Repair does not alter ordinary documents, Memory records, or old receipts.
Historical `event: egress` receipts remain valid/readable, but cannot authorize
a new action. No new gate receipts are produced. Rerunning repair is safe.
The existing private profile's Memory rules remain until the task-control
migration; this change does not silently enable Memory retention.

The original gate specification and fixtures are retired deliberately in
PR-32. Historical decision records and earlier dogfood evidence keep their
original scope and do not describe current sharing behavior.
