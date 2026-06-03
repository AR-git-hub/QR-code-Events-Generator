$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (!(Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Virtual environment was not found. Run START_DEMO_WINDOWS.bat or START_PRODUCTION_WINDOWS.bat first."
    exit 1
}

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

Write-Host "Compiling Python modules..."
& $Python -m compileall bot

Write-Host "Running smoke test..."
& $Python scripts\smoke_test.py

Write-Host "Project check passed."
