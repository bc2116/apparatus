# Profile overlays

`profiles.yaml` is the declarative selection map used when a starter payload
becomes a workspace. It has three closed sections:

- `privacy_modes` maps each privacy-mode name to its policy file. All named
  policy files deploy; `System/profile.yaml` selects the active one.
  This is legacy compatibility: current task Memory decisions take precedence,
  and fresh setup does not ask the user to select a global privacy mode.
- `work_types` maps each work-type name to its managed procedure files.
- `default` names the privacy mode and work types used for a new workspace.

For compatibility with a hand-copied or previously unconfigured payload, an
existing `work_types: []` means no procedure filtering: init retains all
manifest-managed starter procedures while preserving the empty selection in
the profile.

Every path is relative to the payload and must name a file in that payload.
The overlay engine validates the whole manifest before changing a workspace.
It copies selected managed procedures, removes deselected managed procedures,
and leaves every path not named in this manifest alone.

Overlays are data, never code: adding a mode or work type is a manifest and
payload-file change, not a new program branch. For a custom `--payload` path,
`apparatus init` first uses a sibling `profiles/profiles.yaml`; if it is absent,
it uses the checkout's shipped manifest. The generic overlay engine can resolve
synthetic modes in tests; the v0 workspace profile schema remains limited to
the shipped `standard` and `private` modes.
