# PR-37 verification

Local verification on macOS, Python 3.12.4:

- `uv sync --all-packages`: passed.
- `uv run pytest -o addopts='' packages/apparatus-core/tests/test_library_index.py -q`:
  **43 passed**.
- Regression sensitivity: loaded only the original `_writer_lock` function
  from `068e645` into the test process, without modifying workspace files.
  Both deterministic release scenarios and both retry-exhaustion scenarios
  failed against that function (**4 expected failures**). All pass with the
  repair.
- `git diff --check`: passed.
- Full `uv run pytest`: **678 passed, 38 skipped**.
- Independent review accepted the bounded retry and its regression coverage;
  the reviewer also reran all 43 Library index tests successfully.

The release tests obtain mode/link metadata from native opened and unlinked
files. They run on POSIX; the separate Windows implementation is unchanged,
and its existing focused tests pass locally. Actual Windows CI remains pending.
This note does not claim
cross-platform completion or a merged PR.
