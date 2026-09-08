# PR-56 verification

The signed `v0.0.1` tagged attempt completed both platform signing jobs and
assembly, but GitHub skipped PyPI because the unused Windows signer is a
skipped ancestor. The explicit cancellation-aware publication predicate now
requires both direct dependencies to succeed. Regression cases exercise the
actual predicate with a skipped unused signer, failed dependencies,
cancellation, dry-run mode and manual dispatch. The next immutable tag uses
package metadata version `0.0.2`; the full first-release notes move with it.

The on-demand acceptance path verifies the source workflow, tagged commit,
required signing and publication results, expected artifact contents and PyPI
distribution hashes before executing unchanged native installers. It requires
an actual console session on Mac and an ordinary Windows x64 user, plus clean
default targets. Native install, installed version, workspace integrity, one
managed-file repair and project-file preservation are recorded separately.

The focused release-workflow suite passed after making its existing real-build
fixtures version-independent. The 49 acceptance tests passed, including source
and artifact rejection, Mac signature output variants, installed-version
mismatch before managed-file removal, and failed or byte-mismatched repair
without false success. `uv lock --check` and `git diff --check` passed. An
independent review caught and removed a Python 3.10-incompatible test import.
Final CI supplies the required full repository pytest suite.

Actual native install-and-repair acceptance has not run in this PR: it needs
the newly published package. Both signed native artifacts are already proven
in the preceding rehearsal, but this evidence does not claim installation.
The original tagged workflow's public Release remains held until both new
native receipts pass. Starter, installer and conformance behavior are unchanged;
core differs only in its version string, so existing AI-app interaction
evidence is reused with that qualification.
