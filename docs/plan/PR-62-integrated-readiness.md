# PR-62 — Record integrated source-build readiness

- **Target:** Readiness documentation for the retained next-build slices.
- **Branch:** `pr-62-integrated-readiness`.
- **Plan slice:** N6 in [next-build.md](next-build.md).
- **Dependencies:** PR-58, PR-60, and PR-61 landed; source-equivalent base `6d05582`.

## Goal

Produce one concise, source-grounded readiness decision for the integrated
candidate. It must connect verifiable Memory saves (PR-58), the read-only resume
brief (PR-60), safe backup-destination aliases (PR-61), and the refreshed
native Skill-discovery observations without relabeling qualified evidence as a
public-release claim.

This is an evidence and documentation slice. It does not add product behavior,
move sources, add a discovery adapter, publish a package, or authorize an
installer, signing, or release action. Read [ADR-0006](../adr/ADR-0006-lean-workspace-and-skills.md),
N6, the four retained PR prompts, the dated [certification matrix](../certification/matrix.md),
and the cited native records before writing.

## Candidate identity and evidence boundary

Use the candidate wheel SHA-256
`6284f08fd3fccb63e6fa98cfa236f8b7e219c0aeb796fe861bdabd1f7749ab5c`
and payload identity
`200eb6c5833b1977e9c7927301b7567983ee717d5d250bf47be1b1aa61439a07`.
The built payload archive SHA-256 is
`75dddb640b6433f7241e4e2134013abaf63f3adb349f0434ea4cbdc13e453d34`.
The candidate identity record enumerates the source files and verifies 23 wheel
payload files; preserve that file-level identity rather than inventing a commit
claim for an uncommitted build.

Record that PR-61's local integrated source suite passed **1469 tests with 42
skipped**, and its review passed. The PR-60 Windows run required a golden CRLF
repair confined to `.gitattributes`. PR-60 CI passed at `5f64054` and merged
as `06444fe`. Record final PR-61 CI and this PR's full-suite/review outcomes,
then require this PR's current-head CI before merge. Pending CI is not a pass.

The previous PR-58 and PR-60 native records remain dated and source-specific.
They support only their stated synthetic cases; they do not automatically renew
native behavior for this candidate. The PR-61 installed-wheel backup check is a
separate product-CLI result: canonical and ordinary system-alias destinations
passed, while final-link and inside-work-area alias cases correctly failed
closed.

## Required readiness record

Add `docs/certification/next-build-readiness-2026-09-19.md`. It must:

1. State the narrow decision first: retained source-build acceptance passed,
   with each remaining CI gate stated accurately. It is not broad app certification, a new public
   release, or installer/signing acceptance.
2. Name the wheel SHA-256, payload identity, payload archive SHA-256,
   deterministic suite result, actual CI status, and source-build-only boundary. Do
   not include local absolute paths, raw chat logs, account identities, or
   undocumented settings.
3. Summarize the refreshed native discovery cases on the named Cursor IDE
   configuration: root canonical Skill body observed (pass); bound-project
   basic task passed but canonical discovery was not demonstrated (partial);
   collision precedence was not established (partial); non-relevant task showed
   no irrelevant marker but had command-path friction (qualified pass). Preserve
   the limits of each observation.
4. Record the completed saving/fresh no-save continuation as a pass on the
   named candidate and native configuration. The saving conversation persisted a
   Decision with reason, updated the goal next action, added a selected Library
   original and card, and took a snapshot. The fresh 31-second no-save
   conversation ran ordinary continuation without naming the command or two-page
   choice; `EXECUTABLE resume PROJECT` resolved the linked work area and returned a partial
   brief with the missing retired source and unavailable history. It used the
   current Decision and 10-participant/40-minute details, cited the relative
   Decision, brief and outline, and left equipment, facilitator, date and source
   excerpt unknown. Record the 117-file byte-for-byte no-save baseline, the sole
   requested worksheet addition, and no directory/cache/Git/control-state delta.
   Distinguish a Markdown two-page outline from actual print pagination, which
   was not verified. Preserve prompt/result/hash/delta evidence; do not rerun or
   rewrite a failed interaction to obtain a pass.
5. Record N4 as deliberately deferred: no early-use observation has established
   a moved-source repair need; a prepared missing-source negative fixture is not
   product demand. Record N5 as deliberately deferred: missing or partial Skill
   selection does not isolate an adapter/visibility need. Do not turn either
   deferral into a claim that the underlying scenario passed.
6. Retain PR-61's installed-core backup results precisely: the candidate's
   ordinary external destination alias and canonical path each published one
   archive with protected files unchanged and project/Library originals
   excluded; final-link and inside-work-area alias negatives exited 2 with no
   archive. This does not establish a native installer or a broad filesystem
   guarantee.
7. Link to the archived synthetic integrated evidence directory, the dated
   PR-58 and PR-60 records, and the matrix. Link only repository-relative
   evidence; preserve hashes, prompts, outputs, tree deltas and explicit gaps,
   not raw native-chat exports.

## Quickstart update

Update `docs/quickstarts/codex.md` beside its setup and matrix guidance. Link
this readiness note, keep the September 19 observation as an unreleased
source-build/isolated core-and-payload check, and give the tested ordinary
source-checkout example: `uv run apparatus resume PROJECT` for an explicitly
bound project resolves its linked work area. Explain that the native fresh prompt
need not name this command; the assistant selected it in the observed case. This
does not replace the matrix's published installer, signing, repair, or
public-release evidence. Do not change other quickstarts or claim an updated
public version.

## Evidence checkout preservation

Disable Git text conversion only for this dated evidence capsule in
`.gitattributes`, so recorded native bytes and digests survive differing
checkout policies. Verify an export with `core.autocrlf=true` against every
staged archive file; do not normalize captured outputs or weaken hashes.

## Ownership

This PR owns the integrated readiness documentation:

- `docs/plan/PR-62-integrated-readiness.md`, `docs/plan/README.md`, and the
  exact N6 decision in `docs/plan/next-build.md`;
- `docs/certification/next-build-readiness-2026-09-19.md`, the dated
  certification matrix update, and the synthetic integrated evidence directory;
  and
- the tested source-build update in `docs/quickstarts/codex.md`.

Work may divide these files among named contributors, but the final PR must
reconcile them. CI, delivery, package metadata, installers, and product code are
outside this documentation slice. Preserve concurrent work.

The dated-capsule raw-byte rule in `.gitattributes` is also in scope.

## Validation and completion

Check internal links, candidate identity and archive SHA-256 values, exact
test/skip counts, and the pending/partial/pass wording against retained evidence.
Run `uv run pytest` and any available documentation link or formatting checks.
Review the diff to ensure the quickstart neither promises a release nor alters
ordinary setup instructions.

Set the PR-62 plan row to `✅ landed` only in the integration-owned plan update
once these files, the archived evidence, and the final readiness decision agree.
