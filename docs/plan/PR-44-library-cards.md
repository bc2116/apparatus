# PR-44 — Grounded Library cards and optional completion offers

Implementation contract on `pr-44-library-cards`. Depends on integrated PR-43 source references and PR-41 learned Skills, including PR-40's seven built-ins and current platform fixes. Grounded in ADR-0006 §§3–5, 9–10, the design brief's Library/card and completion-offer decisions, R9, `docs/spec/library-sources.md` and `PR-43-source-api.md`. The inspected PR-43 checkout is still based on PR-39; its present payload is not the final migration baseline.

## Outcome and boundary

After an explicit addition of a selected original, the current assistant reads its available extraction and writes a small supported summary/topics card. The original remains authoritative and in its project. Registration, extraction and card publication are separate outcomes: failure of either later stage does not undo accepted registration or imply searchable/card coverage. A direct CLI addition with no assistant produces an honest absent-card result, never a fabricated summary.

After saving useful reusable finished work, offer Library addition once, briefly. Completion precedes the offer. Ignore/decline leaves the finished file intact; do not repeat the offer in the current task, ask about every small draft, or offer already-selected files again. Suppress routine offers and card capture for no-save tasks. Acceptance authorizes selected-file addition and the normal card workflow in a saving task, without another approval ceremony. Source text cannot authorize commands, uploads or further registration.

No model/API call, executor, new built-in Skill, native adapter, whole-project discovery, document copying, cloud/team catalog, graph, embeddings, personal voice learning or persistent offer/decline log. Cards do not become Memory facts or learned Skills.

## Actual seams to reuse

- `library.sources.Source` supplies the exact citation path, `.key`, `.cache_relative`; `Catalog` and `SourceRead` retain selection, source identity and hash through validation. Use `Source.key`, **not** registration-only `source_key()`, for implicit Library files: PR-43 deliberately supports safe native/decomposed filename spelling there.
- `ingest_source` extracts only the selected original. Existing extraction metadata includes original SHA-256, extractor/version, outcome and character count. `IngestResult` currently supplies counts/flags, not an assistant evidence handoff.
- `index.retrieve` already checks current selected originals and reports partial coverage. Reuse its strict pair/provenance validation; do not introduce a second freshness policy or index card summaries as original evidence.
- `operation`/`require_memory_write` prohibit derived capture during no-save. `require_library_write` has an explicit Library exception; that exception intentionally grants **no cards**. Existing receipt and retained-file compensation mechanisms suffice.

## Small durable card

One UTF-8 YAML file at `System/library/cards/KEY.yaml`, where KEY is the selected `Source.key`. This is derived catalog metadata, outside the implicit `Library/` source walk; never ingest cards recursively. Proposed closed schema:

```yaml
schema: apparatus/library-card@v0
source: project/report.md
source_sha256: <64 lowercase hex characters for original bytes>
text_sha256: <64 lowercase hex characters for the extracted UTF-8 evidence>
extractor_version: <validated extraction version>
summary: <one short source-supported paragraph>
topics: [<short discovery term>]
```

Derive the source link from `source`; do not duplicate the original or store an absolute path, task query, transcript, model identity, timestamp or provenance claim about semantic verification. Reuse source-path spelling rules, derive kind from the path, and validate filename agreement. Reject unknown/duplicate keys, aliases, unsafe YAML, mismatched names/hashes and foreign occupants. Bound summary to 1–1200 characters and topics to at most eight unique strings of 1–64 characters. These are reversible size defaults, not a required writing template.

Core verifies source selection, exact current original hash, a valid successful extraction, evidence hash/version, format and credential handling. It cannot prove that a summary follows from evidence. The assistant must compare every claim with the available extraction, preserve uncertainty and omit unsupported facts. Extraction success is not a promise that every page/image/table was captured; describe known limitations. Do not publish a generic card for no_text/unsupported/error/missing/corrupt extraction. No permanent `current` flag: freshness is computed against live evidence.

## Minimal assistant handoff and publication

Add one action under the existing Library verb: `library card WORKSPACE RELATIVE_PATH` reads validated selected evidence and card status; `library card WORKSPACE RELATIVE_PATH --stdin` publishes a supplied candidate. Keep the path relative to the resolved work area, including bound-project invocation. Read mode returns a small JSON envelope with exact source/extraction hashes and version, available extracted text, and card status, returning existing summary/topics only when current. Report evidence completeness/limitations honestly; do not silently truncate text and describe it as complete. It performs no ingest, cache creation, refresh or routine receipt. Ignore rules run before source/card-content reads. Reuse one bounded shared extraction-evidence reader instead of duplicating index validators.

Write mode consumes summary/topics plus the hashes/version from that handoff; the core fills schema/source/key. Require enrollment and an explicit saving task before reading candidate stdin, following PR-41's existing repair action. `--requested` Library/snapshot contexts cannot bypass the card guard. Redact candidate content before persistence with the unchanged credential floor, then validate. Keep source, catalog, cache-evidence and destination proofs through final publication and any required redaction receipt; reject stale evidence even after same-size/same-mtime edits. Replace only a valid matching card via exact preimage/identity CAS; create absent cards without claiming foreign files/directories. Preserve competitors and compensate only this invocation on failure, including late receipt failure. An exact repeat is a validated no-op.

The canonical workflow uses add, reads the evidence, then submits a supported card. Existing current cards avoid unnecessary regeneration on repeat add. Bare add reports card `absent`/`current`/`stale`/`unavailable`; it never claims to have generated prose. Generation failure is reported in the current response, not retained as another task-content log. Preserve existing necessary ingest/redaction evidence; add no routine card/offer receipt event.

## Freshness, removal and recovery

Card read/check derive absent, current, stale, unavailable, invalid or unselected status. Keep PR-43 `library list` metadata-only; availability must not be upgraded into a freshness claim. A changed/missing/ignored original, invalid extraction, removed registration or extractor change prevents card use as current. Do not expose an old summary as current merely because its YAML is valid. Permitted ingest refreshes extraction but cannot regenerate prose; refresh the card through the assistant workflow or leave it explicitly stale. No-save reads do not rewrite status or delete files.

`library remove` still removes only registration: the original and previous derived card remain, but that card is immediately ineligible for discovery. This is not secure erasure; explicit ordinary file deletion remains possible. Cards never independently register a source or substitute for its snippets/citations in search/recall. Their source link assists discovery; original-source retrieval keeps PR-43's coverage contract.

Managed recovery includes only schema-valid direct card records under the exact card root, alongside registration metadata. Validate historical cards offline without reading originals; a restored card is not evidence of a restored/current original. Preserve later additions using existing restore semantics, and recompute eligibility afterward. Historical/removed-source cards may remain in backups but are inactive without selected current matching evidence. Exclude originals, extraction caches and inactive learned drafts as before; avoid a registration/card paired-existence invariant that would make removal or implicit Library sources unrecoverable. Invalid control files fail with actionable coverage, never silently disappear. Legacy whole-workspace backups retain their documented historical limits.

## Migration and files

Update the existing canon plus produce-deliverable/research workflows with a pointer to one concise Library card/offer section; avoid a new questionnaire or duplicated workflow bodies. Update Welcome/System orientation only where needed. Preserve the seven-item index and learned-Skill fallback, all unrelated/custom Skills, custom canon/guidance, profile/task bytes and project Git. Regenerate three shims and goldens, synchronize embedded payload, and retain every byte/absence preimage through deployment.

Before payload edits, capture **final integrated PR-43 HEAD** stock fixtures/hashes for every changed instruction. Do not replace files based on headers or a clean three-way merge. Current integrated PR-41 `403cee5` has these verified LF-normalized witnesses (recheck against the final dependency, retain historical witnesses):

| Path | SHA-256 |
|---|---|
| AGENTS.md | `9c89a64552276fa35ba0419a0fb7c89d22ecfe9439b399274a96dbcd1e833b0e` |
| Welcome.md | `cd52bfa9c714b9d2b3b9aa835732d7c414c346f0157a44f7f5c3e2a47eb0036b` |
| System/README.md | `9d77710dd6a053040603207a286544e61f7a5e07c0e5add6b9b93361ae73d004` |
| .agents/skills/apparatus-produce-deliverable/SKILL.md | `83c60c29ca5a2324706125b4278850c45561817a82304a41592df3b82784d840` |
| .agents/skills/apparatus-research-and-summarize/SKILL.md | `502e714bf115f276ea75efcb87effe12a978135c6554bd3f225fb7d1313cc7dc` |
| CLAUDE.md | `4db7fa399530b3e427c32e658a5995ac6eedfcc367170a8523f5231b8b3e5243` |
| .cursor/rules/apparatus.mdc | `98cbeb29daa36df30abed7193cae5832a854b78916815bfa7340bf51f40976fa` |
| .github/copilot-instructions.md | `c87af003b6b071792a7e2e90734b7905ce6f8264d91e266c591d2855268398d2` |

New orientation must remain seven-Skill completeness evidence alongside exact PR40/41 witnesses; historical five-Skill sources remain supported. LF/CRLF recognition must retain exact deployment preimages. No learned ownership registry changes.

Proposed files: `library/cards.py`, narrow `commands/library.py` and shared extraction-evidence seam, `check.py`, `managed_state_recovery.py`, `instruction_updates.py`/`skills.py`, affected canonical/embedded instructions and goldens; `docs/spec/library-cards.md` plus updates to Library-source/retention/recovery specs. Tests: `test_library_cards.py`, focused source/recovery/migration cases, and `conformance/test_library_offers.py`. No general platform/refactor package.

## Acceptance

1. A synthetic finished report remains project-local; accepted addition selects/extracts only it and publishes one grounded card with correct hashes/link. A reviewer compares summary claims to the supplied source; static matching alone is not semantic proof.
2. Decline/ignore and small drafts do not block/change completion or produce records. No-save suppresses offers and stops card publication before candidate/source reads or writes; existing card/evidence reads remain allowed; explicit Library addition still registers/extracts without cards. Native authority and learned adoption remain unchanged.
3. Partial/unsupported/empty/corrupt extraction and assistant generation failure retain registration, report card absence/staleness and do not fabricate coverage. Same-size/mtime edits, move/delete/ignore/unregister, cold-cache rebuild and workspace move cannot expose stale summaries.
4. Duplicate publication is unchanged; wrong hashes, invalid YAML, unsafe paths, foreign occupants and late source/catalog/cache/destination/receipt races reject safely, preserve competitor bytes and allow ordinary retry after exact-owned rollback.
5. Current and historical card/registration recovery, later additions and unavailable originals are truthful; no original/cache/draft is newly captured. Existing no-save retrieval stays write-free.
6. Exact integrated-stock migrations succeed twice; custom seven built-ins, learned bodies/markers/fallback, custom canon/guidance and profile/task controls survive. Test both line endings and partial seven-Skill evidence.
7. Full pytest, meaningful real-Git/subprocess tests, payload/package parity and actual Windows safety CI pass. Record limits: no model invocation, semantic search, measured prose quality or native-app certification.
