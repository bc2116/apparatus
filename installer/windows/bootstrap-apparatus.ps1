#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter()]
    [string] $Path,

    [Parameter()]
    [switch] $DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$UvInstallUrl = "https://astral.sh/uv/install.ps1"
$PythonSource = "https://github.com/astral-sh/python-build-standalone/releases/download"
$PyPiIndex = "https://pypi.org/simple"
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
        "C:\Projects\Apparatus"
    } elseif ([IO.Path]::IsPathRooted($Path)) {
        [IO.Path]::GetFullPath($Path)
    } else {
        [IO.Path]::GetFullPath((Join-Path (Get-Location).ProviderPath $Path))
    }
    $Target = [IO.Path]::GetFullPath($Target).TrimEnd([IO.Path]::DirectorySeparatorChar)
} catch {
    Stop-Setup "The workspace location is not valid."
}

function Test-ReparseBoundary([string] $Candidate) {
    $Root = [IO.Path]::GetPathRoot($Candidate)
    $Current = $Root
    foreach ($Part in $Candidate.Substring($Root.Length).Split([IO.Path]::DirectorySeparatorChar, [StringSplitOptions]::RemoveEmptyEntries)) {
        $Current = Join-Path $Current $Part
        $Item = Get-Item -LiteralPath $Current -Force -ErrorAction SilentlyContinue
        if ($null -ne $Item -and ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            return $false
        }
    }
    return $true
}

$TargetSafe = $true
$TargetReason = "outside redirected sync folders"
if (-not (Test-ReparseBoundary $Target)) {
    $TargetSafe = $false
    $TargetReason = "blocked: the location passes through a link or reparse point"
}

$Components = $Target.Split([IO.Path]::DirectorySeparatorChar, [StringSplitOptions]::RemoveEmptyEntries)
if ($Components | Where-Object { $_ -match '^(?i:OneDrive)(?:\s*-.*)?$' }) {
    $TargetSafe = $false
    $TargetReason = "blocked: the location is inside OneDrive"
}

function Test-PathWithin([string] $Candidate, [string] $Parent) {
    try {
        $FullCandidate = [IO.Path]::GetFullPath($Candidate).TrimEnd('\') + '\'
        $FullParent = [IO.Path]::GetFullPath($Parent).TrimEnd('\') + '\'
        return $FullCandidate.StartsWith($FullParent, [StringComparison]::OrdinalIgnoreCase)
    } catch {
        return $false
    }
}

$ShellFolders = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
try {
    $Redirected = Get-ItemProperty -LiteralPath $ShellFolders -ErrorAction Stop
    foreach ($Name in @("Personal", "Desktop")) {
        $Property = $Redirected.PSObject.Properties[$Name]
        if ($null -ne $Property) {
            $Value = $Property.Value
            $Expanded = [Environment]::ExpandEnvironmentVariables([string] $Value)
            if (Test-PathWithin $Target $Expanded) {
                $TargetSafe = $false
                $TargetReason = "blocked: the location is inside redirected Documents or Desktop"
            }
        }
    }
} catch {
    if ($_.Exception.Message -like "Apparatus setup stopped:*") { throw }
    # Missing policy state is normal on an unmanaged profile. A present but
    # unreadable key is handled by doctor after the target itself is checked.
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

function Test-ManagedPython {
    if (-not (Test-Path -LiteralPath $UvPythonDir -PathType Container)) { return $false }
    return $null -ne (Get-ChildItem -LiteralPath $UvPythonDir -Directory -Filter "cpython-3.12*" -Force -ErrorAction SilentlyContinue |
        Where-Object { -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) } |
        Select-Object -First 1)
}

function Test-WorkspacePresent {
    if (-not (Test-Path -LiteralPath $Target -PathType Container)) { return $false }
    $RequiredFiles = @(
        "AGENTS.md", "CLAUDE.md", "Welcome.md",
        ".cursor\rules\apparatus.mdc", ".github\copilot-instructions.md",
        "System\README.md", "System\profile.yaml", "System\ignore",
        "System\guidance\model-guidance.md",
        "System\policy\private.md", "System\policy\standard.md",
        "System\procedures\welcome.md",
        "System\procedures\produce-deliverable.md",
        "System\procedures\research-and-summarize.md",
        "System\procedures\review-against-checklist.md",
        "System\procedures\weekly-review.md"
    )
    $RequiredDirectories = @(
        "Goals", "Decisions", "Projects", "Library", "Deliverables",
        "Memory\People", "Memory\Facts", "System\receipts"
    )
    foreach ($Relative in $RequiredFiles) {
        $Candidate = Join-Path $Target $Relative
        if (-not (Test-Path -LiteralPath $Candidate -PathType Leaf) -or -not (Test-ReparseBoundary $Candidate)) {
            return $false
        }
    }
    foreach ($Relative in $RequiredDirectories) {
        $Candidate = Join-Path $Target $Relative
        if (-not (Test-Path -LiteralPath $Candidate -PathType Container) -or -not (Test-ReparseBoundary $Candidate)) {
            return $false
        }
    }
    return $true
}

function Write-State([string] $Step, [string] $State) {
    Write-Output ("  {0,-18} {1}" -f ($Step + ":"), $State)
}

$UvPath = Find-Uv
$GitCommand = Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1

if ($DryRun) {
    Write-Output "Apparatus setup dry-run (detection only; no commands will run)"
    Write-State "Operating system" "present (Windows)"
    Write-State "Target safety" $(if ($TargetSafe) { "present ($Target; $TargetReason)" } else { "missing ($Target; $TargetReason)" })
    Write-State "uv" $(if ($null -ne $UvPath) { "present" } else { "missing (install planned)" })
    Write-State "Managed Python" $(if (Test-ManagedPython) { "present" } else { "missing (install planned)" })
    Write-State "Git" $(if ($null -ne $GitCommand) { "present" } else { "missing (snapshots unavailable; continue planned)" })
    Write-State "Apparatus tool" $(if (Test-Path -LiteralPath $ApparatusBin -PathType Leaf) { "present (upgrade planned)" } else { "missing (install planned)" })
    Write-State "Workspace" $(if (-not $TargetSafe) { "missing (blocked until a safe target is chosen)" } elseif (Test-WorkspacePresent) { "present (init skip planned)" } else { "missing (non-destructive init planned)" })
    Write-State "Doctor" $(if ($TargetSafe) { "planned (report verification follows)" } else { "planned after target repair" })
    Write-State "Network" "planned only for missing/upgrade steps from approved sources"
    exit 0
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

if ($null -ne $GitCommand) {
    Write-Output "Git is present; snapshots can be checked."
} else {
    Write-Output "Git was not found. Setup will continue and doctor will record snapshots as unavailable."
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

if (Test-WorkspacePresent) {
    Write-Output "The existing workspace is intact; init is not needed."
} else {
    Write-Output "Creating or repairing the workspace without replacing existing files..."
    & $ApparatusBin init $Target
    if ($LASTEXITCODE -ne 0) { Stop-Setup "The workspace could not be created or repaired." }
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
if ($ReportText -notmatch '(?m)^uv: ".+"\r?$') {
    Stop-Setup "Doctor did not confirm the installed user-scope toolchain."
}
if ($ReportText -notmatch '(?m)^  at_risk: false\r?$') {
    Stop-Setup "Doctor reported that the workspace is inside a sync engine."
}
if ($null -eq $GitCommand) {
    if ($DoctorStatus -notin @(0, 1)) { Stop-Setup "Doctor could not complete the workspace check." }
    if ($ReportText -notmatch '(?m)^git: null\r?$' -or $ReportText -notmatch '(?m)^snapshots: "unavailable"\r?$') {
        Stop-Setup "Doctor did not record the expected git-absent snapshot state."
    }
} else {
    if ($DoctorStatus -ne 0) { Stop-Setup "Doctor found a blocked or incomplete toolchain." }
    if ($ReportText -notmatch '(?m)^git: ".+"\r?$' -or $ReportText -notmatch '(?m)^snapshots: "available"\r?$') {
        Stop-Setup "Doctor did not confirm the expected snapshot state."
    }
}

Write-Output "Apparatus is ready at $Target. Open Welcome.md with your AI app to begin."
