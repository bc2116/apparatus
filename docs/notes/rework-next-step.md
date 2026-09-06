# Resume the lean rework

PR-32 removes the sharing gate. PR-33 adds current Memory recall and explicit
correction, outdated status, and forgetting. Their plan rows become effective
only after each PR merges. Check the remote PR state before continuing.

Budget checkpoint: PR-32 is merged and its Windows CI passed. PR-33 has passed
independent review, the integrated 572-test macOS suite (38 skips), and payload
build. It is saved as a draft PR while the session pauses at the requested
remaining-usage threshold. First inspect PR-33 CI, resolve any failure, mark it
ready, and merge the verified head before cutting PR-34. No reset was consumed.

Next cut **PR-34 for R2b, task retention**, from the merged source. Do not resume
the held PR-24 certification or repeat the product-choice interview. The owner
approved the product direction in ADR-0006; remaining implementation slices are
in `docs/plan/rework-sequence.md`.

## Source facts to carry forward

- `commands/memory.py` now handles lifecycle plus add/label; `memory.py` supplies
  current-record reads. `recall.py` still handles Library only.
- The private profile blocks all People and labeled Facts. It still permits
  unlabeled task facts. Preserve existing restrictions during migration.
- `commands/profile.py` persists setup answers and seeds People/Goals.
  Forgotten markers suppress automatic seeding at the same path, but do not
  erase those stored answers or prevent a separate explicit new record.
- `library/ingest.py` writes extracted text/metadata in external caches;
  `library/index.py` persists SQLite derived from those extractions.
- `recall.py` currently persists queries/source paths in receipts. Credential
  redaction alone does not implement task-content suppression.
- `receipts.py`, snapshot labels/Git messages, snapshots themselves, and backup
  exports require an explicit scope decision. Exports preserve historical bytes.

R2b must define task identity/resumption and a content-free control marker,
then carry that contract through all managed writers and future learned Skills,
cards, and history. Requested deliverables remain possible; automatic Memory
or derivative capture does not. Explicit Library registration is a separate
user instruction. Do not promise control over provider chats, historical exports,
or native writes that bypass managed commands. Keep operational evidence to
necessary metadata. Specify safe migration and failure behavior before coding.

## Delivery checkpoint

Use one focused branch/PR, keep canonical and embedded payload synchronized,
preserve user customizations, and verify required tests and platform CI before
merge. The migration helpers use retained immediate-parent anchors because
reopening nested directories conflicts with Windows owned handles. Keep that
regression covered. Actual AI app certification and signed release remain later.
