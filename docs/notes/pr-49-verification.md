# PR-49 verification

## Observed defect and scope

A native Library add registered a synthetic project original but reported
extraction unavailable with a symbolic-link diagnostic. A later explicit
alternative cache location succeeded. The native log does not expose the
original operating-system exception; permission denial is consistent with the
observation but is not established by that log alone.

An isolated probe through the actual retained directory-creation helper
established the diagnostic defect: injected EACCES and EPERM permission failures
and an ENOSPC storage failure were all labeled as symbolic links. No global
cache or home directory was inspected or changed. An actual synthetic cache
symlink was rejected and its outside target remained unchanged.

The repair retains cache selection, no-follow creation, explicit link/reparse
checks and workspace exclusion. Permission failures now give a fixed
access-denied message with an explicit writable `APPARATUS_HOME` action outside
the work area. Other creation errors get a truthful safe-creation/storage
message. Neither message interpolates operating-system details or paths. The
same diagnostic boundary covers existing POSIX and Windows creation calls;
there are no automatic retries, permission changes or relocations.

## Checks and artifacts

- `uv sync --all-packages` passed; pypdf remains **6.16.1**.
- Both focused Library files passed: **50 passed**, exit status zero.
- Six creation-fault regressions cover EACCES, EPERM and ENOSPC at initial home
  creation and the retained POSIX child boundary. They assert one attempt,
  preserved exception cause, fixed actionable text, no raw error/path echo and
  no workspace writes or completed Library cache. The three POSIX child cases are inapplicable on
  Windows; the three home cases exercise native platform creation.
- The real registration command regression preserves the valid registration,
  both project originals and existing Memory when cache access is denied. It
  reports failed extraction and no card, and creates no alternative cache.
- Existing cache-link and creation-time substitution tests remain green,
  including the outside-target preservation assertion.
- Both existing test files already run in the Windows CI lane.
- Package and universal payload builders passed. All **80 tracked package
  source/resource files** match wheel and source distribution. All **25 starter
  files** (**23 payload plus 2 profiles**) match embedded files, ZIP and base.
  Payload bytes are unchanged.

The build matches committed source
`1e50521f1aae41759123cc21f1a9f91c9f89a6a9`, based on
`a9d10d02c3c28aa3894e432cf617e6761c5ae94c`. Independent lead review accepted
the source and regression tests with no blockers. The `cache.py` SHA-256 is
`231820bd351b9a6752bbc7ba0f5f049b1c351ef78ad1206def884c1bf4067f9c`.

- Wheel `apparatus_core-0.0.1-py3-none-any.whl` SHA-256:
  `84dea9eb17fcaea356013bb673dfbcc90677962eb2011c00815094327c71b956`.
- Source distribution `apparatus_core-0.0.1.tar.gz` SHA-256:
  `3a85021db3c9e0f08d4cbd9dba8e7c2d57b546db496b79b77f488550f161aa08`.
- Universal payload `apparatus-payload-0.0.1.zip` SHA-256:
  `24e20f0cd31898e66887f21f95a4964fedd36d6f06a5205df14ce20a00b74851`.

Final `uv run pytest` passed: **1265 passed, 38 skipped in 552.43 seconds**.
`git diff --check` passed. Production source stayed frozen throughout the full
run; only the verification note and PR-49 plan status changed afterward.
Native Windows CI and renewed AI app acceptance are separate checks; previous
native observations are not relabeled by these synthetic tests.
