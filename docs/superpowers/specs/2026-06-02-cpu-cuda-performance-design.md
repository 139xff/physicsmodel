# EM Workbench CPU/CUDA Performance Design

## 1. Purpose

EM Workbench currently computes electrostatic fields with nested Python loops and traces 2D field
lines in browser JavaScript. The implementation is correct for the existing release scope, but it
does not provide interactive latency once scenes contain continuous charge sources, refined
discretization, or test-charge trajectories.

This design introduces a shared high-performance Python compute layer that uses:

- compiled multi-core CPU kernels by default;
- optional NVIDIA CUDA kernels when a compatible CUDA runtime is installed;
- automatic workload-aware dispatch;
- the existing scalar solver as a correctness reference and final fallback.

The Python solver remains authoritative for `V` and `E`. The browser remains a static HTML/CSS/ES
module client and does not gain a second WebGPU physics implementation.

## 2. Confirmed Product Decisions

The following choices were confirmed on 2026-06-02:

| Decision | Selected approach |
| --- | --- |
| Scope | Full performance redesign: field evaluation, test-charge motion, and 2D field lines |
| CUDA deployment | Optional CUDA dependency with automatic detection and CPU fallback |
| Precision | `preview` uses `float32`; `refined` uses `float64` |
| 2D field lines | Python high-performance backend, not browser WebGPU |
| Acceptance focus | Interactive preview latency |

## 3. Constraints

- Use only the project-local `.\.tools\uv\uv.exe` workflow.
- Keep scene contracts typed and serializable through Pydantic.
- Keep electrostatic calculations independent of FastAPI and the UI.
- Keep the scalar implementation available as a reference oracle and last-resort fallback.
- Do not require CUDA, an NVIDIA GPU, or `nvcc` for the base installation.
- Do not silently lower `refined` precision to satisfy latency goals.
- Preserve existing warnings, source contribution metadata, and singularity handling.
- Preserve current 2D field-line visual quality: endpoint behavior, direction arrows, conflict
  filtering, and curve smoothing remain user-visible requirements.

## 4. Baseline

The baseline was measured on 2026-06-02 with:

| Component | Value |
| --- | --- |
| CPU | Intel Core i5-14490F, 10 cores, 16 logical processors |
| GPU | NVIDIA GeForce RTX 5060 Ti, 16311 MiB |
| NVIDIA driver | 596.49 |
| CUDA compute capability | 12.0 |
| `nvcc` | Not installed |
| Python | 3.12 through project-local uv |

The benchmark scene contained two point charges, one line segment, one ring, and one disk.

| Workload | Existing median latency |
| --- | ---: |
| `preview`, 25 field samples | 106.279 ms |
| `preview`, 400 field samples | 1777.212 ms |
| `refined`, 25 field samples | 790.863 ms |
| `refined`, 400 field samples | 12223.973 ms |
| `preview`, test-charge trajectory, 100 steps | 2123.262 ms |
| `preview`, test-charge trajectory, 400 steps | 8390.564 ms |

The current implementation is dominated by repeated Python object creation and nested loops over
samples, sources, and numerical integration elements. Test-charge RK4 amplifies the cost by calling
the full Pydantic response-producing field solver multiple times per integration step.

## 5. Goals

### 5.1 Functional goals

- Use one compiled scene representation for field samples, trajectories, and 2D field lines.
- Select the fastest available execution backend without changing API correctness.
- Expose the effective backend, device, precision, warm-up state, cache state, and timing metadata.
- Keep the application fully usable on CPU-only machines.
- Warm common kernels in the background so first interaction does not absorb all JIT cost.

### 5.2 Preview performance goals

The following are warm-start targets on the baseline RTX 5060 Ti machine:

| Workload | Target |
| --- | ---: |
| 400 field samples | <= 100 ms |
| Test-charge trajectory, 400 steps | <= 300 ms |
| 2D field-line refresh | <= 250 ms |

Cold-start timings must be recorded separately. `refined` mode must report its latency but is not
required to meet the preview thresholds because consumer GPUs have weaker `float64` throughput.

### 5.3 Non-goals

- Browser WebGPU compute shaders.
- Mandatory CUDA installation.
- Multi-GPU scheduling.
- Distributed compute.
- Research-grade arbitrary precision.
- Replacing Three.js rendering.
- Batched many-particle simulation in the first delivery.

## 6. Dependency Strategy

The implementation will use:

- `numba` as a normal project dependency for compiled CPU kernels;
- `numba-cuda[cu12]` as an optional `cuda` extra;
- existing `numpy` arrays as the shared packed-scene format.

The base workflow remains:

```powershell
.\.tools\uv\uv.exe sync
```

CUDA-enabled local development uses:

```powershell
.\.tools\uv\uv.exe sync --extra cuda
```

Desktop development with CUDA uses:

```powershell
.\.tools\uv\uv.exe sync --extra desktop --extra cuda
```

The implementation task must resolve and lock compatible versions through project-local uv. It
must validate installation on the baseline machine without assuming a separate `nvcc` installation.

## 7. Architecture

### 7.1 Public facade and scalar reference

`em_workbench.physics.solver.evaluate_scene()` remains the public field-evaluation facade. Existing
callers continue to receive `FieldEvaluationResponse`.

The existing scalar implementation moves behind an explicit scalar backend. It remains executable
for:

- correctness comparison;
- unsupported edge-case fallback;
- environments where compiled backends cannot initialize;
- debugging backend disagreements.

The facade delegates to a compute service that compiles scenes, chooses a backend, executes kernels,
and assembles the existing DTOs.

### 7.2 Packed scene compiler

A scene compiler converts Pydantic source objects into contiguous NumPy arrays. The packed
representation is immutable and keyed by a canonical scene hash, quality mode, and numeric dtype.

The compiler separates two categories:

| Category | Source kinds | Representation |
| --- | --- | --- |
| Discrete Coulomb elements | point, line segment, ring, disk | arrays of element positions, charge values, and owning source indexes |
| Analytic sources | infinite plane, spherical shell | arrays of source parameters evaluated directly in kernels |

The quality mode controls line, ring, and disk discretization counts using the existing solver
settings. Each discrete element retains an owning source index so the high-performance path can
produce both total field values and per-source contribution values.

The packed scene includes warning descriptors and source metadata templates. User-facing warning
strings are assembled outside kernels to avoid string work inside compiled loops.

### 7.3 Compute modes

The compute service supports two result modes:

| Mode | Used by | Output |
| --- | --- | --- |
| `total-only` | trajectories, field-line tracing, dense overlays | total potential and field only |
| `with-contributions` | probe measurements and public `/api/field/evaluate` | total values plus per-source contribution arrays |

This distinction is required for performance. Trajectories and field lines must not allocate or
serialize contribution objects they never display.

### 7.4 CPU backend

The CPU backend uses Numba `njit` kernels:

- batch field evaluation parallelizes over sample points with `parallel=True` and `prange`;
- field-line tracing parallelizes over seed rays;
- test-charge trajectory uses one compiled RK4 loop with no Python calls inside each step.

Single-particle RK4 is intentionally CPU-first. Its steps are sequential and a GPU kernel would have
low occupancy plus launch overhead. The dispatcher can revisit CUDA trajectories if a future feature
introduces many particles.

### 7.5 CUDA backend

The CUDA backend is loaded lazily. Import or initialization failure must not prevent application
startup.

CUDA kernels handle:

- batch total-only field evaluation;
- batch field evaluation with per-source contributions when the workload is large enough;
- parallel 2D field-line tracing, with one thread responsible for one seed ray.

CUDA kernels use fixed-size numeric buffers and return lengths or status codes for variable-length
field lines. Python post-processing converts accepted lines to response DTOs. Continuous sources are
already discretized into packed Coulomb elements before kernel launch.

The CUDA path must chunk workloads when array sizes exceed configured memory budgets. It must report
fallback reasons if allocation, compilation, launch, or synchronization fails.

### 7.6 Workload-aware dispatcher

The dispatcher chooses an execution backend based on:

- requested backend policy: `auto`, `cpu`, `cuda`, or `scalar`;
- CUDA availability;
- warm-up state;
- operation type;
- sample or ray count;
- estimated transfer and launch overhead;
- precision mode.

Default `auto` behavior:

| Operation | Default backend policy |
| --- | --- |
| Small probe request | CPU JIT |
| Dense batch field sampling | CUDA when available, otherwise CPU JIT |
| Single test-charge trajectory | CPU JIT |
| 2D field lines | CUDA when available, otherwise CPU JIT |
| Explicit debugging comparison | Scalar |

The threshold values are configuration constants tuned by benchmarks. They are not public physics
parameters.

### 7.7 Caching

The compute service maintains bounded thread-safe caches:

| Cache | Key | Value |
| --- | --- | --- |
| Packed scene cache | canonical scene hash, quality, dtype | immutable host arrays |
| Device scene cache | packed scene key, CUDA device | copied device arrays |
| Field-line result cache | packed scene key, viewport, quality, density | render-ready line response |

Scene mutation naturally changes the canonical hash and creates a new cache key. Least-recently-used
eviction limits memory. Cache limits are explicit configuration constants and appear in status
metadata.

### 7.8 Warm-up

Background warm-up compiles common `preview float32` CPU kernels after startup. If the CUDA extra and
compatible hardware are available, it also initializes the CUDA context and compiles common CUDA
kernels.

Warm-up must:

- never block the first UI paint;
- expose `idle`, `warming`, `ready`, or `failed` state;
- retain a readable failure reason;
- allow a normal CPU path while CUDA warm-up is incomplete.

## 8. API and Desktop Bridge

### 8.1 Existing field API

`POST /api/field/evaluate` remains backward compatible. Requests may add an optional execution
policy:

```json
{
  "backend": "auto"
}
```

The default is `auto`. Existing clients that omit the field continue to work.

### 8.2 Existing trajectory API

`POST /api/field/trajectory` remains backward compatible and delegates to the compiled trajectory
kernel. It accepts the same optional execution policy. For the first delivery, `auto` selects CPU
JIT for a single particle even when CUDA is available.

### 8.3 New field-line API

Add:

```text
POST /api/field/lines
```

The request includes:

- request ID;
- scene;
- `preview` or `refined` quality;
- 2D viewport bounds;
- trace density;
- maximum line count;
- optional backend policy.

The response includes:

- accepted render lines with world-coordinate points;
- arrow anchor and direction;
- candidate, rejected, conflict-filtered, and accepted counts;
- trace step metadata;
- execution metadata.

The browser keeps SVG curve rendering and lightweight presentation smoothing. It no longer performs
the expensive JavaScript RK4 field-line trace.

### 8.4 New compute status API

Add:

```text
GET /api/compute/status
```

The response includes:

- CPU model, core count, and logical processor count;
- CUDA extra installed or absent;
- CUDA runtime available or unavailable;
- selected CUDA device name and compute capability when available;
- warm-up state;
- cache sizes and limits;
- last fallback reason.

### 8.5 Execution metadata

Responses from field, trajectory, and field-line operations include:

| Field | Meaning |
| --- | --- |
| `backend_requested` | `auto`, `cpu`, `cuda`, or `scalar` |
| `backend_effective` | backend actually used |
| `device` | CPU description or CUDA device name |
| `precision` | `float32` or `float64` |
| `scene_cache_hit` | whether packed-scene compilation was reused |
| `device_cache_hit` | whether CUDA device arrays were reused |
| `warm` | whether kernels were already compiled |
| `compute_ms` | kernel or compiled-loop time |
| `total_ms` | end-to-end compute service time |
| `fallback_reason` | readable reason when a requested path was not used |

The desktop bridge exposes methods corresponding to the new field-line and status endpoints.

## 9. Concurrency and Cancellation

FastAPI and desktop bridge requests share one compute service.

### 9.1 CPU execution

CPU work runs outside the UI thread. Numba kernels release Python overhead and use configured worker
threads for parallel batch operations. The worker count defaults to available logical processors but
can be capped for responsiveness.

### 9.2 CUDA execution

CUDA operations use one serialized device queue per process. This avoids competing contexts and
uncontrolled concurrent allocations. The queue may drop stale queued preview requests before launch.

### 9.3 Stale UI requests

The browser keeps monotonically increasing request IDs. Only the latest preview response is applied.
An already-running CPU or CUDA kernel does not need unsafe mid-kernel cancellation; its result can be
dropped when complete. Queued obsolete preview requests should be removed before execution.

## 10. Browser Changes

- Replace JavaScript `computeFieldLineTraceResult()` execution with an asynchronous field-line API
  request.
- Keep current SVG path generation, arrow rendering, and user-visible layer status.
- Preserve a request ID and discard stale line responses after edits, zoom, pan, or preset changes.
- Display effective backend and precision in the analysis panel.
- Display CUDA warm-up and fallback state without treating CPU fallback as an error.
- Continue using Three.js only for 3D rendering.

The existing JavaScript tracer may remain temporarily behind a debug-only comparison switch during
the migration, then be removed after visual parity tests pass.

## 11. Correctness and Test Strategy

### 11.1 Reference comparisons

The scalar backend is the oracle. Add parameterized tests covering every source type:

- point charge;
- finite line segment;
- ring with arbitrary normal;
- disk with arbitrary normal;
- infinite plane;
- spherical shell inside, on surface, and outside.

For representative scenes, compare:

- scalar versus CPU JIT;
- scalar versus CUDA when CUDA is available;
- CPU JIT versus CUDA;
- total-only versus contribution-summed values.

### 11.2 Precision tolerances

- `preview float32` uses explicit relaxed relative and absolute tolerances appropriate to display
  calculations.
- `refined float64` uses tighter tolerances and remains suitable for probe measurements.
- Tests near singularities verify finite bounded outputs and warning parity.

### 11.3 Trajectory tests

- Compare compiled CPU RK4 with the scalar trajectory oracle.
- Cover uniform fields, dipoles, and near-source termination behavior.
- Verify `record_every` payload reduction.
- Verify that the default dispatcher selects CPU JIT for a single trajectory.

### 11.4 Field-line tests

- Compare CPU and CUDA line termination status, direction, endpoint classes, and visual line counts.
- Verify stale requests cannot overwrite newer viewport results.
- Keep Playwright assertions for visible arrows, zoom/pan behavior, and source edits.
- Add browser evidence that field-line rendering uses the backend API instead of synchronous
  JavaScript tracing.

### 11.5 Fallback tests

- CUDA extra absent.
- CUDA runtime unavailable.
- Unsupported CUDA device.
- CUDA allocation failure.
- CUDA kernel launch failure.
- CPU JIT unavailable.
- Scalar fallback metadata.

Hardware-independent tests use dependency injection or backend probes. Hardware CUDA tests run when
a compatible GPU is present and are reported explicitly.

## 12. Benchmarking

Add:

```text
scripts/benchmark_compute.py
```

Run it only through project-local uv. The script records:

- timestamp;
- CPU model and logical processor count;
- GPU model, driver, and compute capability when available;
- installed backend packages;
- operation;
- requested and effective backend;
- precision;
- cold-start time;
- warm-start repetitions and median;
- cache hit state;
- correctness comparison summary.

Required benchmark workloads:

- 25 and 400 sample field grids;
- `preview` and `refined`;
- scalar, CPU JIT, CUDA, and auto policies;
- 100 and 400 step single-particle trajectories;
- representative 2D field-line views.

Performance thresholds belong in the benchmark script or a separate non-default benchmark test.
They must not make the normal unit-test suite flaky.

## 13. Delivery Order

Each completed task creates the required standalone HTML report.

1. Add benchmark script, compute status DTOs, backend probes, and packed-scene cache.
2. Add CPU JIT total-only batch field kernel and contribution kernel.
3. Add optional CUDA dependency, CUDA batch kernels, device cache, and automatic fallback.
4. Move test-charge RK4 to the compiled CPU path and add workload-aware dispatch.
5. Add CPU and CUDA 2D field-line kernels and `/api/field/lines`.
6. Replace browser JavaScript tracing with asynchronous backend requests.
7. Add warm-up, stale preview queue dropping, status UI, and desktop bridge methods.
8. Run full correctness, lint, Playwright, CUDA hardware, and benchmark verification.
9. Rebuild and smoke-check CPU and CUDA-capable Windows desktop packages.

## 14. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| CUDA JIT cold start delays first use | Background warm-up and separate cold/warm reporting |
| CUDA package is large | Optional `cuda` extra; base install remains CPU-capable |
| GPU launch overhead makes small work slower | Workload-aware dispatcher keeps small probes and single trajectories on CPU |
| `float32` preview differs from scalar output | Explicit preview tolerances and visible precision metadata |
| Device memory grows with refined scenes | Chunking, bounded LRU caches, and allocation fallback |
| Field-line migration changes visuals | Preserve SVG presentation layer and add Playwright visual-behavior assertions |
| CPU parallel work affects UI responsiveness | Worker cap, debouncing, and stale queued request dropping |
| Unsupported CUDA environment | Readable fallback reason and verified CPU JIT path |

## 15. Acceptance Criteria

The performance redesign is complete when:

- CPU-only installation works without CUDA packages.
- CUDA installation automatically detects and uses the RTX 5060 Ti for eligible workloads.
- Existing scalar analytic and symmetry tests remain valid.
- New CPU JIT and CUDA correctness comparisons pass.
- All normal tests and lint pass through project-local uv.
- Browser field lines are computed by the Python backend and preserve existing visible behavior.
- API and desktop UI expose effective backend, precision, warm-up, cache, and fallback state.
- Warm preview benchmarks meet the 400-sample, 400-step trajectory, and field-line latency targets on
  the baseline machine.
- CPU fallback benchmark results are recorded even when CUDA hardware is present.
- Windows desktop smoke evidence is recorded for the CUDA-capable package.

## 16. References

- NVIDIA Numba-CUDA installation guide:
  <https://nvidia.github.io/numba-cuda/user/installation.html>
- NVIDIA Numba-CUDA kernel guide:
  <https://nvidia.github.io/numba-cuda/user/kernels.html>
- Numba CPU parallelization guide:
  <https://numba.readthedocs.io/en/stable/user/parallel.html>
