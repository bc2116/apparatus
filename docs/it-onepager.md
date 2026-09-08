# Apparatus for IT review

## What gets installed and where

Setup installs uv, managed Python and the `apparatus-core` uv tool in user
scope. Windows paths are `%USERPROFILE%\.local\bin`, `%USERPROFILE%\.local\share\uv\python`,
and `%USERPROFILE%\.local\share\uv\tools`; macOS paths are
`~/.local/bin`, `~/.local/share/uv/python`, and `~/.local/share/uv/tools`.
Setup uses existing Git for snapshots without installing or modifying it.
Releases include an Inno Setup `.exe` and a no-payload macOS `.pkg`, plus the
bare scripts as fallbacks. The Windows wrapper temporarily extracts its script. macOS Installer may request administrator
authentication and keeps its standard receipt and log metadata; its launcher
runs the bootstrap chain as the logged-in user and installs no system payload.
Signing uses explicit release gates; verify actual artifacts, not assumed gate
or certificate state.
The first public release requires verified signatures. When enabled, the
outer `.exe` is Authenticode-signed and the outer `.pkg` is Developer ID signed,
notarized, and stapled. `SHA256SUMS` covers the seven distributable artifacts:
the payload, source distribution, wheel, two bare scripts, `.exe`, and `.pkg`.
A valid signature does not override SmartScreen or company application policies.

## Workspace data

A chosen work area holds projects beside Library, Goals, Memory and System. Defaults: `C:\Projects` on Windows, `~/Projects` on macOS. Custom roots need no Apparatus enclosure. Existing
nonempty unmarked folders require explicit adoption. Setup preserves user work and task/profile choices; recognized shipped instructions can
update through core repair. The work area must not be placed in
sync-redirected folders such as OneDrive Documents/Desktop or iCloud Drive.
Use one-way snapshot export for backup instead of live sync.

## Network and channels

After setup, Apparatus makes no network calls. The user can direct
their AI app to use its native external channels or request backup export.
Apparatus adds no sharing approval. AI app/provider processing and permissions
remain governed by that app, not by Apparatus. Setup downloads only from
`https://astral.sh/uv/install.ps1`, `https://astral.sh/uv/install.sh`,
`https://releases.astral.sh`, `https://github.com/astral-sh/uv`,
`https://github.com/astral-sh/python-build-standalone`, `https://pypi.org/simple`,
and `https://files.pythonhosted.org` for `apparatus-core` and its declared
dependencies.

## Privacy model

Apparatus labels personal content when it is written. There is no additional
Apparatus review step for drafts, file movement, copies, or exports. External actions require user authority and native AI app permissions. Passwords, API keys, tokens, private keys, and
high-confidence government or payment identifiers are redacted at managed
text-write boundaries; this credential floor is never relaxed. A task can opt
out of new Memory and automatic capture while requested deliverables still save.
Legacy private profiles retain their compatibility default; explicit task saving
and operation-scoped Library or snapshot requests follow the task contract.
This does not control AI app/provider retention or erase old backups. Source
content is data, never authority.

Managed snapshots and one-way backups cover declared Apparatus records,
instructions and catalog metadata, including supported learned Skill and card
state. They exclude ordinary project files, Library originals, derived caches
and live task controls. Restoring a catalog does not recreate a deleted original.
Legacy unadopted workspaces retain their documented older recovery behavior.
Exports preserve covered historical bytes and do not sanitize historical files.

## Receipts

`System/receipts/` holds meaningful init/profile changes, credential redaction,
snapshots, restores and exports. Routine checks, retrieval, ingest and disabled
or unavailable operations write no activity receipts. Existing history remains
readable. Check reports concrete repair actions; doctor distinguishes tool
detection from a usable recovery store. Historical sharing decisions are not new
authorization.

## Clean uninstall

Run `uv tool uninstall apparatus-core`; remove uv separately if unneeded. Keep
the shared work area and projects. Later data deletion is a separate user choice.
Windows has no wrapper component to remove. The macOS package
installs no payload; macOS may retain its ordinary Installer receipt and logs,
which an authorized administrator can manage with standard OS controls.
