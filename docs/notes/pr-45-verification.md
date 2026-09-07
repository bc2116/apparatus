# PR-45 verification

## September 7 Windows snapshot assertion repair

Git reports saved paths with forward slashes on Windows. The receipt-ordering
test used the native backslash spelling and failed despite the expected receipt
being present. It now compares the relative POSIX spelling against a complete
output line, preserving the real-Git receipt/order assertion. No production code
changed. The focused case passed locally in 3.61 seconds; independent review
accepted the change. Full local validation and a native Windows rerun are pending.

Runtime work was authored on integrated PR-43, then rebased onto final PR-44
`de7c8bee` at `a497c260`. Final PR-44 stock instruction migration is implemented.
The final integrated suite passed locally; actual Windows execution remains pending.

## Runtime boundary

Routine check, recall, ingest, feature-disabled and unavailable-capability paths
no longer publish activity receipts. Actual mutation/redaction/recovery producers
and the shared receipt/retention/filesystem transaction machinery remain intact.
Doctor keeps the existing machine-readable keys while separating Git detection
from a usable recovery store; the unavailable-report updater understands both
historical and current body wording.

Profile apply retains every present or absent manifest-managed endpoint before
planning, including same-byte files omitted by the overlay planner. It reuses those
proofs through receipt publication, apply and final validation. Changed endpoints
hand exact preimages to existing CAS primitives; removals require successful exact
reopen/deletion. True no-op preserves the complete tree. Equal sanitized candidate
bytes still produce required redaction evidence, without a profile-apply event.

## Executed local checks

- Updated init/snapshot/check/profile boundary suite: **134 passed, 7 skipped**.
- Quiet-operation and profile tests: **44 passed**.
- Final focused runtime set (quiet operations, profile, machine report and welcome
  end-to-end): **60 passed, 4 skipped** in **79.85 seconds**.
- A controlled in-process substitution of the prior direct deletion call made the
  read-only-proof removal regression fail as expected. The repository source was
  unchanged by this negative-control run.
- New race tests witness actual successful replacement or require a Windows
  access/sharing error. They do not assume competing replacements succeed on all
  platforms. Same-byte inode swaps, after-planning custom replacement, unchanged
  overlays beside real profile changes and late receipt checkpoints are covered.
- A real Git repair → check → snapshot/restore scenario preserves old history and
  retains init, snapshot and restore evidence without routine activity events.

The public Windows safety lane includes the new quiet-operation file and affected
check, recall and snapshot tests, alongside the existing profile tests. Actual
Windows CI is still required; the local read-only-handle witness is a simulation,
not evidence of a native Windows run. The quiet-guidance migration file is also
included in that lane.

## Pre-integration full run

The first full runtime run completed with **1,166 passed, 38 skipped, 2 failed**
in **458.57 seconds**. Both failures were obsolete routine-receipt expectations:
the welcome story expected ingest/recall events, and the historical R6 upgrade
expected an unavailable-snapshot event. Citation, task-control, profile and actual
mutation-history assertions were preserved while updating those expectations.
The welcome case passed in the focused set above; the R6 case was then rerun.
This is diagnostic pre-integration evidence, not a green final full-suite claim.

The final pre-integration targeted run (both R6 upgrade task modes, quiet
operations, check and machine reports) passed **40 tests, 4 skipped** in **33.38
seconds**. `git diff --check` passed. Runtime source is frozen for dependency
integration; no remaining runtime failure is known from the completed runs.

## Final PR-44 integration and guidance

Only the plan-table merge conflicted; both PR-44 and PR-45 rows were preserved.
The card command's required redaction writer import was retained after integration.
Canonical `AGENTS.md` and `System/README.md` now state quiet history and truthful
capability/repair guidance. The three generated pointers, their goldens and the
embedded starter are synchronized. No built-in Skill body changed.

Five exact final PR-44 instruction files are captured as LF/CRLF-normalized
migration witnesses. Previous stock orientation remains recognized alongside the
new System README. Customized canon and orientation stay user-owned. Tests keep
cards, registrations, learned ownership/body pairs, preferences and no-save
controls byte-identical; repeated repair adds no changes. A late custom instruction
replacement rejects the stale deployment and preserves the competing bytes.

- New migration/card-diagnostic cases: **9 passed** in **3.44 seconds**.
- Complete new migration file, including late-preimage case: **6 passed** in
  **2.62 seconds**.
- The broader guidance/Library-card/instruction/payload set passed **92 cases**;
  four new test-literal errors were corrected and passed in the targeted runs.
- Universal ZIP, wheel and source distribution builders passed.
- **25 tracked starter files** means **23 payload files plus 2 profile files**.
  All 25 match the embedded starter, wheel, source distribution and universal ZIP
  byte-for-byte. All seven built-in Skills remain byte-identical to final PR-44.
  The wheel contains the updated card, profile, check and migration modules and
  retains the `pypdf>=6.16.1` requirement.

These scoped counts come from `git ls-files starter`; payload-only counts exclude
`starter/profiles`. No native discovery/runtime claims are inferred from parity.

Independent final guidance/integration review found no blockers. It verified the
five exact PR-44 fixtures, 23-file payload parity, all three pointers, retained
orientation hashes and the card command's required redaction writer. Lead review
also accepted the profile preimage and exact deletion repairs. Actual Windows CI
remains a delivery check, not a locally completed result.

## Final integrated result

`uv run pytest -o addopts= -q` passed **1,227 tests, 38 skipped** in **430.62
seconds** after final PR-44 integration and all runtime/guidance changes.
`uv sync --all-packages` completed; the PDF dependency remains 6.16.1.
All **80 tracked package source/resource files** match both wheel and source
distribution; the scoped 25-file starter parity above also passed. The final
`git diff --check` is clean. PR-45 deliverables and plan status are complete for
reviewed branch delivery. Actual Windows safety CI and remote delivery remain
lead-owned follow-up checks; no native Windows success is claimed here.
