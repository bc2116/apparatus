# PR-33: Correct, retire, and forget Memory records

Implement R2a of ADR-0006 on `pr-33-memory-lifecycle`, after PR-32. R2 is
split into this bounded record-lifecycle change and a later task-retention
change. Do not imply per-task retention has shipped or alter private profiles.

## Contract

1. Give Facts and People an optional `status`: `current`, `outdated`, or
   `forgotten`. Missing status means current; no bulk rewrite of legacy records.
   Update normative schema, validator, and conformance deliberately together.
2. Add `apparatus memory correct WORKSPACE RECORD --from-file PATH` using a
   complete replacement Markdown record of the same kind. Preserve metadata
   supplied by the user; explicitly document that omitted fields are removed.
   Set current status, apply the existing credential floor and labels, and
   retain the existing private-profile restriction. Never copy prior content
   into history notes or receipts. Require a real existing record.
3. Add `apparatus memory outdated WORKSPACE RECORD` to mark existing content
   outdated without presenting it as current. It must not reactivate a forgotten
   record. Add `apparatus memory forget WORKSPACE RECORD` to replace the file
   with only its schema and `status: forgotten`, with no body or other metadata.
   This tombstone prevents the current profile-seeding path from recreating the
   same record. Repeat forgetting is safe. No forgotten title/path in routine
   success output. Do not claim filename, profile-answer, backup, or Git-history
   erasure. Re-creation from an explicit new user instruction is distinct.
4. Add `apparatus memory recall WORKSPACE QUERY` with deterministic text matching
   and a small bounded result limit. Return current records only, with source
   paths and text; filter lifecycle and ignore rules before returning any title,
   path, or body. Keep Library `apparatus recall` behavior unchanged. No new
   index/database, model call, automatic correction, or receipt per read.
   Malformed/unsafe records produce a clear error, not false full coverage.
5. Use existing retained-root transaction and publication proofs for writes.
   Validate kinds, filenames, UTF-8, record shape, containment and symlink/reparse
   boundaries. Preserve concurrent replacements/edits on failure; roll back only
   invocation-owned mutations and redaction receipts. Explicit targeted edits
   may reach ignored records; ignore controls automatic recall enumeration.
6. Update assistant guidance to consult current Memory and avoid using outdated
   or forgotten records as current. Native raw reads can still inspect outdated
   files; this is not provider-retention control. Synchronize canonical and
   embedded payload, regenerate shims, and extend original-byte migration for
   the immediately previous shipped instructions without overwriting custom text.

## Acceptance and owned paths

Core Memory lifecycle/read module, Memory CLI, record validation/check paths,
targeted safety/lifecycle/schema/profile-seeding tests, canonical/embedded
instructions and their migration/golden checks, current specs/README/changelog
and plan. No backup, snapshot, or profile-retention redesign in this PR.

Prove legacy-current compatibility, corrected source/metadata/body retrieval,
outdated and forgotten exclusion, metadata-free tombstones, no profile-seeding
resurrection, explicit correction rules, ignore filtering, credential redaction,
private-profile restrictions, concurrent-edit and symlink rejection, and rollback
on publication failure. Keep existing safety tests. Run required `uv run pytest`,
payload build, and diff checks; record platform skips separately.

Use one bounded authoring-tier worker and independent authoring-tier review for
this privacy/record mutation. Review at most two repair passes before a concrete
checkpoint. CI must pass before merge; verify remote main. Keep R2b explicitly
planned: task identity/resumption plus every managed writer and derived-content
path require a shared retention contract before claiming task opt-out support.
