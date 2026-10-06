# First optional module sequence

The first consumer is Mailbox Survey, governed by
[ADR-0007](../adr/ADR-0007-optional-mailbox-module.md). Keep core releases
independently shippable. Each implementation owns its tests, review and exact
delivery evidence; synthetic success is not live mailbox qualification.

| Slice | Outcome | Readiness |
|---|---|---|
| [PR-63](PR-63-mailbox-module-prototype.md) | Separate portable Skill, supplied-sample exercise, strict read-only report validator and module boundary. | Executable prompt; status is in the plan index. |
| Lifecycle | Inventory and safe install/repair/update/removal for the first Skill-only module. Preserve edited and foreign files; distinguish package presence from work-area activation. | Outline; cut a prompt from the proven prototype. |
| Installed integration | Prove package resources, core upgrade/repair preservation, user flow and one actually tested input path. | Outline; depends on lifecycle. |
| Optional assessment engine | Qualified, versioned judgment behind the same evidence/report boundary. | Later; no provider or action integration in the first prototype. |

Start the lifecycle with the smallest supported inventory and exact asset
ownership. A narrow module-specific installer is an option if it can provide
honest discovery, user-edit and recovery behavior; do not create general control
records incidentally. Skill-only modules must not disappear from inventory for
lacking a command entry point. A module with commands needs an explicit
workspace/task dispatch contract rather than assuming core verb behavior.

Before claiming removal, account for edited Skill files that a native AI app
could still discover. Preserve user edits, report unresolved active files and
offer concrete reconciliation instead of claiming they have been disabled.
Workspace restore does not automatically restore installed Python packages;
version mismatches need explicit behavior and coverage limits.

Split installation/repair and update/removal into separate focused PRs if their
transaction and preservation work cannot remain reviewable together. Complete
both before claiming a supported lifecycle. Defer catalog UI, marketplace,
arbitrary remote plugin loading, billing tiers, scheduling and model routing.

No additional historical mailbox access is implied by development. Use
synthetic fixtures until a specific source and scope are authorized. A later
connector pilot must name its actual app, connector, dates, scope, evidence,
resource limits and remaining coverage gaps.
