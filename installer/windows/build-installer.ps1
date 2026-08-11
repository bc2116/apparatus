#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $Compiler,

    [Parameter(Mandatory = $true)]
    [string] $OutputDirectory,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9]+\.[0-9]+\.[0-9]+(?:[.-][A-Za-z0-9.]+)?$')]
    [string] $Version
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$Definition = Join-Path $ScriptDirectory "apparatus-installer.iss"
$Bootstrap = Join-Path $ScriptDirectory "bootstrap-apparatus.ps1"

if (-not (Test-Path -LiteralPath $Compiler -PathType Leaf)) {
    throw "The pinned Inno Setup compiler was not found."
}
if (-not (Test-Path -LiteralPath $Definition -PathType Leaf)) {
    throw "The Windows wrapper definition was not found."
}
if (-not (Test-Path -LiteralPath $Bootstrap -PathType Leaf)) {
    throw "The canonical Windows bootstrap script was not found."
}

$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
[IO.Directory]::CreateDirectory($OutputDirectory) | Out-Null

& $Compiler "/DSourceRoot=$ScriptDirectory" "/DOutputDir=$OutputDirectory" "/DVersion=$Version" $Definition
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE."
}

$Artifact = Join-Path $OutputDirectory "apparatus-installer.exe"
if (-not (Test-Path -LiteralPath $Artifact -PathType Leaf)) {
    throw "The Windows wrapper build did not produce apparatus-installer.exe."
}

Write-Output $Artifact
