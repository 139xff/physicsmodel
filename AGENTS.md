# EM Workbench Agent Instructions

## Project Intent

This repository implements `EM Workbench`, a university-level, open-ended interactive
electromagnetism workbench. Release 1 implements electrostatics as described in
`docs/superpowers/specs/2026-05-27-em-workbench-electrostatics-design.md` and `REQUIREMENTS.md`.

## Mandatory Toolchain Rule

- Use only the project-local uv binary: `.\.tools\uv\uv.exe`.
- Python is pinned to 3.12 by `.python-version`; invoke it only through project-local uv.
- All dependency operations go through uv: `.\.tools\uv\uv.exe sync`, `lock`, or `add`.
- All project execution goes through uv: for example
  `.\.tools\uv\uv.exe run pytest`, `.\.tools\uv\uv.exe run ruff check .`, and
  `.\.tools\uv\uv.exe run uvicorn em_workbench.app:app --reload`.
- `uv.lock` is the authoritative dependency resolution. `requirements.txt` is only an exported
  compatibility list, regenerated through
  `.\.tools\uv\uv.exe export --locked --all-groups --no-emit-project --output-file requirements.txt`.
- Do not introduce npm, Node package manifests, pip commands, Poetry, Conda, or direct global
  Python command execution.
- `scripts/bootstrap_uv.ps1` is the one bootstrap exception: it may acquire the pinned uv
  executable into `.tools/uv` before project-local uv exists; it may not install project
  dependencies.
- Three.js and OrbitControls must be pinned local vendor assets obtained by a checked-in Python
  script run through uv. The script and manifest must record upstream URL, SHA-256 and license
  details, then verify an offline smoke path without network runtime imports.
- Install or validate Playwright Chromium only through the uv-managed entry point, for example
  `.\.tools\uv\uv.exe run python -m playwright install chromium`, and report browser evidence in
  the corresponding task report.

## Architecture Boundaries

- Keep electrostatic calculations in pure Python domain modules, independent of FastAPI and UI.
- Keep scene contracts typed and serializable through Pydantic.
- Keep the browser app a static HTML/CSS/ES-module client consuming typed JSON API endpoints.
- Use Three.js only for 3D rendering; the solver remains authoritative for `V` and `E`.
- Keep view state shared so switching `2D / 3D` never resets the scene or probe.

## Quality Workflow

- Follow red-green-refactor for every new behavior: write a failing test, run it through uv, add
  minimal implementation, then rerun tests.
- Verify analytic electrostatic invariants and symmetry cases before adding advanced rendering.
- Before claiming a task complete, run its relevant tests and lint checks through uv.
- Do not claim the full specification is complete when delivering an explicitly scoped vertical
  slice.

## Required HTML Task Reports

After each completed task, create `reports/YYYY-MM-DD-task-NN-<slug>.html`.

Each report must contain:

- Task title and completion timestamp.
- Scope delivered and scope deferred.
- Changed files.
- Exact `uv` commands executed and their outcomes.
- Test/lint/browser verification evidence.
- Known risks or limitations.
- Next scheduled task.

Use accessible standalone HTML with clear headings and tables. The report is an engineering record,
not a marketing page.

## Current Execution Order

1. Establish uv-only project tooling, requirements, plan, and repository baseline.
2. Build FastAPI shell and static workbench surface.
3. Define scene contracts and electrostatic-source editing APIs.
4. Implement and validate the electrostatic solver.
5. Implement shared UI state plus 2D and 3D interaction.
6. Add probes, computation-quality modes, overlays, presets, and optional assistance.
