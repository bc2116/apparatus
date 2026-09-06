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

Initial Windows CI rejected two concurrency tests because retained file handles
correctly block the injected writer. The tests now explicitly require sharing
violation 32 on Windows, still require the successful competing write on POSIX,
and prove published-receipt rollback on both platforms. Production is unchanged.
Independent review required the injected validation failure to be Windows-only
so POSIX still exercises the real stale-content validator. The local full suite
remains 572 passed/38 skipped; platform CI verifies the Windows branch.
