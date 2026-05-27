# EM Workbench Electrostatics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Each implementation task requires specification review, quality review, fresh `uv` verification, and a standalone HTML task report.

**Goal:** Deliver an uv-managed interactive electrostatics workbench web application whose first release supports editable three-dimensional charge distributions, shared 2D/3D viewing, probe analysis, and preview/refined computation.

**Architecture:** Python 3.12 modules own validated scene state and electrostatic computation; FastAPI hosts the JSON API and static browser application. The browser client is native HTML/CSS/ES modules with locally vendored, hash-verified Three.js assets for spatial rendering, avoiding an npm toolchain entirely.

**Tech Stack:** Project-local uv, Python 3.12, FastAPI, Pydantic, NumPy, SciPy, Uvicorn, native browser ES modules, local Three.js vendor assets, pytest, Ruff, Playwright Python.

---

## Delivery Rules

- The project-local executable `.\.tools\uv\uv.exe` is the only dependency and command runner after bootstrapping.
- `pyproject.toml` and `uv.lock` are authoritative; exported `requirements.txt` is compatibility documentation.
- A task is not complete until its tests/lint checks pass through uv and its HTML report is written to `reports/`.
- Each implementation task receives a fresh worker, then a specification reviewer, then a code-quality reviewer.
- Advanced field-line/equipotential extraction is deferred until the solver and main interaction slice are verified.

## Task 1: uv-Only Project Foundation And Governance

**Files:**
- Create or modify: `.gitignore`, `.python-version`, `pyproject.toml`, `uv.lock`, `requirements.txt`
- Create or modify: `REQUIREMENTS.md`, `AGENTS.md`
- Create: `scripts/bootstrap_uv.ps1`, `scripts/render_task_report.py`
- Create: `tests/test_render_task_report.py`
- Create: `reports/2026-05-27-task-01-uv-foundation.html`

**Requirements:**

- Install/use `uv` from `.tools/uv/uv.exe`, pin Python 3.12, sync a lockfile-backed virtual environment.
- Include FastAPI, Pydantic, NumPy, SciPy, Uvicorn, pytest, Ruff, httpx and Playwright Python.
- Specify that Three.js/OrbitControls are obtained by a later checked-in `uv run` vendor script with URLs, hashes, licenses and offline smoke verification.
- Specify Playwright browser installation and reporting as a controlled `uv run python -m playwright install chromium` workflow.
- Define a reusable HTML task-report generator and render the setup report with exact verified commands.

**Verification:**

```powershell
.\.tools\uv\uv.exe lock
.\.tools\uv\uv.exe sync --locked
.\.tools\uv\uv.exe run python -c "import fastapi, numpy, scipy, pydantic; print('uv-foundation-ok')"
.\.tools\uv\uv.exe run pytest tests/test_render_task_report.py
.\.tools\uv\uv.exe run ruff check scripts tests
```

## Task 2: FastAPI Shell, Static Workspace, And Vendored Browser Runtime

**Files:**
- Create: `src/em_workbench/__init__.py`, `src/em_workbench/app.py`
- Create: `web/index.html`, `web/styles.css`, `web/app.js`
- Create: `scripts/vendor_frontend.py`, `web/vendor/manifest.json`
- Create: `tests/test_app.py`, `tests/test_vendor_manifest.py`
- Create: `reports/2026-05-27-task-02-app-shell.html`

**Requirements:**

- Test first that `/health`, `/api/config`, `/`, and local vendor asset paths are served by FastAPI.
- Serve the static UI and API under one `uv run uvicorn` process.
- Vendor pinned Three.js plus OrbitControls with source URLs, SHA-256 and license details in the manifest.
- Create a technical workbench shell with a 2D/3D switch location, scene/sidebar regions and status region; controls may be inert until tested feature tasks.

**Verification:**

```powershell
.\.tools\uv\uv.exe run pytest tests/test_app.py tests/test_vendor_manifest.py
.\.tools\uv\uv.exe run ruff check src tests scripts
```

## Task 3: Typed Scene Contracts And Source Editing API

**Files:**
- Create: `src/em_workbench/models.py`, `src/em_workbench/presets.py`
- Modify: `src/em_workbench/app.py`
- Create: `tests/test_models.py`, `tests/test_scene_api.py`
- Create: `reports/2026-05-27-task-03-scene-contracts.html`

**Requirements:**

- Test first all six approved source types: point, line segment, ring, disk, infinite plane and spherical shell.
- Use SI units and explicit position/orientation contracts; reject physically invalid dimensions or missing density/charge data.
- Provide editable preset scenes and API responses that remain serializable for a browser scene store.

**Verification:**

```powershell
.\.tools\uv\uv.exe run pytest tests/test_models.py tests/test_scene_api.py
.\.tools\uv\uv.exe run ruff check src tests
```

## Task 4: Electrostatic Solver With Preview And Refined Modes

**Files:**
- Create: `src/em_workbench/physics/vectors.py`, `src/em_workbench/physics/solver.py`
- Modify: `src/em_workbench/app.py`
- Create: `tests/test_solver.py`, `tests/test_solver_api.py`
- Create: `reports/2026-05-27-task-04-solver.html`

**Requirements:**

- Start with hard-risk coverage: multiple point charges and arbitrarily oriented charged rings.
- Test analytic point-charge values, superposition, ring axis values, rotated-ring equivalence, near-source handling, and preview/refined result metadata.
- Provide a batched evaluation API suitable for probe and sampled vectors, with request/version identifiers so the client can discard stale preview results.
- Extend analytical or numerical evaluator interfaces for line, disk, plane and shell without falsely presenting unverified precision.

**Verification:**

```powershell
.\.tools\uv\uv.exe run pytest tests/test_solver.py tests/test_solver_api.py
.\.tools\uv\uv.exe run ruff check src tests
```

## Task 5: First Interactive 2D/3D Vertical Slice

**Files:**
- Modify: `web/index.html`, `web/styles.css`, `web/app.js`
- Create: `tests/test_browser_smoke.py`
- Create: `reports/2026-05-27-task-05-interaction-slice.html`

**Requirements:**

- Point charges and rings can be added and edited in browser state.
- A scene persists when switching `2D / 3D`; Three.js renders real source geometry in 3D.
- A single probe displays `V`, `E`, `|E|`, per-source contributions and computation-quality status.
- Client labels each request and ignores outdated responses after rapid edits.
- Install and run Chromium only via uv-managed Playwright command.

**Verification:**

```powershell
.\.tools\uv\uv.exe run python -m playwright install chromium
.\.tools\uv\uv.exe run pytest tests/test_browser_smoke.py
.\.tools\uv\uv.exe run ruff check src tests scripts
```

## Task 6: Remaining Sources And Analytical Overlays

**Files:**
- Modify: `src/em_workbench/physics/solver.py`, `web/app.js`, `web/styles.css`
- Create or modify: solver and browser tests
- Create: `reports/2026-05-27-task-06-complete-static-sources.html`

**Requirements:**

- Complete usable solving/editing for line segment, disk, plane and shell sources.
- Add vector sampling and potential/field color layers; then add field-line/equipotential extraction only with numerical tests and user-visible accuracy status.
- Add optional presets, concise theory drawer and exploration prompts without introducing forced lesson progression.

**Verification:**

```powershell
.\.tools\uv\uv.exe run pytest
.\.tools\uv\uv.exe run ruff check src tests scripts
```
