$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Get-HostPython {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) { return @("py", "-3") }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return @("python") }

    throw "Python 3 is not installed. Install it from https://www.python.org/downloads/ and enable 'Add python.exe to PATH'."
}

function Invoke-HostPython {
    param([string[]]$Arguments)
    $cmd = Get-HostPython
    $baseArgs = @()
    if ($cmd.Length -gt 1) {
        $baseArgs = $cmd[1..($cmd.Length - 1)]
    }
    & $cmd[0] @baseArgs @Arguments
}

Write-Host ""
Write-Host "QR Ticket Bot - production start"
Write-Host ""

if (!(Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    Invoke-HostPython @("-m", "venv", ".venv")
}

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

Write-Host "Installing dependencies..."
& $Python -m pip install -r requirements.txt

if (!(Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ".env was created from .env.example."
    Write-Host "Fill BOT_TOKEN, YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, PUBLIC_BASE_URL, RETURN_URL and WEBHOOK_SECRET."
    Start-Process notepad.exe ".env"
    throw "Configure .env, then run START_PRODUCTION_WINDOWS.bat again."
}

if (!(Test-Path "data")) {
    New-Item -ItemType Directory -Path "data" | Out-Null
}

if (!(Test-Path "data\qr_pool.json") -and (Test-Path "data\qr_pool.example.json")) {
    Copy-Item "data\qr_pool.example.json" "data\qr_pool.json"
}

Write-Host "Checking project..."
& $Python -m compileall bot

Write-Host ""
Write-Host "Bot is starting in production mode. Close this window to stop the bot."
Write-Host ""

& $Python -m bot
