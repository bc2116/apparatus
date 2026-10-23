# Core release candidate 0.0.3 — 2026-10-23

The versioned source passed isolated installed-core probes, the full repository
suite, and four focused native CLI conversations. Current-head CI, independent
review and remote merge complete PR-73's gate; the exact merge commit must then
be recorded as the immutable candidate in the rehearsal record. Signing,
native installer acceptance and publication remain separate gates.

## Source and artifact identity

The tested source is `768b7594bb6946ae5e5f3f615613c82061939170`. Relative to the
[inventory](../releases/next-release-inventory.md), only core project metadata,
the runtime version and its lock entry change product inputs, all to **0.0.3**.
The monorepo and optional-module versions stay unchanged. Changelog and
qualification documents add no runtime behavior. GitHub and PyPI collision
checks found no 0.0.3 before versioning. Recheck before creating the release tag.

The [evidence capsule](evidence/release-candidate-0.0.3/) records source hashes,
embedded-resource comparisons, dependency versions, commands and inventories.
All recorded source inputs still match after integrating the inventory PR's
remote merge. Verify that parity again after this PR merges; tag that exact
merge commit, never a later documentation commit.

| Artifact / recipe | SHA-256 |
|---|---|
| Ordinary `uv build` wheel | `c2d765d45cff226d89c94509dce6c1ba45b226defb40a27e276aba5bece7f0fa` |
| Ordinary `uv build` sdist | `a1e3daf2867b973b362cdb5d16b7329e838c4620c6feb0c83dadd17fca10e949` |
| Normalized acceptance wheel | `a00323402ce367c0a3301cea9463dbb996a08edf0dd90f47451424937f03e558` |
| Payload archive, both recipes | `3fb3d3e0400ecc35cd8e25e98b3294de671c16892392d67e1bd4011678d11f4d` |

The acceptance runner sets `SOURCE_DATE_EPOCH=315532800`; ordinary uv builds
use a different ZIP timestamp. The wheels therefore have different whole-file
hashes. Every archived member is byte-identical, including METADATA and RECORD;
[package-equivalence.json](evidence/release-candidate-0.0.3/package-equivalence.json)
records the comparison. Two normalized wheels and two payloads separately
reproduce exactly. All embedded resources match the canonical starter.
The ordinary wheel also passed a separate clean external import/version/init
check. These local hashes do not predict signed CI artifacts.

Fresh dependency resolution installed pypdf 6.21.2, satisfying the declared
`pypdf>=6.19.0`; the repository suite uses the lock's 6.19.0. Installed
distribution and dependency-wheel hashes are retained. No universal PDF
safety claim or optional-module publication follows.

## Installed behavior

The unchanged prior [core-readiness runner](evidence/core-readiness-2026-10-12/run.py)
ran against the new source/version, outside the checkout. Both CLI aliases
passed fresh init, exact no-change rerun and deliberate shim repair while
preserving project files. It verified Fact capture, source-backed recall,
read-only bound-project resume, Markdown/PDF citations, content-free malformed
PDF failure, refusal of managed writes in no-save tasks, and requested project
output as the only allowed addition. Canonical/ancestor-alias backups passed;
final-link and inside-work-area destinations were rejected without changes.

The additional probe passed explicit adoption with custom instructions and
project content preserved, implicit-adoption rejection with no changes,
Decision capture/recall, managed Memory restore that preserves live task
controls and project content, and stale Library hit suppression without a
no-save inventory change. Its first two attempts used nonexistent CLI flags
(`--no-save-memory`, then `--no-save`). Both failed captures and runner revisions
are preserved. The corrected `--no-memory` invocation passed; these were probe
errors and did not require a product repair.

## Native app observations

Each available app received an isolated synthetic work area installed from the
candidate wheel. First it made a practical 40-minute workshop plan for ten
participants and saved the explicit printed-handouts Decision. A fresh process
then continued with a new, preconfigured no-save task and saved only the
requested follow-up. Owners and other equipment remained unknown.

| Surface | Settings and observed result |
|---|---|
| Codex CLI 0.158.0-alpha.2 | Requested `gpt-6-luna`, medium effort; output did not expose the actual model identity. Both cases passed file-change checks and produced grounded deliverables. Retained command evidence includes recovered path mistakes and an unsuccessful recall before direct source reading. |
| Claude Code CLI 2.1.296 | Requested `sonnet`, medium effort; structured output reported `claude-sonnet-5-5`. Both cases passed file-change checks and produced useful source-linked deliverables. Its JSON supplies no command trace, so invocation of resume is not independently established. |
| Cursor IDE | Launcher reported no installed IDE. No new observation; Cursor agent was not substituted. |
| Codex desktop | Not exercised by this CLI sample. |

For both no-save continuations, the complete work-area/APPARATUS_HOME inventory
changed only by adding `project/followup.md` and its parent's size/mtime. Existing
files, tasks, cache and recovery state did not change. First-task saving produced
the requested Decision and documented snapshot state. Raw provider logs are not
stored; normalized deliverables, selected command evidence and output digests
are retained. App-owned temporary/provider metadata is outside this inventory.

Semantic inspection found the proposed agendas total 40 minutes and neither app
invented named owners or confirmed equipment. Claude's follow-up says none of
the readiness criteria is met; the evidence establishes only that none is
confirmed. That wording limitation is retained, not silently rewritten. This
small sample qualifies the observed file and continuation paths, not general
task accuracy, automatic discovery or broad cross-app certification.

## Validation and next gate

`uv run pytest`: **1,792 passed, 43 skipped**, 550.23 seconds. Builds and isolated
checks passed. Platform skips do not qualify unavailable systems. The offline
evidence checker verifies consistency and file digests; it does not rerun apps
or prove semantic quality. Exact commands are in `validation.json` and individual
captures. Review and current-head CI are required before remote merge.

After merge/parity verification, dispatch the existing Release workflow as a
signed dry-run while main still names that candidate. Record its exact source,
seven distributables, signatures and checksums under PR-74. Do not publish or
upgrade the support matrix based on this source qualification alone.
