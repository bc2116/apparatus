# Installed-core acceptance runner and captured results

This runner was prepared before execution and completed one successful C/PR-71
run on the recorded source candidate. Use Python 3.10+ and `uv` on PATH to
repeat it. Package resolution needs network access once; only the
core wheel and its dependencies enter the isolated venv. Alias fixtures need
permission to create directory symlinks (the complete intended run is POSIX).

Run only after the final retained product source is reviewed and its full SHA
is known. Use new external directories; existing directories are rejected so
failed evidence cannot be overwritten. C documentation changes may coexist,
but tracked build inputs must match clean HEAD.

```sh
python3 docs/certification/evidence/core-readiness-2026-10-12/run.py \
  --source-root SOURCE_CHECKOUT \
  --source-sha FULL_40_CHARACTER_SOURCE_SHA \
  --run-dir NEW_EXTERNAL_RUN_DIRECTORY \
  --evidence-dir NEW_EXTERNAL_EVIDENCE_DIRECTORY
```

The script copies tracked core/starter/build inputs into the external run
directory. It builds the core wheel twice, compares exact bytes, checks the
PDF dependency floor, matches all wheel package files to source, and matches
packaged payload/profiles to canonical starter bytes. It downloads and hashes
core dependencies, installs offline, records installed distribution file
hashes, and proves the imported core is inside the isolated venv. It builds
the deterministic payload twice using that installed core and compares every
archive resource to canonical source.

CLI cases run from an external cwd: fresh/repeat/repair init through both
aliases; linked-project task/Memory/resume; synthetic Markdown/PDF extraction
and search; content-free malformed-PDF failure; check; no-save refusal of a
managed Memory write plus a requested project note; backup canonical and
ancestor-alias positives, final-link and inside-work-area-alias negatives.
The backup fixture label `system-alias` means a synthetic external ancestor
symlink matching the PR-61 test contract, not general OS/filesystem acceptance.
Backups preserve an independent project Git tree and protected originals.

The no-save baseline begins **after task start** and includes every file and
directory in `runtime/`: byte hashes, size, mode and mtime. No controls,
receipts, cache or recovery exemptions apply. A requested note may change its
parent directory's size/mtime. This direct CLI/fixture check does not establish
native assistant behavior or provider retention. Bytecode writes are disabled
for product commands; venv/build/tool caches remain outside the product runtime
inventory and are not covered by the no-save claim.

`commands.json` preserves sanitized commands, output and return codes;
`results.json` preserves the probe completion record. Its provisional manifest
wording describes the capture stage; the separately finalized manifest governs
the archived capsule. Assertion failures preserve existing logs and
inventories for assessment; do not rewrite failure evidence. Exact source,
wheel, payload, downloaded dependency and installed-file hashes are retained.
External paths use `$SOURCE`, `$RUN`, `$EVIDENCE`, `$HOME`, `$UV` and
`$BOOTSTRAP_PYTHON` aliases. Archive bytes stay in the run directory because
product backup receipts can contain local destination paths; evidence retains
their hashes, entry inventories and canonical-destination assertion results.

The root agent owns copying/reconciling evidence and finalizing the archive
manifest after review. This script never writes that final manifest. It does
not run the repository test suite, native assistant chats, module installation,
mailbox tests, OS installers, signing, publication or release actions.
