# PR-46 verification

The installer implementation targets the selected work area directly, passes
adoption only on an explicit request and always delegates normal repair to core
init. The Windows wrapper carries the same adoption flag. The macOS package
retains its default-only launcher; custom roots/adoption use the released script.

## Local evidence

- Normal-flow tests build and unpack an actual `apparatus-core` wheel (resolved
  test version `0.0.1`), assert imports come from that wheel and execute its real
  init, migration, layout, project/Library controls and doctor publication.
  Tool/download collaborators stay in temporary test directories; unexpected
  network installation is denied. No live user toolchain was installed.
- Cases cover fresh/empty roots, ordinary and complete/partial legacy folders,
  explicit refusal/adoption, repeated enrolled repair, custom instructions and
  Skills, task/profile preservation, selected originals, project Git state,
  invalid markers, bound-project rejection and required-step failure.
- Normal execution exposed an inherited `UV_TOOL_DIR` collision with the macOS
  script's readonly internal constant. Before the repair, cleanup failed with
  `readonly variable` before init; setup-specific constant names preserve the
  external uv variables and permit the poisoned-environment regression to pass.
- The initial Git probe can miss a candidate rejected at its path boundary while
  doctor later finds Git on its controlled path. Final acceptance now checks the
  actual report and exit status, including closed available/unavailable pairs,
  missing/duplicate fields and inconsistent results. No dry-run probe was added.
- Existing native dry-run tests retain filesystem/network canaries and hostile
  input witnesses. Explicit adoption adds no dry-run effects or core calls.
- Packaging checks build/expand the no-payload macOS archive and compare exact
  embedded scripts. The existing LF checkout-index proof requires the reviewed
  working scripts to be staged; it was preserved unchanged and passed after
  exact-path staging.

On the PR-46 working tree over plan commit `e4c6be0`, local macOS validation
passed 19 normal-flow cases. The three adoption cases then passed again with
stronger root-Git preservation assertions. Installer dry-run, wrapper and release
coverage passed 32 tests with 8 platform/availability skips. After exact-path
staging, the unchanged
`test_native_wrapper_text_inputs_are_lf_pinned_across_checkouts` passed separately
(1 passed). The IT onepager remains within
its existing 600-word limit. `git diff --check` passed.

## Integrated evidence

The two PR-46 commits were rebased onto reviewed PR-45 `607d559`, including
PR-44 cards. The rebased implementation is `240bfad`; the final integration
adds Windows test-duration reporting and reconciles status and verification
text. Quiet receipt guidance and the closed doctor report fields remain intact.
The combined IT onepager is 584 words, within its existing 600-word limit.

The integrated payload, wheel and source distribution build as version `0.0.1`.
All 25 starter files match source bytes across those three artifacts, including
seven built-in Skill bodies and current learned Skill/card guidance. All 52
Python modules also match source in the wheel and source distribution, including
record schemas and learned Skill/card validation.
Native macOS package build and expansion verify the exact bootstrap/launcher
bytes and absence of a system payload. Build environment: macOS 27.0
(build 26A5425a), Xcode 26.3 (17C519). `pkgutil --check-signature` reports
**no signature** for this local package; no signing or notarization was attempted.

| Local artifact | SHA-256 |
| --- | --- |
| `apparatus-payload-0.0.1.zip` | `24e20f0cd31898e66887f21f95a4964fedd36d6f06a5205df14ce20a00b74851` |
| `apparatus_core-0.0.1-py3-none-any.whl` | `04d6dfa6a26e513e5955c72d1d17465126d6797829f90300cf59fd5ae7f0dca1` |
| `apparatus_core-0.0.1.tar.gz` | `18fd42f494ca25db5475f1ae784c4a422c14115aa94c12cfe3a48195a75915fd` |
| `apparatus-installer-0.0.1.pkg` | `d1060899044b98b6790e5f7d168ea328cd5d1263f1193fd0545023dd4076a8ef` |

On the integrated tree, `uv run pytest` passed **1,247 tests with 38 skips** in
523.38 seconds. This run includes the real-wheel normal flows, native macOS
dry-run and package checks, exact checkout-index LF proof, payload/package
parity and the integrated quiet/card behavior. `git diff --check` also passed.
Only verification prose changed after this full run. Actual Windows/macOS CI
and the compiled Windows wrapper rehearsal remain delivery evidence, not local
claims.

## Required delivery evidence and limits

Run the integrated full pytest suite, payload/package parity and actual Windows
and macOS bootstrap CI. The release workflow also contains compiled Windows
wrapper probes for adoption, duplicate options, spaces and hostile paths. Those
probes require a separate release rehearsal; ordinary PR bootstrap tests do not
execute the compiled wrapper. A manually dispatched release workflow remains a
publication dry-run; signing jobs still follow their explicit gates.

No release was published and no signing gate, certificate or device policy was
changed in this slice. Record actual native build tools, artifact hashes,
unsigned/signed results and any notarization verification before making release
claims. A local rehearsal wheel is not evidence of the package currently served
by PyPI. A successful build or setup is not native AI-app certification, which
remains the separate R12 acceptance effort. Managed recovery does not include
ordinary project files or registered originals, and a restored selection cannot
recreate a missing source.
