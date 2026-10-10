# Mailbox Survey release recognition — 2026-10-10

PR-68 adds exact per-asset content matches and complete matches to the existing
lifecycle status. The executing package remains distinct from deployed content.
Source versions 0.1.0–0.1.3 share identical resources; the output correctly lists
all four rather than selecting an unsupported installed version. Module 0.1.4
adds optional guidance for the existing report summary and keeps its reference
unchanged. No package publication is claimed.

The [verification record](evidence/mailbox-release-recognition-2026-10-10/verification.json)
binds the source files, wheel and historical manifest by SHA-256. All four
historical source commits were checked against their package metadata, version
constants and resource bytes. The exact historical Skill fixture also survived
an actual Git checkout with `core.autocrlf=true`; its explicit LF attribute keeps
its 3,102 bytes and recorded digest stable on Windows checkouts.

## Isolated wheel acceptance

The wheel was built with `uv build --package apparatus-mailbox-survey --wheel`.
Two fresh environments ran from outside the checkout, with isolated Python
imports confirmed to resolve inside the installed environment. Every shipped
source/resource member was compared with the wheel archive.

| Environment | Result |
|---|---|
| Module 0.1.4 wheel, no Core, Python 3.14.7 | 198 report, summary and package tests passed. Both report commands succeeded and left input bytes and mtime unchanged. |
| Module 0.1.4 wheel, published Core 0.0.2, Python 3.14.7 | All 323 module tests passed; one Windows-only skip. |
| Workspace source, Python 3.12.4 | 323 module tests passed; one Windows-only skip. |

The public module command was also exercised directly against a synthetic,
explicitly enrolled work area. Fresh installation reported only 0.1.4 as a
complete match. Replacing its body with the exact historical fixture reported
all four historical complete matches and the existing conflict state. Repair
returned conflict exit code 1 without changing the historical file's bytes or
mtime. Unknown, mixed, missing and malformed-manifest cases are covered by the
module tests, including no creation before complete preflight.

## Core preservation

Using the installed `apparatus init WORKAREA` entry point from published Core
0.0.2, a separate synthetic exercise repeated initialization in four states.
In every case, existing module bytes and mtimes were unchanged.

| Module state before Core init | Result after Core init |
|---|---|
| Current 0.1.4 pair | Still current, complete match 0.1.4. |
| Missing report-format reference | Still partial; explicit module repair subsequently restored the missing file. |
| Complete historical pair | Still a conflict, with all four historical content matches. |
| Synthetic local edit | Still a conflict; module repair refused and preserved the edit. |

This qualifies repeated initialization with one Core version. It is not evidence
of an upgrade between different Core versions, managed recovery for module
assets, or automatic update/removal. Windows acceptance comes from the required
current-head platform CI; the local exercises used macOS.

## Review and remaining scope

Independent specification and implementation review found no material issue.
Lead review added the exact fixture line-ending rule before delivery. Full-suite
and current-head cross-platform results are recorded on the pull request; the
verification record retains the completed local full-suite result.

Automatic update is deferred: the current POSIX name exchange cannot bind its
mutation atomically to the expected preimage. Preserving a displaced foreign
file in a backup does not satisfy the accepted ownership boundary. The
[module sequence](../plan/module-sequence.md) records this unresolved contract.
Recognition adds no mailbox access, source verification, native discovery,
provider qualification, workspace retention or recovery claim.
