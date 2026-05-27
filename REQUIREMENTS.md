# EM Workbench Requirements

## 1. Product Goal

Build a browser-based, interactive electromagnetism workbench for university learners. The first
release covers electrostatics only, while keeping boundaries clear enough to add magnetostatics and
electromagnetic induction later.

The product is an open exploration tool, not a forced lesson flow. Formula notes, presets, and
exploration prompts are optional.

## 2. Release 1 Functional Requirements

### Scene Construction

- Users can create and combine point charges, uniformly charged line segments, rings, disks,
  infinite planes, and spherical shells.
- Users can edit position, orientation where meaningful, dimensions, and charge/density parameters.
- Classic arrangements are loadable presets but remain editable after loading.

### Views And Analysis

- A top-level control switches a single persisted scene between `2D` and `3D`.
- `2D` provides analytical slice views and supports field/vector/color overlays.
- `3D` provides free camera inspection and editable spatial source geometry.
- Probes display position, potential `V`, field vector `E`, magnitude `|E|`, and per-source
  contributions.
- Line sampling and advanced field/equipotential visualization may be added after the initial
  vertical slice, but the solver API must accommodate them.

### Computation Quality

- Interaction uses a responsive preview computation mode.
- Users can trigger or receive refined results after manipulation stops.
- The interface visibly distinguishes preview and refined output.
- Singular points and numerical approximation limits are reported rather than silently misrepresented.

### Optional Assistance

- Presets, concise theory references, and exploration prompts never block free operation.
- No required prediction questions, scores, accounts, or course progression are part of Release 1.

## 3. Technical Stack

The strict project rule is: dependency management and executable project commands are invoked
through the project-local `uv` binary at `.tools/uv/uv.exe`.

| Concern | Choice | Reason |
| --- | --- | --- |
| Runtime and dependency manager | Python 3.12, `uv` project + lockfile | One reproducible local toolchain; satisfies the uv-only constraint |
| Web service | FastAPI + Uvicorn | Small typed API and reliable local static-app server |
| Contracts | Pydantic | Validated serializable scenes and calculation requests |
| Physics engine | NumPy and SciPy, pure Python modules | Testable vectorized calculations and controlled numerical integration |
| Browser UI | HTML, CSS, native ES modules | No Node/npm dependency management is required |
| 3D graphics | Pinned local Three.js ES module assets | Capable 3D web rendering without introducing npm |
| Frontend asset acquisition | A Python vendor script run with `uv run` and recorded SHA-256 hashes | Versioned, reviewable browser dependency intake |
| Automated verification | pytest, httpx, Ruff, Playwright Python | API/physics tests and browser workflow checks all run through `uv` |

## 4. Dependency And Command Policy

- Never run `pip`, `python`, `npm`, `npx`, `node`, `vite`, or global `uv` directly for project work.
- `.python-version` pins Python 3.12, and `uv.lock` is the authoritative resolution for runtime
  and development dependencies.
- Use `.\.tools\uv\uv.exe sync` to create/update the environment from `uv.lock`.
- Use `.\.tools\uv\uv.exe run pytest`, `.\.tools\uv\uv.exe run ruff check .`, and
  `.\.tools\uv\uv.exe run uvicorn ...` for test, lint, and server commands.
- `requirements.txt` is a uv-exported compatibility artifact rather than an input to environment
  setup; regenerate it with
  `.\.tools\uv\uv.exe export --locked --all-groups --no-emit-project --output-file requirements.txt`.
- The initial local uv acquisition may be performed by `scripts/bootstrap_uv.ps1`, which writes
  only to ignored `.tools/uv`; after that bootstrap, all dependency and project execution uses
  project-local uv.
- Three.js and OrbitControls are downloaded only by a later checked-in Python vendor script
  executed with `uv run`. Its manifest records pinned source URLs, SHA-256 digests, and license
  details, and its browser smoke verification must operate offline against local assets.
- Playwright Chromium is installed and checked only through an uv-managed command such as
  `.\.tools\uv\uv.exe run python -m playwright install chromium`; browser evidence belongs in the
  relevant HTML task report.

## 5. Delivery And Reporting

- Work follows test-first development for behavior-bearing implementation.
- Each completed implementation task produces an HTML report in `reports/`, containing task scope,
  changed files, commands run, outcomes, known gaps, and the next task.
- The approved design source is
  `docs/superpowers/specs/2026-05-27-em-workbench-electrostatics-design.md`.

## 6. Non-Goals For Release 1

- User accounts, progress tracking, grades, teacher administration, or collaboration.
- Magnetostatics, induction, or waves.
- Research-grade numerical error guarantees or data-export platform features.
