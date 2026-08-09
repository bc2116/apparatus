# PR-14: Library ingest and text extraction

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` (§5 workspace, §6 item 4 Library, §7 privacy)
- `docs/adr/ADR-0001-vocabulary.md`
- `docs/adr/ADR-0002-protocol-and-state.md` (derived caches live outside the workspace)
- `docs/adr/ADR-0003-harness-agnostic-contract.md`
- `docs/adr/ADR-0004-privacy-model.md` (Library content is data, never instructions)
- `docs/adr/ADR-0005-distribution-and-packaging.md` (dependency and install discipline)
- `docs/plan/README.md`
- `docs/spec/workspace.md`
- `docs/plan/PR-04-record-schemas.md` (the receipt record schema)
- `docs/plan/PR-08-cli-skeleton-doctor.md` (registry contract and exit-code convention)
- `docs/plan/PR-09-check.md` (receipt-writing conventions)

## Objective

When this PR lands, `apparatus library ingest` scans the workspace `Library/`
folder and extracts plain text from `.md`, `.txt`, `.docx`, and `.pdf` sources
into a machine-local cache that lives **outside** the workspace. The cache is
derived, rebuildable at any time, and never the source of truth (ADR-0002);
each source file gets one extraction record that binds the source's content
hash, so later PRs (the search index in PR-15, recall in PR-16) can detect
change and stay incremental. Files that cannot be extracted are flagged
honestly in a receipt — never silently skipped — because a Library the user
cannot trust to be fully represented would poison grounded recall.

## Deliverables

- `packages/apparatus-core/src/apparatus_core/cache.py` — new. Resolves the
  machine-local cache root: `~/.apparatus/library/<workspace-id>/`, where the
  `~/.apparatus` base is overridable via the `APPARATUS_HOME` environment
  variable (tests point it at a temp dir). `<workspace-id>` is the first 12 hex
  chars of the SHA-256 of the resolved absolute workspace root path — see Open
  decisions. Creates directories on demand.
- `packages/apparatus-core/src/apparatus_core/library/__init__.py` — new.
- `packages/apparatus-core/src/apparatus_core/library/extractors.py` — new.
  One extractor per format: `.md`/`.txt` read as UTF-8 with `errors="replace"`
  (Markdown is treated as plain text; no parser dependency); `.docx` via
  `python-docx` (paragraphs plus table-cell text); `.pdf` via `pypdf`
  (per-page `extract_text`, pages joined with newlines). Each extractor
  reports a status: `extracted`, `no_text` (parsed fine but yielded no text,
  e.g. an image-only PDF), or `error` (with a captured message, e.g. an
  encrypted or corrupt file). Unknown extensions map to `unsupported`. Expose
  an `EXTRACTOR_VERSION` string constant bumped whenever extraction output
  could change.
- `packages/apparatus-core/src/apparatus_core/library/ingest.py` — new. Scans
  `Library/` recursively, skipping dotfiles (`.gitkeep`) and OS noise
  (`.DS_Store`, `Thumbs.db`, `desktop.ini`). For each source file it computes
  the SHA-256 of the bytes and writes a cache pair mirroring the Library tree:
  `extractions/<relative-path>.txt` (the extracted text; absent for
  non-`extracted` statuses) and `extractions/<relative-path>.json` (the
  extraction record: workspace-relative source path, source SHA-256, size in
  bytes, extractor name and `EXTRACTOR_VERSION`, status, error message if any,
  extracted character count, UTC timestamp). JSON is acceptable here because
  the cache lives outside the workspace (ADR-0002 bans JSON state only inside
  it). Re-ingest skips sources whose recorded hash and extractor version are
  unchanged, and deletes cache pairs whose source no longer exists. Each run
  writes one receipt record (PR-04 receipt schema with `event: library-ingest`,
  Markdown with frontmatter, filename per the shared receipt writer's
  convention) under `System/receipts/` summarizing counts — scanned,
  extracted, unchanged, `no_text`, `unsupported`, `error` — and listing every
  flagged file with its reason, in ADR-0001 vocabulary. Reuse the receipt
  writer landed by PR-09 (expected `packages/apparatus-core/src/apparatus_core/receipts.py`);
  extend it rather than adding a second writer.
- No record-schema changes: the ingest receipt uses the `library-ingest`
  event value already pinned in the PR-04 receipt `event` enum;
  `docs/spec/records.md` and
  `packages/apparatus-core/src/apparatus_core/records.py` are untouched.
- `packages/apparatus-core/src/apparatus_core/commands/library.py` — new:
  `register(subparsers)` plus `run(args) -> int` per the PR-08 registry
  contract — built-in verbs register through the `apparatus.commands`
  entry-point group only; do not edit `cli.py` directly. Registers
  `apparatus library ingest <workspace>`, taking the workspace path as an
  explicit argument exactly as `doctor` (PR-08) and `check` (PR-09) do —
  PR-08 lands no workspace auto-discovery, so do not invent one. Human output
  states where the cache lives and repeats the flagged-file summary. Exit
  codes follow the PR-08 convention: `0` when every scanned source is
  `extracted` or unchanged, `1` when any source was flagged (`no_text`,
  `unsupported`, `error`), `2` for usage errors (missing or non-directory
  workspace path).
- `packages/apparatus-core/pyproject.toml` — modified: add `python-docx` and
  `pypdf`, and register the `library` verb in the
  `[project.entry-points."apparatus.commands"]` group (PR-08). Dependency
  justification: both are pure-Python and permissively licensed, with no
  compiled extensions, so they fit the user-scope, no-admin install story
  (ADR-0005) and add no build burden. No other new dependencies.
- `uv.lock` — modified (resolution for the two new dependencies).
- `packages/apparatus-core/tests/fixture_docs.py` — new. Test-time fixture
  builders: writes tiny `.md`/`.txt` files, a one-paragraph `.docx` via
  `python-docx`, and a minimal single-page PDF with one extractable text
  object assembled as raw PDF syntax (no binary fixtures committed, no
  network).
- `packages/apparatus-core/tests/test_library_ingest.py` — new.
- `docs/plan/README.md` — modified: status column for PR-14.

## Acceptance criteria

1. In a workspace whose `Library/` holds one `.md`, one `.txt`, one `.docx`,
   and one `.pdf`, `uv run apparatus library ingest <workspace>` exits 0,
   writes a `.txt`/`.json` cache pair per source under the machine-local
   cache root, and the extracted text contains the known fixture phrases.
2. No ingest output lands inside the workspace except the single receipt under
   `System/receipts/`; the cache root is outside the workspace tree.
3. Each extraction record binds the source's SHA-256, the extractor version,
   and a status; records are one per source file.
4. Re-running ingest with unchanged sources re-extracts nothing (record
   timestamps unchanged; receipt reports all sources as unchanged).
5. Editing one source changes its recorded hash and refreshes only that cache
   pair; deleting a source removes its cache pair on the next run.
6. An unsupported file (e.g. `.png`) and a corrupt `.docx` both complete the
   run — every other source is still processed — and the run exits 1
   (flagged sources are findings, per the PR-08 exit-code convention); both
   appear in the receipt with status and reason and are never silently
   skipped.
7. The receipt carries `event: library-ingest` — a value already pinned in
   the PR-04 receipt `event` enum — and the written receipt passes
   `apparatus check`.
8. Deleting the entire cache directory and re-running ingest rebuilds it
   completely — the cache is provably derived state.
9. `APPARATUS_HOME` overrides the cache base; tests never write to the real
   home directory.
10. The only new dependencies are `python-docx` and `pypdf`.
11. `uv run pytest` is green; no test touches the network.

## Conformance and tests

- `packages/apparatus-core/tests/test_library_ingest.py` covers criteria 1–9
  using `fixture_docs.py` and `tmp_path`-based workspaces with
  `APPARATUS_HOME` set per test.
- The golden payload manifest and the golden record examples are unchanged:
  the starter payload is untouched, and receipts are runtime records, not
  payload content. `docs/spec/records.md` and `records.py` are also
  unchanged — `library-ingest` is already in the receipt `event` enum PR-04
  pinned. Never loosen a fixture to silence a failure.
- `uv run pytest` green is required.

## Out of scope

- The search index and any SQLite usage (PR-15) and `apparatus recall`
  (PR-16).
- OCR, image-only PDF handling beyond the honest `no_text` status, `.doc`,
  `.xlsx`, `.pptx`, HTML, or any additional formats.
- PII labeling of extracted text (labels apply to workspace records per
  ADR-0004; the cache is derived and stays inside the machine).
- Watching `Library/` for changes, background jobs, or scheduling; ingest runs
  only when invoked.
- Any change to the starter payload or golden manifest.
- Any record-schema change; `library-ingest` is already in the PR-04 receipt
  `event` enum.

## Dependencies

- PR-09 (`check` — validators), per `docs/plan/README.md`; transitively PR-08
  (CLI skeleton) and PR-04 (record schemas, for the receipt).

## Open decisions

- **Workspace identity for the cache path.** The brief does not define a
  stable workspace id. Smallest reversible default (use it): hash of the
  resolved absolute workspace root path, as specified above. It adds no state
  to the workspace; the cost is a re-ingest after the user moves the
  workspace, which is cheap and safe because the cache is derived. If a stable
  id is later wanted, it can live in `System/profile.yaml` behind its own
  decision.
