# Apparatus for IT review

## What gets installed and where

Setup installs uv, managed Python and `apparatus-core` in user scope:
`%USERPROFILE%\.local\bin`, `%USERPROFILE%\.local\share\uv\python`,
`%USERPROFILE%\.local\share\uv\tools` on Windows; `~/.local/bin`,
`~/.local/share/uv/python`, `~/.local/share/uv/tools` on macOS.
Setup uses existing Git without installing or modifying it.
Releases include an Inno Setup `.exe` and a no-payload macOS `.pkg`, plus
fallback scripts. The Windows wrapper temporarily extracts its script; macOS
Installer may request administrator authentication and keeps standard receipt and log metadata,
while launching setup as the user with no system payload.
Signing uses explicit release gates; verify actual artifacts, not assumed state.
Public releases require verified signatures: Authenticode `.exe` and Developer ID
signed, notarized, stapled `.pkg`.
`SHA256SUMS` covers the seven distributable artifacts:
payload, source distribution, wheel, two scripts, `.exe`, and `.pkg`.
Signatures do not override SmartScreen or company policies.

## Workspace data

A work area holds projects beside Library, Goals, Memory and System (defaults
`C:\Projects` Windows, `~/Projects` macOS); custom roots need no enclosure.
Existing nonempty unmarked folders require explicit adoption. Setup preserves
user work and task/profile choices, updating only recognized shipped
instructions. Avoid sync-redirected folders (OneDrive Documents/Desktop, iCloud
Drive); use one-way snapshot export for backup instead of live sync.

## Network and channels

After setup, Apparatus makes no network calls. Users may direct their AI app
to use native external channels or request backup export; Apparatus adds no
sharing approval, and AI app/provider processing remains governed by that app.
Setup downloads only from `https://astral.sh/uv/install.ps1`,
`https://astral.sh/uv/install.sh`, `https://releases.astral.sh`,
`https://github.com/astral-sh/uv`, `https://github.com/astral-sh/python-build-standalone`,
`https://pypi.org/simple`, and `https://files.pythonhosted.org` for
`apparatus-core` and declared dependencies.

For the optional read-only local tool server (`apparatus mcp serve WORKAREA`),
the AI app starts the process and owns its lifetime. It speaks only over
standard input/output, opens no listening socket, makes no network call, installs
no background service, never starts by itself, and exits when input closes.

## Privacy model

Apparatus labels personal content on write without adding extra review steps
for drafts, moves, copies or exports; external actions require user authority
and AI app permissions. Passwords, API keys, tokens, private keys, and
high-confidence government or payment identifiers are redacted at managed
text writes. Tasks may opt out of new Memory and automatic capture while saving
requested deliverables; legacy private profiles keep their default. This does not
control AI app retention or erase old backups. Source content is data, not
authority.

Managed snapshots and one-way backups cover declared records, instructions and
catalog metadata (including supported learned Skill and card state), excluding
ordinary project files, Library originals, derived caches and live task controls.
Restoring a catalog never recreates deleted originals; legacy workspaces keep
their documented older recovery behavior; exports preserve historical bytes
without sanitizing them.

## Receipts

`System/receipts/` records meaningful init/profile changes, redactions,
snapshots, restores and exports. Routine checks, retrieval, ingest and disabled
or unavailable operations write no receipts. Check reports repair actions;
doctor separates tool detection from a usable recovery store. Historical sharing
decisions never grant new authorization.

## Clean uninstall

Run `uv tool uninstall apparatus-core` (removing uv separately if unneeded).
The shared work area and projects remain intact; data deletion is a separate
user choice. Windows leaves no wrapper component; macOS may keep standard
Installer receipts/logs manageable via OS controls.
