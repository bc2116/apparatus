# PR-28: Workspace ignore rules v1

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` (§5 workspace, §6 day-1 capabilities, §7 privacy)
- `docs/adr/ADR-0002-protocol-and-state.md` (files-first; derived caches)
- `docs/adr/ADR-0004-privacy-model.md` (the gates ignore rules must never weaken)
- `docs/spec/workspace.md`
- `docs/plan/PR-09-check.md`, `PR-14-library-ingest.md`, `PR-15-library-index.md`,
  `PR-16-recall.md` (the machinery this PR retrofits)

## Objective

When this PR lands, the user can tell the workspace machinery to leave parts
of the workspace alone. A single ignore-rules file with familiar
gitignore-style patterns makes matched paths invisible to Library ingest,
indexing, and recall, and excluded from record validation — so a sensitive
subfolder, a scratch area, or a third-party dump can sit inside the workspace
without being read, extracted, indexed, or cited. Ignore rules are a privacy
and tidiness tool; they never weaken the safety gates.

## Deliverables

- `docs/spec/ignore-rules.md` — the normative spec:
  - **File:** `System/ignore` — one gitignore-style pattern per line,
    workspace-relative, `#` comments allowed. Plain language header comment
    explaining what it does and does not affect.
  - **Honored by:** Library ingest/extraction (matched sources are neither
    read nor extracted), the local search index (matched extractions are
    evicted on next refresh), recall (matched sources never appear as
    evidence), and `check` (records under matched paths are not validated,
    but their count is reported so exclusion is visible, never silent).
  - **Never affected:** the egress gate and the credential floor (ADR-0004) —
    content the user explicitly sends outward is always scanned regardless of
    ignore rules; durable-write redaction always applies. State this
    prominently.
  - **Built-in defaults** (always ignored, not user-editable): OS metadata
    noise (`.DS_Store`, `Thumbs.db`, `desktop.ini`) and the workspace's own
    git internals.
  - **Reporting:** every existing receipt-producing verb that skips content
    because of ignore rules says so in its receipt (counts and rule
    provenance, not paths or file contents). Library search has no receipt
    event in the closed v1 schema, so it reports the same facts in command
    output without adding an event or changing record schemas.
- `starter/payload/System/ignore` — shipped with the built-in explanation
  header and the commented default patterns; payload manifest updated.
- Pattern engine in `packages/apparatus-core` (e.g. `ignore.py`): implement
  with Python stdlib `fnmatch`/`pathlib` semantics documented in the spec —
  no new dependency; document the supported subset honestly (full gitignore
  parity is NOT claimed; unsupported syntax is reported by `check`).
- Retrofits, each with tests: ingest skips matched sources; index refresh
  evicts newly-matched extractions; recall never returns matched sources;
  `check` reports ignored-path counts and validates the ignore file's own
  syntax.
- `docs/spec/workspace.md` — System contents table row for `System/ignore`.
- `docs/plan/README.md` — status row updated.

## Acceptance criteria

1. `docs/spec/ignore-rules.md` exists and covers file location, syntax
   subset, the honored-by list, the never-affected list, built-in defaults,
   and receipt reporting.
2. A source added to `System/ignore` after ingest disappears from search and
   recall results after the next refresh, proven by a test.
3. A matched source is never opened during ingest (test with an unreadable or
   sentinel file that would fail loudly if opened).
4. `check` reports the count of records/paths excluded by ignore rules and
   flags unsupported pattern syntax with a plain-language message.
5. Egress-gate tests prove ignore rules change nothing at egress: a file
   under an ignored path, when explicitly passed to `apparatus egress check`,
   is scanned exactly as any other file.
6. The shipped `System/ignore` header explains, in ADR-0001 vocabulary, what
   ignoring does, what it never does (egress, credential floor), and how to
   edit the file by asking the assistant.
7. Payload manifest and workspace spec updated deliberately in this PR.
8. `uv run pytest` green.

## Conformance and tests

- Updated: `conformance/golden/payload-manifest.txt` (one new file).
- Added: pattern-engine unit tests (supported subset, edge cases, unsupported
  syntax detection); per-verb retrofit tests as listed above.
- Unchanged: record schemas and all PR-04 fixtures.

## Out of scope

- No changes to snapshot/restore behavior (see Open decisions).
- No per-folder ignore files (single `System/ignore` only in v1).
- No UI beyond the file itself and the assistant editing it on request.
- No external-automation opt-out markers for the workspace as a whole (see
  Open decisions).

## Dependencies

PR-09 (check), PR-14 (Library ingest), PR-15 (Library index), PR-16
(recall), and PR-18 (egress gate) must have landed, matching
`docs/plan/README.md`.

## Open decisions

- **Receipt reporting for read-only search.** The receipt event enum is closed
  and Library search deliberately has no receipt. Smallest reversible default:
  existing receipt-producing verbs record count and provenance in their
  receipts, while search reports them in command output. This preserves both
  the receipt schema and search's established JSON contract.
- **Egress acceptance sequencing.** Acceptance criterion 5 requires the PR-18
  egress command and tests, so PR-18 is a dependency even though it was omitted
  from the prompt's original dependency list. PR-28 does not duplicate egress;
  it integrates the ignored-file regression after PR-18 lands.

- **Snapshots and ignored paths.** Smallest reversible default: snapshots
  still include ignored paths — recovery-first, matching the "you cannot
  break this" promise — with the privacy-first alternative (exclude them)
  recorded for a later decision once real usage exists.
- **A root-level opt-out marker** telling external workspace automations to
  leave an Apparatus workspace alone entirely (the inverse concern: other
  tools ignoring us). Useful in multi-tool environments; deferred until a
  concrete external tool contract exists to honor it.
