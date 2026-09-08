# PR-56 — Verify published installers on clean native runners

The first signed release is ready, but actual installer install-and-repair
acceptance needs the newly published package. The owner's Mac has a nonempty
Projects folder and the available Windows VM is ARM64. Provide one bounded,
on-demand acceptance path on fresh native macOS and Windows x64 runners.

## Deliverables and acceptance

- Correct the PyPI job's implicit dependency status gate: the intentionally
  skipped unused Windows signer must not skip publication after both direct
  dependencies succeed. Use an explicit cancellation-aware status function,
  require build and assembly success, tagged push, and publish mode. Preserve
  all protected environments and successful-signature requirements.
- Keep the already-created v0.0.1 tag immutable and record it as unpublished.
  Advance only package version metadata to 0.0.2 and move the first public
  release notes to that heading. Product and payload behavior stay unchanged.
- Extend the existing Release workflow's manual dispatch with an optional
  positive numeric `acceptance_run_id`. With no value, retain every existing
  rehearsal and tagged-publish behavior. With a value, run acceptance only;
  skip the build/sign/publish path. This mode needs no signing secrets,
  deployment environment or write permission. Use minimal `contents: read`
  and `actions: read` only where required; preserve immutable action pins.
- Resolve the source run in this same repository. Require the actual tagged
  push run, a valid version tag whose resolved commit equals its head, and
  successful build, both wrapper builds, exactly one Windows signer, Mac
  signer, assembly and PyPI publication. The public GitHub Release may remain
  waiting at its existing approval gate. Reject other events, wrong source
  identity, malformed IDs/tags, missing/failed/duplicated signer paths and
  incomplete package publication. Never execute downloaded source commands.
- Download the final apparatus-release artifact from that exact source run.
  Require the expected seven distributables, notes and checksum file; verify
  all hashes, regular files and exact filenames before native execution.
  Verify its Python distribution hashes against PyPI metadata for the same
  version. Do not accept an unrelated latest package as the tested version.
- Use fresh `macos-15` and `windows-2025` runners. Observe OS/architecture.
  Mac preflight must use the real console user, owned home and usable user
  session, with absent/empty ~/Projects. Do not rewrite console lookup, set
  a fake HOME, alter the package or substitute its flat script. Windows must
  be x64 and a normal user context, with an absent/empty target C:\Projects.
  Refuse unsafe/preexisting targets instead of adopting, moving or deleting
  them. A preflight refusal is a coverage gap, never an acceptance pass.
- Verify the native signature/notarization/ticket as applicable, invoke the
  unchanged signed .pkg through Installer / unchanged .exe wrapper, require
  successful completion, and verify the installed package version/workspace.
  Add a synthetic project sentinel, remove exactly one known unchanged
  shipped managed file, rerun the same native installer once, and verify
  repair restores its exact bytes while preserving the project sentinel.
  Keep commands and waits bounded. No extra assistant chats or broad matrix.
- Upload a concise JSON/Markdown acceptance receipt with source run/tag/head,
  artifact hashes, observed platform/architecture, command results, version,
  repair/preservation evidence and explicit limitations. Never upload
  credentials, private account data, whole runner homes or raw environments.
- Add focused meaningful validation for mode routing and artifact/source
  rejection where appropriate. Full required repository pytest is supplied
  by final-head CI; avoid another duplicate local full-suite run.
- Update the plan row as landed and a verification note in the same PR.
  Preserve product, payload, installer behavior and dependency constraints.

## Release boundary

The parent operator owns publication, environment approvals, artifact selection
and final acceptance. This change does not approve public installer downloads.
The unpublished tag attempt is v0.0.1, run 34267860246 on reviewed commit
bdee9fc0233696a3e8c1ded4c78a11ce649e792a. Its build and both signatures passed,
but the PyPI job was skipped by the implicit dependency gate. The first public
package will be 0.0.2 on a fresh tag after this repair. These are execution
facts, not hardcoded defaults for future users of the acceptance path.
