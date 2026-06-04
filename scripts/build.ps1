<#
.SYNOPSIS
    Build the Windows Software Updater executables and (optionally) the
    Inno Setup installer.

.DESCRIPTION
    Runs PyInstaller against the two spec files in packaging\, producing
    dist\Updater.exe and "dist\Update Notifier.exe". With -Installer, it then
    invokes the Inno Setup compiler (ISCC.exe) to produce the setup .exe.

.PARAMETER Installer
    Also compile the Inno Setup installer after building the executables.

.PARAMETER Clean
    Remove build\ and dist\ before building.

.EXAMPLE
    .\scripts\build.ps1
    .\scripts\build.ps1 -Installer
    .\scripts\build.ps1 -Clean -Installer
#>
[CmdletBinding()]
param(
    [switch]$Installer,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "==> Project root: $root" -ForegroundColor Cyan

if ($Clean) {
    Write-Host "==> Cleaning build/ and dist/" -ForegroundColor Yellow
    Remove-Item -Recurse -Force "build", "dist" -ErrorAction SilentlyContinue
}

# Ensure build dependencies are present.
Write-Host "==> Installing build dependencies" -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install -e ".[build]"

Write-Host "==> Building Updater.exe" -ForegroundColor Cyan
pyinstaller "packaging\Updater.spec" --noconfirm

Write-Host "==> Building Update Notifier.exe" -ForegroundColor Cyan
pyinstaller "packaging\UpdateNotifier.spec" --noconfirm

Write-Host "==> Executables written to dist\" -ForegroundColor Green
Get-ChildItem "dist\*.exe" | Format-Table Name, Length, LastWriteTime

if ($Installer) {
    $iscc = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 7\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $iscc) {
        throw "ISCC.exe not found. Install Inno Setup 6+ from https://jrsoftware.org/isdl.php"
    }

    Write-Host "==> Compiling installer with $iscc" -ForegroundColor Cyan
    & $iscc "packaging\installer.iss"
    Write-Host "==> Installer written to dist\installer\" -ForegroundColor Green
}

Write-Host "==> Done." -ForegroundColor Green
