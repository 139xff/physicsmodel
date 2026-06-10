"""Rutherford alpha-particle scattering.

This module uses an exact Coulomb force instead of the field solver. The field
solver intentionally clamps very small source distances for general scene
evaluation, but Rutherford scattering needs the near-nucleus repulsion to stay
intact so head-on particles turn around instead of passing through.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from em_workbench.models import ElectrostaticSource, Position, Scene
from em_workbench.physics.compute.contracts import BackendPolicy, ExecutionMetadata
from em_workbench.physics.solver import COULOMB_CONSTANT, SolverQuality
from em_workbench.physics.vectors import Vector3, orthonormal_basis_from_normal


class ScatterModel(BaseModel):
    """Strict serializable DTO base for scattering payloads."""

    model_config = ConfigDict(extra="forbid", strict=True)


class Nucleus(ScatterModel):
    """Fixed target charge, such as a gold nucleus."""

    charge_c: FiniteFloat
    position: Position = Position(x=0.0, y=0.0, z=0.0)


class AlphaBeam(ScatterModel):
    """Identical alpha particles launched in the +x direction."""

    charge_c: FiniteFloat
    mass_kg: FiniteFloat = Field(gt=0)
    speed_m_per_s: FiniteFloat = Field(gt=0)
    start_x_m: FiniteFloat
    impact_parameters_m: list[FiniteFloat] = Field(min_length=1, max_length=121)


class ScatterTrack(ScatterModel):
    """One alpha particle's outcome and downsampled path."""

    impact_parameter_m: FiniteFloat
    scattering_angle_deg: FiniteFloat
    rutherford_angle_deg: FiniteFloat
    closest_approach_m: FiniteFloat
    samples: list[Position]


class ScatterResponse(ScatterModel):
    """Full scattering run for API and UI consumption."""

    request_id: str | None = None
    characteristic_distance_m: FiniteFloat
    dt_s: FiniteFloat
    field_model: Literal["point-nucleus", "scene-sources"] = "point-nucleus"
    tracks: list[ScatterTrack]
    warnings: list[str] = Field(default_factory=list)
    execution: ExecutionMetadata | None = None


def coulomb_acceleration(
    alpha_pos: Vector3,
    nucleus_pos: Vector3,
    charge_alpha: float,
    charge_nucleus: float,
    mass_kg: float,
) -> Vector3:
    """Exact Coulomb acceleration of the alpha particle."""
    displacement = alpha_pos - nucleus_pos
    distance = displacement.magnitude()
    if distance == 0.0:
        return Vector3(0.0, 0.0, 0.0)
    force_scale = COULOMB_CONSTANT * charge_alpha * charge_nucleus / (distance**3)
    return displacement.scale(force_scale / mass_kg)


def rutherford_angle_deg(impact_parameter_m: float, characteristic_distance_m: float) -> float:
    """Return signed Rutherford deflection, tan(theta / 2) = d / (2b)."""
    if impact_parameter_m == 0.0:
        return 180.0
    theta = 2.0 * math.atan2(characteristic_distance_m, 2.0 * abs(impact_parameter_m))
    sign = 1.0 if impact_parameter_m >= 0.0 else -1.0
    return math.degrees(theta) * sign


def _position(vector: Vector3) -> Position:
    return Position(x=vector.x, y=vector.y, z=vector.z)


def _simulate_one(
    nucleus: Nucleus,
    beam: AlphaBeam,
    impact_parameter_m: float,
    *,
    dt_s: float,
    max_steps: int,
    exit_radius_m: float,
    record_every: int,
) -> ScatterTrack:
    charge_alpha = beam.charge_c
    charge_nucleus = nucleus.charge_c
    mass_kg = beam.mass_kg
    nucleus_pos = Vector3.from_position(nucleus.position)
    position = Vector3(beam.start_x_m, impact_parameter_m, 0.0)
    velocity = Vector3(beam.speed_m_per_s, 0.0, 0.0)
    start_distance = (position - nucleus_pos).magnitude()
    closest_approach_m = start_distance
    samples = [_position(position)]

    def acceleration(pos: Vector3) -> Vector3:
        return coulomb_acceleration(pos, nucleus_pos, charge_alpha, charge_nucleus, mass_kg)

    for step in range(1, max_steps + 1):
        k1x = velocity
        k1v = acceleration(position)
        k2x = velocity + k1v.scale(dt_s / 2.0)
        k2v = acceleration(position + k1x.scale(dt_s / 2.0))
        k3x = velocity + k2v.scale(dt_s / 2.0)
        k3v = acceleration(position + k2x.scale(dt_s / 2.0))
        k4x = velocity + k3v.scale(dt_s)
        k4v = acceleration(position + k3x.scale(dt_s))

        position = position + (k1x + k2x.scale(2.0) + k3x.scale(2.0) + k4x).scale(
            dt_s / 6.0
        )
        velocity = velocity + (k1v + k2v.scale(2.0) + k3v.scale(2.0) + k4v).scale(
            dt_s / 6.0
        )

        relative = position - nucleus_pos
        distance = relative.magnitude()
        closest_approach_m = min(closest_approach_m, distance)
        if step % record_every == 0:
            samples.append(_position(position))

        if step > 3 and distance >= start_distance and relative.dot(velocity) > 0.0:
            break
        if distance > exit_radius_m:
            break

    samples.append(_position(position))
    characteristic_distance_m = _characteristic_distance(nucleus, beam)
    return ScatterTrack(
        impact_parameter_m=impact_parameter_m,
        scattering_angle_deg=math.degrees(math.atan2(velocity.y, velocity.x)),
        rutherford_angle_deg=rutherford_angle_deg(
            impact_parameter_m,
            characteristic_distance_m,
        ),
        closest_approach_m=closest_approach_m,
        samples=samples,
    )


def _source_geometry_distance(source: ElectrostaticSource, sample: Vector3) -> float:
    position = Vector3.from_position(source.position)
    if source.kind == "point":
        return (sample - position).magnitude()
    if source.kind == "line_segment":
        axis = Vector3.from_position(source.orientation).normalized()
        displacement = sample - position
        projected = max(0.0, min(source.length_m, displacement.dot(axis)))
        nearest = position + axis.scale(projected)
        return (sample - nearest).magnitude()
    if source.kind == "ring":
        _axis_u, _axis_v, normal = orthonormal_basis_from_normal(
            Vector3.from_position(source.normal)
        )
        displacement = sample - position
        plane_distance = displacement.dot(normal)
        in_plane = displacement - normal.scale(plane_distance)
        return math.hypot(plane_distance, in_plane.magnitude() - source.radius_m)
    if source.kind == "disk":
        _axis_u, _axis_v, normal = orthonormal_basis_from_normal(
            Vector3.from_position(source.normal)
        )
        displacement = sample - position
        plane_distance = displacement.dot(normal)
        in_plane = displacement - normal.scale(plane_distance)
        radial_excess = max(0.0, in_plane.magnitude() - source.radius_m)
        return math.hypot(plane_distance, radial_excess)
    if source.kind == "infinite_plane":
        normal = Vector3.from_position(source.normal).normalized()
        return abs((sample - position).dot(normal))
    if source.kind == "spherical_shell":
        return abs((sample - position).magnitude() - source.radius_m)
    return (sample - position).magnitude()


def _scene_geometry_distance(scene: Scene, sample: Vector3) -> float:
    if not scene.sources:
        return sample.magnitude()
    return min(_source_geometry_distance(source, sample) for source in scene.sources)


def _scene_reference_position(scene: Scene) -> Vector3:
    if not scene.sources:
        return Vector3(0.0, 0.0, 0.0)
    x = math.fsum(source.position.x for source in scene.sources) / len(scene.sources)
    y = math.fsum(source.position.y for source in scene.sources) / len(scene.sources)
    z = math.fsum(source.position.z for source in scene.sources) / len(scene.sources)
    return Vector3(x, y, z)


def _trim_scene_samples(
    samples,
    *,
    reference: Vector3,
    start_radius: float,
    exit_radius_m: float,
) -> list:
    if len(samples) <= 1:
        return list(samples)
    for index, sample in enumerate(samples[1:], start=1):
        position = Vector3.from_position(sample.position)
        velocity = Vector3.from_position(sample.velocity)
        relative = position - reference
        distance = relative.magnitude()
        if distance > exit_radius_m:
            return list(samples[: index + 1])
        if index > 3 and distance >= start_radius and relative.dot(velocity) > 0.0:
            return list(samples[: index + 1])
    return list(samples)


def _simulate_scene_scattering(
    scene: Scene,
    beam: AlphaBeam,
    *,
    dt_s: float,
    max_steps: int,
    exit_radius_m: float,
    record_every: int,
    quality: SolverQuality,
    backend: BackendPolicy,
) -> tuple[list[ScatterTrack], ExecutionMetadata | None, list[str]]:
    from em_workbench.physics.compute.dispatcher import DEFAULT_COMPUTE_SERVICE
    from em_workbench.physics.dynamics import TestCharge

    reference = _scene_reference_position(scene)
    tracks: list[ScatterTrack] = []
    execution: ExecutionMetadata | None = None
    warnings: list[str] = []
    for impact_parameter_m in beam.impact_parameters_m:
        start = Vector3(beam.start_x_m, impact_parameter_m, 0.0)
        start_radius = (start - reference).magnitude()
        trajectory = DEFAULT_COMPUTE_SERVICE.simulate_trajectory(
            scene,
            TestCharge(
                charge_c=beam.charge_c,
                mass_kg=beam.mass_kg,
                position=Position(x=start.x, y=start.y, z=start.z),
                velocity=Position(x=beam.speed_m_per_s, y=0.0, z=0.0),
            ),
            dt_s=dt_s,
            steps=max_steps,
            quality=quality,
            record_every=record_every,
            backend=backend,
        )
        if execution is None:
            execution = trajectory.execution
        warnings.extend(trajectory.warnings)
        trajectory_samples = _trim_scene_samples(
            trajectory.samples,
            reference=reference,
            start_radius=start_radius,
            exit_radius_m=exit_radius_m,
        )
        final_sample = trajectory_samples[-1]
        final_velocity = Vector3.from_position(final_sample.velocity)
        positions = [sample.position for sample in trajectory_samples]
        tracks.append(
            ScatterTrack(
                impact_parameter_m=impact_parameter_m,
                scattering_angle_deg=math.degrees(
                    math.atan2(final_velocity.y, final_velocity.x)
                ),
                rutherford_angle_deg=0.0,
                closest_approach_m=min(
                    _scene_geometry_distance(scene, Vector3.from_position(sample.position))
                    for sample in trajectory_samples
                ),
                samples=positions,
            )
        )
    return tracks, execution, sorted(set(warnings))


def _characteristic_distance(nucleus: Nucleus, beam: AlphaBeam) -> float:
    kinetic_energy_j = 0.5 * beam.mass_kg * beam.speed_m_per_s**2
    return COULOMB_CONSTANT * beam.charge_c * nucleus.charge_c / kinetic_energy_j


def simulate_scattering(
    nucleus: Nucleus | None,
    beam: AlphaBeam,
    *,
    scene: Scene | None = None,
    dt_s: float,
    max_steps: int = 20000,
    exit_radius_m: float | None = None,
    record_every: int = 10,
    request_id: str | None = None,
    quality: SolverQuality = "preview",
    backend: BackendPolicy = "auto",
) -> ScatterResponse:
    """Fire the beam and return every alpha particle's path and angle."""
    if dt_s <= 0.0:
        raise ValueError("dt_s must be positive.")
    if max_steps < 1:
        raise ValueError("max_steps must be at least 1.")
    if record_every < 1:
        raise ValueError("record_every must be at least 1.")

    radius = exit_radius_m if exit_radius_m is not None else 3.0 * abs(beam.start_x_m)
    if scene is not None:
        if not scene.sources:
            raise ValueError("scene scattering requires at least one electrostatic source.")
        tracks, execution, warnings = _simulate_scene_scattering(
            scene,
            beam,
            dt_s=dt_s,
            max_steps=max_steps,
            exit_radius_m=radius,
            record_every=record_every,
            quality=quality,
            backend=backend,
        )
        return ScatterResponse(
            request_id=request_id,
            characteristic_distance_m=0.0,
            dt_s=dt_s,
            field_model="scene-sources",
            tracks=tracks,
            warnings=warnings,
            execution=execution,
        )

    if nucleus is None:
        raise ValueError("nucleus is required when scene is not provided.")
    characteristic_distance_m = _characteristic_distance(nucleus, beam)
    return ScatterResponse(
        request_id=request_id,
        characteristic_distance_m=characteristic_distance_m,
        dt_s=dt_s,
        field_model="point-nucleus",
        tracks=[
            _simulate_one(
                nucleus,
                beam,
                impact_parameter_m,
                dt_s=dt_s,
                max_steps=max_steps,
                exit_radius_m=radius,
                record_every=record_every,
            )
            for impact_parameter_m in beam.impact_parameters_m
        ],
    )
