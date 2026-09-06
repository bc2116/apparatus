# PR-39 verification

Final local integration includes the patched PDF dependency and the inherited
Windows binding/canonical-path repairs. `uv run pytest` passed **949 tests,
38 skipped** in 247.20 seconds. The welcome implementation is unchanged;
actual Windows CI must pass the integrated head before delivery.

Local preparation on macOS, Python 3.12.4, 2026-09-06:

- Full `uv run pytest`: **946 passed, 38 skipped** in 223.53 seconds after integrating recovery,
  Library locking, adoption and portable Skills. The initial parent run had
  934 passed and 38 skipped.
- All 23 source/embedded payload files match. Thirteen exact PR-38 instruction
  fixtures were checked against their historical source; five hidden Skill
  fixtures are explicitly tracked.
- Task-first command stories cover saving and no-save tasks, project-local
  output, dirty project Git preservation, a single explicit preference change
  with either profile status, and unchanged unrelated profile values.
- Migration checks cover stock LF/CRLF instructions, custom content, stale
  preimages, late compensation and repeat no-op. Ignore checks retain ordinary
  sources, custom rules and disabled features.
- Research conformance uses the requested format while preserving citations,
  credential protection and meaningful recovery behavior. Checklist and weekly
  reviews remain requested-only.
- Independent review accepted the final instructions, profile change and
  migration. `git diff --check` passed.

The required Windows lane includes the new task-first regression suite. Actual
Windows CI and dependency merges remain delivery gates. These
command and instruction checks do not prove live assistant behavior or native
app certification.
