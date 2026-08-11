# Apparatus installers and setup scripts

The primary setup path is the released installer for your operating system:

- `apparatus-installer.exe` on Windows;
- `apparatus-installer.pkg` on macOS.

Double-click the installer and follow the operating-system prompts. Each
installer carries the corresponding setup script unchanged, runs it, and then
removes its temporary copy. The scripts create or repair an Apparatus workspace
in this order:

1. install uv in the current user's profile when it is missing;
2. install a uv-managed Python when it is missing;
3. detect git without installing or changing it;
4. install or update `apparatus-core` from PyPI;
5. create or non-destructively repair the workspace; and
6. run `apparatus doctor` and verify the machine report.

The installed `apparatus-core` package contains the universal workspace payload.
The scripts do not download a separate payload.

## Windows installer

Double-click `apparatus-installer.exe` for the default setup. The wrapper uses
Inno Setup's minimal native progress interface, runs without elevation, installs
no wrapper payload or uninstaller, and leaves all setup decisions to the
embedded PowerShell script.

For a wrapper dry-run or a different workspace location, pass the wrapper's
strictly checked options from PowerShell or Command Prompt. `/DRYRUN` maps to
the script's `-DryRun`; `/WORKSPACEPATH=` maps to `-Path`:

```powershell
.\apparatus-installer.exe /DRYRUN
.\apparatus-installer.exe /WORKSPACEPATH="D:\Work\Apparatus"
.\apparatus-installer.exe /DRYRUN /WORKSPACEPATH="D:\Work\Apparatus"
```

Duplicate or unknown options are rejected, and the wrapper returns the setup
script's nonzero status if setup stops.

### PowerShell script fallback

Each release also includes `bootstrap-apparatus.ps1` as a flat fallback file.
Open PowerShell in the folder containing it, then run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap-apparatus.ps1
```

The default workspace location is `C:\Projects\Apparatus`. Use a different
location with `-Path`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap-apparatus.ps1 -Path "D:\Work\Apparatus"
```

See the complete detected plan without downloading or changing anything:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap-apparatus.ps1 -DryRun
```

The script refuses OneDrive path components, redirected Documents or Desktop
locations, and reparse-point boundaries. Live workspace state must not sit in a
sync engine. Use one-way snapshot export for backup.

## macOS installer

Double-click `apparatus-installer.pkg` for the default setup. macOS Installer
may require an administrator authentication prompt even though the package has
no payload. Its launcher identifies the logged-in user and runs the complete
bootstrap chain in that user's session and with that user's identity; the chain
never runs as root. All chain writes remain in the user profile or the workspace
target. macOS retains its standard package receipt and may retain Installer log
metadata, but the wrapper installs no application, service, daemon, or other
system payload.

The native package interface has no safe custom-option channel. Use the flat
shell-script fallback when you need `--dry-run` or `--path`.

### Shell script fallback

Each release also includes `bootstrap-apparatus.sh` as a flat fallback file.
Open Terminal in the folder containing it, then run:

```bash
/usr/bin/env -u BASH_ENV -u ENV /bin/bash bootstrap-apparatus.sh
```

The default workspace location is `~/Projects/Apparatus`. Use a different
location with `--path`:

```bash
/usr/bin/env -u BASH_ENV -u ENV /bin/bash bootstrap-apparatus.sh --path "$HOME/Work/Apparatus"
```

See the complete detected plan without downloading or changing anything:

```bash
/usr/bin/env -u BASH_ENV -u ENV /bin/bash bootstrap-apparatus.sh --dry-run
```

Dry-run begins at script interpreter entry. It performs read-only detection and
prints to standard output or standard error, but runs no installer, makes no
network request, runs no workspace command, and makes no persistent filesystem
change.

The script refuses symbolic-link boundaries and locations inside iCloud Drive.
Live workspace state must not sit in a sync engine. Use one-way snapshot export
for backup.

## Re-running and repair

Re-running either script is safe. Satisfied steps are skipped, a missing
managed Python or tool is repaired, existing workspace files are never
overwritten by setup, and a fresh doctor check always finishes the run. A
complete existing workspace skips `init`; a partial workspace is passed to
the existing non-destructive repair behavior.

If git is present on `PATH`, doctor checks snapshot availability. If git is
absent, setup continues and records snapshots as unavailable. Ask your IT team
for a user-scope git installation, then re-run the script to repair snapshot
availability.

## Network sources and privacy

Setup permits only these sources:

- the official uv installers at `https://astral.sh/uv/install.ps1` and
  `https://astral.sh/uv/install.sh`;
- the installers' current official redirects at
  `https://releases.astral.sh/installers/uv/latest/uv-installer.ps1` and
  `https://releases.astral.sh/installers/uv/latest/uv-installer.sh`;
- uv release files at
  `https://releases.astral.sh/github/uv/releases/download`, with the official
  `https://github.com/astral-sh/uv/releases/download` fallback;
- uv's documented managed-Python distributions at
  `https://github.com/astral-sh/python-build-standalone/releases/download`;
- the PyPI index at `https://pypi.org/simple` and its package-file host at
  `https://files.pythonhosted.org` for `apparatus-core` and its declared
  package dependencies.

There is no telemetry. Setup sends no workspace content, machine report,
credentials, or personal data to those sources.

## Current limitations

Wrapper signing is implemented but gated off while Apparatus acquires
certificates. With a gate unset, releases still build and checksum both
unsigned wrappers and both fallback scripts. When enabled, Authenticode signs
the outer Windows `.exe`; Developer ID signs the outer macOS `.pkg`, which is
then notarized and stapled. No release should be described as signed unless its
gate ran successfully and its signature was verified. The PowerShell fallback
command above uses a process-only execution-policy bypass; it does not change
machine policy. See the [IT reviewer one-pager](../docs/it-onepager.md) and
[signing runbook](../docs/signing-runbook.md).

Some managed devices block downloads, script execution, or user-scope tool
installation. The script stops instead of requesting elevation and always says
that re-running is safe. On such a device, the universal payload can still be
used as a degraded files-only workspace. Doctor reports the unavailable
toolchain honestly; this fallback is not the normal setup path.

The scripts support Windows and macOS only. They do not bundle git, select an
AI app, install optional packs, or change device policy.
