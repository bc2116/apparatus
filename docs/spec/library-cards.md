# Library cards and completion offers

A card is a small assistant-written description of one selected original. The
original stays authoritative and project-local. Cards help discovery; search and
recall still cite validated original extraction, never card prose as evidence.
No model is invoked by the core. An explicit addition in a saving task authorizes
the assistant to read available extraction and write a supported card without
another approval step. A bare CLI addition reports the card outcome separately
from registration and extraction; it cannot generate prose.

## Evidence and commands

`library card WORKAREA RELATIVE_PATH` returns JSON with `source`, `card_status`
and `evidence_status`. Successful extraction adds its available `text`,
`source_sha256`, `text_sha256`, `extractor_version` and a coverage caveat. Summary
and topics appear only for a current card. Status is `absent`, `current`, `stale`,
`unavailable`, `invalid` or `unselected`. Current means matching provenance and
valid format; it does not establish semantic correctness or complete extraction
of every page, image or table. The assistant compares claims against the evidence,
preserves uncertainty and known limits, and omits unsupported claims.

The read opens only the selected original and its exact extraction metadata/text
pair, with catalog metadata validation. It performs no source discovery, ingest,
cache creation, refresh or receipt write. The shared `index.selected_evidence`
context retains the source, catalog, cache directory and exact pair/absence
proofs through final validation; search uses the same per-source validation.
Missing, unsupported, empty, failed, corrupt or stale extraction cannot produce a
current card or fabricated coverage. An unavailable response never includes an
old summary. Re-ingest may repair evidence but does not regenerate prose.

`apparatus --task ID library card WORKAREA RELATIVE_PATH --stdin` accepts JSON or
YAML with exactly `summary`, `topics`, `source_sha256`, `text_sha256` and
`extractor_version`. Source paths are relative to the resolved work area even
when invoked from a bound project. Enrollment and an explicit saving task are
required before candidate input is read; the existing task-start/enrollment
repair action is returned otherwise. No-save rejects publication even inside a
requested Library or snapshot exception. Existing evidence/card reads remain
permitted and write-free. Feature-off and ignore rules prevent publication.

## Durable format

One UTF-8 YAML file lives at `System/library/cards/KEY.yaml`; KEY is the full
`Source.key` hash, including the existing safe native spelling for implicit
Library sources. No card directory or record ships in the starter payload.
The closed mapping contains exactly:

```yaml
schema: apparatus/library-card@v0
source: project/report.md
source_sha256: <original bytes SHA-256>
text_sha256: <available extracted UTF-8 text SHA-256>
extractor_version: <validated extraction version>
summary: <short supported paragraph>
topics: [<discovery term>]
```

Hashes are 64 lowercase hexadecimal characters. Summary is nonblank and at most
1200 characters; topics are at most eight distinct nonblank strings, each at most
64 characters. The version is 1–128 characters. Unknown/duplicate keys, aliases,
unsafe paths and filename disagreement are rejected. There is no stored current
flag, absolute path, task query, timestamp, transcript or semantic-verification
claim. Candidate summary/topics pass the existing credential redactor before any
persistence; only its existing redaction receipt is emitted when needed.

Publication retains source, selection, cache and destination proofs. Provisional
parents are invocation-owned and validated through publication, receipt settlement
and the final boundary. `Catalog(transaction_compatible=True)` is used here and
in restore to coexist with exact transaction proofs; ordinary reads keep their
original mode. Exact clean repeats are validated no-ops. Repeated candidates that require
redaction retain the required metadata-only redaction receipt even when the
sanitized card is unchanged. Replacement uses exact
identity/bytes CAS and compensation; foreign or competing content is preserved.
Late evidence changes and receipt failures compensate only invocation-owned writes.

## Ignore, removal and recovery

A source-known command checks both source and card path ignore rules before
reading card content or original/cache evidence. Check first honors the card
record path ignore before opening it. It then parses closed metadata to learn the
source and applies source ignore before original/cache reads; ignored summaries
are never exposed. Check visits only direct card records and catalog/control
metadata, without discovering project sources. Invalid or hidden records report
incomplete coverage and a repair action.

Removal leaves the original, extraction and old card in place, but the removed
project source is immediately unselected. Cards never register originals.
Changed/missing/ignored originals and cold caches prevent current use. Moving a
work area preserves relative references but requires usable matching extraction
before a card becomes current. Refresh through the same read/write workflow.

Managed snapshots and backups include structurally valid direct card records.
Historical validation reads no originals or caches and does not require paired
registration: implicit and removed sources remain recoverable. Restore preserves
later additions; restored cards are reevaluated against current evidence. No
original, cache, task control or inactive learned draft is added to coverage.
Legacy whole-workspace recovery retains its documented historical scope.

## Optional offer

After useful finished work is saved, the assistant may make one brief Library
addition offer. Completion is already complete; ignore or decline does not block
or change it. Do not repeat offers in the task, offer every small draft, offer
already-selected files, or retain acceptance/decline logs. No-save suppresses
routine offers and cards. Explicit requested Library registration/extraction
remains available without enabling cards. Generation failure is explained in the
current response without a persistent failure log or fabricated summary.
