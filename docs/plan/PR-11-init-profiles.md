# PR-11: init and profile overlay engine

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` — especially §5 (workspace, default
  locations), §6.1 (interview → profile), §7 (private mode is an overlay)
- `docs/adr/ADR-0001-vocabulary.md`
- `docs/adr/ADR-0002-protocol-and-state.md` — files first; profile is YAML
- `docs/adr/ADR-0004-privacy-model.md` — private mode is a profile overlay,
  not a fork
- `docs/plan/README.md`
- `docs/plan/PR-05-starter-procedures.md` and
  `docs/plan/PR-06-policy-overlays-egress-spec.md` — the files overlays select
- `docs/plan/PR-08-cli-skeleton-doctor.md` — registry, exit codes, redirection
  detection
- `docs/spec/workspace.md` — two artifacts one shape; deploy strips `.gitkeep`

## Objective

`apparatus init <path>` turns the universal starter payload into a deployed
workspace: it copies the payload, strips `.gitkeep` placeholders, applies the
profile overlay (with `System/profile.yaml` driving which procedures, policy,
and templates are active), warns when the target sits inside a sync-redirected
folder, takes the initial snapshot, and writes a receipt. The overlay engine is
the mechanism the welcome interview (PR-17) and "re-run my setup interview"
build on, so its contract — deterministic file operations driven by one
declarative manifest, never code branches per profile — is the real product of
this PR. Re-running `init` on an existing workspace is the repair tool and must
never overwrite user content.

## Deliverables

- `packages/apparatus-core/src/apparatus_core/payload.py` — locates the
  payload source (see Open decisions) and copies it.
- `packages/apparatus-core/src/apparatus_core/overlays.py` — loads
  `starter/profiles/profiles.yaml`, resolves a profile to a concrete file
  set, applies it as deterministic copy/remove operations.
- `packages/apparatus-core/src/apparatus_core/commands/init.py` — argparse
  wiring per the PR-08 registry contract.
- `packages/apparatus-core/pyproject.toml` — modified: register the `init`
  verb in the `apparatus.commands` entry-point group.
- No record-schema changes: the init receipt uses the `init` event value
  already pinned in the PR-04 receipt `event` enum; `docs/spec/records.md`,
  `packages/apparatus-core/src/apparatus_core/records.py`, and the golden
  example records are untouched.
- `starter/profiles/profiles.yaml` — the v1 overlay manifest: each
  `privacy_mode` (standard, private) names the policy file it activates —
  both policy files always deploy under `System/policy/` and
  `System/profile.yaml` selects the active one (PR-06 ships both in the
  payload), so the mode entry is a validated pointer, never a
  deploy-or-remove instruction; each `work_type` maps to a set of procedure
  files; a `default` block names the fallback mode and work types. All
  paths are payload-relative and must reference the actual filenames PR-05
  and PR-06 shipped. In v1 every work type maps to all five starter
  procedures — they are the brief's day-1
  capabilities (§6) and ship for everyone; do not invent work-type-specific
  procedure subsets. The engine's ability to vary sets is proven by the
  synthetic-manifest test (criterion 4), not by v1 content.
- `starter/profiles/README.md` — what overlays are, the manifest format, and
  the rule that overlays are data, never code.
- `packages/apparatus-core/tests/test_overlays.py`
- `packages/apparatus-core/tests/test_init.py`
- `docs/plan/README.md` — modified: PR-11 status row only.

## Acceptance criteria

1. `apparatus init <path>` on a fresh directory (created if absent) deploys
   the full payload tree, strips every `.gitkeep`, applies the default
   profile, records the applied selections (privacy mode, work types) in
   `System/profile.yaml` — `status` stays `unconfigured` until the welcome
   interview (PR-17) records real answers — takes an initial snapshot
   labeled "Workspace created", writes an init receipt (`event: init`) under
   `System/receipts/`, and exits 0.
2. Optional flags `--privacy-mode {standard,private}` and
   `--work-types LIST` seed `System/profile.yaml`; omitted flags fall back to
   the manifest's `default` block on fresh init and to the existing
   `profile.yaml` values on re-run.
3. Overlay semantics: both policy overlay files (`standard.md` and
   `private.md`) are always deployed under `System/policy/`, and
   `System/profile.yaml`'s `privacy_mode` selects the active one (PR-06) —
   a hand-copied payload and an init-deployed workspace therefore have the
   identical file set. The selected procedure subset is deployed under
   `System/procedures/`; non-selected overlay-managed procedure files are
   not deployed, and on re-run after a profile change, previously deployed
   overlay-managed files that are no longer selected are removed.
   Overlay-managed paths are exactly those the manifest names — the engine
   touches nothing else.
4. The engine is generic: no `if privacy_mode == ...` branches anywhere.
   Adding a work type or mode is a manifest edit plus payload files. A test
   proves it by applying a synthetic manifest with an invented mode.
5. Repair semantics on an existing workspace: missing required folders and
   missing payload files are restored; any existing file outside
   overlay-managed paths is never overwritten or deleted, byte-identical or
   not. The receipt lists what was repaired. Exit 0.
6. Manifest validation: every path in `profiles.yaml` must exist in the
   payload; a dangling path is exit 2 with the offending entry named. A
   pytest test enforces the same invariant against the shipped manifest.
7. Sync-redirection: the target path is evaluated with PR-08's `detect.py`
   logic; a redirected location produces a prominent plain-language warning
   on stdout and a note in the receipt, but init proceeds (the installer's
   steer-away behavior is PR-22's).
8. Snapshot step reuses PR-10's `snapshots.py`; when git is unavailable the
   documented degraded path applies (message, receipt, no crash) and init
   still exits 0 — a missing snapshot capability must not block workspace
   creation.
9. Target path exists but is a file, or payload source cannot be found: exit
   2 with actionable messages.
10. All stdout text uses ADR-0001 vocabulary — "workspace", "procedure",
    "snapshot"; never "repo", "template instantiation", or app brand names.
11. Stdlib plus the YAML dependency already present from PR-04; nothing new.
12. `uv run pytest` is green.

## Conformance and tests

- `starter/profiles/` is outside `starter/payload/`, so the golden payload
  manifest is untouched; conformance must stay green unmodified.
- `tests/test_init.py` uses temp dirs for all three required cases:
  - fresh: full tree present, no `.gitkeep` anywhere, default profile
    recorded, receipt exists, snapshot exists when git is available;
  - repeat: a user-created file in `Projects/` and an edited `Welcome.md`
    survive byte-identical; a deleted `Goals/` folder is restored; changing
    `--privacy-mode` updates the `privacy_mode` selector in
    `System/profile.yaml` while both policy files remain deployed under
    `System/policy/`;
  - redirected path: synthetic OneDrive-style path triggers the warning and
    the receipt note.
- `tests/test_overlays.py` covers manifest loading, dangling-path rejection,
  the synthetic-manifest genericity test, and add/remove on profile change.
- A test asserts `apparatus check` (PR-09) passes on a freshly initialized
  workspace — init's output must be check-clean by construction.

## Out of scope

- The welcome interview itself and any conversational flow (PR-17) — init is
  the deterministic bottom half only.
- Packaging the payload into the wheel or any distribution artifact (PR-20).
- Steering users to a different disk location or refusing redirected paths
  (PR-22 bootstrapper behavior).
- Rendering shims or regenerating `Welcome.md` content (PR-13 / PR-17).
- Migrating workspaces between payload versions.

## Dependencies

- PR-09 and PR-10 (per `docs/plan/README.md`): `check` must pass on init's
  output, and the initial-snapshot step reuses PR-10's `snapshots.py` —
  never reimplement git logic here. If PR-10 has not landed yet, land it
  first.

## Open decisions

- Payload source resolution for installed (non-checkout) runs is genuinely
  unresolved until PR-20. Smallest reversible default, used here: an
  explicit `--payload PATH` flag, defaulting to the `starter/payload/`
  directory resolved relative to this repository when running from the
  checkout; exit 2 with a clear message when neither is available.
