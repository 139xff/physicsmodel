import pytest

from em_workbench.models import Scene
from em_workbench.physics.compute.contracts import CudaRuntimeStatus
from em_workbench.physics.compute.dispatcher import ComputeService
from em_workbench.physics.dynamics import (
    TestCharge as Particle,
)
from em_workbench.physics.dynamics import (
    simulate_trajectory,
    simulate_trajectory_scalar,
)


def test_compiled_trajectory_matches_scalar_rk4_for_dipole(
    representative_scene: Scene,
    particle: Particle,
) -> None:
    scalar = simulate_trajectory_scalar(
        representative_scene,
        particle,
        dt_s=0.001,
        steps=80,
        quality="preview",
    )
    compiled = simulate_trajectory(
        representative_scene,
        particle,
        dt_s=0.001,
        steps=80,
        quality="preview",
    )

    assert compiled.execution is not None
    assert compiled.execution.backend_effective == "cpu-jit"
    assert compiled.samples[-1].position.x == pytest.approx(
        scalar.samples[-1].position.x,
        rel=2e-5,
    )
    assert compiled.samples[-1].position.y == pytest.approx(
        scalar.samples[-1].position.y,
        rel=2e-5,
    )
    assert compiled.samples[-1].velocity.x == pytest.approx(
        scalar.samples[-1].velocity.x,
        rel=2e-5,
    )


def test_auto_trajectory_dispatch_uses_cpu_even_when_cuda_is_available(
    representative_scene: Scene,
    particle: Particle,
) -> None:
    service = ComputeService(
        cuda_probe=lambda: CudaRuntimeStatus(
            installed=True,
            available=True,
            device_name="test-gpu",
        )
    )

    result = service.simulate_trajectory(
        representative_scene,
        particle,
        dt_s=0.001,
        steps=8,
        quality="preview",
        backend="auto",
    )

    assert result.execution is not None
    assert result.execution.backend_effective == "cpu-jit"


def test_compiled_trajectory_record_every_reduces_payload(
    representative_scene: Scene,
    particle: Particle,
) -> None:
    result = simulate_trajectory(
        representative_scene,
        particle,
        dt_s=0.001,
        steps=9,
        quality="preview",
        record_every=4,
    )

    assert [sample.t_s for sample in result.samples] == pytest.approx([0.0, 0.004, 0.008, 0.009])
