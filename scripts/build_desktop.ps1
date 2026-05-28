$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

.\.tools\uv\uv.exe run --extra desktop --extra bundle pyinstaller `
  --noconfirm `
  --clean `
  packaging\em_workbench_desktop.spec
