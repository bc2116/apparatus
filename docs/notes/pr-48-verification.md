# PR-48 verification

A native first-task acceptance attempt reached a valid work-area profile through
macOS's `/var` external ancestor alias and failed before snapshot creation. A
read-only reproduction outside the AI app established the same `ENOTDIR` failure
at the `var` component; the canonical `/private/var` path read identical valid
profile bytes and enabled settings. The earlier app attempt remains a failed
acceptance observation; this repair does not relabel it as a pass.

## Change and boundary

The shared `features._profile_read` entry calls the existing workspace preflight
primitive before platform dispatch. Only external ancestors are canonicalized.
The workspace leaf is still rejected when linked; retained `System` and profile
reads, exact identity/content checks and post-parse currentness checks are
unchanged and reuse the captured canonical path. Preflight failures become the
existing actionable feature error. Missing pre-profile state keeps its defaults.
No CLI-only workaround, payload change, installer edit or filesystem redesign.

## Executed checks

- `uv sync --all-packages` completed; pypdf remains **6.16.1**.
- Before the fix, the two direct alias-selection cases and real CLI snapshot
  regression all failed: **3 failed** in **1.37 seconds**.
- After the fix, the full feature-selection file passed: **31 passed, 7 skipped**
  in **14.67 seconds**. Those skips are existing native Windows cases.
- New tests cover enabled/disabled settings, absent workspace/System/profile
  compatibility, unsafe workspace/System/profile links, translated preflight
  errors and same-byte canonical-root replacement after parsing.
- A real managed snapshot succeeds through a synthetic external alias while
  preserving the complete dirty project file/Git tree: committed, staged,
  unstaged and untracked content. The selected work area gains its isolated
  recovery store and no root Git repository.
- The existing Windows safety lane already runs `test_feature_selection.py`.
  Its new alias fixtures require native link support; they do not silently skip
  unavailable link primitives. Native Windows execution remains a CI check.
- `git diff --check` passed. No earlier app fixture was modified.

Independent lead review accepted the shared-boundary repair and focused
regressions with no blocker. The scoped alias-repair full suite passed:
**1258 passed, 38 skipped in 560.98 seconds**. This run precedes integration of
the separately reviewed inherited Windows compatibility repairs.


## Preliminary alias-repair artifacts

These artifacts precede the inherited Windows compatibility repairs and are
not the final combined native-acceptance build. The wheel, source distribution
and universal payload builders passed. All
**80 tracked package source/resource files** match the wheel and source
distribution. All **25 starter files** (**23 payload plus 2 profile files**) match
the embedded copy and universal ZIP and remain byte-identical to base `78e09ec`.

- Wheel: `apparatus_core-0.0.1-py3-none-any.whl` — SHA-256
  `0cc1e459a51bf4e1cab5abe91c21433eba41ac2a9871d3315ef2892d84955330`.
- Source distribution: `apparatus_core-0.0.1.tar.gz` — SHA-256
  `a048eed5f758c397d376258883145a9f0def27bc67c07b9ee5d4473c99f284bf`.
- Universal payload: `apparatus-payload-0.0.1.zip` — SHA-256
  `24e20f0cd31898e66887f21f95a4964fedd36d6f06a5205df14ce20a00b74851`.

The payload hash is unchanged because this repair edits core feature reading
only. Renewed native AI app acceptance must use the repaired wheel and a new
fixture; artifacts and local tests are not native-app certification.


## Final combined integration

The two PR-48 commits were rebased onto reviewed PR-46 head
`7686b66a717c822e67dc646c24a8e0a88348cb8d`, producing source head
`7c0c6c4252bf948a0e4dd32decfb35cf308e963d`. Comparison with the previous
PR-48 head adds exactly the inherited three-file Windows repair: explicit UTF-8
conformance reads, contextual unsafe optional-payload diagnostics in `skills.py`,
and the PR-40 verification note. No additional payload or installer behavior
changed.

- The final combined `uv run pytest` passed: **1258 passed, 38 skipped in
  530.38 seconds**. Focused tests were not needlessly repeated.
- Fresh payload and package builders passed. All **80 tracked package
  source/resource files** match the final wheel and source distribution.
- All **25 starter files** (**23 payload plus 2 profile files**) match the
  embedded copy, final universal ZIP and the reviewed PR-46 base.
- `git diff --check` passed. Only this verification note and PR-48's plan status
  changed after the tested and packaged source head.

Final combined artifact SHA-256 values:

- `apparatus_core-0.0.1-py3-none-any.whl`:
  `5b3f11834131f564d0c521d5dfb77a39c9da4d08d13dd50e11bd39c587c02936`.
- `apparatus_core-0.0.1.tar.gz`:
  `7e6dff6c05aad6db629218166d4ae72dab62ed7a3ac5ba508faf837ce99b1da7`.
- `apparatus-payload-0.0.1.zip`:
  `24e20f0cd31898e66887f21f95a4964fedd36d6f06a5205df14ce20a00b74851`.

These combined artifacts supersede the preliminary alias-only builds above.
The lead has the final wheel for fresh native acceptance. Local verification
does not establish native Windows CI or AI app certification, and the earlier
failing Cursor fixture remains unchanged.
