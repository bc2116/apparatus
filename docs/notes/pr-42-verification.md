# PR-42 verification

macOS, Python 3.12.4, 2026-09-06:

- Full `uv run pytest`: **766 passed, 38 skipped** in 119.85 seconds,
  including existing Library extraction/index/recall and package conformance.
- `uv lock --upgrade-package 'pypdf==6.16.1'` changes only pypdf's package entry
  and Apparatus's matching dependency metadata.
- The resolved runtime is pypdf 6.16.1. Built wheel metadata requires
  `pypdf>=6.16.1`, preserving Apparatus's Python `>=3.10` requirement; the
  dependency supports Python `>=3.9`.
- Payload and wheel builds and `git diff --check` pass. Independent review
  accepted the dependency scope and advisory attribution.

Actual Windows CI remains a merge gate. Normal Library compatibility tests do
not independently reproduce all upstream security cases. The upstream evidence
is linked in the implementation plan.
