# PR-33 verification

People and Facts support explicit correction, outdated status, and forgetting.
Current Memory recall filters lifecycle and ignore rules before returning
source/text results. Existing records without status remain current.

- `uv run pytest`: **572 passed, 38 skipped** on macOS after integrating the
  preceding Windows migration repair. Platform skips are not certification.
- `uv run python tools/build_payload.py`: passed; canonical/embedded payload
  and package checks are also part of conformance.
- `git diff --check`: passed.
- Added lifecycle tests to Windows CI, including transaction, credential/private
  restrictions, full-record correction, forgotten markers, profile reseeding,
  installed CLI, ignored records, and concurrent edits.
- Independent authoring-tier review accepted after one repair pass. Four race
  regressions verify unchanged plans by both bytes and identity, initially and
  before commit, preventing stale repeated forgetting from reporting success.

Forgetting leaves the original filename marker and does not erase profile
answers, other copies, snapshots, exports, or provider history. Restoring old
state can restore old Memory. Task-specific retention remains R2b; private
profiles retain their existing behavior. Read `rework-next-step.md` to resume.
Remote CI and exact merge state are recorded by the pull request.

Initial Windows CI rejected two concurrency tests. Earlier diagnoses conflated
an untagged result with proof of either a sharing violation or a successful
write. The tests now record an explicit successful byte count or a Windows
PermissionError/EACCES outcome. A successful competing write must be rejected by
the real stale-target validator. Only an observed blocked write permits the
rollback fault injection, after real validation succeeds. Both branches assert
exact final bytes and receipt/temp cleanup. Production is unchanged. Independent
review accepted the repair. Actual Windows CI establishes the platform result
before merge; no particular Windows error code is assumed.
