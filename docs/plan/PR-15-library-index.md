# PR-15: Library local search index

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` (§6 item 4 Library, §3 principles)
- `docs/adr/ADR-0001-vocabulary.md`
- `docs/adr/ADR-0002-protocol-and-state.md` (derived caches: rebuildable, never source of truth)
- `docs/adr/ADR-0003-harness-agnostic-contract.md`
- `docs/adr/ADR-0005-distribution-and-packaging.md` (lean core, dependency discipline)
- `docs/plan/README.md`
- `docs/spec/workspace.md`
- `docs/plan/PR-08-cli-skeleton-doctor.md` (registry contract and exit-code convention)
- `docs/plan/PR-14-library-ingest.md` (cache layout, extraction records, and the `library` verb this PR extends)

## Objective

When this PR lands, extracted Library text is searchable locally:
`apparatus library search <workspace> <query>` returns ranked hits with workspace-relative
source references and snippets, backed by a SQLite FTS5 index stored in the
same machine-local cache as the extractions (stdlib `sqlite3`, no new
dependencies). The index refreshes incrementally, keyed on the source content
hashes that PR-14's extraction records bind, so a large Library stays cheap to
keep current. The index is pure derived state: it can be rebuilt from the
extraction cache at any moment, and its absence is never an error state that
blocks any other verb — it only means search has nothing to search yet. This
is the retrieval substrate that `apparatus recall` (PR-16) builds grounded,
citable answers on.

## Deliverables

- `packages/apparatus-core/src/apparatus_core/library/index.py` — new. Owns
  the index database at `<cache-root>/index.sqlite3` (cache root per PR-14's
  `cache.py`). Schema: an FTS5 virtual table holding the extracted text with
  the workspace-relative source path, plus a plain bookkeeping table
  `indexed_sources(source_path PRIMARY KEY, source_sha256, extractor_version,
  indexed_at)` used for incremental diffing. Provides:
  - `refresh(...)` — compares extraction records (status `extracted` only)
    against `indexed_sources` by source hash and extractor version; inserts
    new sources, replaces changed ones, deletes rows whose extraction record
    is gone. Touches only changed rows.
  - `rebuild(...)` — drops and recreates both tables from the extraction cache.
  - `search(query, limit)` — ranks with FTS5 `bm25()`, reports
    `score = -bm25` so higher is better, and produces a short snippet via the
    FTS5 `snippet()` function with the match highlighted. User queries are
    sanitized before being handed to FTS5 (quote each whitespace-separated
    term as a string token) so natural-language input with apostrophes,
    hyphens, or unbalanced quotes never raises a syntax error.
  - An explicit capability probe: if the host Python's SQLite lacks FTS5,
    search fails with a one-line honest message naming the limitation and
    exit code 1 (degraded result, per the PR-08 exit-code convention) — and
    nothing outside search is affected.
- `packages/apparatus-core/src/apparatus_core/commands/library.py` — modified
  (created by PR-14): add a `search` subcommand so the verb is
  `apparatus library search <workspace> <query>`, taking the workspace path
  as an explicit argument like `ingest` (PR-14) and `check` (PR-09). No
  edits to `cli.py` and no new entry point — the `library` verb is already
  registered in the `apparatus.commands` group (PR-08 registry contract).
  Flags: `--limit N` (default 5), `--json` (machine-readable hit list for
  the assistant: source path, snippet, score), and `--rebuild` (force a
  from-scratch rebuild before querying). Search always runs an incremental
  `refresh()` first, so results reflect the current extraction cache without
  a separate verb. When there are no extractions at all, print exactly one
  plain-language line telling the user (in ADR-0001 vocabulary) that nothing
  from their Library has been ingested yet and that `apparatus library
  ingest` fixes that; exit 1 (degraded result) for the search verb only.
  Usage errors (missing or non-directory workspace path) exit 2, per PR-08.
- `packages/apparatus-core/tests/test_library_index.py` — new.
- `docs/plan/README.md` — modified: status column for PR-15.

## Acceptance criteria

1. After PR-14 ingest of fixture documents, `uv run apparatus library search
   <workspace> <known phrase>` returns the containing document as the top
   hit, with a workspace-relative source reference (e.g. `Library/notes.md`),
   a snippet containing the highlighted match, and a numeric score; `--json`
   emits the same hits as structured data.
2. Ranking is deterministic: running the same query twice against the same
   fixture corpus returns an identical ordered hit list, ordered by
   descending score (higher is better).
3. Incremental refresh: after editing one source and re-running ingest, a
   search picks up the new content, the unchanged sources' `indexed_sources`
   rows (including `indexed_at`) are untouched, and only the changed row was
   rewritten.
4. Deleting a source and re-running ingest removes its hits from search
   results after the automatic refresh.
5. Deleting `index.sqlite3` entirely and searching again transparently
   rebuilds the index from extraction records and returns the same results as
   before deletion; `--rebuild` does the same on demand.
6. With no extraction cache present, `library search` prints the single
   honest guidance line and exits 1, while other verbs (e.g.
   `apparatus check`) are completely unaffected by index absence.
7. Queries containing quotes, apostrophes, hyphens, and FTS5 operator-looking
   text return results or an empty hit list — never a traceback or SQL error.
8. The index file lives in the machine-local cache directory, never inside
   the workspace, and no new package dependencies are added (stdlib
   `sqlite3` only).
9. `uv run pytest` is green; no test touches the network.

## Conformance and tests

- `packages/apparatus-core/tests/test_library_index.py` covers criteria 1–8:
  index build after ingest, incremental refresh after a source change,
  source-deletion cleanup, rebuild-from-scratch equivalence, index-absence
  behavior, and query sanitization — reusing PR-14's `fixture_docs.py`
  builders and `APPARATUS_HOME` pointed at `tmp_path`.
- No conformance golden fixtures change: the starter payload and workspace
  record schemas are untouched.
- `uv run pytest` green is required.

## Out of scope

- `apparatus recall`, abstain thresholds, and recall receipts (PR-16).
- Semantic/embedding search, stemming beyond FTS5's default tokenizer,
  synonyms, or relevance tuning — bm25 as shipped is the v0 contract.
- Indexing anything other than PR-14 extraction records with status
  `extracted` (no direct file reads from `Library/`, no workspace records).
- New CLI verbs beyond `library search` (no standalone `reindex` verb; the
  `--rebuild` flag covers it).
- Receipts for search runs — search is read-only and writes nothing to the
  workspace.
- Any change to ingest behavior, extractors, or the cache layout from PR-14.

## Dependencies

- PR-14 (Library ingest and text extraction), per `docs/plan/README.md`;
  transitively PR-09 and PR-08.

## Open decisions

- None. The retrieval contract is deliberately pinned above (stdlib `sqlite3`
  with FTS5, `bm25()` ranking, machine-local cache placement, honest
  degradation when FTS5 is absent); everything beyond it — semantic search,
  tuning, additional verbs — is explicitly out of scope for v0.
