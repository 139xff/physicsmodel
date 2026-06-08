import math

import numpy as np
import pytest
from fastapi.testclient import TestClient

from em_workbench.app import app
from em_workbench.models import Scene
from em_workbench.physics.compute.contracts import CudaRuntimeStatus
from em_workbench.physics.compute.dispatcher import ComputeService
from em_workbench.physics.compute.field_lines import (
    FIELD_LINE_START_RADIUS_M,
    ViewportBounds,
    build_field_line_inputs,
    trace_field_lines,
)
from em_workbench.physics.compute.packed_scene import compile_scene
from em_workbench.physics.compute.runtime import probe_runtime

client = TestClient(app)
BOUNDS = ViewportBounds(min_x=-0.20, max_x=0.20, min_y=-0.20, max_y=0.20)
CUDA_REQUIRED = pytest.mark.skipif(not probe_runtime().cuda.available, reason="CUDA unavailable")


def test_cpu_field_lines_trace_dipole_with_render_ready_metadata(
    representative_scene: Scene,
) -> None:
    response = trace_field_lines(representative_scene, BOUNDS, quality="preview", backend="cpu")

    assert response.execution.backend_effective == "cpu-jit"
    assert 0 < len(response.lines) <= response.display_max_count
    assert response.candidate_line_count >= len(response.lines)
    assert all(len(line.points) >= 2 for line in response.lines)
    assert all(
        line.topology in {"source-to-source", "source-to-infinity", "infinity-to-source"}
        for line in response.lines
    )
    assert all(
        math.hypot(line.arrow_direction.x, line.arrow_direction.y) == pytest.approx(1.0)
        for line in response.lines
    )


def test_cpu_field_lines_use_smooth_rk4_step_spacing_for_point_charge() -> None:
    scene = Scene(
        id="single-point-smoothness",
        title="Single point field-line smoothness",
        sources=[
            {
                "id": "point-1",
                "kind": "point",
                "label": "Point",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0, "unit": "m"},
                "charge_c": 1e-9,
            }
        ],
    )

    response = trace_field_lines(scene, BOUNDS, quality="preview", backend="cpu")

    segment_lengths = [
        math.hypot(next_point.x - point.x, next_point.y - point.y)
        for line in response.lines
        for point, next_point in zip(line.points, line.points[1:], strict=False)
    ]
    assert segment_lengths
    assert max(segment_lengths) <= 0.009
    assert sum(segment_lengths) / len(segment_lengths) <= 0.008


def test_field_line_api_returns_latest_render_contract(representative_scene: Scene) -> None:
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


@pytest.mark.parametrize(
    "source",
    [
        {
            "id": "line-segment-1",
            "kind": "line_segment",
            "label": "Positive line segment",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0, "unit": "m"},
            "orientation": {"x": 1.0, "y": 0.0, "z": 0.0},
            "length_m": 0.12,
            "charge_c": 1e-9,
        },
        {
            "id": "ring-1",
            "kind": "ring",
            "label": "Positive ring",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0, "unit": "m"},
            "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
            "radius_m": 0.08,
            "charge_c": 1e-9,
        },
        {
            "id": "disk-1",
            "kind": "disk",
            "label": "Positive disk",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0, "unit": "m"},
            "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
            "radius_m": 0.08,
            "charge_c": 1e-9,
        },
    ],
)
def test_cpu_field_lines_seed_integrated_sources(source: dict[str, object]) -> None:
    scene = Scene(
        id=f"{source['id']}-scene",
        title="Integrated source field lines",
        sources=[source],
    )

    response = trace_field_lines(scene, BOUNDS, quality="preview", backend="cpu")

    assert response.candidate_line_count > 0
    assert response.lines
    assert {line.source_id for line in response.lines} == {source["id"]}
    assert all(len(line.points) >= 2 for line in response.lines)


def test_cpu_field_lines_keep_mixed_finite_sources_visually_balanced() -> None:
    scene = Scene(
        id="mixed-finite-source-scene",
        title="Mixed finite source field lines",
        sources=[
            {
                "id": "point-1",
                "kind": "point",
                "label": "Point",
                "position": {"x": -0.16, "y": 0.0, "z": 0.0, "unit": "m"},
                "charge_c": 1e-9,
            },
            {
                "id": "line-segment-1",
                "kind": "line_segment",
                "label": "Line segment",
                "position": {"x": -0.08, "y": 0.08, "z": 0.0, "unit": "m"},
                "orientation": {"x": 1.0, "y": 0.0, "z": 0.0},
                "length_m": 0.16,
                "charge_c": 1.5e-9,
            },
            {
                "id": "ring-1",
                "kind": "ring",
                "label": "Ring",
                "position": {"x": 0.12, "y": 0.0, "z": 0.0, "unit": "m"},
                "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                "radius_m": 0.08,
                "charge_c": 2e-9,
            },
            {
                "id": "disk-1",
                "kind": "disk",
                "label": "Disk",
                "position": {"x": 0.0, "y": -0.11, "z": 0.0, "unit": "m"},
                "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                "radius_m": 0.09,
                "charge_c": 2e-9,
            },
        ],
    )

    response = trace_field_lines(scene, BOUNDS, quality="preview", backend="cpu")

    counts = {source_id: 0 for source_id in ["point-1", "line-segment-1", "ring-1", "disk-1"]}
    for line in response.lines:
        counts[line.source_id] += 1
    assert min(counts.values()) >= 16
    assert max(counts.values()) / min(counts.values()) <= 1.75


def test_cpu_field_lines_truncate_mixed_sources_fairly() -> None:
    scene = Scene(
        id="mixed-finite-source-truncated-scene",
        title="Mixed finite source field lines with a small display cap",
        sources=[
            {
                "id": "point-1",
                "kind": "point",
                "label": "Point",
                "position": {"x": -0.16, "y": 0.0, "z": 0.0, "unit": "m"},
                "charge_c": 1e-9,
            },
            {
                "id": "line-segment-1",
                "kind": "line_segment",
                "label": "Line segment",
                "position": {"x": -0.08, "y": 0.08, "z": 0.0, "unit": "m"},
                "orientation": {"x": 1.0, "y": 0.0, "z": 0.0},
                "length_m": 0.16,
                "charge_c": 1.5e-9,
            },
            {
                "id": "ring-1",
                "kind": "ring",
                "label": "Ring",
                "position": {"x": 0.12, "y": 0.0, "z": 0.0, "unit": "m"},
                "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                "radius_m": 0.08,
                "charge_c": 2e-9,
            },
            {
                "id": "disk-1",
                "kind": "disk",
                "label": "Disk",
                "position": {"x": 0.0, "y": -0.11, "z": 0.0, "unit": "m"},
                "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                "radius_m": 0.09,
                "charge_c": 2e-9,
            },
        ],
    )

    response = trace_field_lines(
        scene,
        BOUNDS,
        quality="preview",
        backend="cpu",
        display_max_count=16,
    )

    counts = {source_id: 0 for source_id in ["point-1", "line-segment-1", "ring-1", "disk-1"]}
    for line in response.lines:
        counts[line.source_id] += 1
    assert len(response.lines) == 16
    assert min(counts.values()) >= 3
    assert max(counts.values()) / min(counts.values()) <= 2


def test_field_line_inputs_seed_line_segments_uniformly_along_visible_geometry() -> None:
    scene = Scene(
        id="line-segment-seed-scene",
        title="Line segment seed distribution",
        sources=[
            {
                "id": "line-segment-1",
                "kind": "line_segment",
                "label": "Positive line segment",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0, "unit": "m"},
                "orientation": {"x": 1.0, "y": 0.0, "z": 0.0},
                "length_m": 0.16,
                "charge_c": 1e-9,
            }
        ],
    )
    packed = compile_scene(scene, quality="preview")

    inputs = build_field_line_inputs(scene, packed, density=1.0, dtype=np.dtype(np.float32))

    positive_side = sorted(float(seed[0]) for seed in inputs.seeds if float(seed[1]) > 0.0)
    negative_side = sorted(float(seed[0]) for seed in inputs.seeds if float(seed[1]) < 0.0)
    assert len(positive_side) == len(negative_side) == inputs.candidate_count // 2
    assert all(abs(abs(float(seed[1])) - FIELD_LINE_START_RADIUS_M) < 1e-7 for seed in inputs.seeds)
    assert positive_side == pytest.approx(negative_side)
    assert positive_side[0] == pytest.approx(0.16 / len(positive_side) / 2)
    assert positive_side[-1] == pytest.approx(0.16 - 0.16 / len(positive_side) / 2)
    gaps = [
        positive_side[index + 1] - positive_side[index]
        for index in range(len(positive_side) - 1)
    ]
    assert max(gaps) / min(gaps) < 1.05


@pytest.mark.parametrize("source_kind", ["ring", "disk"])
def test_field_line_inputs_seed_radial_sources_uniformly_on_visible_boundary(
    source_kind: str,
) -> None:
    scene = Scene(
        id=f"{source_kind}-seed-scene",
        title="Radial source seed distribution",
        sources=[
            {
                "id": f"{source_kind}-1",
                "kind": source_kind,
                "label": f"Positive {source_kind}",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0, "unit": "m"},
                "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                "radius_m": 0.08,
                "charge_c": 1e-9,
            }
        ],
    )
    packed = compile_scene(scene, quality="preview")

    inputs = build_field_line_inputs(scene, packed, density=1.0, dtype=np.dtype(np.float32))

    radii = [math.hypot(float(seed[0]), float(seed[1])) for seed in inputs.seeds]
    assert min(radii) == pytest.approx(0.08 + FIELD_LINE_START_RADIUS_M, rel=1e-5)
    assert max(radii) == pytest.approx(0.08 + FIELD_LINE_START_RADIUS_M, rel=1e-5)
    angles = sorted(
        (math.atan2(float(seed[1]), float(seed[0])) + math.tau) % math.tau
        for seed in inputs.seeds
    )
    gaps = [
        (angles[(index + 1) % len(angles)] - angles[index]) % math.tau
        for index in range(len(angles))
    ]
    assert max(gaps) / min(gaps) < 1.01


def test_explicit_cuda_field_lines_fall_back_to_cpu_when_runtime_is_unavailable(
    representative_scene: Scene,
) -> None:
    service = ComputeService(
        cuda_probe=lambda: CudaRuntimeStatus(
            installed=True,
            available=False,
            fallback_reason="CUDA runtime unavailable.",
        )
    )

    response = service.trace_field_lines(
        representative_scene,
        BOUNDS,
        quality="preview",
        backend="cuda",
    )

    assert response.execution.backend_requested == "cuda"
    assert response.execution.backend_effective == "cpu-jit"
    assert response.execution.fallback_reason == "CUDA runtime unavailable."


def test_auto_field_lines_keep_small_interactive_workloads_on_cpu(
    representative_scene: Scene,
) -> None:
    service = ComputeService(
        cuda_probe=lambda: CudaRuntimeStatus(
            installed=True,
            available=True,
            device_name="test-gpu",
        )
    )

    response = service.trace_field_lines(
        representative_scene,
        BOUNDS,
        quality="preview",
        backend="auto",
    )

    assert response.execution.backend_effective == "cpu-jit"


@CUDA_REQUIRED
def test_cuda_field_lines_match_cpu_render_contract(representative_scene: Scene) -> None:
    service = ComputeService()

    cpu = service.trace_field_lines(representative_scene, BOUNDS, quality="preview", backend="cpu")
    cuda = service.trace_field_lines(
        representative_scene,
        BOUNDS,
        quality="preview",
        backend="cuda",
    )

    assert cuda.execution.backend_effective == "cuda"
    assert cuda.candidate_line_count == cpu.candidate_line_count
    assert abs(len(cuda.lines) - len(cpu.lines)) <= 4
    assert {line.topology for line in cuda.lines} == {line.topology for line in cpu.lines}
    cpu_by_seed = {(line.source_id, line.seed_index): line for line in cpu.lines}
    matched = [
        (cpu_by_seed[(line.source_id, line.seed_index)], line)
        for line in cuda.lines
        if (line.source_id, line.seed_index) in cpu_by_seed
    ]
    assert matched
    for cpu_line, cuda_line in matched:
        assert cuda_line.min_direction_dot >= 0.2
        assert math.dist(
            (cpu_line.points[-1].x, cpu_line.points[-1].y),
            (cuda_line.points[-1].x, cuda_line.points[-1].y),
        ) <= 0.025
