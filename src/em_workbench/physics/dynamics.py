"""Test-charge dynamics: move a probe charge through the electrostatic field.

This module is the missing "make it move" layer. It does NOT introduce any new
field physics -- it reuses ``evaluate_scene`` from ``solver.py`` to read the
electric field E at the particle's current position, then integrates Newton's
second law

    F = q E          (force on the test charge)
    a = F / m        (Newton's second law)
    dx/dt = v        (kinematics)
    dv/dt = a

with a 4th-order Runge-Kutta (RK4) step. RK4 is chosen over plain Euler because
it stays accurate with much larger time steps, which matters once the field is
non-uniform (e.g. near a point charge).

The test charge is assumed to be small enough that it does not disturb the
sources that create the field (the standard "test charge" idealisation).
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from em_workbench.models import Position, Scene
from em_workbench.physics.compute.contracts import BackendPolicy, ExecutionMetadata
from em_workbench.physics.contact import POINT_CHARGE_CONTACT_RADIUS_M
from em_workbench.physics.solver import SolverQuality, evaluate_scene_scalar
from em_workbench.physics.vectors import Vector3


class DynamicsModel(BaseModel):
    """Strict serializable DTO base, matching the solver's conventions."""

    model_config = ConfigDict(extra="forbid", strict=True)


class TestCharge(DynamicsModel):
    """A movable probe charge driven by the scene's field."""

    charge_c: FiniteFloat
    mass_kg: FiniteFloat = Field(gt=0)
    position: Position
    velocity: Position  # reused as a 3-component vector in m/s


class TrajectorySample(DynamicsModel):
    """One recorded state along the trajectory."""

    t_s: FiniteFloat
    position: Position
    velocity: Position
    acceleration: Position
    field_v_per_m: Position
    field_magnitude_v_per_m: FiniteFloat


class TrajectoryResponse(DynamicsModel):
    """Full integrated trajectory for API/UI consumption."""

    request_id: str | None = None
    dt_s: FiniteFloat
    step_count: int
    samples: list[TrajectorySample]
    warnings: list[str] = Field(default_factory=list)
    execution: ExecutionMetadata | None = None


def _vec(p: Position | Vector3) -> Vector3:
    return Vector3.from_components(p.x, p.y, p.z)


def _pos(v: Vector3) -> Position:
    return Position(x=v.x, y=v.y, z=v.z)


def _apply_point_charge_contact(
    scene: Scene,
    position: Vector3,
    velocity: Vector3,
) -> tuple[Vector3, Vector3, bool]:
    contacted = False
    for source in scene.sources:
        if source.kind != "point":
            continue
        center = Vector3.from_position(source.position)
        displacement = position - center
        distance = displacement.magnitude()
        if distance >= POINT_CHARGE_CONTACT_RADIUS_M:
            continue
        contacted = True
        if distance > 1e-15:
            normal = displacement.scale(1.0 / distance)
        else:
            speed = velocity.magnitude()
            normal = (-velocity).scale(1.0 / speed) if speed > 0 else Vector3(1.0, 0.0, 0.0)
        position = center + normal.scale(POINT_CHARGE_CONTACT_RADIUS_M)
        normal_velocity = velocity.dot(normal)
        if normal_velocity < 0.0:
            velocity = velocity - normal.scale(2.0 * normal_velocity)
    return position, velocity, contacted


def field_at(scene: Scene, point: Vector3, quality: SolverQuality) -> Vector3:
    """Read the total electric field E (V/m) at one point by reusing the solver."""
    response = evaluate_scene_scalar(
        scene,
        [Position(x=point.x, y=point.y, z=point.z)],
        quality=quality,
    )
    e = response.samples[0].field_v_per_m
    return Vector3.from_components(e.x, e.y, e.z)


def potential_at(scene: Scene, point: Vector3, quality: SolverQuality) -> float:
    """Read the total electric potential V at one point by reusing the solver."""
    response = evaluate_scene_scalar(
        scene,
        [Position(x=point.x, y=point.y, z=point.z)],
        quality=quality,
    )
    return response.samples[0].potential_v


def mechanical_energy(
    scene: Scene,
    position: Vector3,
    velocity: Vector3,
    charge_c: float,
    mass_kg: float,
    quality: SolverQuality,
) -> float:
    return 0.5 * mass_kg * velocity.magnitude_squared() + charge_c * potential_at(
        scene,
        position,
        quality,
    )


def _correct_velocity_for_energy(
    scene: Scene,
    position: Vector3,
    velocity: Vector3,
    charge_c: float,
    mass_kg: float,
    quality: SolverQuality,
    target_energy_j: float,
) -> Vector3:
    kinetic_j = target_energy_j - charge_c * potential_at(scene, position, quality)
    target_speed = (max(0.0, 2.0 * kinetic_j / mass_kg)) ** 0.5
    current_speed = velocity.magnitude()
    if current_speed <= 0.0:
        return velocity
    return velocity.scale(target_speed / current_speed)


def acceleration(
    scene: Scene, position: Vector3, charge_c: float, mass_kg: float, quality: SolverQuality
) -> Vector3:
    """a = qE/m -- the only line where charge, field and mass meet."""
    return field_at(scene, position, quality).scale(charge_c / mass_kg)


def simulate_trajectory(
    scene: Scene,
    particle: TestCharge,
    *,
    dt_s: float,
    steps: int,
    quality: SolverQuality = "preview",
    record_every: int = 1,
    request_id: str | None = None,
    backend: BackendPolicy = "auto",
) -> TrajectoryResponse:
    """Integrate a test charge through the selected compute backend."""
    from em_workbench.physics.compute.dispatcher import DEFAULT_COMPUTE_SERVICE

    return DEFAULT_COMPUTE_SERVICE.simulate_trajectory(
        scene,
        particle,
        dt_s=dt_s,
        steps=steps,
        quality=quality,
        record_every=record_every,
        request_id=request_id,
        backend=backend,
    )


def simulate_trajectory_scalar(
    scene: Scene,
    particle: TestCharge,
    *,
    dt_s: float,
    steps: int,
    quality: SolverQuality = "preview",
    record_every: int = 1,
    request_id: str | None = None,
) -> TrajectoryResponse:
    """Integrate the test charge through the scene field with RK4.

    Parameters
    ----------
    dt_s:
        Time step. Smaller is more accurate but slower. For a uniform field any
        value is essentially exact; near a point charge use something small
        (e.g. 1e-3 s scaled to your units).
    steps:
        Number of integration steps to run.
    record_every:
        Store every Nth state in the returned trajectory to keep payloads small.
    """
    if dt_s <= 0.0:
        raise ValueError("dt_s must be positive.")
    if steps < 1:
        raise ValueError("steps must be at least 1.")

    q = particle.charge_c
    m = particle.mass_kg
    x = _vec(particle.position)
    v = _vec(particle.velocity)
    target_energy_j = mechanical_energy(scene, x, v, q, m, quality)

    def accel(pos: Vector3) -> Vector3:
        return acceleration(scene, pos, q, m, quality)

    samples: list[TrajectorySample] = []

    def record(t: float, pos: Vector3, vel: Vector3) -> None:
        e = field_at(scene, pos, quality)
        a = e.scale(q / m)
        samples.append(
            TrajectorySample(
                t_s=t,
                position=_pos(pos),
                velocity=_pos(vel),
                acceleration=_pos(a),
                field_v_per_m=_pos(e),
                field_magnitude_v_per_m=e.magnitude(),
            )
        )

    record(0.0, x, v)
    t = 0.0
    for step in range(1, steps + 1):
        # Classic RK4 on the coupled system (x' = v, v' = a(x)).
        k1x = v
        k1v = accel(x)
        k2x = v + k1v.scale(dt_s / 2.0)
        k2v = accel(x + k1x.scale(dt_s / 2.0))
        k3x = v + k2v.scale(dt_s / 2.0)
        k3v = accel(x + k2x.scale(dt_s / 2.0))
        k4x = v + k3v.scale(dt_s)
        k4v = accel(x + k3x.scale(dt_s))

        x = x + (k1x + k2x.scale(2.0) + k3x.scale(2.0) + k4x).scale(dt_s / 6.0)
        v = v + (k1v + k2v.scale(2.0) + k3v.scale(2.0) + k4v).scale(dt_s / 6.0)
        x, v, contacted = _apply_point_charge_contact(scene, x, v)
        if contacted:
            v = _correct_velocity_for_energy(scene, x, v, q, m, quality, target_energy_j)
        t += dt_s

        if step % record_every == 0 or step == steps:
            record(t, x, v)

    return TrajectoryResponse(
        request_id=request_id,
        dt_s=dt_s,
        step_count=steps,
        samples=samples,
    )


def iter_states(
    scene: Scene,
    particle: TestCharge,
    *,
    dt_s: float,
    quality: SolverQuality = "preview",
) -> Iterable[tuple[float, Vector3, Vector3]]:
    """Streaming variant: yield (t, position, velocity) one RK4 step at a time.

    Use this if you prefer to drive the animation from the backend step-by-step
    instead of precomputing the whole trajectory.
    """
    q = particle.charge_c
    m = particle.mass_kg
    x = _vec(particle.position)
    v = _vec(particle.velocity)
    target_energy_j = mechanical_energy(scene, x, v, q, m, quality)

    def accel(pos: Vector3) -> Vector3:
        return acceleration(scene, pos, q, m, quality)

    t = 0.0
    yield t, x, v
    while True:
        k1x, k1v = v, accel(x)
        k2x, k2v = v + k1v.scale(dt_s / 2.0), accel(x + k1x.scale(dt_s / 2.0))
        k3x, k3v = v + k2v.scale(dt_s / 2.0), accel(x + k2x.scale(dt_s / 2.0))
        k4x, k4v = v + k3v.scale(dt_s), accel(x + k3x.scale(dt_s))
        x = x + (k1x + k2x.scale(2.0) + k3x.scale(2.0) + k4x).scale(dt_s / 6.0)
        v = v + (k1v + k2v.scale(2.0) + k3v.scale(2.0) + k4v).scale(dt_s / 6.0)
        x, v, contacted = _apply_point_charge_contact(scene, x, v)
        if contacted:
            v = _correct_velocity_for_energy(scene, x, v, q, m, quality, target_energy_j)
        t += dt_s
        yield t, x, v
