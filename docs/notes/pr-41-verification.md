# PR-41 verification

Final local integration includes PR-40, the patched PDF dependency and both
inherited Windows repairs. `uv run pytest` passed **1,043 tests, 38 skipped**
in 415.44 seconds. Independent review accepted the seven-Skill stock migration
and learned-Skill integration. Actual Windows CI remains required before merge.

Author validation before PR-40 integration:

- `uv run pytest`: **979 passed, 38 skipped** in 305.28 seconds.
- Focused learned-Skill, Skill-check and recovery coverage: **66 passed**.
  Additional command, path and migration cases were included in the full run.
- `uv run python tools/build_payload.py --out <temporary-directory>` passed.
- `uv build --package apparatus-core --out-dir <temporary-directory>` built
  the source distribution and wheel. The wheel contains the learned-Skill
  helpers, command module and registered CLI entry point.
- Canonical and embedded starter trees match byte-for-byte (23 files).
  Shims and their goldens are regenerated. `git diff --check` passed.

The tests exercise inactive credential-checked drafts; exact digest-bound
adoption; repeat/no-op and editable adopted bodies; no-save and missing-task
rejection before input reads; absent enrollment; unsafe/foreign destinations;
closed ownership metadata; late publication and redaction-receipt compensation;
observed concurrent mutation or native denial; bound-project routing; and
registered-pair capture, archive export and historical restore. A later adoption
survives restoring an earlier snapshot. Drafts and unregistered native files
remain outside managed recovery. Historical manifests reject unpaired files.

These are file, subprocess and real-Git proofs, not live AI-app invocation or
certification claims. The new suite is included in Windows safety CI; an actual
Windows run and independent implementation review remain required. PR-40's
expanded built-in registry must be integrated and validated before delivery;
learned ownership uses a separate registry and does not assume a built-in count.

Independent review repair: adoption now requires a newly created, invocation-owned
native Skill directory at publication and binds the body write to that exact
directory proof. A competing empty directory or one containing a user resource
is preserved and rejected, without publishing a body or ownership record. Both
deterministic race cases fail against the pre-repair implementation and pass
after the repair. Existing late-publication compensation and retry cases pass.

After this repair, the complete learned-Skill/check/recovery selection passed
**71 tests**, and `uv run pytest` passed **981 tests, 38 skipped** in 270.02 seconds.
`git diff --check` passed. Actual Windows validation and PR-40 integration remain
delivery checks; no native runtime evidence is inferred from this local run.

## Integration with PR-40

Rebased onto PR-40 `6ad3e04`, retaining its seven canonical Skills, economy/prose
guidance, historical five-Skill source compatibility and named recovery coverage.
Exact PR-40 orientation and shim fixtures now provide stock migration witnesses.
Current PR-41 and historical PR-40 orientation both require a complete seven-Skill
source; PR-38/39 witnesses retain their historical five-Skill meaning.

- The migration cases cover LF/CRLF stock, custom bodies/instructions/guidance,
  saving/no-save tasks, unchanged profile/task controls and repeat no-op behavior.
- The real-Git case restores PR-40 state while preserving later learned adoptions,
  then remigrates the canon and exports all seven built-ins and registered learned
  pairs without drafts.
- The integration selection passed **160 tests**. The updated historical case
  and new migration/source checks then passed **17 tests** (33 deselected).
- Integrated `uv run pytest`: **1040 passed, 38 skipped** in 457.23 seconds.
- Payload ZIP and core source-distribution/wheel builds passed. All 23 canonical
  and embedded files match, with regenerated shims matching goldens. All seven
  bodies match the universal ZIP, wheel and source distribution; learned command
  modules and the CLI entry point were verified in the wheel.
- `git diff --check` passed.

PR-40 dependency integration is complete for this validation state. Independent
integration review, actual Windows validation and subsequent upstream repairs
remain delivery checks. No native AI-app invocation or certification is claimed.
