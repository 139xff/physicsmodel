# EM Workbench Desktop App Migration Plan

Date: 2026-05-29

## Goal

Turn the current EM Workbench browser project into a standalone desktop application that can be
opened like normal software, without requiring the user to start a visible server or type a URL.

## Product Direction

The current web workbench remains the main UI surface. The desktop app should wrap that surface and
replace HTTP-only calls with a local Python bridge. The existing Python electrostatics solver stays
authoritative.

## Architecture

```text
Desktop executable
  ├─ embedded browser view
  │  └─ web/index.html, CSS, ES modules, Three.js vendor assets
  ├─ JavaScript API client
  │  ├─ desktop bridge mode: window.emWorkbenchBridge
  │  └─ development mode: /api/... HTTP endpoints
  └─ Python domain layer
     ├─ scene contracts
     ├─ presets
     └─ electrostatic solver
```

## Phase 1: Bridge-Ready Web Client

Completed in this slice:

- Add `web/api-client.js`.
- Keep browser development working through the existing FastAPI endpoints.
- Add a bridge-first API path for future desktop runtime integration.
- Prevent transient zero direction/normal vectors from being sent to the solver while a user is
  still editing fields.

## Phase 2: True Desktop Runtime

Recommended implementation:

- Add `PySide6` as an optional desktop dependency through project-local uv.
- Add `src/em_workbench/desktop.py`.
- Use Qt WebEngine to load the local static workbench.
- Expose `window.emWorkbenchBridge` methods:
  - `config`
  - `listPresets`
  - `getPreset`
  - `evaluateField`
- Call the existing Pydantic models, preset registry, and solver directly.

## Phase 3: Packaging

Recommended packaging path:

- Use PyInstaller or Nuitka after the desktop runtime works.
- Bundle:
  - Python package
  - `web/` static files
  - vendored Three.js assets
  - uv-locked dependency environment evidence
- Produce a Windows `.exe` preview build first.

## Deferred

- Installer signing.
- Auto-update.
- Cross-platform builds.
- User scene library and filesystem save dialogs.
- Full offline help/manual packaging.
