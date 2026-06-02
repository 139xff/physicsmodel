import numpy as np
import pytest

from em_workbench.models import Position, Scene
from em_workbench.physics.compute.contracts import CudaRuntimeStatus
from em_workbench.physics.compute.dispatcher import ComputeService
from em_workbench.physics.compute.runtime import probe_runtime

CUDA_REQUIRED = pytest.mark.skipif(not probe_runtime().cuda.available, reason="CUDA unavailable")


@pytest.fixture
def unavailable_cuda_probe():
    def probe() -> CudaRuntimeStatus:
        return CudaRuntimeStatus(
            installed=True,
            available=False,
            fallback_reason="CUDA runtime unavailable.",
        )

    return probe


def _grid_points(count: int) -> list[Position]:
    return [
        Position(
            x=-0.3 + 0.6 * (index % 20) / 19,
            y=-0.3 + 0.6 * (index // 20) / 19,
            z=0.04,
        )
        for index in range(count)
    ]


def test_auto_dispatch_falls_back_to_cpu_when_cuda_probe_is_unavailable(
    representative_scene: Scene,
    sample_points: list[Position],
    unavailable_cuda_probe,
) -> None:
    service = ComputeService(cuda_probe=unavailable_cuda_probe)

    result = service.evaluate_totals(
        representative_scene,
        sample_points,
        quality="preview",
        backend="auto",
    )

    assert result.execution.backend_effective == "cpu-jit"
    assert result.execution.fallback_reason == "CUDA runtime unavailable."


def test_explicit_cuda_dispatch_falls_back_to_cpu_when_cuda_probe_is_unavailable(
    representative_scene: Scene,
    sample_points: list[Position],
    unavailable_cuda_probe,
) -> None:
    service = ComputeService(cuda_probe=unavailable_cuda_probe)

    result = service.evaluate_totals(
        representative_scene,
        sample_points,
        quality="preview",
        backend="cuda",
    )

    assert result.execution.backend_requested == "cuda"
    assert result.execution.backend_effective == "cpu-jit"
    assert result.execution.fallback_reason == "CUDA runtime unavailable."


@CUDA_REQUIRED
@pytest.mark.parametrize(
    "quality,rtol,potential_atol,field_atol",
    [
        ("preview", 2e-5, 5e-5, 1e-3),
        ("refined", 1e-10, 1e-10, 1e-9),
    ],
)
def test_cuda_totals_match_cpu_for_large_batches_and_reuse_device_scene(
    representative_scene: Scene,
    quality: str,
    rtol: float,
    potential_atol: float,
    field_atol: float,
) -> None:
    service = ComputeService()
    points = _grid_points(400)

    cpu = service.evaluate_totals(representative_scene, points, quality=quality, backend="cpu")
    cuda_first = service.evaluate_totals(
        representative_scene,
        points,
        quality=quality,
        backend="cuda",
    )
    cuda_second = service.evaluate_totals(
        representative_scene,
        points,
        quality=quality,
        backend="cuda",
    )

    assert cuda_first.execution.backend_effective == "cuda"
    assert cuda_first.execution.device == "NVIDIA GeForce RTX 5060 Ti"
    assert cuda_first.execution.device_cache_hit is False
    assert cuda_second.execution.device_cache_hit is True
    np.testing.assert_allclose(
        cuda_first.potential_v,
        cpu.potential_v,
        rtol=rtol,
        atol=potential_atol,
    )
    np.testing.assert_allclose(
        cuda_first.field_v_per_m,
        cpu.field_v_per_m,
        rtol=rtol,
        atol=field_atol,
    )


@CUDA_REQUIRED
def test_auto_dispatch_uses_cuda_for_large_batches(representative_scene: Scene) -> None:
    result = ComputeService().evaluate_totals(
        representative_scene,
        _grid_points(400),
        quality="preview",
        backend="auto",
    )

    assert result.execution.backend_effective == "cuda"
