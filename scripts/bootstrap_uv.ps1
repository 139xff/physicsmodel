[CmdletBinding()]
param(
    [string]$Version = "0.11.16",
    [string]$ExpectedArchiveSha256 = "dd9d6d6554bfab265bfa98aa8e8a406c5c3a7b97582f93de1f4d48d9154a0395",
    [string]$ExpectedUvExeSha256 = "c5a583d5f1f6d055fc1c32c87d8eceee90edc69a5b9af5da70811befdfc04880",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$targetDir = Join-Path $projectRoot ".tools\uv"
$targetUv = Join-Path $targetDir "uv.exe"

function Assert-UvExecutableDigest {
    param([Parameter(Mandatory)][string]$Path)

    $actualUvExeSha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualUvExeSha256 -ne $ExpectedUvExeSha256.ToLowerInvariant()) {
        throw "uv executable SHA-256 mismatch. Expected $ExpectedUvExeSha256, received $actualUvExeSha256."
    }
}

if ((Test-Path -LiteralPath $targetUv) -and -not $Force) {
    Assert-UvExecutableDigest -Path $targetUv
    $installedVersionOutput = (& $targetUv --version | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $installedVersionOutput -notmatch "^uv $([regex]::Escape($Version))\b") {
        throw "Project-local uv exists but is not the required version $Version. Run with -Force."
    }
    Write-Host "Project-local uv is already present at $targetUv."
    Write-Host $installedVersionOutput
    exit 0
}

$archiveName = "uv-x86_64-pc-windows-msvc.zip"
$sourceUrl = "https://releases.astral.sh/github/uv/releases/download/$Version/$archiveName"
$temporaryDir = Join-Path ([System.IO.Path]::GetTempPath()) ("em-workbench-uv-" + [guid]::NewGuid())
$archivePath = Join-Path $temporaryDir $archiveName
$expandedDir = Join-Path $temporaryDir "expanded"

New-Item -ItemType Directory -Force -Path $temporaryDir | Out-Null

try {
    Write-Host "Downloading uv $Version from $sourceUrl"
    Invoke-WebRequest -Uri $sourceUrl -OutFile $archivePath

    $actualSha256 = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualSha256 -ne $ExpectedArchiveSha256.ToLowerInvariant()) {
        throw "uv archive SHA-256 mismatch. Expected $ExpectedArchiveSha256, received $actualSha256."
    }

    Expand-Archive -LiteralPath $archivePath -DestinationPath $expandedDir -Force
    $downloadedUv = Join-Path $expandedDir "uv.exe"
    if (-not (Test-Path -LiteralPath $downloadedUv)) {
        throw "The downloaded uv archive does not contain uv.exe."
    }
    Assert-UvExecutableDigest -Path $downloadedUv

    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    Copy-Item -LiteralPath $downloadedUv -Destination $targetUv -Force
    Assert-UvExecutableDigest -Path $targetUv

    & $targetUv --version
    if ($LASTEXITCODE -ne 0) {
        throw "The downloaded project-local uv binary did not run successfully."
    }

    Write-Host "Project-local uv is ready. Next run: .\.tools\uv\uv.exe sync --locked"
}
finally {
    Remove-Item -LiteralPath $temporaryDir -Recurse -Force -ErrorAction SilentlyContinue
}
