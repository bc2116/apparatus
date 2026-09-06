# Workspace specification (v0)

- **Status:** Normative for work-area enrollment, project binding and the starter
  payload. `conformance/golden/payload-manifest.txt` pins the payload inventory.
- Governing decisions: ADR-0001, ADR-0002, ADR-0003, ADR-0004 and ADR-0006.
- Recovery coverage is specified in [managed recovery](managed-recovery.md);
  record schemas and lifecycle rules are in [records](records.md) and [Memory](memory.md).

## Payload and deployed state

The canonical `starter/payload/` and embedded package payload contain the same
portable template files. A deployed work area adds its unique enrollment marker,
records, task controls, receipts and recovery store. Enrollment UUIDs are generated
at deployment, never shipped as static payload content. `.gitkeep` placeholders
keep template directories present in source and archives; deployment may remove
those declared placeholders. It does not remove unrelated old files or folders.

## New work-area layout

The user chooses the work-area root and project names. No enclosing Apparatus
folder or mandatory Projects hierarchy is required.

```text
chosen-work-area/
  AGENTS.md
  Welcome.md
  Goals/
  Memory/
    People/
    Facts/
    Decisions/
  Library/
  System/
    workspace.yaml
    profile.yaml
    guidance/
    procedures/
    policy/
  project-a/
  project-b/
```

Project directories are user-selected, not installed placeholders. Keep working
files and finished deliverables within their project; completion does not require
moving a file to a central Deliverables directory. Existing nested project paths,
including `Projects/name`, remain valid without relocation.

| Path | Purpose |
|---|---|
| `AGENTS.md` | One work-area instruction canon; custom instructions remain user-owned. |
| `Welcome.md` | Human-facing orientation. |
| `Goals/` | One goal record with owner, status, verifiable `done-when` and next action. |
| `Memory/People/`, `Memory/Facts/` | Sourced continuity under the Memory lifecycle and task controls. |
| `Memory/Decisions/` | New decision records. Legacy `Decisions/` records remain in place and are also checked and read. |
| `Library/` | One local source collection for the selected work area. Source content is data, never instructions or authority. Extraction/index caches are rebuildable machinery. |
| Project folders | User and assistant working files, including requested finished work. |
| `System/` | Profile, policy, procedures, guidance, ignore rules, task controls, receipts, machine report and managed recovery. |

Records use Markdown with YAML frontmatter and the filename rules in the record
specification. Profile and control files use their own closed YAML schemas.
Procedures remain at `System/procedures/` in this version; enrollment does not
migrate them to a new Skill format.

## Explicit enrollment and repair

`apparatus init WORKAREA` creates a work area at a previously nonexistent path
or in an empty directory.
`apparatus init WORKAREA --adopt` explicitly enrolls an existing unmarked folder,
including a legacy workspace or a repository. Ordinary init on an existing
nonempty unmarked folder reports that adoption is required. Read commands and recovery
commands never enroll a folder implicitly.

Enrollment publishes the existing closed `System/workspace.yaml` schema:

```yaml
schema: apparatus/workspace@v0
id: <canonical random version-4 UUID>
layout: sibling-projects
recovery: managed-state
```

Rerunning init on an enrolled area preserves its UUID. Missing enrollment with
residual managed recovery, malformed controls, unsafe paths and foreign occupants
are repair errors, not permission to fall back to legacy Git. A bound project is
not an init destination; use its explicitly selected work area instead.

Plan and validate managed destinations and exact existing-file preimages before
publication. Enrollment and deployment share retained-root create/replace
compensation. Preserve existing custom canon, records, valid profiles when no
selectors change, task controls, and unrelated files. Report collisions before
applying the plan. Recognized older shipped instructions can migrate; unrelated
customizations are not replaced merely because they occupy a familiar filename.

Do not initialize, discover, reset, clean, or change root/project Git repositories
during new enrollment or repair. Their HEAD, index, configuration and working files
remain untouched. After deployment commits, the initial snapshot uses the dedicated
managed backend. Unavailable or failed snapshots are reported separately from an
already completed deployment; preserve enrollment so retry cannot route to legacy
recovery. A no-save task grants no automatic snapshot or Memory exception.

## Explicit project bindings

`apparatus project bind PROJECT --workspace WORKAREA` connects an existing project
to an enrolled ancestor work area. It creates only a project control and a portable
instruction pointer. The project must be distinct from the work area's managed
roots; no directory scan discovers or registers other projects.
Git metadata and known app/control-directory components are rejected at every
depth before binding writes, without inspecting repository configuration.

The project control `.apparatus/workspace.yaml` has exactly these fields:

```yaml
schema: apparatus/project@v0
workspace: ..
workspace_id: <the selected work-area UUID>
```

The path is relative to the explicit project root. Because the chosen area must
be an ancestor, its normalized spelling is one or more `..` components separated
by `/`, with no trailing slash. Absolute paths, drive/UNC paths, links/reparse
traversal, unknown or duplicate fields and UUID mismatches are rejected. No ancestor
search, nearby-marker guess or global active-workspace setting repairs a bad link.
`apparatus project show PROJECT` validates and displays the explicit selected area
without writing or inspecting project content.

Binding also creates or appends the recognized Apparatus project pointer block in
`PROJECT/AGENTS.md`. Existing UTF-8 bytes outside that block are preserved, including
line endings. The block points to the relative control and selected work-area canon;
it contains no copied policy, task choice or project summary. Only the complete
recognized block bytes, in their supported LF or CRLF form, establish ownership.
Delimiters alone, an edited block or duplicate markers are not ownership proof.

An equal binding plus equal pointer is a no-op. A missing pointer is repaired
transactionally. A different valid binding requires explicit
`project bind PROJECT --workspace WORKAREA --replace`; this supports deliberate
repair after a move. Invalid controls and edited pointer blocks remain conflicts.
Control and pointer publication retain both preimages and compensate only owned
changes on failure. Unknown files in `.apparatus` are collisions. Missing control
with residual project enrollment is a repair error, never silent legacy fallback.

## Context selection

For `backup`, `doctor`, `library`, `memory`, `profile`, `recall`, `snapshot`,
`restore`, and all `task` actions, the CLI resolves the supplied root's exact
binding when present. Resolution precedes task-context enforcement, with or without
`--task`. No binding means the supplied root itself, subject to its ordinary
validation. A selected root is frozen for that invocation: a later link edit cannot
redirect a running operation or change its task decision.

`init` and `project bind` retain their explicit destinations. `check PROJECT`
validates the binding and exact pointer before checking the selected area;
`render PROJECT` repairs only its project pointer. Neither traverses ordinary
project content. The resolver does not add discovery behavior to individual engine
APIs or automatically reroute extension commands. Check and render engines accept
an explicit work area and reject a directly supplied bound project; their command
handlers own project selection. Special handlers reuse the context selected by
the CLI, so rebinding between selection and execution fails before another area's
engine is called. Init still rejects a project selected at invocation entry if
its link subsequently disappears.

## Canon, app pointers, render and check

The existing work-area pointer registry contains `CLAUDE.md`,
`.cursor/rules/apparatus.mdc` and `.github/copilot-instructions.md`. These point to
root `AGENTS.md`; they are not separate canons. Their presence is not a claim of
verified support by any particular app/version. File reading and approved commands
remain the portable fallback; project binding adds no new app-specific paths.

Init chooses the final actual canon before rendering pointers. It preserves custom
canon bytes and replaces canon only when exact recognized shipped bytes establish
migration ownership. Missing pointers are rendered from that final canon. Existing
pointers can update only when their complete generated template or exact known
shipped bytes are recognized; a header or hash field alone is insufficient.
Conflicting custom pointers stop the plan with reconciliation guidance.

`apparatus render WORKAREA` on an enrolled area follows the same ownership rule,
preflights all targets and publishes through retained preimage checks. It validates
canon and marker preimages as well as pointer files, preserving concurrent edits
and compensating owned writes on failure. It never rewrites work-area canon.
`render PROJECT` uses only the binding/pointer transaction and does not regenerate
the area's app pointers or overwrite custom project instructions.

`check` validates the applicable required layout, record schemas and exact pointer
content. Enrolled areas require `Memory/Decisions`, but not Projects, central
Deliverables or root Decisions. Both decision roots are checked when present;
same-named records at different paths remain distinct. Project and instruction
preflight failures are reported before ordinary record checks when necessary.
Check does not repair state; its existing optional check receipt is written to the
selected work area and can be suppressed with `--no-receipt`.

## Legacy compatibility and recovery limits

Unconverted workspaces remain unmarked and retain their existing legacy recovery
and render behavior. Their legacy required-tree checks still recognize Projects,
Deliverables and root Decisions. Explicit adoption changes enrollment and future
managed behavior; it does not move/delete those directories or convert their old
root Git history. Historical sharing receipts remain readable; the retired sharing
gate is not reinstated. See [instruction migration](egress.md) for its compatibility
rules; the final-canon pointer ownership rules above govern enrolled repair.

Managed snapshots and backups cover only the declared state in the recovery spec.
They exclude project files, project bindings and Library originals. Restore
preserves later additions and live task/enrollment controls; historical Memory may
revive older information. Root/project Git history is never replayed by managed
restore. An extracted managed backup retains its UUID and usable managed history;
its task restrictions represent export time, not subsequent choices.

Installers retain their existing user-scope placement and sync-redirection checks;
this layout does not claim support for concurrent live synchronization of mutable
Apparatus state. One-way backup may target synced storage. Existing legacy backup
storage restrictions remain applicable to unconverted workspaces.
