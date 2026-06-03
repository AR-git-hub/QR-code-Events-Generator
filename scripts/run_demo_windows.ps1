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
Write-Host "QR Ticket Bot - demo start"
Write-Host "This mode does not charge real money."
Write-Host ""

if (!(Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    Invoke-HostPython @("-m", "venv", ".venv")
}

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

Write-Host "Installing dependencies..."
& $Python -m pip install -r requirements.txt

if (!(Test-Path ".env")) {
    $token = Read-Host "Paste Telegram bot token from BotFather"
    if ([string]::IsNullOrWhiteSpace($token)) {
        throw "BOT_TOKEN is required."
    }
    $adminIds = Read-Host "Paste admin Telegram user ID or leave empty. You can get it later with /id"

    $envText = @"
BOT_TOKEN=$token

PAYMENT_PROVIDER=fake

PUBLIC_BASE_URL=http://localhost:8080
RETURN_URL=http://localhost:8080/return
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8080
WEBHOOK_SECRET=dev-secret

YOOKASSA_SHOP_ID=
YOOKASSA_SECRET_KEY=

DATABASE_PATH=data/bot.sqlite3
QR_OUTPUT_DIR=data/qr
QR_POOL_PATH=data/qr_pool.json
EXPORT_DIR=data/exports
FREE_QR_OUTPUT_DIR=data/free_qr
ALLOW_DYNAMIC_QR=true
ADMIN_USER_IDS=$adminIds
"@
    Set-Content -Path ".env" -Value $envText -Encoding UTF8
    Write-Host ".env created."
}

if (!(Test-Path "data")) {
    New-Item -ItemType Directory -Path "data" | Out-Null
}

if (!(Test-Path "data\qr_pool.json") -and (Test-Path "data\qr_pool.example.json")) {
    Copy-Item "data\qr_pool.example.json" "data\qr_pool.json"
    Write-Host "Demo QR pool created from data\qr_pool.example.json."
}

Write-Host "Checking project..."
& $Python -m compileall bot

Write-Host ""
Write-Host "Bot is starting. Open Telegram, send /start to your bot, choose a tariff, then press 'Демо: подтвердить оплату'."
Write-Host "Close this window to stop the bot."
Write-Host ""

& $Python -m bot
