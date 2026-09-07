# PR-49 — Explain Library cache creation failures accurately

Depends on PR-48. Native app acceptance observed a successful registration
followed by a cache error described as a symbolic-link problem. The native
output does not expose the original operating-system error. An isolated
reproduction establishes that the cache creation boundary also gives this
message for permission and storage failures, so the diagnostic can misdirect
repair even when no link exists.

## Scope

Keep the cache location contract, no-follow directory operations, link/reparse
checks, and Library registration/extraction/card separation unchanged. Give
permission failures a fixed, actionable access diagnostic. Other creation
failures must be described truthfully without printing sensitive paths or raw
operating-system details. Preserve explicit unsafe-link rejection. Do not retry,
change permissions, relocate caches automatically or add a new subsystem.

Own `cache.py`, focused cases in the existing Library test files, this prompt,
the plan status row and a short verification note. A new native acceptance
baseline must identify this narrow repair; keep prior runs as dated observations.

## Acceptance

1. Isolated permission and storage faults do not falsely assert a symbolic link.
2. An unsafe existing cache component or a link substituted during creation is
   still rejected without writing outside the selected cache.
3. Failed extraction retains a valid original registration, produces no card
   and gives a concrete action. Existing originals remain unchanged.
4. Focused tests, full `uv run pytest`, package/payload parity and required
   native CI pass. Keep the payload unchanged. Do not alter conformance fixtures
   merely to accommodate an inaccurate diagnostic.

Use frontier/high for the retained-filesystem-boundary review. Deliver one
focused DCO-signed PR and preserve unrelated work.
