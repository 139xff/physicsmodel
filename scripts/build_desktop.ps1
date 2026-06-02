$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

.\.tools\uv\uv.exe run --locked --no-sync --extra desktop --extra bundle pyinstaller `
  --noconfirm `
  --clean `
  packaging\em_workbench_desktop.spec

$VersionLine = Select-String -Path pyproject.toml -Pattern '^version = "(.+)"$' | Select-Object -First 1
if (-not $VersionLine) {
  throw "Could not read project version from pyproject.toml"
}
$Version = $VersionLine.Matches[0].Groups[1].Value
$PortableRoot = Join-Path $ProjectRoot "dist\EMWorkbench"
$ReadmeSource = Join-Path $ProjectRoot "packaging\PORTABLE_README.txt"
$ReadmeTarget = Join-Path $PortableRoot "README.txt"
$ZipPath = Join-Path $ProjectRoot "dist\EMWorkbench-$Version-windows-x64-portable.zip"

Copy-Item -LiteralPath $ReadmeSource -Destination $ReadmeTarget -Force
if (Test-Path -LiteralPath $ZipPath) {
  Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path $PortableRoot -DestinationPath $ZipPath -CompressionLevel Optimal
Write-Host "Portable package created: $ZipPath"
