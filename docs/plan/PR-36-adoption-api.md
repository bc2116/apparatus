# PR-36 shared interface

All paths below are relative to the repository. Product paths are relative to an
explicit work area or project. The lead owns project binding and CLI routing;
authors coordinate before altering these interfaces.

## Project binding (lead)

`project_binding.py` exports `BindingError(ValueError)`,
`read_project_binding(project) -> ProjectBinding | None`,
`resolve_project_context(project) -> ResolvedContext`,
`bind_project(project, workspace, *, replace=False) -> BindingResult`, and
`check_project_pointer(project) -> None` (raises BindingError on a conflict).
Pointer validation and `bind_project` also accept an optional retained `context`
for command handlers. They validate that selected context through their work;
it does not authorize retargeting or provide a global active-workspace setting.
`BindingResult` exposes `project: Path`, `workspace: Path`, `changed: bool`.
`ResolvedContext` is a context manager exposing `project: Path`, `workspace: Path`,
`workspace_id: str`, and `validate()`. It retains the explicit project and work-area
roots plus exact binding/marker proof until closed. Context selection is frozen:
validate before dispatch; later binding edits never redirect an operation.
`ProjectBinding` exposes `project`, `workspace_id`, `relative_workspace`, and captured
metadata/proof for the resolver. No caller guesses an ancestor if it is absent.

The only project control is `.apparatus/workspace.yaml` (schema, workspace,
workspace_id). The pointer block in `AGENTS.md` is identical across projects and
references this relative control path, not an absolute or duplicated canon. Ownership
means exact recognized block bytes (LF or CRLF), never delimiters alone. Missing
binding with a residual `.apparatus` directory or recognized pointer is a repair
error rather than a legacy fallback. Invalid/foreign controls remain conflicts.

`bind_project` plans and validates both files before mutation. It creates a missing
pointer, appends the recognized block to valid custom UTF-8 instructions while
preserving their original bytes, or accepts the exact current block. It never edits
custom block contents. Existing equal binding plus equal block is a no-op; `replace`
allows explicit retarget of a valid old binding after a move. Existing unknown files
in `.apparatus` are collisions. Use retained-root exact create/replace compensation
for both artifacts and directory creation; keep concurrent changes intact.

`commands/init.py` must reject an explicitly bound project as an enrollment target
using `read_project_binding` / `resolve_project_context`. It does not change the
resolved work area's files merely because the requested destination was a project.
`commands/render.py` may detect a binding and repair only its project pointer with
`bind_project(project, resolved.workspace)`; otherwise keep work-area scope.
`check PROJECT` checks exact binding/pointer before checking the resolved area.
The lead performs command routing before global task enforcement as specified in
the main prompt, preserving the original destination for these special commands.
The CLI passes its selection to special handlers separately from that destination.
They reuse the selected context, including an explicit absence, rather than
resolve the project again. Check and render engines accept a selected work area;
only their command handlers follow project bindings. Bound-project init is
rejected even if the link disappears after initial selection.

## Enrollment (enrollment author)

Reuse the existing closed marker schema. A creation helper may return canonical
UUID marker bytes for a fresh area. Enrollment must be in the same retained
`deploy_init_plan` transaction as managed deployment, not a follow-up free write.
Use a narrow expected-preimage / validation hook if necessary; avoid another
transaction framework. Current profiles remain byte-exact when selectors are omitted.
No `.git` inspection/initialization is allowed for fresh/adopted/enrolled work areas.
Ordinary existing unmarked folders need `--adopt`, including legacy Apparatus roots;
read/other recovery commands keep their legacy behavior until explicit enrollment.

`workspace_layout.new_layout_bytes() -> bytes` generates canonical closed marker
bytes with a new UUID. `deploy_init_plan` accepts optional
`enrollment_content: bytes | None` and
`validate_enrollment: Callable[[WorkspaceAnchor, bool], None] | None`. The callback
receives false before deployment writes and true at each final acceptance check.
The marker is created by the existing owned-file transaction, with expected
absence, and compensated alongside all other deployment changes. Existing marker
bytes/identity and UUID are validated rather than rewritten. Fresh or empty
existing folders can enroll directly; nonempty unmarked folders require `--adopt`.
During deployment, `project_binding.require_unbound_root(anchor)` rechecks only
the retained root's immediate control and canon endpoints. It raises BindingError
for an occupant of `.apparatus` or a project-link marker without reopening the root
while invocation-created directory handles are retained. The new enrollment
marker's exact bytes and identity are verified by deployment's owned-file proofs.

## Instructions and validation (instruction author)

Work-area instruction planning chooses the final actual canon before rendering
missing pointers. Preserve custom canon; migrate only exact recognized shipped
bytes. Existing custom/foreign pointers are collisions before deployment. Use the
same rule in enrolled work-area render, with retained preimage checking rather
than blanket writes. Never infer ownership from a comment header or hash field alone.
The current command `render PROJECT` performs only the project-pointer operation
above; no new native adapter paths are invented in this PR.

`check.py` reads both `Memory/Decisions` and legacy `Decisions` when present. The
new layout no longer requires `Projects`, root `Deliverables`, or root `Decisions`.
The lifecycle/schema lead adds decision current/outdated/forgotten support, so the
instruction author can use existing record validation without a second validator.
Current root canon and profile overlays stay synchronized with the embedded payload.
