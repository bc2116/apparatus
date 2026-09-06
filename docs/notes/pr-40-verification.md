# PR-40 verification

Final local integration includes the patched PDF dependency and inherited
Windows binding/canonical-path repairs. `uv run pytest` passed **992 tests,
38 skipped** in 363.82 seconds. Actual Windows CI must pass this integrated
source before delivery. The two Skill bodies are unchanged from accepted review.

Authoring and local validation: 2026-09-06, macOS, Python 3.12.4.

The payload has seven canonical portable Skills. Five legacy procedure mappings
and their exact pointers remain separate. Complete historical five-Skill sources
remain usable; seven-Skill evidence requires a complete seven-file source.
Migration retains root and byte/absence proofs, preserves custom instructions,
profile/task controls and unrelated files, and reuses existing compensation.

Evidence completed:

- 35 new integration cases cover five/seven migration and source validation,
  LF/CRLF stock witnesses, custom content, stale preimages, late compensation,
  task controls, no extra retention, historical Git/archive/restore round trips
  and exact legacy-pointer compatibility. Existing Skill, overlay, instruction
  and payload coverage was extended deliberately to seven names.
- Four static guidance/prose tests pin resource/repair boundaries, the unchanged
  starting table, selective editing and protected content. They do not execute
  models or prove semantic quality.
- The lead independently reviewed the complete synthetic long-document pair and
  accepted preservation and usefulness; see [the scenario note](r6-synthetic-scenarios.md).
- `uv sync --all-packages`, `uv run python conformance/payload_check.py`,
  `uv run python tools/build_payload.py`, and
  `uv build --package apparatus-core` passed. The universal payload has 23 files.
  All seven source, embedded, wheel and universal ZIP bodies match exactly;
  the source distribution includes all seven. Pointer rendering matches goldens.
- `git diff --check` and the staged equivalent passed. The four hidden new
  payload files were explicitly added to Git; no commit was made by the author.

`uv run pytest` passed: **989 passed, 38 skipped in 320.67 seconds**.
The first run found three conformance assumptions about the old five-Skill set/numbered
workflows and explicit authority wording; those were addressed and focused
reruns passed without weakening the everyday workflow or authority checks.

Independent implementation review accepted the final diff against the contract
and ADR. Actual Windows CI and dependency merges remain delivery checks.
The Windows safety lane includes both new test modules. The late competitor
fixture records whether the native filesystem permits the competing write and
asserts preservation or complete rollback accordingly; it does not assume a
platform-specific outcome or skip safety checks. No native adapter certification,
live model efficacy, measured savings or new quota enforcement is claimed.

## Windows portability repair

Windows run `34048742428` at `156302eb` completed with **786 passed, 79 skipped,
1 deselected and 2 failed** in 3918.45 seconds. A prose fixture used the platform
default encoding, and a rejected source reparse point lost its relative filename
from the diagnostic. Both were reproducible failures, not a runner timeout.

All four guidance/fixture text readers now specify UTF-8. The retained source
reader keeps missing-file behavior and wraps other I/O failures with the known
relative filename and readable-file/no-links guidance. It does not follow or
retry an unsafe source. Existing sentinel-preservation assertions remain intact.
Independent review accepted both repairs.

The focused existing guidance, source-symlink and Skill tests passed **32 tests**
in 4.33 seconds. The complete repaired local suite passed **992 tests, 38 skipped**
in 300.62 seconds. The preceding ancestry-only rebase onto the merged portable
Skills dependency preserved the exact prior file tree. Actual Windows rerun is
still required before delivery.
