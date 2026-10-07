# PR-66 — Preserve partial module installation on failure

## Outcome

Harden the create-only Mailbox Survey installer before adding update or removal.
A POSIX identity check followed by pathname deletion has a substitution window:
the occupant can change between the final check and unlink. Do not use that
sequence to compensate a failed module installation. Keep this fix local to the
module and compatible with published Apparatus Core 0.0.2.

## Contract

Preserve the existing all-destination preflight, retained root/enrollment/parent
checks, exact-byte ownership and bounded nonblocking readers. A successful
install or repair still creates only the two fixed missing packaged assets.
No overwrite, removal, new ownership record or provider access is introduced.

After a publication failure, close retained resources and leave partial assets
and directories in place. Report a bounded, content-free error explaining that
installation may be partial: inspect with `status`; use `repair` only when the
remaining assets match the package; review and preserve conflicting edits.
Do not claim rollback, atomic pair publication, cleanup, or a complete install.
An incomplete Skill could remain discoverable, so explicitly tell the user not
to use it until status reports current.

Audit the entire creation call chain, including child handoff, low-level partial
writes and detached-parent failures. Module POSIX adapters must never perform
check-then-pathname deletion while compensating these paths. Use exclusive,
descriptor-relative creation and exact retained identities; preserve partial
bytes on a short write or verification failure. Do not weaken filesystem
boundaries or globally patch core methods. Windows may retain the core's exact
handle protections for failed low-level writes; module-level compensation is
preservation-first on both platforms. Leave unrelated files and directories.

## Deliverables and acceptance

- Update module deployment implementation, focused regressions, package README
  and current module specification. Bump only the module to 0.1.2 and update its
  lock entry. Keep deployed resources unchanged.
- Cover failure after the first publication, low-level partial write, failed
  child handoff, detached parent and concurrent replacement at the former final
  deletion boundary. Preserve both foreign and unchanged partial files; verify
  exact partial installs can be repaired and partial corrupt files remain
  conflicts. Exercise errors through the public command without private data.
- Preserve existing successful install/status/repair, unsafe endpoint, bounded
  read and enrollment tests. Do not loosen conformance fixtures.
- Run focused tests, full `uv run pytest`, installed-wheel tests against released
  core 0.0.2 and current-head cross-platform CI before merge.
- Record concise synthetic evidence and update the module sequence and plan row
  in the same PR. Earlier certification remains historical evidence; this PR
  supersedes its failed-publication cleanup claim.

Update/removal remain separate subsequent work. Safe withdrawal, old-content
recognition and process-interruption recovery need explicit contracts before
implementation. Module assets remain outside core managed recovery.
