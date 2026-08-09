# PR-10: snapshot and restore

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` — especially §6.5 (snapshots and recovery),
  §14 (open questions: portable git)
- `docs/adr/ADR-0001-vocabulary.md` — snapshot/restore terms; banned words
- `docs/adr/ADR-0002-protocol-and-state.md` — decision 6 (snapshots) and 5
  (receipts)
- `docs/adr/ADR-0005-distribution-and-packaging.md` — degraded mode is
  reported honestly
- `docs/plan/README.md`
- `docs/plan/PR-08-cli-skeleton-doctor.md` — registry, exit codes, machine
  report
- `docs/spec/workspace.md` — placement on disk; snapshot export note

## Objective

`apparatus snapshot` and `apparatus restore` deliver the user promise "you
cannot break this" (design brief §6.5) per ADR-0002 decision 6: local git
under the hood, initialized inside the workspace when absent, with a generic
author identity; a snapshot is add-all plus a commit carrying a human-readable
label; restore lists snapshots and returns the workspace to any of them by id,
always taking an automatic pre-restore snapshot first so every restore is
itself reversible. When git is missing the verbs degrade gracefully — an
explicit unavailable state in the machine report and a receipt, never a crash
or a silent skip — and no user-facing text ever describes the workspace as a
git repository.

## Deliverables

- `packages/apparatus-core/src/apparatus_core/snapshots.py` — engine:
  availability probe, repo initialization, `take_snapshot`, `list_snapshots`,
  `restore_snapshot`; all git invocations captured, never streamed to stdout.
- `packages/apparatus-core/src/apparatus_core/commands/snapshot.py` and
  `packages/apparatus-core/src/apparatus_core/commands/restore.py` — argparse
  wiring per the PR-08 registry contract.
- `packages/apparatus-core/src/apparatus_core/receipts.py` — created here if
  PR-09 has not landed yet, otherwise reused as-is (whichever PR lands first
  owns creation; same `write_receipt` API either way).
- `packages/apparatus-core/pyproject.toml` — modified: register both verbs in
  the `apparatus.commands` entry-point group.
- No record-schema changes: snapshot and restore receipts use the `snapshot`
  and `restore` event values already pinned in the PR-04 receipt `event`
  enum; `docs/spec/records.md`,
  `packages/apparatus-core/src/apparatus_core/records.py`, and the golden
  example records are untouched.
- `packages/apparatus-core/tests/test_snapshots.py`
- `docs/plan/README.md` — modified: PR-10 status row only.

## Acceptance criteria

1. `apparatus snapshot <workspace> [--label TEXT]` initializes a git repo
   inside the workspace if absent, stages everything, and commits with the
   label as message (default label: "Snapshot taken <UTC timestamp>"). Author
   identity is repo-local only: `user.name` "Apparatus" and a generic
   non-personal email; the user's global git config is never read for
   identity nor ever modified. Exit 0 on success.
2. With no changes since the last snapshot, the verb reports "no changes
   since the last snapshot" (plain language), creates nothing, and exits 0.
3. `apparatus restore <workspace> --list` prints each snapshot's id (short
   hash presented only as "snapshot id"), UTC date, and label, newest first.
4. `apparatus restore <workspace> <id>` first takes an automatic snapshot
   labeled "Before restore to <id>", then makes the workspace content
   (everything except the `.git` directory) exactly match the target
   snapshot — including deleting files created after it and restoring files
   deleted since. History is preserved: the pre-restore snapshot remains
   restorable afterwards.
5. An unknown snapshot id exits 1 with an actionable message that suggests
   `--list`. A path that is not a workspace directory exits 2.
6. Successful snapshot and restore runs each write a receipt under
   `System/receipts/` via `write_receipt` (`event: snapshot` and
   `event: restore` respectively, plus label and snapshot id).
   Ordering matters because receipts are workspace content: `snapshot`
   writes its receipt first so the snapshot includes it; `restore` writes
   its receipt after content is restored so the receipt survives.
7. Git missing (probe fails): both verbs print a plain-language explanation
   ("Snapshots are unavailable on this machine..."), write a receipt
   recording the unavailable outcome (under the invoking verb's event,
   `snapshot` or `restore`), update `System/machine-report.md`'s
   `snapshots:` field to `unavailable` when that file exists, and exit 1.
   Never a traceback, never a silent no-op.
8. No raw git output reaches stdout or stderr in any path; all subprocess
   output is captured. User-facing text uses only ADR-0001 vocabulary:
   "snapshot", "restore", "workspace" — never "commit", "revert", "reset",
   "repository", or "checkout".
9. The availability probe reuses PR-08's `detect.py` git detection rather
   than duplicating it, and is injectable for tests.
10. Stdlib only (subprocess, shutil, pathlib); no GitPython or similar — a
    dependency is unjustified when the calls are five git subcommands.
11. `uv run pytest` is green.

## Conformance and tests

- No conformance fixture changes: the payload, golden manifest, and golden
  example records are untouched, as are `docs/spec/records.md` and
  `records.py` — the `snapshot` and `restore` event values are already in
  the receipt `event` enum PR-04 pinned. Every existing constraint stays
  enforced; nothing is loosened.
- `tests/test_snapshots.py` runs against temp directories (real git when
  present on the test machine):
  - snapshot → modify/add/delete files → snapshot → restore to first id →
    tree bytes match the first state exactly, `.git` excluded from
    comparison;
  - the automatic pre-restore snapshot exists and restoring to it returns
    the later state;
  - no-changes snapshot creates no new snapshot id;
  - unknown id and non-workspace path exit codes;
  - receipts written for snapshot, restore, and the unavailable path.
- The no-git path is simulated by pointing the injectable probe/`which` at
  an empty directory PATH (monkeypatching), asserting: exit 1, plain-language
  message, receipt written, machine report field updated when present, and
  no exception.
- A test asserts stdout for a successful run contains no git vocabulary.

## Out of scope

- One-way snapshot export to synced storage — `docs/spec/workspace.md`
  mentions it alongside snapshots, but it is not in this PR; flag it to the
  plan owner rather than building it.
- Bundling or installing portable git (PR-22 territory; see Open decisions).
- Scheduled or automatic end-of-procedure snapshots — procedures call the
  verb; nothing here hooks into them.
- Any `.gitignore`, branch, remote, or merge behavior. Snapshots are a
  single linear sequence; no remotes are ever configured.
- Changing `doctor` beyond what PR-08 already wrote (the `snapshots:` field
  already exists in the machine report).

## Dependencies

- PR-08 (per `docs/plan/README.md`). PR-09 is not required; see the
  `receipts.py` deliverable note.

## Open decisions

- Windows portable-git strategy (bundled MinGit vs. detect-and-skip) is an
  open question in design brief §14 and stays open here: this PR implements
  detect-and-degrade only, and must not preempt the decision. Note it in the
  PR description; resolution belongs to PR-22.
