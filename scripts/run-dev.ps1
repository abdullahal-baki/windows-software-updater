<#
.SYNOPSIS
    Run the updater GUI from source for development.

.DESCRIPTION
    Creates a virtual environment on first run, installs the package in
    editable mode with dev extras, then launches the updater.

.PARAMETER Notifier
    Run the background notifier instead of the GUI.
#>
[CmdletBinding()]
param(
    [switch]$Notifier
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".venv")) {
    Write-Host "==> Creating virtual environment (.venv)" -ForegroundColor Cyan
    python -m venv .venv
}

$python = Join-Path $root ".venv\Scripts\python.exe"

Write-Host "==> Installing package (editable) with dev extras" -ForegroundColor Cyan
& $python -m pip install --upgrade pip
& $python -m pip install -e ".[dev]"

if ($Notifier) {
    Write-Host "==> Launching Update Notifier" -ForegroundColor Green
    & $python -m wsu.app.notifier
}
else {
    Write-Host "==> Launching Updater GUI" -ForegroundColor Green
    & $python -m wsu
}
