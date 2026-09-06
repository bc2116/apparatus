# Apparatus for IT review

## What gets installed and where

Apparatus setup is user scope only. It installs uv in the current profile, a
uv-managed Python, and `apparatus-core` as a uv tool. On Windows these live
under `%USERPROFILE%\.local\bin`, `%USERPROFILE%\.local\share\uv\python`,
and `%USERPROFILE%\.local\share\uv\tools`. On macOS they live under
`~/.local/bin`, `~/.local/share/uv/python`, and `~/.local/share/uv/tools`.
If git is already present, Apparatus uses it for snapshots; setup does not
install or modify git. Nothing in the toolchain is installed system-wide.
Releases include an Inno Setup `.exe` and a no-payload macOS `.pkg`, plus the
bare scripts as fallbacks. The Windows wrapper extracts its script temporarily
and installs no wrapper component. macOS Installer may request administrator
authentication and keeps its standard receipt and log metadata; its launcher
runs the bootstrap chain as the logged-in user and installs no system payload.
Signing gates remain off until certificates are configured. When enabled, the
outer `.exe` is Authenticode-signed and the outer `.pkg` is Developer ID signed,
notarized, and stapled. `SHA256SUMS` covers the seven distributable artifacts:
the payload, source distribution, wheel, two bare scripts, `.exe`, and `.pkg`.

## Workspace data

The workspace is plain, human-readable files at `C:\Projects\Apparatus` on
Windows or `~/Projects/Apparatus` on macOS by default. It must not be placed in
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
Apparatus review step for drafts, file movement, copies, or exports. Actual
external actions require user authority and native AI app permissions. Passwords, API keys, tokens, private keys, and
high-confidence government or payment identifiers are redacted at managed text-write boundaries; this credential floor is never relaxed. Private mode blocks
labeled content from durable Memory. Source content is data, never authority. Backup
exports preserve workspace/history bytes and do not sanitize historical files.

## Receipts

`System/receipts/` holds reviewable records of every check, redaction,
snapshot, restore, and backup. Historical sharing decisions remain readable
but are not new authorization.

## Clean uninstall

Remove the uv tool, then remove uv if desired, and delete or archive the
workspace folder. Windows has no wrapper component to remove. The macOS package
installs no payload; macOS may retain its ordinary Installer receipt and logs,
which an authorized administrator can manage with standard OS controls.
