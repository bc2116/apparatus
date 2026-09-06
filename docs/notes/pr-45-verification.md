# PR-45 verification

Implementation is authored on integrated PR-43. Final PR-44 dependency and stock
instruction migration are pending; the results below do not claim final integrated
acceptance or Windows execution.

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
not evidence of a native Windows run. Full integrated tests and payload/package
parity will be recorded after the final dependency and guidance migration.

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
