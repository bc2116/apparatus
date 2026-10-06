# First optional module sequence

The first consumer is Mailbox Survey, governed by
[ADR-0007](../adr/ADR-0007-optional-mailbox-module.md). Keep core releases
independently shippable. Each implementation owns its tests, review and exact
delivery evidence; synthetic success is not live mailbox qualification.

| Slice | Outcome | Readiness |
|---|---|---|
| [PR-63](PR-63-mailbox-module-prototype.md) | Separate portable Skill, supplied-sample exercise, strict read-only report validator and module boundary. | Executable prompt; status is in the plan index. |
| [PR-64](PR-64-mailbox-module-install.md) | Optional lifecycle dependency and explicit status/install/repair commands. Create only missing exact packaged Skill assets in an enrolled work area; preserve conflicts and unrelated files. | Executable prompt; create-only deployment, not a full lifecycle. |
| Update and removal | Define old-version ownership, safe update/removal, and behavior for retained user edits. | Next focused slice; PR-64 has no overwrite or removal path. |
| Installed integration | Prove package resources, core upgrade/repair preservation, user flow and one actually tested input path. | Separate slice after lifecycle behavior is defined. Automatic app discovery remains unqualified. |
| Optional assessment engine | Qualified, versioned judgment behind the same evidence/report boundary. | Later; no provider or action integration in the first prototype. |

The PR-64 installer owns only the fixed Skill body and report-format reference
when their bytes match the package assets. Package presence and deployed
Skill state are separate; package version is not a persistent deployed-version
record. Module assets are outside core managed recovery. Installing generic
shipped guidance creates no task-derived data and is permitted under no-save.

Before claiming removal, account for edited Skill files that a native AI app
could still discover. Preserve user edits, report unresolved active files and
offer concrete reconciliation instead of claiming they have been disabled.
Workspace restore does not automatically restore installed Python packages;
version mismatches need explicit behavior and coverage limits.

Defer catalog UI, marketplace, arbitrary remote plugin loading, billing tiers,
scheduling and model routing. Automatic discovery remains unverified; the
assistant can read the deployed canonical Skill explicitly.

No additional historical mailbox access is implied by development. Use
synthetic fixtures until a specific source and scope are authorized. A later
connector pilot must name its actual app, connector, dates, scope, evidence,
resource limits and remaining coverage gaps.
