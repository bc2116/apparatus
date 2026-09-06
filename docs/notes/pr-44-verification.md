# PR-44 verification

Implementation baseline: integrated PR-43 `735d4b2`, including seven built-ins,
learned Skills and the preceding platform/PDF repairs. Exact changed stock files
were captured from that committed tree before editing. Later PR-43 `6c185ee`
changes verification notes only; final dependency integration remains with the
release owner.

## Behavior and ownership

The shared evidence context opens one selected original and its exact extraction
pair. Tests forbid unrelated original reads, Library discovery and cache-record
enumeration while producing a card, including implicit Library sources with an
initially absent `System/library` and safe decomposed filename spelling.

The card suite covers saving-task/enrollment/feature/ignore guards before input,
no-save requested-exception isolation, read-only inspection, provenance and
closed-schema rejection, terminal extraction outcomes, same-size/mtime changes,
missing/removed/ignored sources, cold-cache rebuild and whole-area move, exact
clean repeats, and supported refresh after source re-ingest. Required redaction
receipts survive the equal-sanitized-content case. Late receipt failure restores
only owned card/receipt state and allows ordinary retry.

Competing destination/catalog/cache and late original edits are witnessed at
actual publication boundaries. Where native Windows denies a mutation, fixtures
accept only observed `PermissionError` with `errno.EACCES`; successful writes must
be detected by the real retained validator and their exact bytes preserved. No
blanket OS success assumption or relaxed filesystem inventory rule is used.

Real subprocess tests resolve a bound project to its shared card store. Real-Git
snapshot/export/restore includes cards and registration records, preserves later
additions, and excludes originals; offline historical validation does not imply
source recovery. Invalid card controls are actionable in check and recovery.
Card summaries do not become original search evidence.

Exact PR-43 LF/CRLF migrations preserve custom seven-Skill bodies, canon,
guidance, learned body/ownership pairs, profile and no-save controls. A second
init is unchanged. PR-43 orientation still requires all seven built-ins; earlier
five- and seven-Skill witnesses remain available.

## Synthetic prose review

Source: “Four bench trials were recorded: three completed and one timed out.
Results may not generalize.”

Card: “Of four bench trials, three completed and one timed out; results may not
generalize.” Topics: “bench trials”, “uncertain results”.

The candidate retains both outcomes, the sample count and the explicit limit;
it does not turn three successes into a general performance claim. This is an
author-reviewed synthetic pair. Provenance hashes and schema tests establish
byte/selection integrity, not a model's semantic grounding or prose quality.
Portable instruction conformance checks the single canonical offer workflow and
the existing Skill pointers; no live assistant was prompted to evaluate offers.

## Validation and remaining gates

- The focused card and instruction selection passed. Its final inventory of
  47 card cases and one instruction contract case also passed in the full suite.
- `uv run python tools/build_payload.py` passed.
- `uv build --package apparatus-core` produced the wheel and source distribution.
- All 23 canonical/embedded payload files match the universal ZIP, wheel and
  source distribution; the card module is packaged, all seven built-ins remain,
  and the three generated shim goldens match.
- `git diff --check` passed.
- Full `uv run pytest -o addopts= -q`: **1,197 passed, 38 skipped** in
  **471.02 seconds**, against the frozen source tree.

The card suite is explicitly included in Windows safety CI. Actual Windows,
independent review and final dependency integration remain delivery gates. No
model/API invocation, semantic-search feature, native-app certification,
cloud/team library, source copying or original-file recovery is claimed.
