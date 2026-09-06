#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter()]
    [string] $Path,

    [Parameter()]
    [switch] $DryRun,

    [Parameter()]
    [switch] $Adopt
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$UvInstallUrl = "https://astral.sh/uv/install.ps1"
$UvInstallRedirectUrl = "https://releases.astral.sh/installers/uv/latest/uv-installer.ps1"
$UvReleaseSource = "https://releases.astral.sh/github/uv/releases/download"
$UvReleaseFallback = "https://github.com/astral-sh/uv/releases/download"
$PythonSource = "https://github.com/astral-sh/python-build-standalone/releases/download"
$PyPiIndex = "https://pypi.org/simple"
$PyPiFiles = "https://files.pythonhosted.org"
$PythonRequest = "3.12"

function Stop-Setup([string] $Message) {
    [Console]::Error.WriteLine("Apparatus setup stopped: $Message")
    [Console]::Error.WriteLine("Re-running is safe. See installer/README.md for help.")
    exit 1
}

if ($env:OS -ne "Windows_NT") {
    Stop-Setup "This script supports Windows only."
}

$UserProfile = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
if ([string]::IsNullOrWhiteSpace($UserProfile) -or -not [IO.Path]::IsPathRooted($UserProfile)) {
    Stop-Setup "The user profile could not be resolved."
}

try {
    $Target = if ([string]::IsNullOrWhiteSpace($Path)) {
        "C:\Projects"
    } elseif ([IO.Path]::IsPathRooted($Path)) {
        [IO.Path]::GetFullPath($Path)
    } else {
        [IO.Path]::GetFullPath((Join-Path (Get-Location).ProviderPath $Path))
    }
    $Target = [IO.Path]::GetFullPath($Target)
    $TargetRoot = [IO.Path]::GetPathRoot($Target)
    while ($Target.Length -gt $TargetRoot.Length -and $Target.EndsWith([string] [IO.Path]::DirectorySeparatorChar)) {
        $Target = $Target.Substring(0, $Target.Length - 1)
    }
} catch {
    Stop-Setup "The workspace location is not valid."
}
$TargetIsUnc = $TargetRoot.StartsWith("\\", [StringComparison]::Ordinal)

function Test-ReparseBoundary([string] $Candidate) {
    $Candidate = [IO.Path]::GetFullPath($Candidate)
    $Root = [IO.Path]::GetPathRoot($Candidate)
    $Current = $Root
    foreach ($Part in $Candidate.Substring($Root.Length).Split([IO.Path]::DirectorySeparatorChar, [StringSplitOptions]::RemoveEmptyEntries)) {
        $Current = Join-Path $Current $Part
        try {
            $Attributes = [IO.File]::GetAttributes($Current)
        } catch [IO.FileNotFoundException] {
            break
        } catch [IO.DirectoryNotFoundException] {
            break
        }
        if ($Attributes -band [IO.FileAttributes]::ReparsePoint) {
            return $false
        }
    }
    return $true
}

$TargetSafe = $true
$TargetReason = "outside redirected sync folders"
try {
    if (-not ($DryRun -and $TargetIsUnc) -and -not (Test-ReparseBoundary $Target)) {
        $TargetSafe = $false
        $TargetReason = "blocked: the location passes through a link or reparse point"
    } elseif ($DryRun -and $TargetIsUnc) {
        $TargetReason = "UNC target preserved lexically; safety inspection deferred"
    }
} catch {
    Stop-Setup "The workspace location could not be inspected safely."
}

$Separators = [char[]] @([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
$Components = $Target.Split($Separators, [StringSplitOptions]::RemoveEmptyEntries)
if ($Components | Where-Object { $_ -cmatch '^(?i:OneDrive)(?:\s*-.*)?$' }) {
    $TargetSafe = $false
    $TargetReason = "blocked: the location is inside OneDrive"
}

function Test-PathWithin([string] $Candidate, [string] $Parent) {
    $FullCandidate = [IO.Path]::GetFullPath($Candidate)
    $FullParent = [IO.Path]::GetFullPath($Parent)
    $CandidateRoot = [IO.Path]::GetPathRoot($FullCandidate)
    $ParentRoot = [IO.Path]::GetPathRoot($FullParent)
    while ($FullCandidate.Length -gt $CandidateRoot.Length -and $FullCandidate.EndsWith('\')) {
        $FullCandidate = $FullCandidate.Substring(0, $FullCandidate.Length - 1)
    }
    while ($FullParent.Length -gt $ParentRoot.Length -and $FullParent.EndsWith('\')) {
        $FullParent = $FullParent.Substring(0, $FullParent.Length - 1)
    }
    if (-not $CandidateRoot.Equals($ParentRoot, [StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }
    if ($FullCandidate.Equals($FullParent, [StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }
    $Boundary = if ($FullParent.EndsWith('\')) { $FullParent } else { $FullParent + '\' }
    return $FullCandidate.StartsWith($Boundary, [StringComparison]::OrdinalIgnoreCase)
}

function Test-RedirectedTarget(
    [string] $Candidate,
    [System.Collections.IDictionary] $Values,
    [string] $Profile
) {
    foreach ($Name in @("Personal", "Desktop")) {
        if (-not $Values.Contains($Name)) { continue }
        $Value = $Values[$Name]
        if ($Value -isnot [string] -or [string]::IsNullOrWhiteSpace($Value)) {
            throw "malformed redirected-folder state"
        }
        $Expanded = [Text.RegularExpressions.Regex]::Replace(
            $Value,
            '%USERPROFILE%',
            [Text.RegularExpressions.MatchEvaluator] { param($Match) $Profile },
            [Text.RegularExpressions.RegexOptions]::IgnoreCase
        )
        if ($Expanded -match '%[^%]+%' -or -not [IO.Path]::IsPathRooted($Expanded)) {
            throw "malformed redirected-folder state"
        }
        if (Test-PathWithin $Candidate $Expanded) { return $true }
    }
    return $false
}

$ShellFolders = "Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
$RegistryKey = $null
try {
    $RegistryKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($ShellFolders, $false)
    if ($null -eq $RegistryKey) {
        $RedirectedNames = @()
    } else {
        $RedirectedNames = @($RegistryKey.GetValueNames())
    }
    $RedirectedValues = @{}
    foreach ($Name in @("Personal", "Desktop")) {
        if ($RedirectedNames -notcontains $Name) { continue }
        $RedirectedValues[$Name] = $RegistryKey.GetValue(
            $Name,
            $null,
            [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames
        )
    }
    if (Test-RedirectedTarget $Target $RedirectedValues $UserProfile) {
        $TargetSafe = $false
        $TargetReason = "blocked: the location is inside redirected Documents or Desktop"
    }
} catch {
    Stop-Setup "Redirected Documents and Desktop state could not be inspected safely."
} finally {
    if ($null -ne $RegistryKey) { $RegistryKey.Dispose() }
}

$UvBin = Join-Path $UserProfile ".local\bin\uv.exe"
$UvPythonDir = Join-Path $UserProfile ".local\share\uv\python"
$UvToolDir = Join-Path $UserProfile ".local\share\uv\tools"
$UvToolBin = Join-Path $UserProfile ".local\bin"
$UvCacheDir = Join-Path $UserProfile ".cache\uv"
$ApparatusBin = Join-Path $UvToolBin "apparatus.exe"

function Find-Uv {
    if ((Test-Path -LiteralPath $UvBin -PathType Leaf) -and -not ((Get-Item -LiteralPath $UvBin -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        return $UvBin
    }
    return $null
}

function Find-Git {
    $Command = Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $Command) { return $null }
    try {
        $Version = & $Command.Source --version 2>&1
        if ($LASTEXITCODE -eq 0 -and [string] $Version -match '^git version \S+') {
            return $Command.Source
        }
    } catch {}
    return $null
}

function Test-ManagedPython {
    if (-not (Test-Path -LiteralPath $UvPythonDir -PathType Container)) { return $false }
    return $null -ne (Get-ChildItem -LiteralPath $UvPythonDir -Directory -Filter "cpython-3.12*" -Force -ErrorAction SilentlyContinue |
        Where-Object { -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) } |
        Select-Object -First 1)
}

function Write-State([string] $Step, [string] $State) {
    Write-Output ("  {0,-18} {1}" -f ($Step + ":"), $State)
}

$UvPath = Find-Uv
$GitPath = Find-Git

if ($DryRun) {
    Write-Output "Apparatus setup dry-run (read-only detection; no install, network, or workspace commands)"
    Write-State "Operating system" "present (Windows)"
    Write-State "Target safety" $(if ($TargetSafe) { "present ($Target; $TargetReason)" } else { "missing ($Target; $TargetReason)" })
    Write-State "uv" $(if ($null -ne $UvPath) { "present" } else { "missing (install planned)" })
    Write-State "Managed Python" $(if (Test-ManagedPython) { "present" } else { "missing (install planned)" })
    Write-State "Git" $(if ($null -ne $GitPath) { "present" } else { "missing (capability unconfirmed; continue planned)" })
    Write-State "Apparatus tool" $(if (Test-Path -LiteralPath $ApparatusBin -PathType Leaf) { "present (upgrade planned)" } else { "missing (install planned)" })
    Write-State "Workspace" $(if (-not $TargetSafe) { "missing (blocked until a safe target is chosen)" } elseif ($TargetIsUnc) { "planned (UNC inspection deferred; core validation and repair)" } else { "planned (core validation and repair; existing nonempty folders require -Adopt)" })
    if ($Adopt) { Write-State "Adoption" "planned (explicitly requested)" }
    Write-State "Doctor" $(if ($TargetSafe) { "planned (report verification follows)" } else { "planned after target repair" })
    Write-State "Network" "planned only for missing/upgrade steps from approved sources"
    return
}

if (-not $TargetSafe) {
    Stop-Setup "$TargetReason. Live workspace state must not sit in a sync engine; use one-way snapshot export for backup."
}

if ((Test-Path -LiteralPath $Target) -and -not (Test-Path -LiteralPath $Target -PathType Container)) {
    Stop-Setup "The workspace location exists and is not a folder."
}

foreach ($UserScopePath in @($UserProfile, $UvBin, $UvPythonDir, $UvToolDir, $UvToolBin, $UvCacheDir)) {
    if (-not (Test-ReparseBoundary $UserScopePath)) {
        Stop-Setup "A user-scope tool location passes through a link or reparse point."
    }
}

# Ignore caller-provided uv, pip, and Python configuration before setting the
# small environment needed by this invocation.
Get-ChildItem Env: | Where-Object { $_.Name -match '^(UV_|PIP_|PYTHON)' } | ForEach-Object {
    Remove-Item ("Env:" + $_.Name) -ErrorAction SilentlyContinue
}
$env:VIRTUAL_ENV = $null
$env:INSTALLER_DOWNLOAD_URL = $null
$env:UV_INSTALL_DIR = Join-Path $UserProfile ".local\bin"
$env:UV_PYTHON_INSTALL_DIR = $UvPythonDir
$env:UV_TOOL_DIR = $UvToolDir
$env:UV_TOOL_BIN_DIR = $UvToolBin
$env:UV_CACHE_DIR = $UvCacheDir
$env:UV_DEFAULT_INDEX = $PyPiIndex
$env:UV_NO_CONFIG = "1"
$env:UV_MANAGED_PYTHON = "1"
$env:UV_PYTHON_INSTALL_MIRROR = $PythonSource
$env:UV_NO_MODIFY_PATH = "1"

if ($null -ne $UvPath) {
    try {
        & $UvPath --version *> $null
        if ($LASTEXITCODE -ne 0) { $UvPath = $null }
    } catch {
        $UvPath = $null
    }
}

if ($null -eq $UvPath) {
    Write-Output "Installing uv in your user profile..."
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $Installer = Invoke-RestMethod -Uri $UvInstallUrl
        Invoke-Expression $Installer
    } catch {
        Stop-Setup "uv could not be installed. A download, execution, or device policy may be blocking it."
    }
    $UvPath = $UvBin
}
if (-not (Test-Path -LiteralPath $UvPath -PathType Leaf)) {
    Stop-Setup "uv is not available after installation."
}

function Invoke-Uv([string[]] $Arguments) {
    & $UvPath @Arguments
    if ($LASTEXITCODE -ne 0) {
        Stop-Setup "A required user-scope tool step failed. A download or device policy may be blocking it."
    }
}

function Test-ManagedPythonReady {
    if (-not (Test-ManagedPython)) { return $false }
    try {
        & $UvPath python find --no-config --managed-python $PythonRequest *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

if (Test-ManagedPythonReady) {
    Write-Output "Managed Python is present."
} else {
    Write-Output "Installing managed Python..."
    Invoke-Uv -Arguments @("python", "install", "--no-config", "--managed-python", "--mirror", $PythonSource, $PythonRequest)
}

if ($null -ne $GitPath) {
    Write-Output "Git is present; snapshots can be checked."
} else {
    Write-Output "Git was not confirmed by the initial probe. Doctor will report actual snapshot capability."
}

if (Test-Path -LiteralPath $ApparatusBin -PathType Leaf) {
    Write-Output "Checking for an Apparatus update..."
    Invoke-Uv -Arguments @("tool", "upgrade", "--no-config", "--default-index", $PyPiIndex, "apparatus-core")
} else {
    Write-Output "Installing Apparatus from PyPI..."
    Invoke-Uv -Arguments @("tool", "install", "--no-config", "--managed-python", "--default-index", $PyPiIndex, "apparatus-core")
}
if (-not (Test-Path -LiteralPath $ApparatusBin -PathType Leaf)) {
    Stop-Setup "The Apparatus command is missing after installation."
}
if (-not (Test-ReparseBoundary $ApparatusBin)) {
    Stop-Setup "The Apparatus command is redirected through a reparse point."
}

$ControlledPath = [Collections.Generic.List[string]]::new()
$ControlledPath.Add($UvToolBin)
if ($null -ne $GitPath) {
    $GitDirectory = [IO.Path]::GetDirectoryName($GitPath)
    if (-not [string]::IsNullOrWhiteSpace($GitDirectory) -and -not $ControlledPath.Contains($GitDirectory)) {
        $ControlledPath.Add($GitDirectory)
    }
}
$SystemDirectory = [Environment]::GetFolderPath([Environment+SpecialFolder]::System)
if ([string]::IsNullOrWhiteSpace($SystemDirectory)) {
    Stop-Setup "The Windows system command location could not be resolved."
}
$ControlledPath.Add($SystemDirectory)
$WindowsDirectory = [IO.Directory]::GetParent($SystemDirectory).FullName
if (-not $ControlledPath.Contains($WindowsDirectory)) { $ControlledPath.Add($WindowsDirectory) }
$env:PATH = $ControlledPath -join ";"

Write-Output "Validating the chosen work area and repairing recognized shipped content..."
$InitOptions = @()
if ($Adopt) { $InitOptions += "--adopt" }
& $ApparatusBin init $Target @InitOptions
if ($LASTEXITCODE -ne 0) {
    [Console]::Error.WriteLine("If core requests adoption and you want to enroll this folder, run the released script:")
    $QuotedTarget = "'" + $Target.Replace("'", "''") + "'"
    [Console]::Error.WriteLine("  .\bootstrap-apparatus.ps1 -Path $QuotedTarget -Adopt")
    Stop-Setup "Core init stopped. Follow its diagnostic; check target permissions if it is not writable. Existing deployment may remain when a later snapshot failed."
}

$Report = Join-Path $Target "System\machine-report.md"
function Test-ReportBoundary {
    if (-not (Test-ReparseBoundary $Report)) { return $false }
    if (Test-Path -LiteralPath $Report) {
        return Test-Path -LiteralPath $Report -PathType Leaf
    }
    return $true
}
if (-not (Test-ReportBoundary)) { Stop-Setup "The workspace report path is redirected or unsafe." }

& $ApparatusBin doctor $Target
$DoctorStatus = $LASTEXITCODE
if (-not (Test-ReportBoundary) -or -not (Test-Path -LiteralPath $Report -PathType Leaf)) {
    Stop-Setup "The workspace report path changed during doctor."
}
$ReportText = Get-Content -LiteralPath $Report -Raw -Encoding UTF8
$ReportLines = @($ReportText -split "`r?`n")
if ($ReportLines.Count -lt 3 -or $ReportLines[0] -cne '---') {
    Stop-Setup "Doctor returned malformed report frontmatter."
}
$ReportEnd = [Array]::IndexOf($ReportLines, '---', 1)
if ($ReportEnd -lt 2) { Stop-Setup "Doctor returned empty or unclosed report frontmatter." }
$ReportFields = $ReportLines[1..($ReportEnd - 1)]
$UvFields = @($ReportFields | Where-Object { $_ -cmatch '^uv:' })
if ($UvFields.Count -ne 1 -or $UvFields[0] -cnotmatch '^uv: "[^"\p{C}]+"$') {
    Stop-Setup "Doctor did not confirm the installed user-scope toolchain."
}
$RiskFields = @($ReportFields | Where-Object { $_ -cmatch '^  at_risk:' })
if ($RiskFields.Count -ne 1 -or $RiskFields[0] -cne '  at_risk: false') {
    Stop-Setup "Doctor reported that the workspace is inside a sync engine."
}
$GitFields = @($ReportFields | Where-Object { $_ -cmatch '^git:' })
$SnapshotFields = @($ReportFields | Where-Object { $_ -cmatch '^snapshots:' })
if ($GitFields.Count -ne 1 -or $SnapshotFields.Count -ne 1) {
    Stop-Setup "Doctor returned missing or duplicate capability fields. Rerun doctor and inspect its report."
}
if ($GitFields[0] -ceq 'git: null' -and $SnapshotFields[0] -ceq 'snapshots: "unavailable"') {
    if ($DoctorStatus -notin @(0, 1)) { Stop-Setup "Doctor could not complete capability detection." }
    Write-Output "Snapshots are unavailable. Make Git available to your AI app, then rerun setup."
} elseif ($GitFields[0] -cmatch '^git: "[^"\p{C}]+"$' -and $SnapshotFields[0] -ceq 'snapshots: "available"') {
    if ($DoctorStatus -ne 0) { Stop-Setup "Doctor found a blocked or incomplete toolchain." }
} else {
    Stop-Setup "Doctor returned inconsistent Git and snapshot capability fields. Rerun doctor and inspect its report."
}

Write-Output "Apparatus is ready at $Target. Open this work area in your AI app and ask for your actual task; Welcome.md explains the available help."
