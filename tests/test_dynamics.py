import pytest

from em_workbench.models import PointChargeSource, Position, Scene
from em_workbench.physics.compute.contracts import CudaRuntimeStatus
from em_workbench.physics.compute.dispatcher import ComputeService
from em_workbench.physics.contact import POINT_CHARGE_CONTACT_RADIUS_M
from em_workbench.physics.dynamics import (
    TestCharge as Particle,
)
from em_workbench.physics.dynamics import (
    simulate_trajectory,
    simulate_trajectory_scalar,
)
from em_workbench.physics.solver import COULOMB_CONSTANT


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


def test_attractive_point_charge_contact_preserves_mechanical_energy() -> None:
    scene = Scene(
        id="energy-scene",
        title="Energy scene",
        sources=[
            PointChargeSource(
                id="positive-source",
                kind="point",
                label="Positive source",
                position=Position(x=0.0, y=0.0, z=0.0),
                charge_c=1.0e-9,
            )
        ],
    )
    particle = Particle(
        charge_c=-1.0e-9,
        mass_kg=1.0e-6,
        position=Position(x=-0.02, y=0.0, z=0.0),
        velocity=Position(x=0.35, y=0.0, z=0.0),
    )

    def energy(sample) -> float:
        radius = max(abs(sample.position.x), POINT_CHARGE_CONTACT_RADIUS_M)
        potential_energy = (
            COULOMB_CONSTANT * scene.sources[0].charge_c * particle.charge_c / radius
        )
        speed_sq = sample.velocity.x**2 + sample.velocity.y**2 + sample.velocity.z**2
        return 0.5 * particle.mass_kg * speed_sq + potential_energy

    for simulate in [simulate_trajectory_scalar, simulate_trajectory]:
        result = simulate(
            scene,
            particle,
            dt_s=1.0e-4,
            steps=320,
            quality="preview",
            record_every=1,
        )
        initial_energy = energy(result.samples[0])
        assert min(abs(sample.position.x) for sample in result.samples) == pytest.approx(
            POINT_CHARGE_CONTACT_RADIUS_M,
            abs=1.0e-7,
        )
        assert max(abs(energy(sample) - initial_energy) for sample in result.samples) < 1.0e-10
