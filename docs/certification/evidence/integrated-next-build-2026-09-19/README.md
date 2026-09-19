# Integrated next-build evidence

This capsule records an unreleased source build, not a replacement for dated
published-installer evidence. `run.json` lists artifact hashes; `build-identity.json`
identifies 77 source inputs, the installed wheel, payload identity and archive,
and the exact native app/model configuration.

- `native-discovery/` preserves four independent fresh-chat cases, exact prompts
  with portable runtime placeholders, input bodies, persisted outputs, tree
  hashes and scoped observations. No wording retries were used.
- `continuation/` preserves a separate saving/fresh pair. The fresh chat invoked
  `resume PROJECT` through an explicit binding, then used the saved Decision
  without a reminder. Its no-save delta adds only the requested worksheet.
- `installed-core/` records independent product-command backup and init/repair
  checks of the same wheel. These commands did not execute a model.

Runtime, work-area and task placeholders in prompts were replaced with the
case's isolated paths and existing opaque task ID. They are configuration,
not extra task hints. Each discovery prompt retained its original PR-59 wording
apart from the declared executable added before this follow-up. The native
runtime was replaced with the frozen PR-61 wheel before any baseline or prompt.
Git was absent only from the continuation's product-process PATH. A synthetic
retired source was registered and moved outside the work area before either
continuation chat; it was never relinked or used as current evidence.

Root Skill use passed. Bound selection and collision precedence remain partial;
no adapter is inferred from a missing marker alone. The non-relevant assistant
initially guessed two executable paths before using the supplied one. The
native resume UI preview truncated later lines; the assistant reported the
missing source and unavailable history, and a separately archived read-only
invocation reproduced the full output without changing any native-after file.

No raw conversation export, credential, live user source, cache content, Git
object content or machine-specific path is included. Hash-only tree inventories
include isolated caches and synthetic Git metadata. Markdown worksheet page
sections were verified; physical print pagination was not.

The captured worksheet retains its original Markdown hard-break spaces and
space-only lines so its bytes still match the native after-hash. The ordinary
`git diff --check` reports those 15 lines; the scoped check excluding only this
raw output passes. No whitespace policy or assertion was weakened.

`source-checkout/resume-output.txt` is a separate deterministic smoke check of
the documented `uv sync --all-packages` / `uv run apparatus resume PROJECT`
path. Unlike the native negative fixture's launcher, this source command has
Git available and reports the real latest snapshot and its explicit coverage.
It still returns a partial brief for the missing original. The complete native
after-tree remained byte-identical after this read-only check.

The archive's `.gitattributes` rule disables text conversion for this exact
capsule. A real checkout-index probe with `core.autocrlf=true` first reproduced
changed JSON bytes under the default checkout policy. The scoped raw-byte rule
keeps every captured file and recorded digest intact, without imposing a new
line ending on the original evidence.
