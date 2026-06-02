# EM Workbench

[中文说明](README-ZH.md)

EM Workbench is an open-ended university electromagnetism workbench. The current release focuses on
electrostatics: users can build charge configurations, switch between 2D and 3D views, inspect field
visualizations, and measure potential and electric field values with a probe.

The project can run in two modes:

- A local development web app powered by FastAPI.
- A standalone Windows desktop app that does not require users to start a server or open a URL.

## Current Features

- Add and edit electrostatic sources:
  - point charge
  - uniformly charged line segment
  - charged ring
  - charged disk
  - infinite charged plane
  - charged spherical shell
- Switch between 2D and 3D views without resetting the scene.
- Render 2D field vectors and potential heatmap overlays.
- Render 3D source geometry and field vector arrows with local Three.js assets.
- Use probes to read potential `V`, electric field vector `E`, field magnitude `|E|`, and per-source
  contributions.
- Load editable presets such as the electric dipole.
- Run preview and refined solver modes.
- Use a standalone Windows portable package for easy sharing.

## Release Package

For non-developers, use the Windows portable package:

```text
dist/EMWorkbench-0.1.0-windows-x64-portable.zip
```

How to use it:

1. Download or receive the zip file.
2. Extract the whole archive.
3. Open the `EMWorkbench` folder.
4. Double-click `EMWorkbench.exe`.

No Python installation, server command, or browser URL is required.

The `dist/` directory is ignored by Git. For public sharing, upload the zip file to GitHub Releases
instead of committing it to the repository.

## Development Setup

This repository uses the project-local `uv` executable only:

```powershell
.\.tools\uv\uv.exe sync
```

If `.tools/uv/uv.exe` is missing, bootstrap it first:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_uv.ps1
```

Do not use global `pip`, global `python`, npm, or Node package managers for this project.

## Run The Web Development App

```powershell
.\.tools\uv\uv.exe run uvicorn em_workbench.app:app --reload
```

Then open the local address printed by Uvicorn.

## Run The Desktop App From Source

Install desktop dependencies:

```powershell
.\.tools\uv\uv.exe sync --extra desktop
```

Check the desktop runtime:

```powershell
.\.tools\uv\uv.exe run --extra desktop em-workbench-desktop --check
```

Launch the desktop app:

```powershell
.\.tools\uv\uv.exe run --extra desktop em-workbench-desktop
```

## Optional CUDA Acceleration

The default installation and portable desktop package run on CPU JIT without requiring CUDA.
When running from source on a supported NVIDIA system, install the optional CUDA extra together
with the desktop extra:

```powershell
.\.tools\uv\uv.exe sync --extra desktop --extra cuda
```

CUDA is detected at runtime. Automatic dispatch uses the GPU for suitable field batches and keeps
smaller or sequential workloads on CPU when that is faster. If CUDA is unavailable, computation
falls back to CPU JIT. The compute backend status block in the app shows the effective backend,
precision, and warm-up state.

## Build The Windows Portable Package

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_desktop.ps1
```

The script builds:

```text
dist/EMWorkbench/
dist/EMWorkbench-0.1.0-windows-x64-portable.zip
```

## Verification

Run lint and tests through the project-local uv:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync ruff check --no-cache src tests scripts
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider
```

The desktop package can be smoke-tested with:

```powershell
$p = Start-Process -FilePath .\dist\EMWorkbench\EMWorkbench.exe -ArgumentList '--check' -Wait -PassThru
$p.ExitCode
```

## Project Structure

```text
web/                  Static browser UI, styles, ES modules, local Three.js assets
src/em_workbench/     FastAPI app, desktop bridge, scene contracts, physics solver
tests/                Unit, API, solver, browser, and desktop bridge tests
scripts/              uv bootstrap, report rendering, vendor and desktop build scripts
packaging/            PyInstaller spec and portable package README
docs/                 Design specs and implementation plans
reports/              HTML engineering task reports
```

## Scope

Release 1 is electrostatics only. It intentionally does not include accounts, teacher dashboards,
grades, collaboration, magnetostatics, induction, or electromagnetic waves.

## Notes

- Three.js and OrbitControls are vendored locally and should not be loaded from a CDN at runtime.
- The solver is implemented in Python and remains the authoritative source for field and potential
  values.
- The Windows package is currently unsigned, so Windows SmartScreen may warn that the publisher is
  unknown.
