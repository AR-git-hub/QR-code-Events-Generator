$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$ReleaseRoot = Join-Path $RepoRoot ".release"
$StageRoot = Join-Path $ReleaseRoot "qr-ticket-bot"
$ZipPath = Join-Path $ReleaseRoot "qr-ticket-bot-release.zip"

function Assert-InsideRepo {
    param([string]$Path)
    $full = [System.IO.Path]::GetFullPath($Path)
    if (!$full.StartsWith($RepoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to touch path outside repository: $full"
    }
}

Assert-InsideRepo $ReleaseRoot
Assert-InsideRepo $StageRoot
Assert-InsideRepo $ZipPath

if (Test-Path $StageRoot) {
    Remove-Item -LiteralPath $StageRoot -Recurse -Force
}

if (!(Test-Path $ReleaseRoot)) {
    New-Item -ItemType Directory -Path $ReleaseRoot | Out-Null
}

New-Item -ItemType Directory -Path $StageRoot | Out-Null

$excludeDirs = @(
    ".venv",
    ".git",
    ".idea",
    ".release",
    "__pycache__",
    ".pytest_cache",
    "logs",
    "data\qr",
    "data\exports",
    "data\free_qr",
    "validator_app\.gradle",
    "validator_app\.gradle-local",
    "validator_app\.android-sdk",
    "validator_app\build",
    "validator_app\app\build"
)

$excludeFiles = @(
    ".env",
    ".env.local",
    ".env.production",
    "data\bot.sqlite3",
    "data\qr_pool.json",
    "validator_app\local.properties"
)

function Should-Exclude {
    param([string]$RelativePath)

    foreach ($dir in $excludeDirs) {
        if ($RelativePath -eq $dir -or $RelativePath.StartsWith("$dir\", [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }

    foreach ($file in $excludeFiles) {
        if ($RelativePath -eq $file) {
            return $true
        }
    }

    if ($RelativePath.EndsWith(".pyc")) {
        return $true
    }

    return $false
}

Get-ChildItem -Path $RepoRoot -Recurse -File | ForEach-Object {
    $relative = $_.FullName.Substring($RepoRoot.Length).TrimStart("\", "/")
    if (!(Should-Exclude $relative)) {
        $target = Join-Path $StageRoot $relative
        $targetDir = Split-Path -Parent $target
        if (!(Test-Path $targetDir)) {
            New-Item -ItemType Directory -Path $targetDir | Out-Null
        }
        Copy-Item -LiteralPath $_.FullName -Destination $target
    }
}

if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

Compress-Archive -Path (Join-Path $StageRoot "*") -DestinationPath $ZipPath -Force

Write-Host "Release zip created:"
Write-Host $ZipPath
