$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$escapedRoot = [WildcardPattern]::Escape($RepoRoot)

$processes = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match "python" -and
    $_.CommandLine -like "*-m bot*" -and
    $_.CommandLine -like "*$escapedRoot*"
}

if (!$processes) {
    Write-Host "No running bot process found for this project."
    exit 0
}

foreach ($process in $processes) {
    Write-Host "Stopping process $($process.ProcessId)..."
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
}

Write-Host "Stopped."
