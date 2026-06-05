"""Rutherford alpha-particle scattering.

This module uses an exact Coulomb force instead of the field solver. The field
solver intentionally clamps very small source distances for general scene
evaluation, but Rutherford scattering needs the near-nucleus repulsion to stay
intact so head-on particles turn around instead of passing through.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from em_workbench.models import Position
from em_workbench.physics.solver import COULOMB_CONSTANT
from em_workbench.physics.vectors import Vector3


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
    tracks: list[ScatterTrack]


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


def _characteristic_distance(nucleus: Nucleus, beam: AlphaBeam) -> float:
    kinetic_energy_j = 0.5 * beam.mass_kg * beam.speed_m_per_s**2
    return COULOMB_CONSTANT * beam.charge_c * nucleus.charge_c / kinetic_energy_j


def simulate_scattering(
    nucleus: Nucleus,
    beam: AlphaBeam,
    *,
    dt_s: float,
    max_steps: int = 20000,
    exit_radius_m: float | None = None,
    record_every: int = 10,
    request_id: str | None = None,
) -> ScatterResponse:
    """Fire the beam and return every alpha particle's path and angle."""
    if dt_s <= 0.0:
        raise ValueError("dt_s must be positive.")
    if max_steps < 1:
        raise ValueError("max_steps must be at least 1.")
    if record_every < 1:
        raise ValueError("record_every must be at least 1.")

    radius = exit_radius_m if exit_radius_m is not None else 3.0 * abs(beam.start_x_m)
    characteristic_distance_m = _characteristic_distance(nucleus, beam)
    return ScatterResponse(
        request_id=request_id,
        characteristic_distance_m=characteristic_distance_m,
        dt_s=dt_s,
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
