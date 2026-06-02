# EM Workbench CPU/CUDA Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Python and browser hot loops with a shared high-performance compute layer that uses Numba multi-core CPU kernels, optional Numba-CUDA kernels, workload-aware dispatch, and verified CPU fallback.

**Architecture:** Keep the current Pydantic scene contracts and scalar solver as the correctness oracle. Add a focused `em_workbench.physics.compute` package that compiles scenes into immutable NumPy arrays, dispatches CPU JIT or CUDA kernels by workload, and exposes field samples, trajectories, field lines, status, cache, and warm-up metadata through the existing FastAPI and desktop surfaces.

**Tech Stack:** Project-local uv, Python 3.12, NumPy, Numba CPU JIT, optional `numba-cuda[cu12]`, FastAPI, Pydantic, PySide6 desktop bridge, native browser ES modules, pytest, Ruff, Playwright Python.

---

## Delivery Rules

- Run every Python, dependency, test, lint, browser, and packaging command through `.\.tools\uv\uv.exe`, except the existing PowerShell packaging wrapper.
- Follow red-green-refactor for each behavior: add one failing test, run it, make the minimum implementation change, rerun focused tests, then run the task verification set.
- Preserve the scalar solver as an executable oracle. Do not delete scalar contribution functions.
- Preserve existing JSON compatibility unless a response gains an optional field.
- Use `preview -> float32` and `refined -> float64`.
- Treat CUDA as optional. Base installation and CPU-only tests must remain functional without `numba-cuda`.
- Generate one accessible standalone HTML engineering report after each completed task.
- Commit after each task. Do not include unrelated local changes.
- Before starting, preserve the existing unstaged desktop bootstrap regression test in `tests/test_browser_smoke.py`; Task 0 owns it.
- Ignore the local untracked runtime directory `releases/opened-20260601-140453/`.

## File Structure

Create a focused compute package instead of expanding `solver.py`:

| File | Responsibility |
| --- | --- |
| `src/em_workbench/physics/compute/contracts.py` | Backend policy, execution metadata, compute status, and shared internal result dataclasses |
| `src/em_workbench/physics/compute/runtime.py` | CPU description, lazy CUDA probe, and readable fallback reasons |
| `src/em_workbench/physics/compute/packed_scene.py` | Canonical scene hash, immutable NumPy arrays, quality-aware discretization, and bounded host cache |
| `src/em_workbench/physics/compute/cpu_backend.py` | Numba CPU total-only, contribution, trajectory, and field-line kernels |
| `src/em_workbench/physics/compute/cuda_backend.py` | Lazy optional CUDA import, CUDA field kernels, CUDA field-line kernels, device cache, and chunking |
| `src/em_workbench/physics/compute/dispatcher.py` | Workload-aware backend selection, timing, fallback, and public compute service |
| `src/em_workbench/physics/compute/field_lines.py` | Backend-neutral 2D field-line request/response DTOs and render-ready post-processing |
| `src/em_workbench/physics/compute/warmup.py` | Background CPU/CUDA warm-up state machine |
| `src/em_workbench/physics/solver.py` | Existing scalar oracle plus DTO assembly through the compute service |
| `src/em_workbench/physics/dynamics.py` | Existing trajectory DTOs plus compiled trajectory delegation |
| `src/em_workbench/app.py` | HTTP request models and status/field-line endpoints |
| `src/em_workbench/desktop_bridge.py` | Synchronous domain bridge plus asynchronous desktop compute queue |
| `src/em_workbench/desktop.py` | Qt WebChannel methods and safe document-creation bootstrap |
| `web/api-client.js` | HTTP/desktop transport, status, and asynchronous field-line requests |
| `web/app.js` | Backend field-line orchestration, stale-result suppression, and compute-status UI |
| `scripts/benchmark_compute.py` | Reproducible cold/warm CPU, CUDA, scalar, and auto benchmarks |

## Verification Commands Used Repeatedly

```powershell
.\.tools\uv\uv.exe run --locked --no-sync ruff check --no-cache src tests scripts
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider
```

## Task 0: Repair Desktop Bridge Bootstrap Before Performance Work

The existing Qt bridge script runs at `DocumentCreation`. At that moment `document.documentElement`
may still be `null`. The current unstaged regression test already reproduces the user-visible
`Cannot read properties of null (reading 'appendChild')` failure.

**Files:**
- Modify: `src/em_workbench/desktop.py`
- Modify: `tests/test_browser_smoke.py`
- Create: `reports/2026-06-02-task-21-desktop-bridge-bootstrap.html`

- [ ] **Step 1: Run the existing regression test and verify the red state**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_browser_smoke.py::test_desktop_bridge_bootstrap_waits_for_document_root -q
```

Expected: FAIL with `Cannot read properties of null (reading 'appendChild')`.

- [ ] **Step 2: Make script attachment wait for the document root**

Replace the direct `document.documentElement.appendChild(script);` call inside
`_bridge_bootstrap_script()` with:

```javascript
  function appendBridgeScript() {
    if (!document.documentElement) {
      window.setTimeout(appendBridgeScript, 0);
      return;
    }
    document.documentElement.appendChild(script);
  }
  appendBridgeScript();
```

- [ ] **Step 3: Verify focused browser and desktop checks**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_browser_smoke.py::test_desktop_bridge_bootstrap_waits_for_document_root tests/test_desktop_bridge.py -q
.\.tools\uv\uv.exe run --locked --no-sync --extra desktop em-workbench-desktop --check
```

Expected: all selected tests pass and output contains `desktop runtime ok`.

- [ ] **Step 4: Run lint, create the HTML report, and commit**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync ruff check --no-cache src tests scripts
git add src/em_workbench/desktop.py tests/test_browser_smoke.py reports/2026-06-02-task-21-desktop-bridge-bootstrap.html
git commit -m "Fix desktop bridge bootstrap timing"
```

Expected: lint passes and the commit contains only the bridge fix, regression test, and report.

## Task 1: Add Compute Contracts, Backend Probe, Dependencies, And Status API

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `requirements.txt`
- Create: `src/em_workbench/physics/compute/__init__.py`
- Create: `src/em_workbench/physics/compute/contracts.py`
- Create: `src/em_workbench/physics/compute/runtime.py`
- Modify: `src/em_workbench/app.py`
- Create: `tests/test_compute_runtime.py`
- Modify: `tests/test_app.py`
- Create: `reports/2026-06-02-task-22-compute-runtime-status.html`

- [ ] **Step 1: Add failing runtime and HTTP tests**

Create `tests/test_compute_runtime.py`:

```python
from em_workbench.physics.compute.runtime import probe_runtime


def test_runtime_probe_always_reports_cpu_and_cuda_state() -> None:
    status = probe_runtime()

    assert status.cpu.logical_processors >= 1
    assert status.cpu.description
    assert isinstance(status.cuda.installed, bool)
    assert isinstance(status.cuda.available, bool)
    if not status.cuda.available:
        assert status.cuda.device_name is None
        assert status.cuda.fallback_reason
```

Append to `tests/test_app.py`:

```python
def test_compute_status_reports_cpu_and_optional_cuda_runtime() -> None:
    response = client.get("/api/compute/status")

    assert response.status_code == 200
    status = response.json()
    assert status["cpu"]["logical_processors"] >= 1
    assert status["warmup"]["state"] == "idle"
    assert isinstance(status["cuda"]["installed"], bool)
    assert isinstance(status["cuda"]["available"], bool)
```

- [ ] **Step 2: Run tests and verify missing-module failures**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_compute_runtime.py tests/test_app.py::test_compute_status_reports_cpu_and_optional_cuda_runtime -q
```

Expected: FAIL because `em_workbench.physics.compute` and `/api/compute/status` do not exist.

- [ ] **Step 3: Add locked CPU and optional CUDA dependencies**

Run:

```powershell
.\.tools\uv\uv.exe add "numba>=0.61,<1"
.\.tools\uv\uv.exe add --optional cuda "numba-cuda[cu12]"
.\.tools\uv\uv.exe export --locked --all-groups --no-emit-project --output-file requirements.txt
```

Expected: `pyproject.toml`, `uv.lock`, and `requirements.txt` update through project-local uv.

- [ ] **Step 4: Add shared contracts**

Create `src/em_workbench/physics/compute/contracts.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

BackendPolicy = Literal["auto", "cpu", "cuda", "scalar"]
EffectiveBackend = Literal["cpu-jit", "cuda", "scalar"]
Precision = Literal["float32", "float64"]
WarmupState = Literal["idle", "warming", "ready", "failed"]


class ComputeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CpuRuntimeStatus(ComputeModel):
    description: str
    physical_cores: int | None
    logical_processors: int


class CudaRuntimeStatus(ComputeModel):
    installed: bool
    available: bool
    device_name: str | None = None
    compute_capability: str | None = None
    fallback_reason: str | None = None


class WarmupStatus(ComputeModel):
    state: WarmupState = "idle"
    failure_reason: str | None = None


class CacheStatus(ComputeModel):
    packed_scenes: int = 0
    packed_scene_limit: int = 16
    device_scenes: int = 0
    device_scene_limit: int = 8
    field_lines: int = 0
    field_line_limit: int = 16


class ComputeStatus(ComputeModel):
    cpu: CpuRuntimeStatus
    cuda: CudaRuntimeStatus
    warmup: WarmupStatus
    cache: CacheStatus
    last_fallback_reason: str | None = None


class ExecutionMetadata(ComputeModel):
    backend_requested: BackendPolicy
    backend_effective: EffectiveBackend
    device: str
    precision: Precision
    scene_cache_hit: bool
    device_cache_hit: bool = False
    warm: bool
    compute_ms: float
    total_ms: float
    fallback_reason: str | None = None


@dataclass(frozen=True)
class TotalFieldArrays:
    potential_v: object
    field_v_per_m: object
```

- [ ] **Step 5: Add a lazy CUDA probe**

Create `src/em_workbench/physics/compute/runtime.py`:

```python
from __future__ import annotations

import os
import platform

from em_workbench.physics.compute.contracts import (
    CacheStatus,
    ComputeStatus,
    CpuRuntimeStatus,
    CudaRuntimeStatus,
    WarmupStatus,
)


def _cpu_status() -> CpuRuntimeStatus:
    logical = os.cpu_count() or 1
    return CpuRuntimeStatus(
        description=platform.processor() or platform.machine() or "CPU",
        physical_cores=None,
        logical_processors=logical,
    )


def _cuda_status() -> CudaRuntimeStatus:
    try:
        from numba import cuda
    except Exception as error:
        return CudaRuntimeStatus(
            installed=False,
            available=False,
            fallback_reason=f"CUDA package unavailable: {error}",
        )
    try:
        if not cuda.is_available():
            return CudaRuntimeStatus(
                installed=True,
                available=False,
                fallback_reason="CUDA runtime unavailable.",
            )
        device = cuda.get_current_device()
        capability = ".".join(str(part) for part in device.compute_capability)
        return CudaRuntimeStatus(
            installed=True,
            available=True,
            device_name=device.name.decode() if isinstance(device.name, bytes) else str(device.name),
            compute_capability=capability,
        )
    except Exception as error:
        return CudaRuntimeStatus(
            installed=True,
            available=False,
            fallback_reason=f"CUDA probe failed: {error}",
        )


def probe_runtime() -> ComputeStatus:
    return ComputeStatus(
        cpu=_cpu_status(),
        cuda=_cuda_status(),
        warmup=WarmupStatus(),
        cache=CacheStatus(),
    )
```

- [ ] **Step 6: Add the status endpoint**

Add to `src/em_workbench/app.py`:

```python
from em_workbench.physics.compute.contracts import ComputeStatus
from em_workbench.physics.compute.runtime import probe_runtime


@app.get("/api/compute/status", response_model=ComputeStatus)
def compute_status() -> ComputeStatus:
    return probe_runtime()
```

- [ ] **Step 7: Verify CPU-only and optional-CUDA status**

Run:

```powershell
.\.tools\uv\uv.exe sync --locked
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_compute_runtime.py tests/test_app.py::test_compute_status_reports_cpu_and_optional_cuda_runtime -q
.\.tools\uv\uv.exe sync --locked --extra cuda
.\.tools\uv\uv.exe run --locked --no-sync python -c "from em_workbench.physics.compute.runtime import probe_runtime; print(probe_runtime().model_dump_json(indent=2))"
```

Expected: tests pass without CUDA; with the CUDA extra installed, the baseline RTX 5060 Ti reports
`available: true` and compute capability `12.0`.

- [ ] **Step 8: Run lint, create the HTML report, and commit**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync ruff check --no-cache src tests scripts
git add pyproject.toml uv.lock requirements.txt src/em_workbench/physics/compute src/em_workbench/app.py tests/test_compute_runtime.py tests/test_app.py reports/2026-06-02-task-22-compute-runtime-status.html
git commit -m "Add optional CUDA runtime status"
```

## Task 2: Compile Scenes Into Immutable Packed Arrays And Cache Them

**Files:**
- Create: `src/em_workbench/physics/compute/packed_scene.py`
- Create: `tests/test_packed_scene.py`
- Create: `reports/2026-06-02-task-23-packed-scene-cache.html`

- [ ] **Step 1: Add failing compiler tests**

Create `tests/test_packed_scene.py` with tests that assert:

```python
import numpy as np

from em_workbench.models import Scene
from em_workbench.physics.compute.packed_scene import PackedSceneCache, compile_scene


def _scene() -> Scene:
    return Scene.model_validate(
        {
            "id": "packed-scene",
            "title": "Packed scene",
            "sources": [
                {
                    "id": "q",
                    "kind": "point",
                    "label": "q",
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "charge_c": 1e-9,
                },
                {
                    "id": "line",
                    "kind": "line_segment",
                    "label": "line",
                    "position": {"x": 0.0, "y": 0.1, "z": 0.0},
                    "orientation": {"x": 1.0, "y": 0.0, "z": 0.0},
                    "length_m": 0.2,
                    "charge_c": 2e-9,
                },
            ],
        }
    )


def test_compile_scene_uses_preview_float32_and_owner_indexes() -> None:
    packed = compile_scene(_scene(), quality="preview")

    assert packed.dtype == np.dtype(np.float32)
    assert packed.element_positions.shape == (49, 3)
    assert packed.element_charges.shape == (49,)
    assert packed.element_source_indexes.tolist() == [0] + [1] * 48
    assert packed.source_ids == ("q", "line")
    assert not packed.element_positions.flags.writeable


def test_cache_returns_same_immutable_scene_for_same_key() -> None:
    cache = PackedSceneCache(limit=2)

    first, first_hit = cache.get_or_compile(_scene(), quality="refined")
    second, second_hit = cache.get_or_compile(_scene(), quality="refined")

    assert first_hit is False
    assert second_hit is True
    assert second is first
```

- [ ] **Step 2: Run tests and verify import failure**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_packed_scene.py -q
```

Expected: FAIL because `packed_scene.py` does not exist.

- [ ] **Step 3: Implement packed scene compiler**

Create `src/em_workbench/physics/compute/packed_scene.py` with:

```python
from __future__ import annotations

import hashlib
import math
from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock

import numpy as np

from em_workbench.models import Scene
from em_workbench.physics.solver import _settings_for_quality
from em_workbench.physics.vectors import Vector3, orthonormal_basis_from_normal


def dtype_for_quality(quality: str) -> np.dtype:
    return np.dtype(np.float32 if quality == "preview" else np.float64)


@dataclass(frozen=True)
class PackedScene:
    cache_key: str
    dtype: np.dtype
    source_ids: tuple[str, ...]
    element_positions: np.ndarray
    element_charges: np.ndarray
    element_source_indexes: np.ndarray
    plane_positions: np.ndarray
    plane_normals: np.ndarray
    plane_densities: np.ndarray
    plane_source_indexes: np.ndarray
    shell_positions: np.ndarray
    shell_radii: np.ndarray
    shell_charges: np.ndarray
    shell_source_indexes: np.ndarray


def _readonly(array: np.ndarray) -> np.ndarray:
    array.flags.writeable = False
    return array


def _cache_key(scene: Scene, quality: str, dtype: np.dtype) -> str:
    payload = f"{quality}|{dtype.str}|{scene.model_dump_json()}".encode()
    return hashlib.sha256(payload).hexdigest()
```

Implement `compile_scene()` by:

1. Adding one element for each point charge.
2. Adding midpoint elements for each line segment using `settings["line_segments"]`.
3. Adding midpoint angular elements for rings using `settings["ring_segments"]`.
4. Adding midpoint radial/angular patches for disks using
   `settings["disk_radial_segments"] * settings["disk_angular_segments"]`.
5. Storing infinite planes and shells in analytic arrays.
6. Converting arrays to the selected dtype and marking them read-only.

Use these concrete midpoint formulas:

```python
for index in range(settings["line_segments"]):
    offset = -0.5 * source.length_m + (index + 0.5) * source.length_m / settings["line_segments"]
    element_positions.append(center + axis.scale(offset))
    element_charges.append(total_charge / settings["line_segments"])
    element_source_indexes.append(source_index)

for index in range(settings["ring_segments"]):
    angle = 2.0 * math.pi * (index + 0.5) / settings["ring_segments"]
    point = center + axis_u.scale(math.cos(angle) * source.radius_m)
    point = point + axis_v.scale(math.sin(angle) * source.radius_m)
    element_positions.append(point)
    element_charges.append(total_charge / settings["ring_segments"])
    element_source_indexes.append(source_index)

for radial_index in range(settings["disk_radial_segments"]):
    radius = (radial_index + 0.5) * source.radius_m / settings["disk_radial_segments"]
    dq = surface_density * radius * dr * dtheta
    for angular_index in range(settings["disk_angular_segments"]):
        angle = (angular_index + 0.5) * dtheta
        point = center + axis_u.scale(math.cos(angle) * radius)
        point = point + axis_v.scale(math.sin(angle) * radius)
        element_positions.append(point)
        element_charges.append(dq)
        element_source_indexes.append(source_index)
```

Add a bounded cache:

```python
class PackedSceneCache:
    def __init__(self, limit: int = 16) -> None:
        self.limit = limit
        self._items: OrderedDict[str, PackedScene] = OrderedDict()
        self._lock = RLock()

    def get_or_compile(self, scene: Scene, *, quality: str) -> tuple[PackedScene, bool]:
        dtype = dtype_for_quality(quality)
        key = _cache_key(scene, quality, dtype)
        with self._lock:
            cached = self._items.get(key)
            if cached is not None:
                self._items.move_to_end(key)
                return cached, True
        packed = compile_scene(scene, quality=quality)
        with self._lock:
            self._items[key] = packed
            self._items.move_to_end(key)
            while len(self._items) > self.limit:
                self._items.popitem(last=False)
        return packed, False

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
```

- [ ] **Step 4: Verify compiler tests and scalar solver tests**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_packed_scene.py tests/test_solver.py -q
```

Expected: PASS.

- [ ] **Step 5: Run lint, create the HTML report, and commit**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync ruff check --no-cache src tests scripts
git add src/em_workbench/physics/compute/packed_scene.py tests/test_packed_scene.py reports/2026-06-02-task-23-packed-scene-cache.html
git commit -m "Compile electrostatic scenes into packed arrays"
```

## Task 3: Add Numba CPU Batch Field Kernels And Scalar Comparison

**Files:**
- Create: `src/em_workbench/physics/compute/cpu_backend.py`
- Create: `src/em_workbench/physics/compute/dispatcher.py`
- Modify: `src/em_workbench/physics/solver.py`
- Create: `tests/conftest.py`
- Create: `tests/test_cpu_backend.py`
- Modify: `tests/test_solver.py`
- Create: `reports/2026-06-02-task-24-cpu-jit-field-kernels.html`

- [ ] **Step 1: Add shared representative compute fixtures**

Create `tests/conftest.py`:

```python
import pytest

from em_workbench.models import Position, Scene
from em_workbench.physics.dynamics import TestCharge


@pytest.fixture
def representative_scene() -> Scene:
    return Scene.model_validate(
        {
            "id": "representative",
            "title": "Representative compute scene",
            "sources": [
                {"id": "q1", "kind": "point", "label": "q1", "position": {"x": -0.08, "y": 0.0, "z": 0.0}, "charge_c": 2e-9},
                {"id": "q2", "kind": "point", "label": "q2", "position": {"x": 0.08, "y": 0.0, "z": 0.0}, "charge_c": -2e-9},
                {"id": "line", "kind": "line_segment", "label": "line", "position": {"x": 0.0, "y": -0.12, "z": 0.0}, "orientation": {"x": 1.0, "y": 0.0, "z": 0.0}, "length_m": 0.18, "charge_c": 1.5e-9},
                {"id": "ring", "kind": "ring", "label": "ring", "position": {"x": 0.0, "y": 0.1, "z": 0.0}, "normal": {"x": 0.0, "y": 0.0, "z": 1.0}, "radius_m": 0.06, "charge_c": -1.2e-9},
                {"id": "disk", "kind": "disk", "label": "disk", "position": {"x": 0.0, "y": 0.0, "z": -0.08}, "normal": {"x": 0.0, "y": 0.0, "z": 1.0}, "radius_m": 0.08, "charge_c": 1e-9},
            ],
        }
    )


@pytest.fixture
def sample_points() -> list[Position]:
    return [
        Position(x=-0.20, y=-0.15, z=0.04),
        Position(x=0.00, y=0.00, z=0.04),
        Position(x=0.22, y=0.18, z=0.04),
    ]


@pytest.fixture
def particle() -> TestCharge:
    return TestCharge.model_validate(
        {
            "charge_c": -1e-9,
            "mass_kg": 6e-6,
            "position": {"x": -0.08, "y": 0.04, "z": 0.0},
            "velocity": {"x": 0.06, "y": 0.0, "z": 0.0},
        }
    )
```

- [ ] **Step 2: Add failing CPU parity tests**

Create `tests/test_cpu_backend.py` with parameterized scenes for point, line, ring, disk, plane, and
shell sources. Use:

```python
import numpy as np
import pytest

from em_workbench.physics.compute.cpu_backend import evaluate_totals_cpu
from em_workbench.physics.compute.packed_scene import compile_scene
from em_workbench.physics.solver import evaluate_scene_scalar


@pytest.mark.parametrize("quality,rtol", [("preview", 2e-5), ("refined", 1e-10)])
def test_cpu_totals_match_scalar_reference(representative_scene, sample_points, quality, rtol) -> None:
    packed = compile_scene(representative_scene, quality=quality)
    points = np.asarray([[point.x, point.y, point.z] for point in sample_points], dtype=packed.dtype)

    potential, field = evaluate_totals_cpu(packed, points)
    scalar = evaluate_scene_scalar(representative_scene, sample_points, quality=quality)

    assert potential == pytest.approx([sample.potential_v for sample in scalar.samples], rel=rtol)
    assert field == pytest.approx(
        [[sample.field_v_per_m.x, sample.field_v_per_m.y, sample.field_v_per_m.z] for sample in scalar.samples],
        rel=rtol,
        abs=1e-7,
    )
```

Add a contribution parity test that compares `evaluate_contributions_cpu()` output summed across
source indexes to `evaluate_totals_cpu()`.

- [ ] **Step 3: Run tests and verify missing backend failure**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_cpu_backend.py -q
```

Expected: FAIL because `cpu_backend.py` does not exist.

- [ ] **Step 4: Implement compiled CPU kernels**

Create `src/em_workbench/physics/compute/cpu_backend.py`. Use Numba `njit` and `prange` over sample
indexes. The core kernel signature is:

```python
@njit(cache=True, parallel=True)
def _evaluate_totals_kernel(
    points,
    element_positions,
    element_charges,
    plane_positions,
    plane_normals,
    plane_densities,
    shell_positions,
    shell_radii,
    shell_charges,
):
    sample_count = points.shape[0]
    potential = np.zeros(sample_count, dtype=points.dtype)
    field = np.zeros((sample_count, 3), dtype=points.dtype)
    for sample_index in prange(sample_count):
        x = points[sample_index, 0]
        y = points[sample_index, 1]
        z = points[sample_index, 2]
        for element_index in range(element_positions.shape[0]):
            dx = x - element_positions[element_index, 0]
            dy = y - element_positions[element_index, 1]
            dz = z - element_positions[element_index, 2]
            distance_sq = dx * dx + dy * dy + dz * dz
            if distance_sq <= MIN_SOURCE_DISTANCE_SQ:
                continue
            distance = math.sqrt(distance_sq)
            scale = COULOMB_CONSTANT * element_charges[element_index]
            potential[sample_index] += scale / distance
            field_scale = scale / (distance_sq * distance)
            field[sample_index, 0] += dx * field_scale
            field[sample_index, 1] += dy * field_scale
            field[sample_index, 2] += dz * field_scale
```

Complete the same kernel with analytic plane and shell loops that preserve scalar formulas.

Insert these loops after the discrete-element loop:

```python
        for plane_index in range(plane_positions.shape[0]):
            dx = x - plane_positions[plane_index, 0]
            dy = y - plane_positions[plane_index, 1]
            dz = z - plane_positions[plane_index, 2]
            signed_distance = (
                dx * plane_normals[plane_index, 0]
                + dy * plane_normals[plane_index, 1]
                + dz * plane_normals[plane_index, 2]
            )
            plane_scale = plane_densities[plane_index] / (2.0 * EPSILON_0)
            potential[sample_index] -= plane_scale * abs(signed_distance)
            if abs(signed_distance) > MIN_SOURCE_DISTANCE_M:
                direction = 1.0 if signed_distance > 0.0 else -1.0
                field[sample_index, 0] += direction * plane_scale * plane_normals[plane_index, 0]
                field[sample_index, 1] += direction * plane_scale * plane_normals[plane_index, 1]
                field[sample_index, 2] += direction * plane_scale * plane_normals[plane_index, 2]

        for shell_index in range(shell_positions.shape[0]):
            dx = x - shell_positions[shell_index, 0]
            dy = y - shell_positions[shell_index, 1]
            dz = z - shell_positions[shell_index, 2]
            distance_sq = dx * dx + dy * dy + dz * dz
            distance = math.sqrt(distance_sq)
            shell_scale = COULOMB_CONSTANT * shell_charges[shell_index]
            if distance < shell_radii[shell_index]:
                potential[sample_index] += shell_scale / shell_radii[shell_index]
            elif distance > MIN_SOURCE_DISTANCE_M:
                potential[sample_index] += shell_scale / distance
                field_scale = shell_scale / (distance_sq * distance)
                field[sample_index, 0] += dx * field_scale
                field[sample_index, 1] += dy * field_scale
                field[sample_index, 2] += dz * field_scale
```

Implement `_evaluate_contributions_kernel()` with output shape `(sample_count, source_count, 4)`:
column `0` is potential and columns `1:4` are field components. Add wrappers:

```python
def evaluate_totals_cpu(packed: PackedScene, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return _evaluate_totals_kernel(
        points,
        packed.element_positions,
        packed.element_charges,
        packed.plane_positions,
        packed.plane_normals,
        packed.plane_densities,
        packed.shell_positions,
        packed.shell_radii,
        packed.shell_charges,
    )


def evaluate_contributions_cpu(packed: PackedScene, points: np.ndarray) -> np.ndarray:
    return _evaluate_contributions_kernel(
        points,
        len(packed.source_ids),
        packed.element_positions,
        packed.element_charges,
        packed.element_source_indexes,
        packed.plane_positions,
        packed.plane_normals,
        packed.plane_densities,
        packed.plane_source_indexes,
        packed.shell_positions,
        packed.shell_radii,
        packed.shell_charges,
        packed.shell_source_indexes,
    )
```

- [ ] **Step 5: Preserve scalar API and add a CPU dispatcher**

In `solver.py`, rename the current body implementation to:

```python
def evaluate_scene_scalar(
    scene: Scene,
    sample_points: Iterable[Position | dict[str, float] | tuple[float, float, float]],
    *,
    quality: SolverQuality = "preview",
    request_id: str | None = None,
) -> FieldEvaluationResponse:
```

Keep the existing scalar contribution functions unchanged. Add a new `evaluate_scene()` facade that
delegates to:

```python
return DEFAULT_COMPUTE_SERVICE.evaluate_scene(
    scene,
    sample_points,
    quality=quality,
    request_id=request_id,
    backend=backend,
)
```

Create `dispatcher.py` with `ComputeService`, a `PackedSceneCache`, `evaluate_totals()`, and
`evaluate_scene()`. For `with-contributions`, assemble existing `FieldSampleResult` and
`SourceContribution` DTOs from CPU arrays while preserving scalar warning and metadata templates.

- [ ] **Step 6: Verify parity and existing APIs**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_cpu_backend.py tests/test_solver.py tests/test_solver_api.py tests/test_app.py -q
```

Expected: PASS. Existing APIs retain their previous fields and gain optional execution metadata.

- [ ] **Step 7: Run lint, create the HTML report, and commit**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync ruff check --no-cache src tests scripts
git add src/em_workbench/physics/compute src/em_workbench/physics/solver.py tests/conftest.py tests/test_cpu_backend.py tests/test_solver.py reports/2026-06-02-task-24-cpu-jit-field-kernels.html
git commit -m "Add multi-core CPU field kernels"
```

## Task 4: Add Optional CUDA Field Kernels, Device Cache, And Auto Dispatch

**Files:**
- Create: `src/em_workbench/physics/compute/cuda_backend.py`
- Modify: `src/em_workbench/physics/compute/dispatcher.py`
- Create: `tests/test_cuda_backend.py`
- Modify: `tests/test_compute_runtime.py`
- Create: `reports/2026-06-02-task-25-cuda-field-kernels.html`

- [ ] **Step 1: Add hardware-independent failing fallback tests**

Create `tests/test_cuda_backend.py`:

```python
import pytest

from em_workbench.physics.compute.contracts import CudaRuntimeStatus
from em_workbench.physics.compute.dispatcher import ComputeService


@pytest.fixture
def unavailable_cuda_probe():
    def probe() -> CudaRuntimeStatus:
        return CudaRuntimeStatus(
            installed=True,
            available=False,
            fallback_reason="CUDA runtime unavailable.",
        )

    return probe


def test_auto_dispatch_falls_back_to_cpu_when_cuda_probe_is_unavailable(
    representative_scene,
    sample_points,
    unavailable_cuda_probe,
) -> None:
    service = ComputeService(cuda_probe=unavailable_cuda_probe)

    result = service.evaluate_totals(representative_scene, sample_points, quality="preview", backend="auto")

    assert result.execution.backend_effective == "cpu-jit"
    assert result.execution.fallback_reason == "CUDA runtime unavailable."
```

Add a CUDA hardware test guarded by:

```python
CUDA_REQUIRED = pytest.mark.skipif(not probe_runtime().cuda.available, reason="CUDA unavailable")
```

The hardware test requests `backend="cuda"` for 400 samples and compares results with CPU JIT using
`rel=2e-5` for preview and `rel=1e-10` for refined.

- [ ] **Step 2: Run CPU-only fallback tests and verify failure**

Run:

```powershell
.\.tools\uv\uv.exe sync --locked
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_cuda_backend.py -q
```

Expected: FAIL because CUDA backend dispatch is not implemented.

- [ ] **Step 3: Implement lazy CUDA module**

Create `cuda_backend.py`. Import CUDA only inside `load_cuda()`:

```python
def load_cuda():
    try:
        from numba import cuda
    except Exception as error:
        raise CudaUnavailable(f"CUDA package unavailable: {error}") from error
    if not cuda.is_available():
        raise CudaUnavailable("CUDA runtime unavailable.")
    return cuda
```

Define a CUDA field kernel with one thread per sample:

```python
def build_totals_kernel(cuda):
    @cuda.jit
    def kernel(points, element_positions, element_charges, potential, field):
        sample_index = cuda.grid(1)
        if sample_index >= points.shape[0]:
            return
        x = points[sample_index, 0]
        y = points[sample_index, 1]
        z = points[sample_index, 2]
        for element_index in range(element_positions.shape[0]):
            dx = x - element_positions[element_index, 0]
            dy = y - element_positions[element_index, 1]
            dz = z - element_positions[element_index, 2]
            distance_sq = dx * dx + dy * dy + dz * dz
            if distance_sq > MIN_SOURCE_DISTANCE_SQ:
                distance = math.sqrt(distance_sq)
                scale = COULOMB_CONSTANT * element_charges[element_index]
                potential[sample_index] += scale / distance
                field_scale = scale / (distance_sq * distance)
                field[sample_index, 0] += dx * field_scale
                field[sample_index, 1] += dy * field_scale
                field[sample_index, 2] += dz * field_scale
    return kernel
```

Add the plane and shell loops from Task 3 inside the CUDA kernel using the same formulas and array
order. Implement `DeviceSceneCache(limit=8)`, copied immutable device arrays, chunked launches,
synchronization, timing, and host result copies. Use `threads_per_block = 128` and:

```python
blocks_per_grid = (sample_count + threads_per_block - 1) // threads_per_block
kernel[blocks_per_grid, threads_per_block](
    points_device,
    scene.element_positions,
    scene.element_charges,
    scene.plane_positions,
    scene.plane_normals,
    scene.plane_densities,
    scene.shell_positions,
    scene.shell_radii,
    scene.shell_charges,
    potential_device,
    field_device,
)
cuda.synchronize()
```

- [ ] **Step 4: Add workload-aware dispatch**

In `dispatcher.py`, add constants:

```python
CUDA_BATCH_SAMPLE_THRESHOLD = 128
CUDA_FIELD_LINE_THRESHOLD = 24
```

Selection rules:

```python
if backend == "scalar":
    return "scalar"
if backend == "cpu":
    return "cpu-jit"
if backend == "cuda":
    return "cuda"
if operation == "trajectory":
    return "cpu-jit"
if operation == "field-lines" or sample_count >= CUDA_BATCH_SAMPLE_THRESHOLD:
    return "cuda" if self.cuda_probe().available else "cpu-jit"
return "cpu-jit"
```

Catch `CudaUnavailable`, allocation errors, launch errors, and synchronization errors. Retry once
through CPU JIT and record the exception text as `fallback_reason`.

- [ ] **Step 5: Verify CPU fallback and RTX 5060 Ti hardware execution**

Run:

```powershell
.\.tools\uv\uv.exe sync --locked --extra cuda
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_cuda_backend.py tests/test_cpu_backend.py -q
.\.tools\uv\uv.exe run --locked --no-sync python -c "from em_workbench.physics.compute.runtime import probe_runtime; print(probe_runtime().cuda.model_dump_json(indent=2))"
```

Expected: fallback tests pass; CUDA hardware tests run rather than skip; device is RTX 5060 Ti with
compute capability `12.0`.

- [ ] **Step 6: Run lint, create the HTML report, and commit**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync ruff check --no-cache src tests scripts
git add src/em_workbench/physics/compute tests/test_cuda_backend.py tests/test_compute_runtime.py reports/2026-06-02-task-25-cuda-field-kernels.html
git commit -m "Add optional CUDA field kernels"
```

## Task 5: Move Single Test-Charge RK4 Into A Compiled CPU Kernel

**Files:**
- Modify: `src/em_workbench/physics/compute/cpu_backend.py`
- Modify: `src/em_workbench/physics/compute/dispatcher.py`
- Modify: `src/em_workbench/physics/dynamics.py`
- Create: `tests/test_dynamics.py`
- Modify: `tests/test_app.py`
- Create: `reports/2026-06-02-task-26-cpu-jit-trajectory.html`

- [ ] **Step 1: Add failing trajectory parity and dispatch tests**

Create `tests/test_dynamics.py` with:

```python
import pytest

from em_workbench.physics.compute.contracts import CudaRuntimeStatus
from em_workbench.physics.compute.dispatcher import ComputeService
from em_workbench.physics.dynamics import simulate_trajectory, simulate_trajectory_scalar


def test_compiled_trajectory_matches_scalar_rk4_for_dipole(representative_scene, particle) -> None:
    scalar = simulate_trajectory_scalar(representative_scene, particle, dt_s=0.001, steps=80, quality="preview")
    compiled = simulate_trajectory(representative_scene, particle, dt_s=0.001, steps=80, quality="preview")

    assert compiled.execution.backend_effective == "cpu-jit"
    assert compiled.samples[-1].position.x == pytest.approx(scalar.samples[-1].position.x, rel=2e-5)
    assert compiled.samples[-1].position.y == pytest.approx(scalar.samples[-1].position.y, rel=2e-5)


def test_auto_trajectory_dispatch_uses_cpu_even_when_cuda_is_available(representative_scene, particle) -> None:
    service = ComputeService(
        cuda_probe=lambda: CudaRuntimeStatus(installed=True, available=True, device_name="test-gpu")
    )

    result = service.simulate_trajectory(
        representative_scene,
        particle,
        dt_s=0.001,
        steps=8,
        quality="preview",
        backend="auto",
    )

    assert result.execution.backend_effective == "cpu-jit"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_dynamics.py -q
```

Expected: FAIL because scalar and compiled trajectory entry points are not separated.

- [ ] **Step 3: Add compiled RK4 kernel**

Add a non-parallel `@njit(cache=True)` CPU kernel to `cpu_backend.py`:

```python
@njit(cache=True)
def _trajectory_kernel(
    initial_position,
    initial_velocity,
    charge_over_mass,
    dt_s,
    steps,
    record_every,
    element_positions,
    element_charges,
    plane_positions,
    plane_normals,
    plane_densities,
    shell_positions,
    shell_radii,
    shell_charges,
):
    record_count = steps // record_every + 2
    times = np.empty(record_count, dtype=initial_position.dtype)
    positions = np.empty((record_count, 3), dtype=initial_position.dtype)
    velocities = np.empty((record_count, 3), dtype=initial_position.dtype)
    fields = np.empty((record_count, 3), dtype=initial_position.dtype)
```

Extract the Task 3 single-sample math into `_field_at_single()` and call it from both batch and
trajectory kernels. Implement the RK4 loop with:

```python
    def acceleration(position):
        _potential, field = _field_at_single(
            position,
            element_positions,
            element_charges,
            plane_positions,
            plane_normals,
            plane_densities,
            shell_positions,
            shell_radii,
            shell_charges,
        )
        return field * charge_over_mass

    def record(index, time_s, position, velocity):
        _potential, field = _field_at_single(
            position,
            element_positions,
            element_charges,
            plane_positions,
            plane_normals,
            plane_densities,
            shell_positions,
            shell_radii,
            shell_charges,
        )
        times[index] = time_s
        positions[index] = position
        velocities[index] = velocity
        fields[index] = field

    position = initial_position.copy()
    velocity = initial_velocity.copy()
    time_s = 0.0
    record_index = 0
    record(record_index, time_s, position, velocity)
    record_index += 1
    for step in range(1, steps + 1):
        k1x = velocity
        k1v = acceleration(position)
        k2x = velocity + k1v * (dt_s / 2.0)
        k2v = acceleration(position + k1x * (dt_s / 2.0))
        k3x = velocity + k2v * (dt_s / 2.0)
        k3v = acceleration(position + k2x * (dt_s / 2.0))
        k4x = velocity + k3v * dt_s
        k4v = acceleration(position + k3x * dt_s)
        position = position + (k1x + 2.0 * k2x + 2.0 * k3x + k4x) * (dt_s / 6.0)
        velocity = velocity + (k1v + 2.0 * k2v + 2.0 * k3v + k4v) * (dt_s / 6.0)
        time_s += dt_s
        if step % record_every == 0 or step == steps:
            record(record_index, time_s, position, velocity)
            record_index += 1
    return times[:record_index], positions[:record_index], velocities[:record_index], fields[:record_index]
```

- [ ] **Step 4: Delegate dynamics through dispatcher**

Rename the existing Python implementation to `simulate_trajectory_scalar()`. Keep it as the oracle.
Make `simulate_trajectory()` delegate to `DEFAULT_COMPUTE_SERVICE.simulate_trajectory()`.

Add optional `execution: ExecutionMetadata | None = None` to `TrajectoryResponse`.

- [ ] **Step 5: Verify focused trajectory, API, and desktop bridge tests**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_dynamics.py tests/test_app.py::test_trajectory_endpoint_simulates_test_charge_motion tests/test_desktop_bridge.py::test_desktop_bridge_simulates_trajectory_without_http_server -q
```

Expected: PASS.

- [ ] **Step 6: Run lint, create the HTML report, and commit**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync ruff check --no-cache src tests scripts
git add src/em_workbench/physics/compute src/em_workbench/physics/dynamics.py tests/test_dynamics.py tests/test_app.py reports/2026-06-02-task-26-cpu-jit-trajectory.html
git commit -m "Compile test charge trajectories on CPU"
```

## Task 6: Add Backend 2D Field-Line Kernels And HTTP API

**Files:**
- Create: `src/em_workbench/physics/compute/field_lines.py`
- Modify: `src/em_workbench/physics/compute/cpu_backend.py`
- Modify: `src/em_workbench/physics/compute/cuda_backend.py`
- Modify: `src/em_workbench/physics/compute/dispatcher.py`
- Modify: `src/em_workbench/app.py`
- Create: `tests/test_field_lines.py`
- Modify: `tests/test_app.py`
- Create: `reports/2026-06-02-task-27-backend-field-lines.html`

- [ ] **Step 1: Add failing field-line DTO, parity, and API tests**

Create `tests/test_field_lines.py` with:

```python
from fastapi.testclient import TestClient

from em_workbench.app import app
from em_workbench.physics.compute.field_lines import ViewportBounds, trace_field_lines


client = TestClient(app)
BOUNDS = ViewportBounds(min_x=-0.20, max_x=0.20, min_y=-0.20, max_y=0.20)


def test_cpu_field_lines_trace_dipole_with_render_ready_metadata(representative_scene) -> None:
    response = trace_field_lines(representative_scene, BOUNDS, quality="preview", backend="cpu")

    assert response.execution.backend_effective == "cpu-jit"
    assert 0 < len(response.lines) <= response.display_max_count
    assert response.candidate_line_count >= len(response.lines)
    assert all(len(line.points) >= 2 for line in response.lines)
    assert all(line.topology in {"source-to-source", "source-to-infinity", "infinity-to-source"} for line in response.lines)


def test_field_line_api_returns_latest_render_contract(representative_scene) -> None:
    response = client.post(
        "/api/field/lines",
        json={
            "request_id": "field-lines-1",
            "scene": representative_scene.model_dump(mode="json"),
            "bounds": BOUNDS.model_dump(mode="json"),
            "quality": "preview",
            "backend": "cpu",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "field-lines-1"
    assert body["execution"]["backend_effective"] in {"cpu-jit", "cuda"}
    assert body["lines"]
```

Add a CUDA parity test guarded by CUDA availability. Compare candidate count, accepted count range,
topology set, direction dot minimum, and endpoints within one trace step instead of requiring
bit-identical curve points.

- [ ] **Step 2: Run tests and verify missing implementation**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_field_lines.py -q
```

Expected: FAIL because `field_lines.py` and `/api/field/lines` do not exist.

- [ ] **Step 3: Add typed field-line contracts**

Create `field_lines.py` with strict Pydantic DTOs:

```python
class ViewportBounds(ComputeModel):
    min_x: float
    max_x: float
    min_y: float
    max_y: float


class FieldLinePoint(ComputeModel):
    x: float
    y: float


class FieldLineResult(ComputeModel):
    seed_index: int
    source_id: str
    terminal_source_id: str | None = None
    topology: Literal["source-to-source", "source-to-infinity", "infinity-to-source"]
    stop_reason: str
    points: list[FieldLinePoint]
    arrow_anchor: FieldLinePoint
    arrow_direction: FieldLinePoint
    min_direction_dot: float


class FieldLineResponse(ComputeModel):
    request_id: str | None = None
    lines: list[FieldLineResult]
    candidate_line_count: int
    rejected_line_count: int
    conflict_rejected_line_count: int
    display_max_count: int
    execution: ExecutionMetadata
```

- [ ] **Step 4: Port trace semantics into CPU and CUDA kernels**

Port the current browser constants and behavior:

- point-source seed allocation based on total absolute charge;
- minimum and maximum rays per source;
- adaptive RK4 with full-step versus two-half-step error;
- singularity stop radius;
- viewport padding bounds;
- maximum step count;
- source endpoint classification;
- direction quality checks;
- display line cap and source-pair de-duplication.

Use fixed arrays:

```python
points = np.empty((candidate_count, max_steps + 1, 2), dtype=packed.dtype)
point_counts = np.zeros(candidate_count, dtype=np.int32)
stop_codes = np.zeros(candidate_count, dtype=np.int32)
terminal_source_indexes = np.full(candidate_count, -1, dtype=np.int32)
```

CPU uses `prange(candidate_count)`. CUDA uses one thread per candidate ray and the same stop-code
contract. Convert stop codes and accepted arrays into `FieldLineResponse` in `field_lines.py`.

- [ ] **Step 5: Add HTTP request and route**

Add to `app.py`:

```python
class FieldLineEvaluateRequest(BaseModel):
    request_id: str = Field(min_length=1)
    scene: Scene
    bounds: ViewportBounds
    quality: SolverQuality = "preview"
    density: float = Field(default=1.0, gt=0.0, le=4.0)
    display_max_count: int = Field(default=120, ge=1, le=500)
    backend: BackendPolicy = "auto"


@app.post("/api/field/lines", response_model=FieldLineResponse)
def evaluate_field_lines(request: FieldLineEvaluateRequest) -> FieldLineResponse:
    return trace_field_lines(
        request.scene,
        request.bounds,
        request_id=request.request_id,
        quality=request.quality,
        density=request.density,
        display_max_count=request.display_max_count,
        backend=request.backend,
    )
```

- [ ] **Step 6: Verify CPU, CUDA, and API field lines**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_field_lines.py tests/test_app.py -q
```

Expected: CPU and API tests pass; CUDA parity test runs on RTX 5060 Ti.

- [ ] **Step 7: Run lint, create the HTML report, and commit**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync ruff check --no-cache src tests scripts
git add src/em_workbench/physics/compute src/em_workbench/app.py tests/test_field_lines.py tests/test_app.py reports/2026-06-02-task-27-backend-field-lines.html
git commit -m "Trace 2D field lines in compute backend"
```

## Task 7: Replace Browser CPU Field-Line Tracing With Async Backend Requests

**Files:**
- Modify: `web/api-client.js`
- Modify: `web/app.js`
- Modify: `tests/test_browser_smoke.py`
- Create: `reports/2026-06-02-task-28-browser-backend-field-lines.html`

- [ ] **Step 1: Add failing Playwright tests for backend requests and stale responses**

Append tests that intercept `/api/field/lines`, toggle field lines, and assert:

```python
def test_browser_field_lines_are_loaded_from_backend(page: Page) -> None:
    requests: list[str] = []
    page.on("request", lambda request: requests.append(request.url))

    _add_point_charge(page)
    page.locator("#toggle-field-lines").click()
    expect(page.get_by_test_id("field-line-layer")).to_have_attribute("data-compute-source", "backend")

    assert any(url.endswith("/api/field/lines") for url in requests)


def test_browser_discards_stale_field_line_response_after_zoom(page: Page) -> None:
    expect(page.get_by_test_id("field-line-layer")).to_have_attribute("data-request-current", "true")
```

Use Playwright route delays to return the first field-line response after the second one and assert
that the rendered request ID is the second request ID.

- [ ] **Step 2: Run focused browser tests and verify failure**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_browser_smoke.py::test_browser_field_lines_are_loaded_from_backend tests/test_browser_smoke.py::test_browser_discards_stale_field_line_response_after_zoom -q
```

Expected: FAIL because field lines still trace synchronously in JavaScript.

- [ ] **Step 3: Add transport**

Add to `web/api-client.js`:

```javascript
export async function evaluateFieldLines(request) {
  const bridgeResult = await callDesktopBridge("evaluateFieldLines", request);
  if (bridgeResult !== null) {
    return bridgeResult;
  }

  const response = await fetch("/api/field/lines", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseJsonResponse(response, "Field-line evaluation failed");
}
```

- [ ] **Step 4: Replace synchronous tracing with request scheduling**

In `web/app.js`:

- import `evaluateFieldLines`;
- store `state.fieldLineResult`, `state.fieldLineRequestId`, and `fieldLineRequestSerial`;
- build request bounds from `compute2dFieldLineBounds(scale)`;
- debounce edits, zoom, and pan;
- apply a response only when its request ID equals the latest ID;
- render SVG paths and arrows from backend points;
- keep the existing JavaScript tracer behind
  `const ENABLE_LEGACY_FIELD_LINE_DEBUG_COMPARISON = false;`.

Render metadata:

```html
data-compute-source="backend"
data-rendered-request-id="${traceResult.request_id}"
data-request-current="${traceResult.request_id === state.fieldLineRequestId ? "true" : "false"}"
data-effective-backend="${traceResult.execution.backend_effective}"
data-precision="${traceResult.execution.precision}"
```

- [ ] **Step 5: Verify existing visual behavior and async behavior**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_browser_smoke.py -q
```

Expected: all Playwright tests pass, including arrow geometry, line caps, pair de-duplication, zoom,
pan, and stale response suppression.

- [ ] **Step 6: Run lint, create the HTML report, and commit**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync ruff check --no-cache src tests scripts
git add web/api-client.js web/app.js tests/test_browser_smoke.py reports/2026-06-02-task-28-browser-backend-field-lines.html
git commit -m "Load 2D field lines from compute backend"
```

## Task 8: Add Warm-Up, Compute Status UI, And Async Desktop Compute Queue

**Files:**
- Create: `src/em_workbench/physics/compute/warmup.py`
- Modify: `src/em_workbench/physics/compute/dispatcher.py`
- Modify: `src/em_workbench/app.py`
- Modify: `src/em_workbench/desktop_bridge.py`
- Modify: `src/em_workbench/desktop.py`
- Modify: `web/api-client.js`
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/styles.css`
- Modify: `tests/test_compute_runtime.py`
- Modify: `tests/test_desktop_bridge.py`
- Modify: `tests/test_browser_smoke.py`
- Create: `reports/2026-06-02-task-29-warmup-desktop-queue-status-ui.html`

- [ ] **Step 1: Add failing warm-up and async queue tests**

Test state transitions:

```python
def test_warmup_moves_from_idle_to_ready() -> None:
    warmup = ComputeWarmup(run_cpu=lambda: None, run_cuda=lambda: None)

    warmup.start()
    warmup.join(timeout=5)

    assert warmup.status().state == "ready"
```

Test desktop queue submission:

```python
def test_desktop_queue_returns_ticket_then_result() -> None:
    queue = DesktopComputeQueue()

    ticket = queue.submit("status", "")
    result = queue.wait(ticket, timeout_s=5)

    assert json.loads(result)["cpu"]["logical_processors"] >= 1
```

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_compute_runtime.py tests/test_desktop_bridge.py -q
```

Expected: FAIL because warm-up and queue classes do not exist.

- [ ] **Step 3: Implement warm-up state machine**

Create `warmup.py` with a daemon thread, a lock, and these public methods:

```python
from __future__ import annotations

from collections.abc import Callable
from threading import RLock, Thread

from em_workbench.physics.compute.contracts import WarmupStatus


class ComputeWarmup:
    def __init__(self, run_cpu: Callable[[], None], run_cuda: Callable[[], None]) -> None:
        self._run_cpu = run_cpu
        self._run_cuda = run_cuda
        self._status = WarmupStatus()
        self._thread: Thread | None = None
        self._lock = RLock()

    def start(self) -> None:
        with self._lock:
            if self._status.state != "idle":
                return
            self._status = WarmupStatus(state="warming")
            self._thread = Thread(target=self._run, name="em-compute-warmup", daemon=True)
            self._thread.start()

    def join(self, timeout: float | None = None) -> None:
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def status(self) -> WarmupStatus:
        with self._lock:
            return self._status.model_copy()

    def _run(self) -> None:
        try:
            self._run_cpu()
            self._run_cuda()
        except Exception as error:
            with self._lock:
                self._status = WarmupStatus(state="failed", failure_reason=str(error))
            return
        with self._lock:
            self._status = WarmupStatus(state="ready")
```

Warm CPU preview field and trajectory kernels with a tiny packed scene. Warm CUDA preview field and
field-line kernels only when CUDA probe reports available.

- [ ] **Step 4: Implement asynchronous desktop compute queue**

Add `DesktopComputeQueue` in `desktop_bridge.py`:

```python
class DesktopComputeQueue:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="em-compute")
        self._futures: dict[str, Future[str]] = {}
        self._lock = RLock()

    def submit(self, method: str, payload: str) -> str:
        ticket = uuid4().hex
        future = self._executor.submit(self._invoke, method, payload)
        with self._lock:
            self._futures[ticket] = future
        return ticket

    def poll(self, ticket: str) -> str:
        with self._lock:
            future = self._futures.get(ticket)
        if future is None:
            return json.dumps({"state": "missing"})
        if not future.done():
            return json.dumps({"state": "pending"})
        with self._lock:
            self._futures.pop(ticket, None)
        try:
            return json.dumps({"state": "ready", "result": future.result()})
        except Exception as error:
            return json.dumps({"state": "failed", "error": str(error)})
```

Implement `_invoke()` with exact methods: `status`, `evaluateField`, `evaluateTrajectory`, and
`evaluateFieldLines`. Add Qt slots `submitCompute` and `pollCompute`.

- [ ] **Step 5: Add desktop polling transport and status UI**

In `web/api-client.js`, poll desktop tickets with `window.setTimeout(resolve, 16)` until state is
`ready` or `failed`. Add `getComputeStatus()`.

In `web/index.html`, add a compact status block with test IDs:

```html
<section class="status-block compute-block">
  <h3>计算后端</h3>
  <p data-testid="compute-backend">正在检测</p>
  <p data-testid="compute-warmup">预热状态：idle</p>
</section>
```

In `web/app.js`, load status during initialization and update the block after field, trajectory, and
field-line responses.

- [ ] **Step 6: Verify warm-up, HTTP, desktop, and browser status**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_compute_runtime.py tests/test_desktop_bridge.py tests/test_browser_smoke.py -q
.\.tools\uv\uv.exe run --locked --no-sync --extra desktop em-workbench-desktop --check
```

Expected: PASS and `desktop runtime ok`.

- [ ] **Step 7: Run lint, create the HTML report, and commit**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync ruff check --no-cache src tests scripts
git add src/em_workbench web tests reports/2026-06-02-task-29-warmup-desktop-queue-status-ui.html
git commit -m "Warm compute kernels and report backend status"
```

## Task 9: Add Reproducible CPU, CUDA, And Auto Benchmarks

**Files:**
- Create: `scripts/benchmark_compute.py`
- Create: `tests/test_benchmark_compute.py`
- Create: `reports/2026-06-02-task-30-compute-benchmark.html`

- [ ] **Step 1: Add failing benchmark smoke test**

Create `tests/test_benchmark_compute.py`:

```python
from scripts.benchmark_compute import run_benchmarks


def test_benchmark_script_emits_machine_and_workload_records() -> None:
    report = run_benchmarks(backends=["scalar"], warm_runs=1, include_refined=False)

    assert report["machine"]["cpu"]["logical_processors"] >= 1
    names = {record["name"] for record in report["records"]}
    assert "field-preview-25" in names
    assert "field-preview-400" in names
    assert "trajectory-preview-100" in names
    assert "trajectory-preview-400" in names
```

- [ ] **Step 2: Run test and verify import failure**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_benchmark_compute.py -q
```

Expected: FAIL because the script does not exist.

- [ ] **Step 3: Implement benchmark script**

Implement `run_benchmarks(backends, warm_runs, include_refined)` and CLI arguments:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync python scripts/benchmark_compute.py --backend scalar --backend cpu --backend cuda --backend auto --warm-runs 5 --output reports/2026-06-02-compute-benchmark.json
```

Emit JSON with:

```json
{
  "machine": {},
  "records": [
    {
      "name": "field-preview-400",
      "backend_requested": "auto",
      "backend_effective": "cuda",
      "cold_ms": 0.0,
      "warm_ms": [],
      "warm_median_ms": 0.0,
      "target_ms": 100.0,
      "target_met": true
    }
  ]
}
```

Measure 25 and 400 field samples, 100 and 400 trajectory steps, and representative dipole field
lines. Compare non-scalar results with scalar output and include a correctness summary.

- [ ] **Step 4: Run CPU and CUDA benchmarks**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider tests/test_benchmark_compute.py -q
.\.tools\uv\uv.exe run --locked --no-sync python scripts/benchmark_compute.py --backend scalar --backend cpu --backend cuda --backend auto --warm-runs 5 --output reports/2026-06-02-compute-benchmark.json
```

Expected: benchmark JSON records actual CPU and RTX 5060 Ti CUDA execution. Warm `auto` preview
targets are:

```text
field-preview-400       <= 100 ms
trajectory-preview-400  <= 300 ms
field-lines-preview     <= 250 ms
```

- [ ] **Step 5: Run lint, create the HTML report, and commit**

Run:

```powershell
.\.tools\uv\uv.exe run --locked --no-sync ruff check --no-cache src tests scripts
git add scripts/benchmark_compute.py tests/test_benchmark_compute.py reports/2026-06-02-compute-benchmark.json reports/2026-06-02-task-30-compute-benchmark.html
git commit -m "Benchmark CPU and CUDA compute backends"
```

## Task 10: Run Full Verification And Rebuild Windows Desktop Packages

**Files:**
- Modify: `README.md`
- Modify: `README-ZH.md`
- Modify: `packaging/README.md`
- Modify: `requirements.txt`
- Create: `reports/2026-06-02-task-31-cpu-cuda-release-verification.html`

- [ ] **Step 1: Export locked compatibility requirements**

Run:

```powershell
.\.tools\uv\uv.exe export --locked --all-groups --no-emit-project --output-file requirements.txt
```

- [ ] **Step 2: Run complete CPU-only verification**

Run:

```powershell
.\.tools\uv\uv.exe sync --locked --extra desktop
.\.tools\uv\uv.exe run --locked --no-sync ruff check --no-cache src tests scripts
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider
.\.tools\uv\uv.exe run --locked --no-sync --extra desktop em-workbench-desktop --check
```

Expected: lint, full pytest, and desktop check pass without CUDA extra.

- [ ] **Step 3: Run complete CUDA verification**

Run:

```powershell
.\.tools\uv\uv.exe sync --locked --extra desktop --extra cuda
.\.tools\uv\uv.exe run --locked --no-sync python -m pytest -p no:cacheprovider
.\.tools\uv\uv.exe run --locked --no-sync python scripts/benchmark_compute.py --backend cpu --backend cuda --backend auto --warm-runs 5 --output reports/2026-06-02-compute-benchmark-final.json
```

Expected: hardware CUDA tests run on RTX 5060 Ti and warm preview targets pass.

- [ ] **Step 4: Rebuild portable desktop package and smoke-check it**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_desktop.ps1
$p = Start-Process -FilePath .\dist\EMWorkbench\EMWorkbench.exe -ArgumentList '--check' -Wait -PassThru
$p.ExitCode
```

Expected: package builds and exit code is `0`.

- [ ] **Step 5: Document CPU and CUDA usage**

Update README files with:

```powershell
.\.tools\uv\uv.exe sync --extra desktop
.\.tools\uv\uv.exe sync --extra desktop --extra cuda
```

Explain that CUDA is optional, auto-detected, and visible in the compute backend status block.

- [ ] **Step 6: Create release verification report and commit**

Run:

```powershell
git add README.md README-ZH.md packaging/README.md requirements.txt reports/2026-06-02-compute-benchmark-final.json reports/2026-06-02-task-31-cpu-cuda-release-verification.html
git commit -m "Verify CPU and CUDA desktop performance release"
git status --short --branch
```

Expected: only intentionally ignored or explicitly preserved local runtime files remain untracked.

## Final Review Checklist

- [ ] CPU-only sync works without CUDA packages.
- [ ] Optional CUDA sync detects RTX 5060 Ti compute capability `12.0`.
- [ ] Scalar, CPU JIT, and CUDA field outputs match within mode-specific tolerances.
- [ ] Single test-charge trajectory defaults to compiled CPU and meets target latency.
- [ ] 2D field lines come from the Python backend and preserve existing browser behavior.
- [ ] Stale preview and field-line responses cannot overwrite newer results.
- [ ] UI reports effective backend, precision, warm-up, cache, and fallback state.
- [ ] Normal pytest, Ruff, Playwright, desktop check, package smoke, and benchmark commands pass.
- [ ] Every completed implementation task has an accessible standalone HTML report.
