# PR-12: Memory verbs, PII labeler, credential floor

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` — especially §6.3 (Memory with People), §7
  (privacy and safety model)
- `docs/adr/ADR-0001-vocabulary.md`
- `docs/adr/ADR-0002-protocol-and-state.md` — record kinds fact and person
- `docs/adr/ADR-0004-privacy-model.md` — the authoritative decision this PR
  implements: label don't block, credential floor, private mode
- `docs/plan/README.md`
- `docs/plan/PR-04-record-schemas.md` — fact and person schemas
- `docs/plan/PR-06-policy-overlays-egress-spec.md` — policy overlay files
- `docs/plan/PR-09-check.md` — receipts module and exit codes

## Objective

Durable memory becomes safe by construction. This PR lands the memory verbs
(`apparatus memory add-fact`, `add-person`, `label`), the deterministic PII
labeler, and the credential floor per ADR-0004. The labeler writes silent
labels into record frontmatter — metadata only, content never altered by
labeling — so the egress gate (PR-18) has something to enforce. The credential
floor auto-redacts secrets in place before any durable write, in every mode,
with a redaction receipt. Private mode blocks labeled content from durable
memory with a clear message. Remembering people stays a feature: in standard
mode nothing is ever blocked, only labeled.

## Deliverables

- `packages/apparatus-core/src/apparatus_core/labeler.py` — deterministic
  pattern-based labeling: `find_labels(text) -> list[Label]` plus frontmatter
  application. Pattern classes: email, phone number, address-like, id-like.
  There is deliberately no name pattern class — see criterion 9.
- `packages/apparatus-core/src/apparatus_core/credentials.py` — the floor:
  `redact(text) -> (clean_text, list[RedactionFinding])`. Classes: password
  assignments, API keys/tokens, private key blocks (PEM), high-confidence
  government identifiers (SSN-shaped), payment card numbers (13–19 digits
  passing Luhn).
- `packages/apparatus-core/src/apparatus_core/commands/memory.py` — the
  `memory` verb with `add-fact`, `add-person`, and `label` subcommands, per
  the PR-08 registry contract.
- `packages/apparatus-core/pyproject.toml` — modified: register the `memory`
  verb in the `apparatus.commands` entry-point group.
- `packages/apparatus-core/tests/test_labeler.py`
- `packages/apparatus-core/tests/test_credentials.py`
- `packages/apparatus-core/tests/test_memory_commands.py`
- `packages/apparatus-core/tests/fixtures/labeler/` — fixture texts, one or
  more per pattern class, all fictional.
- `docs/plan/README.md` — modified: PR-12 status row only.

## Acceptance criteria

1. `apparatus memory add-fact <workspace> --title TEXT (--body TEXT |
   --from-file PATH)` writes one record to `Memory/Facts/<kebab-title>.md`
   conforming to the PR-04 fact schema. `add-person` does the same to
   `Memory/People/` with `--name` and optional `--role`. Filenames are
   kebab-case; a collision appends a numeric suffix rather than overwriting.
2. Write pipeline order, always: credential floor → labeler → mode gate →
   durable write. The floor runs in every mode, no exception, no flag to
   disable it.
3. Credential floor behavior: each matched token is replaced in place with a
   placeholder naming its class (e.g. `[redacted-api-key]`); surrounding
   prose is kept verbatim. When any redaction occurred and the record is
   written, a redaction receipt is written via `receipts.py` recording
   classes and counts — never the matched secrets themselves, in the
   receipt or anywhere else.
4. Labeler behavior: labels land in the record's frontmatter as a list of
   stable strings (`pii/email`, `pii/phone`, `pii/address`, `pii/id`); the
   record body is byte-identical to the post-floor input. Labeling is
   deterministic and idempotent: relabeling an already-labeled record
   changes nothing.
5. Mode gate: the machine-readable mode is `privacy_mode` in
   `System/profile.yaml`. In `standard`, labeled content is always written.
   In `private`, a record that acquired any PII label is not written at all:
   the verb prints a plain-language message naming the label classes found
   (never the matched values), nothing durable is created — no record, no
   receipt — and the exit code is 1.
6. `apparatus memory label <workspace>` sweeps existing records under
   `Memory/People/` and `Memory/Facts/` (hand-written ones included):
   applies the floor (with receipts for any redaction) and refreshes
   frontmatter labels idempotently. In private mode the sweep still labels
   and reports, but never deletes or blocks existing records — the block
   applies to new writes only.
7. Payment card matching requires Luhn validity; a 16-digit number failing
   Luhn is not redacted (a fixture proves it). SSN-shaped matching requires
   the delimited pattern, not any 9-digit run.
8. Everything is pure stdlib (`re`, plus the YAML dependency already present
   from PR-04). No NLP or ML dependency — determinism is the requirement,
   per ADR-0004 ("deterministic where possible").
9. Names, per the v1 decision under ADR-0004: the labeler ships no name
   pattern class, because free-text personal names have no deterministic
   pattern and NLP is excluded by design. Instead, every record in
   `Memory/People/` is structurally labeled as person data — living in
   `Memory/People/` and carrying `name` is the label; no pattern needs to
   fire. The egress gate additionally exact-matches names and emails drawn
   from `Memory/People/` records against outbound content; that matching is
   implemented in PR-18, not here. Free-text detection of names that appear
   in no People record is a documented v1 limitation, stated in
   `docs/spec/egress.md`.
10. All stdout text uses ADR-0001 vocabulary and stays calm, not alarmist
    (ADR-0004 consequence): labels are silent metadata; only private-mode
    blocks and redactions speak up.
11. Exit codes per the PR-08 convention: 0 written, 1 blocked (private mode),
    2 usage errors (missing workspace, both `--body` and `--from-file`,
    schema-invalid result).
12. `uv run pytest` is green, and `apparatus check` passes on a workspace
    after each successful verb (records are schema-valid by construction).

## Conformance and tests

- No changes to the starter payload or golden manifest.
- `tests/fixtures/labeler/` holds fictional texts covering every pattern
  class: email, phone, address-like, id-like, password assignment, API
  key/token, PEM block, SSN-shaped, Luhn-valid card — plus negative cases
  (Luhn-failing 16-digit number, undelimited 9-digit number, ordinary prose).
  Nothing in fixtures may be a real person, credential, or identifier.
- `test_labeler.py`: every class detected on its fixture; idempotency; body
  untouched by labeling; negative cases produce no labels.
- `test_credentials.py`: every class redacted in place with prose kept;
  placeholder naming; negative cases untouched; findings carry class and
  count only.
- `test_memory_commands.py`: both verbs in both modes (written+labeled in
  standard; blocked with message and clean workspace in private); redaction
  receipt written; the `label` sweep on a hand-written record; collision
  suffixing; exit codes.

## Out of scope

- The egress gate and redacted-copy offers (PR-18) — this PR only produces
  the labels egress consumes. The People-derived exact-match scan of names
  and emails at egress is also PR-18's, built on the person records this
  PR's verbs write.
- Interview-driven mode selection (PR-17); here the mode is read from
  `System/profile.yaml` as deployed by PR-11.
- Labeling content outside `Memory/` (Goals, Decisions, Library, receipts).
- Any allowlist/denylist configuration, custom patterns, or per-user tuning.
- Natural-language entity recognition; anything nondeterministic.

## Dependencies

- PR-09 (per `docs/plan/README.md`); reuses its `receipts.py` and the PR-04
  schemas present transitively.

## Open decisions

- Label taxonomy strings are not fixed by ADR-0004. Smallest reversible
  default, used here: `pii/<class>` slugs in a frontmatter `labels` list;
  PR-18 consumes whatever this PR ships, so record the final strings in the
  PR description.
- Where the machine-readable mode lives: profile vs. policy file. Smallest
  reversible default, used here: `privacy_mode` in `System/profile.yaml`
  (already schema'd), with the PR-06 policy file remaining the assistant's
  prose contract.
