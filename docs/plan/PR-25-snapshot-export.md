# PR-25: Snapshot export (backup) v1

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` — especially §5 (backup is a one-way snapshot
  export to synced storage, never live sync)
- `docs/adr/ADR-0001-vocabulary.md` — snapshot/workspace terms; banned words
- `docs/adr/ADR-0002-protocol-and-state.md` — decision 7 (sync-hostile by
  design; backup is a one-way snapshot export)
- `docs/adr/ADR-0005-distribution-and-packaging.md` — degraded mode is
  reported honestly
- `docs/plan/README.md`
- `docs/plan/PR-04-record-schemas.md` — receipt schema, the pinned `event`
  enum, and the receipt filename convention
- `docs/plan/PR-08-cli-skeleton-doctor.md` — registry contract, exit codes
- `docs/plan/PR-10-snapshot-restore.md` — snapshot engine, receipts, the
  no-git degraded path
- `docs/spec/workspace.md` — "Placement on disk" (the backup pointer this PR
  fulfils)

## Objective

The workspace is sync-hostile by design: live state never sits inside a file
sync engine, and the promised backup path is a deliberate, one-way snapshot
export to synced storage (design brief §5; `docs/spec/workspace.md`,
"Placement on disk"). This PR delivers that path. `apparatus backup export
<workspace> <destination>` produces a dated, self-contained archive of the
entire workspace at a destination folder — typically inside the user's synced
storage — taking a snapshot first when snapshots are available and working
without git when they are not. The verb is strictly one-way: it writes one
archive and never reads destination content back. Restoring from a backup
archive is documented as a manual unzip in this PR; a guided restore flow is
deliberately not built here.

## Deliverables

- `packages/apparatus-core/src/apparatus_core/backup.py` — export engine:
  UTC archive naming, collision suffixing, zip creation, snapshot-first
  behavior via the PR-10 engine, receipt writing.
- `packages/apparatus-core/src/apparatus_core/commands/backup.py` — argparse
  wiring per the PR-08 registry contract: a `backup` verb with an `export`
  subcommand taking explicit `<workspace>` and `<destination>` arguments.
- `packages/apparatus-core/pyproject.toml` — modified: register the verb in
  the `apparatus.commands` entry-point group.
- `docs/spec/workspace.md` — modified: the "Placement on disk" backup note
  gains one sentence stating how a backup archive is restored (unzip it to a
  fresh folder; no guided restore exists in v1).
- `packages/apparatus-core/tests/test_backup.py`
- `docs/plan/README.md` — modified: PR-25 status row only.

## Acceptance criteria

1. `apparatus backup export <workspace> <destination>` writes
   `apparatus-backup-YYYY-MM-DD-HHMMSS.zip` (UTC timestamp, all lowercase)
   into the destination directory and exits 0. The archive contains the
   entire workspace tree, hidden files included — `System/`, receipts, and
   a standalone snapshot history directory when present — so a restored backup
   keeps its snapshots. A workspace whose snapshot history is stored externally
   (as in a linked git worktree) is rejected with a clear explanation; see Open
   decisions. Nothing is excluded and nothing outside the workspace root is
   included; every archive produced is self-contained.
2. Snapshot-first: when snapshots are available (reusing the PR-10
   availability probe, injectable for tests), the verb takes a snapshot
   labeled "Before backup export <UTC timestamp>" before archiving, so the
   archive captures a restorable state. PR-10's no-change semantics apply
   unchanged: an untouched workspace produces no new snapshot and that is
   not an error.
3. Works without git: when snapshots are unavailable, the verb still
   produces the archive and exits 0, telling the user in plain language that
   the backup contains the workspace exactly as it is now, without a fresh
   snapshot. Never a crash, never a silent skip.
4. Strictly one-way: the verb never reads destination content. No listing
   or pruning of old archives, no parsing of existing archives, no restore
   path, and nothing at the destination is ever used as input to the
   workspace. The only destination operations are retaining a no-follow anchor,
   exclusively creating the new file, and writing that file. An exclusive-create
   collision retries with `-2`, `-3`, … before `.zip` (mirroring the receipt
   filename collision rule), without listing or reading the destination.
5. A successful export writes a receipt under `System/receipts/` via
   `write_receipt` with `event: backup-export` — a value already present in
   the enum pinned by PR-04; this PR adds nothing to that enum. The receipt
   records the archive filename, the destination path, the archive size, and
   the pre-export snapshot id when one was taken. It is written after the
   archive lands, so a failed export leaves no success receipt; the receipt
   itself is captured by the next export.
6. Argument validation, per the PR-08 exit-code convention: a `<workspace>`
   path that is not a workspace directory exits 2; a `<destination>` that
   does not exist or is not a directory exits 2 with an actionable message;
   a destination inside the workspace exits 2 (an archive must never be
   written into the tree being archived).
7. Success output is plain language: archive name, destination, size, and
   one sentence on restoring ("To restore, unzip this archive into a fresh
   folder."). ADR-0001 vocabulary throughout — workspace, snapshot, backup —
   never "repository", "commit", or "checkout"; no raw git output reaches
   stdout or stderr in any path.
8. Stdlib only (`zipfile`, `pathlib`, `datetime`); all timestamps UTC. No
   new runtime dependencies.
9. `uv run pytest` is green.

## Conformance and tests

- No conformance fixture changes: the payload, golden manifest, golden
  example records, and the receipt `event` enum are all untouched
  (`backup-export` is already pinned by PR-04).
- `tests/test_backup.py` runs against temp directories for both workspace
  and destination (real git when present on the test machine):
  - export → unzip to a fresh temp folder → tree bytes match the workspace
    at export time, hidden files included;
  - the pre-export snapshot exists and is restorable when git is present;
  - the no-git path (injectable probe pointed at an empty PATH): archive
    still produced, exit 0, plain-language message, receipt written;
  - one-way proof: a pre-existing unrelated file at the destination is
    byte-identical after the run, and no destination file is ever opened
    for reading;
  - same-second collision produces the `-2` suffix;
  - non-workspace path, missing destination, and destination-inside-
    workspace each exit 2;
  - the `backup-export` receipt exists, follows the pinned receipt filename
    convention, and validates against the receipt schema.
- A test asserts stdout for a successful run contains no git vocabulary.

## Out of scope

- Any guided or automated restore-from-backup flow — restore is a documented
  manual unzip in v1; flag demand for more to the plan owner rather than
  building it.
- Scheduled or automatic backups; procedures may call the verb, but nothing
  here hooks into them.
- Retention or pruning of old archives — pruning requires reading the
  destination, which the one-way rule forbids.
- Verifying that the destination actually is synced storage; the destination
  is just a directory the user chose.
- Incremental or differential archives, encryption, or compression tuning.
- Any change to `snapshot`/`restore` behavior (PR-10 owns those verbs).
- Any change to `starter/payload/` or the golden manifest.

## Dependencies

- PR-10 (snapshot and restore), per `docs/plan/README.md` — the availability
  probe, snapshot engine, and `write_receipt` are reused, never duplicated.

## Open decisions

- **Post-write archive verification.** Re-opening the just-written zip to
  verify its central directory would catch write corruption, but it is a
  read at the destination. Smallest reversible default, taken here: no
  read-back at all — the one-way rule stays absolute and simple, and
  `zipfile`'s write-time errors are the integrity check. Revisit if real
  corrupted-archive reports appear; a self-check of the verb's own artifact
  could be added later without weakening the rule that destination content
  is never an input.
- **Linked worktree snapshot storage.** A linked git worktree represents its
  snapshot storage with a `.git` pointer to a directory outside the workspace.
  The requirements that an export contain no outside bytes and retain complete
  snapshot history cannot both hold for that shape. Smallest conservative v1
  default: reject linked-worktree exports with a clear explanation. Standalone
  `.git` directories and workspaces operating without git remain supported.
  Guided collection of external snapshot storage is not introduced here.
