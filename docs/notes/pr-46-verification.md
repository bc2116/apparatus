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

Required final integration includes PR-45 and its PR-44 dependency; do not treat
this earlier-base evidence as final integration coverage. Final commit, full
suite and actual native CI results belong in the final PR review.

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
