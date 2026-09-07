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
5. validate, create or repair the chosen work area through core init; and
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
the script's `-DryRun`; `/WORKSPACEPATH=` maps to `-Path`; `/ADOPT` maps to `-Adopt`:

```powershell
.\apparatus-installer.exe /DRYRUN
.\apparatus-installer.exe /WORKSPACEPATH="D:\Work"
.\apparatus-installer.exe /DRYRUN /WORKSPACEPATH="D:\Work" /ADOPT
```

Duplicate or unknown options are rejected, and the wrapper returns the setup
script's nonzero status if setup stops.

### PowerShell script fallback

Each release also includes `bootstrap-apparatus.ps1` as a flat fallback file.
Open PowerShell in the folder containing it, then run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap-apparatus.ps1
```

The default workspace location is `C:\Projects`. Use a different
location with `-Path`; `/ADOPT` maps to `-Adopt`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap-apparatus.ps1 -Path "D:\Work"
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
shell-script fallback when you need `--dry-run`, `--path`, or explicit
`--adopt`. The package cannot forward these options. If its default already contains work, core requests
explicit adoption; use the released script instead of assuming consent.

### Shell script fallback

Each release also includes `bootstrap-apparatus.sh` as a flat fallback file.
Open Terminal in the folder containing it, then run:

```bash
/usr/bin/env -u BASH_ENV -u ENV /bin/bash bootstrap-apparatus.sh
```

The default workspace location is `~/Projects`. Use a different
location with `--path`:

```bash
/usr/bin/env -u BASH_ENV -u ENV /bin/bash bootstrap-apparatus.sh --path "$HOME/Work"
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

Choose the actual work area, containing your projects beside one Library; setup
never adds a required Apparatus enclosure. The default is a convenience only.
A fresh path or empty folder needs no adoption flag. For any existing nonempty
unmarked folder, including a legacy workspace, explicitly request enrollment:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap-apparatus.ps1 -Path "D:\Work" -Adopt
.\apparatus-installer.exe /WORKSPACEPATH="D:\Work" /ADOPT
```

```bash
/usr/bin/env -u BASH_ENV -u ENV /bin/bash bootstrap-apparatus.sh --path "$HOME/Work" --adopt
```

No installer infers adoption from existing files or retries with consent added.
Every normal run calls core init, including complete older workspaces. Core
updates recognized shipped instructions, preserves custom files and ordinary
projects, and reports conflicts. It preserves the work-area ID and task/profile
choices on repair. A bound project is not a setup target; use its chosen work
area. Permissions or missing-drive failures require choosing a writable target,
not elevation or automatic relocation.

A failed later snapshot or doctor step does not erase successful enrollment.
Follow the reported action and rerun; setup reports ready only after its required
steps finish. Open the work area in your AI app and ask for your actual task.
Welcome.md is reference material, not a questionnaire prerequisite.

Git detection describes capability, not a proven recovery store. If Git is
absent, setup continues with snapshots unavailable. Make Git available in the
AI app's command environment, then rerun setup. Managed snapshots and one-way
backups cover declared Apparatus records, instructions and catalog metadata;
they exclude ordinary projects, Library originals, derived caches and live task
controls. Restoring a catalog cannot recreate a deleted original. Follow the
[current recovery specification](../docs/spec/managed-recovery.md) for exact
coverage, including learned Skills and any supported Library cards.

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

Wrapper signing is implemented behind explicit release gates. A first public
release requires verified signed artifacts. With a gate unset, rehearsals can
still build and checksum both
unsigned wrappers and both fallback scripts. When enabled, Authenticode signs
the outer Windows `.exe`; Developer ID signs the outer macOS `.pkg`, which is
then notarized and stapled. Do not infer current gate or certificate availability from this documentation.
No release should be described as signed unless its gate ran successfully and
its signature was verified. Packaging checks do not certify a native AI app. The PowerShell fallback
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

## Remove the tool without removing your projects

Uninstall `apparatus-core` with `uv tool uninstall apparatus-core`; remove uv
separately only if you no longer need it. Keep the chosen work area and sibling
projects. Tool removal does not require deleting data. Any later archival or
deletion is a separate user choice; setup provides no automatic cleanup.
