import math

import pytest
from fastapi.testclient import TestClient

from em_workbench.app import app
from em_workbench.models import Scene
from em_workbench.physics.compute.contracts import CudaRuntimeStatus
from em_workbench.physics.compute.dispatcher import ComputeService
from em_workbench.physics.compute.field_lines import ViewportBounds, trace_field_lines
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
