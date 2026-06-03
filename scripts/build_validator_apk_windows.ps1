$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$AppRoot = Join-Path $RepoRoot "validator_app"
$GradleVersion = "8.10.2"
$GradleRoot = Join-Path $AppRoot ".gradle-local"
$GradleZip = Join-Path $GradleRoot "gradle-$GradleVersion-bin.zip"
$GradleDir = Join-Path $GradleRoot "gradle-$GradleVersion"
$GradleBat = Join-Path $GradleDir "bin\gradle.bat"
$LocalSdk = Join-Path $AppRoot ".android-sdk"
$SdkManager = Join-Path $LocalSdk "cmdline-tools\latest\bin\sdkmanager.bat"
$CmdlineToolsVersion = "13114758"
$CmdlineToolsZip = Join-Path $LocalSdk "commandlinetools-win-$CmdlineToolsVersion.zip"

if (!(Test-Path $AppRoot)) {
    throw "validator_app was not found."
}

function Download-File {
    param(
        [string]$Url,
        [string]$OutFile
    )
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
        & curl.exe -L --fail --retry 3 --output $OutFile $Url
    } else {
        Invoke-WebRequest -Uri $Url -OutFile $OutFile
    }
}

if (!(Test-Path $GradleBat)) {
    New-Item -ItemType Directory -Force -Path $GradleRoot | Out-Null
    $download = $true
    if (Test-Path $GradleZip) {
        try {
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $zip = [System.IO.Compression.ZipFile]::OpenRead($GradleZip)
            $zip.Dispose()
            $download = $false
        } catch {
            Write-Host "Existing Gradle archive is invalid. Re-downloading..."
            Remove-Item -LiteralPath $GradleZip -Force
        }
    }

    if ($download) {
        Write-Host "Downloading Gradle $GradleVersion..."
        Download-File "https://services.gradle.org/distributions/gradle-$GradleVersion-bin.zip" $GradleZip
    }
    Write-Host "Extracting Gradle..."
    Expand-Archive -LiteralPath $GradleZip -DestinationPath $GradleRoot -Force
}

if (!$env:ANDROID_HOME -and !$env:ANDROID_SDK_ROOT -and !(Test-Path (Join-Path $AppRoot "local.properties"))) {
    Write-Host "Android SDK was not found. Installing local Android SDK command-line tools..."
    New-Item -ItemType Directory -Force -Path $LocalSdk | Out-Null
    if (!(Test-Path $SdkManager)) {
        if (!(Test-Path $CmdlineToolsZip)) {
            Download-File "https://dl.google.com/android/repository/commandlinetools-win-$CmdlineToolsVersion`_latest.zip" $CmdlineToolsZip
        }
        $TempTools = Join-Path $LocalSdk "cmdline-tools-temp"
        if (Test-Path $TempTools) {
            Remove-Item -LiteralPath $TempTools -Recurse -Force
        }
        New-Item -ItemType Directory -Force -Path $TempTools | Out-Null
        Expand-Archive -LiteralPath $CmdlineToolsZip -DestinationPath $TempTools -Force
        $LatestTools = Join-Path $LocalSdk "cmdline-tools\latest"
        if (Test-Path $LatestTools) {
            Remove-Item -LiteralPath $LatestTools -Recurse -Force
        }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LatestTools) | Out-Null
        Move-Item -LiteralPath (Join-Path $TempTools "cmdline-tools") -Destination $LatestTools
        Remove-Item -LiteralPath $TempTools -Recurse -Force
    }

    Write-Host "Accepting Android SDK licenses..."
    "y`ny`ny`ny`ny`ny`ny`ny`ny`ny`n" | & $SdkManager --sdk_root=$LocalSdk --licenses | Out-Host

    Write-Host "Installing Android SDK packages..."
    & $SdkManager --sdk_root=$LocalSdk "platform-tools" "platforms;android-35" "build-tools;35.0.0"

    Set-Content -Path (Join-Path $AppRoot "local.properties") -Value ("sdk.dir=" + ($LocalSdk -replace "\\", "\\\\")) -Encoding ASCII
}

Write-Host "Building validator APK..."
Set-Location $AppRoot
& $GradleBat ":app:assembleDebug"

$ApkPath = Join-Path $AppRoot "app\build\outputs\apk\debug\app-debug.apk"
if (!(Test-Path $ApkPath)) {
    throw "APK was not created."
}

$OutDir = Join-Path $RepoRoot "dist"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$OutApk = Join-Path $OutDir "qr-ticket-validator-debug.apk"
Copy-Item -LiteralPath $ApkPath -Destination $OutApk -Force

Write-Host "APK created:"
Write-Host $OutApk
