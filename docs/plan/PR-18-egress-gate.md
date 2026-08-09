# PR-18: Egress gate v1

## Context — required reading

- `AGENTS.md` — session rules, hard rules, definition of done
- `docs/design/design-brief.md` — §7 privacy and safety model; §14 open
  question on the egress trigger taxonomy
- `docs/adr/ADR-0004-privacy-model.md` — the governing decision: label at
  write, enforce at egress; credential floor never relaxed; receipts
- `docs/adr/ADR-0001-vocabulary.md` — canonical terms for all user-facing text
- `docs/adr/ADR-0002-protocol-and-state.md` — receipts are Markdown records
  under `System/`, one file per event
- `docs/adr/ADR-0003-harness-agnostic-contract.md` — read files, write files,
  run approved commands; nothing more
- `docs/spec/egress.md` — normative egress spec (landed in PR-06); this PR
  implements it and never quietly redefines it
- `docs/spec/workspace.md` — folder semantics; `System/receipts/`
- `docs/plan/README.md` — phases, status table (update it in this PR)
- `docs/plan/PR-06-policy-overlays-egress-spec.md` and
  `docs/plan/PR-12-memory-labeler.md` — the spec, policy overlays, labeler,
  and credential-floor detector this PR builds on

## Objective

When this PR lands, the load-bearing safety feature of ADR-0004 exists as a
deterministic command: `apparatus egress check <workspace> <file...>` inspects
content about to leave the workspace, enumerates labeled items, runs the
credential-floor scan, exact-matches names and emails drawn from
`Memory/People/` records against the outbound content, writes a redacted copy
alongside each original that has findings, records the human's decision in an
egress receipt, and exits non-zero whenever sensitive items are present and no
decision has been recorded. Starter
procedures whose steps are share-shaped (per the taxonomy in
`docs/spec/egress.md`) are updated to call the gate before anything crosses
the boundary. "Label, don't block" becomes defensible because the boundary
check now fires every time.

## Deliverables

- `packages/apparatus-core/src/apparatus_core/egress.py` — new module: labeled
  item enumeration over outbound files per the content-scan semantics in
  `docs/spec/egress.md` (reusing the PR-12 labeler's pattern classes for
  free-form files; never duplicate its patterns), credential-floor scan
  (import the PR-12 detector; never duplicate its patterns), People-derived
  exact-match scan (names and emails drawn from `Memory/People/` records,
  matched exactly against the outbound content), redacted-copy generation,
  receipt writing, exit-code policy.
- `packages/apparatus-core/src/apparatus_core/commands/egress.py` — new:
  argparse wiring (`register`/`run`) for
  `apparatus egress check <workspace> <file...> [--decision <value>]`,
  registered in the `apparatus.commands` entry-point group in
  `packages/apparatus-core/pyproject.toml` per the PR-08 registry contract —
  no second registration path.
- `starter/payload/System/procedures/produce-deliverable.md` and
  `starter/payload/System/procedures/weekly-review.md` (filenames as landed in
  PR-05) — declare each share-shaped step with the `[share]` marker
  `docs/spec/egress.md` fixes, and add the explicit gate step before it;
  audit the remaining starter procedures and update every one whose steps
  export, send, publish, or otherwise move content out of the workspace.
  Procedure text: vocabulary per ADR-0001, and it must direct the assistant
  to stop and ask the human whenever the gate reports sensitive items.
- `packages/apparatus-core/tests/test_egress_gate.py` — new tests, with input
  fixtures under `packages/apparatus-core/tests/fixtures/egress/`.
- `conformance/golden/egress/` — one golden trio pinning the redaction
  contract: an input document containing labeled personal content plus one
  clearly fake credential, the expected redacted copy (byte-exact), and the
  expected findings summary. `conformance/test_egress_golden.py` — new test
  asserting the trio. `conformance/README.md` — fixtures table updated.
- `docs/spec/egress.md` — modified only if implementation exposes a genuine
  gap or contradiction; per `AGENTS.md`, fix the spec in the same PR and call
  the change out in the PR description.
- `docs/plan/README.md` — status row for PR-18 updated.

## Acceptance criteria

1. `apparatus egress check <workspace> <file...>` takes the workspace path as
   its explicit first argument, like every other verb — no workspace
   auto-discovery exists — followed by one or more file paths inside that
   workspace; a missing workspace, a missing file, or a file outside the
   workspace exits 2 (usage error, per the PR-08 exit-code convention) with a
   clear error and writes nothing.
2. The gate enumerates labeled items in the outbound content per
   `docs/spec/egress.md`, reporting file, label kind, and line for each item.
3. The gate exact-matches names and emails drawn from `Memory/People/`
   records against the outbound content, reporting file, matched kind
   (person name or email), and line for each hit. Names appearing in no
   People record are not detected — the documented v1 limitation in
   `docs/spec/egress.md` — and a test covers both a People name being
   flagged and a name from no People record passing unflagged.
4. The credential-floor scan reuses the PR-12 detector; findings are reported
   with kind and location.
5. For every file with findings, a redacted copy is written alongside the
   original as `<stem>.redacted<suffix>` — matched token replaced, surrounding
   prose kept (ADR-0004 §4) — leaving the original untouched.
6. No findings: exit 0; the receipt records a clean pass.
7. Findings and no `--decision`: exit 1; nothing is approved; the output tells
   the assistant to present the enumeration and the redacted copy to the human.
8. Findings and `--decision use-redacted` or `--decision send-original`
   (credential findings absent — see criterion 9): exit
   0, and the receipt records the decision verbatim as the human's explicit
   choice. The updated procedures forbid the assistant from passing
   `--decision` without first asking the human.
9. Credential findings are never approvable: `--decision send-original` in the
   presence of a credential finding is refused — exit 1, with a stable
   machine-readable refusal code in the output that tests assert (not prose;
   the PR-08 exit-code convention stays 0/1/2) — the redacted copy remains
   the only egress path, and the receipt records the
   refusal. Receipts never contain the matched credential text — kind, count,
   and location only.
10. Egress behavior is mode-independent in v1, exactly as `docs/spec/egress.md`
    states: the gate behaves identically under `privacy_mode: standard` and
    `privacy_mode: private` (private mode differs only at Memory-write time),
    and a test proves the same inputs produce the same findings, redacted
    copies, receipt content, and exit codes in both modes.
11. Every run writes one receipt under `System/receipts/` (event `egress`,
    schema-valid via `apparatus check`) naming files checked, findings by kind
    and count, redacted copies written, and the decision (or its absence).
12. `uv run pytest` is green.

## Conformance and tests

- New: `conformance/golden/egress/` and `conformance/test_egress_golden.py`
  pin the redaction contract byte-for-byte. Fake credentials in fixtures
  follow the clearly-fake style PR-12's tests established; never real ones.
- New tests in `packages/apparatus-core/tests/test_egress_gate.py` covering:
  clean pass (exit 0, clean receipt); labeled-items flow (enumeration, exit 1
  without a decision, exit 0 with each decision value, receipt content);
  People-derived matching (a fictional `Memory/People/` record fixture whose
  name and email appear in an outbound file and are flagged, plus a name from
  no People record passing unflagged); credential hit (redaction,
  send-original refusal, receipt hygiene); redacted-copy correctness (token
  replaced, prose intact, original unchanged); and mode independence
  (identical behavior on the same inputs in standard and private modes).
- Existing fixtures (payload manifest, record schemas) are unchanged except
  the deliberate starter-procedure edits, which change file content only, not
  the payload file set.

## Out of scope

- No sending, publishing, uploading, or network I/O of any kind — the gate
  inspects and records; the human acts.
- No interactive prompt UI in the CLI: the decision arrives as a flag relayed
  by the assistant after asking the human.
- No changes to the write-time labeler or credential floor (PR-12), to policy
  overlay content semantics (PR-06), or to the share-shaped taxonomy beyond
  what implementing `docs/spec/egress.md` requires.
- No filesystem watching or automatic egress detection; procedures invoke the
  gate explicitly.
- No end-to-end welcome flow (PR-19).

## Dependencies

PR-12 (memory verbs, PII labeler, credential floor) must have landed, matching
`docs/plan/README.md`. The egress spec and policy overlays (PR-06), starter
procedures (PR-05), and `check`/receipts (PR-09) arrive transitively.

## Open decisions

- How the human's decision is relayed to the CLI. Smallest reversible default:
  a `--decision` flag whose value the receipt records verbatim; a
  decision-file mechanism can replace it later without changing receipts.
- Decision scope when multiple files are checked in one run. Smallest
  reversible default: the decision applies to the whole run's file list, and
  the receipt names every file it covered; per-file decisions can be added
  later as repeated flags.
