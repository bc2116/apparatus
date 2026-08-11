# Apparatus setup scripts

These scripts create or repair an Apparatus workspace without administrator
access on a typical machine. They work in this order:

1. install uv in the current user's profile when it is missing;
2. install a uv-managed Python when it is missing;
3. detect git without installing or changing it;
4. install or update `apparatus-core` from PyPI;
5. create or non-destructively repair the workspace; and
6. run `apparatus doctor` and verify the machine report.

The installed `apparatus-core` package contains the universal workspace payload.
The scripts do not download a separate payload.

## Windows

Open PowerShell in the folder containing the script, then run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\bootstrap-apparatus.ps1
```

The default workspace location is `C:\Projects\Apparatus`. Use a different
location with `-Path`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\bootstrap-apparatus.ps1 -Path "D:\Work\Apparatus"
```

See the complete detected plan without downloading or changing anything:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\bootstrap-apparatus.ps1 -DryRun
```

The script refuses OneDrive path components, redirected Documents or Desktop
locations, and reparse-point boundaries. Live workspace state must not sit in a
sync engine. Use one-way snapshot export for backup.

## macOS

Open Terminal in the folder containing the script, then run:

```bash
/usr/bin/env -u BASH_ENV -u ENV /bin/bash macos/bootstrap-apparatus.sh
```

The default workspace location is `~/Projects/Apparatus`. Use a different
location with `--path`:

```bash
/usr/bin/env -u BASH_ENV -u ENV /bin/bash macos/bootstrap-apparatus.sh --path "$HOME/Work/Apparatus"
```

See the complete detected plan without downloading or changing anything:

```bash
/usr/bin/env -u BASH_ENV -u ENV /bin/bash macos/bootstrap-apparatus.sh --dry-run
```

Dry-run begins at script interpreter entry. It performs read-only detection and
prints to standard output or standard error, but runs no installer, makes no
network request, runs no workspace command, and leaves no persistent file.

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

These scripts are unsigned. The Windows command above uses a process-only
execution-policy bypass; it does not change the machine policy. Signed wrappers
land in PR-26.

Some managed devices block downloads, script execution, or user-scope tool
installation. The script stops instead of requesting elevation and always says
that re-running is safe. On such a device, the universal payload can still be
used as a degraded files-only workspace. Doctor reports the unavailable
toolchain honestly; this fallback is not the normal setup path.

The scripts support Windows and macOS only. They do not bundle git, select an
AI app, install optional packs, or change device policy.
