# PR-39 verification

Local preparation on macOS, Python 3.12.4, 2026-09-06:

- Full `uv run pytest`: **934 passed, 38 skipped** on the initial PR-38 parent.
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

The required Windows lane includes the new task-first regression suite. Final
dependency integration and actual Windows CI remain delivery gates. These
command and instruction checks do not prove live assistant behavior or native
app certification.
