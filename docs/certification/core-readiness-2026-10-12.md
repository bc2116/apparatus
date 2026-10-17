# Retained core source-build readiness — 2026-10-12

## Decision and boundary

The installed-core acceptance probes and full repository suite passed on the
retained source candidate. Independent review found no material issues.
PR-70 remote-merge/source parity, current-head CI and PR-71 remote merge remain
external delivery gates before completion. This is source-build acceptance, not a public release,
signed/native installer acceptance or broad AI-app certification.

The [bounded plan](../plan/next-release-features.md) now takes its two-slice path:
[PR-70's comparison](document-review-comparison-2026-10-12.md) retains current
Skills, omits A2 and leaves relinking deferred; PR-71 verifies core. Additional
email testing remains deferred. Existing module regression tests still run,
but optional-module publication and new mailbox qualification are outside this cycle.

## Candidate and change inventory

Candidate source: `bfb18de0205cdc45480c33da60b3dbdb80399e03`, the independently
reviewed PR-70 head. Its source identity is verified before and after probes;
remote-merge parity is checked separately. No runtime or payload changes are
introduced by PR-70/71. Since PR-62's `6d05582` candidate, the retained core change
is the distributable `pypdf>=6.19.0` floor. The other affected retained paths are
its lock metadata and a CI-matrix test. Optional-module changes keep their own
qualification boundary. The [source inventory](evidence/core-readiness-2026-10-12/source-changes.json)
records those paths without relabeling earlier evidence.

| Artifact | SHA-256 / observed value |
|---|---|
| Core wheel, source version 0.0.2 | `4dc33640087647e5b08a4e3490bcb0c7e4c36a242d72cb256e6850c887761bce` |
| Payload archive | `75dddb640b6433f7241e4e2134013abaf63f3adb349f0434ea4cbdc13e453d34` |
| Wheel requirement | `pypdf>=6.19.0` |
| Fresh isolated resolution | `pypdf 6.20.1` |

Two builds produced identical wheel bytes and two builds produced identical
payload archives. All embedded source resources matched canonical starter bytes;
the payload contains 25 payload/profile files plus its manifest. Its archive hash
matches the older unchanged payload. The installed package imported from the
fresh external environment; no optional module was installed. Dependency wheel
hashes and resolved installed-file identities are captured. Fresh resolution
follows wheel requirements, not the repository lock; the ordinary repository
suite separately uses its locked environment. This is not a universal PDF safety claim.

## Installed behavior

A bounded runner built from an external copy, preserving source inputs, then ran
the installed executable outside the checkout on synthetic files:

- Both `apparatus` and `ap` initialized a work area, repeated init without any
  inventory change, and repaired one removed shim to its exact bytes while
  preserving the project sentinel. Expected explicit-repair receipt/recovery
  writes are enumerated; they are not no-save exemptions.
- A saving task persisted a verifiable Fact. Resume resolved a bound project,
  returned its goal/next action and changed no inventoried runtime state.
- Markdown and generated PDF originals were registered, extracted and found by
  source/snippet. A malformed PDF returned a content-free extraction error;
  its sentinel body did not appear in command output or error text. `check` passed.
- After no-save task creation and baseline capture, a managed Memory write was
  refused with zero state change. Task inspection, resume and check also wrote
  nothing. One explicitly requested fixture note was then added; only its parent
  directory size/mtime changed. No existing file, control, cache, receipt or
  recovery metadata changed. This is a deterministic CLI/fixture probe, not a
  native assistant conversation. PR-70's separate native continuation retains
  its own source identity and narrower coverage.
- Canonical and valid ancestor-symlink backup destinations each produced one
  archive, used the canonical destination in output/receipt, excluded project
  files and Library originals, and preserved protected files and independent
  project Git state. Final-link and inside-work-area alias destinations exited
  2 with zero archives and exact state preservation. The ancestor alias is a
  synthetic POSIX fixture, not a broad filesystem guarantee.

## Evidence and remaining qualification

The [capsule](evidence/core-readiness-2026-10-12/) includes the rerunnable probe,
source/artifact/dependency identities, commands, inventories and explicit result
assertions. Its offline checker verifies captured consistency and digests; it
does not rebuild artifacts or establish native behavior. Local artifact bytes
remain build outputs, not newly published distributions.

`uv run pytest` passed with **1,792 passed and 43 skipped** in 542.69 seconds.
The locked source environment used pypdf 6.19.0; the isolated wheel environment
resolved 6.20.1. Platform-conditional skips do not qualify unavailable lanes.
Independent review verified source identity, resource parity, captured outcomes
and boundaries; it did not rerun builds or the suite. The offline checker passes.

After current-head CI, dependency merge/parity and remote merge pass, the retained
source is ready to enter the separate [release runbook](../release-runbook.md).
Versioning, signing, native installer acceptance and publication remain separate.
Prior native discovery observations stay dated and limited; this work neither
adds an adapter nor upgrades them to a new automatic-discovery claim.
