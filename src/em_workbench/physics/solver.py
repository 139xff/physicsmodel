"""Electrostatic potential and electric-field evaluation."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from em_workbench.models import (
    DiskSource,
    ElectrostaticSource,
    InfinitePlaneSource,
    LineSegmentSource,
    Position,
    RingSource,
    Scene,
    SphericalShellSource,
)
from em_workbench.physics.vectors import ZERO_VECTOR, Vector3, orthonormal_basis_from_normal

EPSILON_0 = 8.854_187_812_8e-12
COULOMB_CONSTANT = 1.0 / (4.0 * math.pi * EPSILON_0)
RESULT_VERSION = "electrostatic-solver-v1"
MIN_SOURCE_DISTANCE_M = 1.0e-9

SolverQuality = Literal["preview", "refined"]
MetadataValue = bool | int | float | str


class SolverModel(BaseModel):
    """Strict serializable DTO base for solver output."""

    model_config = ConfigDict(extra="forbid", strict=True)


class FieldVector(SolverModel):
    """Three-component electric-field vector in V/m."""

    x: FiniteFloat
    y: FiniteFloat
    z: FiniteFloat

    @classmethod
    def from_vector(cls, vector: Vector3) -> FieldVector:
        return cls(x=vector.x, y=vector.y, z=vector.z)


class SourceContribution(SolverModel):
    """One source's contribution to a sampled field result."""

    source_id: str
    source_kind: str
    potential_v: FiniteFloat
    field_v_per_m: FieldVector
    field_magnitude_v_per_m: FiniteFloat
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)


class FieldSampleResult(SolverModel):
    """Total electrostatic result at one sample point."""

    point: Position
    potential_v: FiniteFloat
    field_v_per_m: FieldVector
    field_magnitude_v_per_m: FiniteFloat
    contributions: list[SourceContribution]
    warnings: list[str] = Field(default_factory=list)


class FieldEvaluationResponse(SolverModel):
    """Batch field-evaluation response for API and UI request deconfliction."""

    request_id: str | None = None
    result_version: str = RESULT_VERSION
    quality: SolverQuality
    sample_count: int
    samples: list[FieldSampleResult]
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)


def evaluate_scene(
    scene: Scene,
    sample_points: Iterable[Position | dict[str, float] | tuple[float, float, float]],
    *,
    quality: SolverQuality = "preview",
    request_id: str | None = None,
) -> FieldEvaluationResponse:
    """Evaluate electrostatic potential and field for a scene at sample points."""
    settings = _settings_for_quality(quality)
    sample_vectors = [Vector3.from_sample(sample) for sample in sample_points]
    results = [
        _evaluate_sample(scene.sources, sample, quality, settings) for sample in sample_vectors
    ]
    warnings = _unique_warnings(warning for result in results for warning in result.warnings)
    return FieldEvaluationResponse(
        request_id=request_id,
        result_version=RESULT_VERSION,
        quality=quality,
        sample_count=len(results),
        samples=results,
        warnings=warnings,
        metadata={
            "quality": quality,
            "epsilon0_f_per_m": EPSILON_0,
            "coulomb_constant_n_m2_per_c2": COULOMB_CONSTANT,
            "min_source_distance_m": MIN_SOURCE_DISTANCE_M,
            **settings,
        },
    )


def _settings_for_quality(quality: SolverQuality) -> dict[str, int]:
    if quality == "preview":
        return {
            "ring_segments": 64,
            "line_segments": 48,
            "disk_radial_segments": 8,
            "disk_angular_segments": 48,
        }
    if quality == "refined":
        return {
            "ring_segments": 512,
            "line_segments": 256,
            "disk_radial_segments": 20,
            "disk_angular_segments": 144,
        }
    raise ValueError(f"Unknown solver quality: {quality}")


def _evaluate_sample(
    sources: list[ElectrostaticSource],
    sample: Vector3,
    quality: SolverQuality,
    settings: dict[str, int],
) -> FieldSampleResult:
    contributions = [_evaluate_source(source, sample, quality, settings) for source in sources]
    total_potential = math.fsum(contribution.potential_v for contribution in contributions)
    total_field = ZERO_VECTOR
    for contribution in contributions:
        total_field = total_field + Vector3.from_sample(contribution.field_v_per_m)
    warnings = _unique_warnings(
        warning for contribution in contributions for warning in contribution.warnings
    )
    return FieldSampleResult(
        point=Position(x=sample.x, y=sample.y, z=sample.z),
        potential_v=total_potential,
        field_v_per_m=FieldVector.from_vector(total_field),
        field_magnitude_v_per_m=total_field.magnitude(),
        contributions=contributions,
        warnings=warnings,
    )


def _evaluate_source(
    source: ElectrostaticSource,
    sample: Vector3,
    quality: SolverQuality,
    settings: dict[str, int],
) -> SourceContribution:
    if source.kind == "point":
        return _point_contribution(source, sample)
    if source.kind == "ring":
        return _ring_contribution(source, sample, settings["ring_segments"])
    if source.kind == "line_segment":
        return _line_segment_contribution(source, sample, settings["line_segments"])
    if source.kind == "disk":
        return _disk_contribution(
            source,
            sample,
            settings["disk_radial_segments"],
            settings["disk_angular_segments"],
        )
    if source.kind == "infinite_plane":
        return _infinite_plane_contribution(source, sample)
    if source.kind == "spherical_shell":
        return _spherical_shell_contribution(source, sample)
    return _zero_contribution(
        source.id,
        source.kind,
        [f"Source kind {source.kind!r} is not supported by solver quality {quality!r}."],
        {"method": "unsupported"},
    )


def _point_contribution(source: ElectrostaticSource, sample: Vector3) -> SourceContribution:
    return _point_charge_contribution(
        source_id=source.id,
        source_kind=source.kind,
        charge_c=source.charge_c,
        charge_position=Vector3.from_position(source.position),
        sample=sample,
        metadata={"method": "analytic-point"},
    )


def _point_charge_contribution(
    *,
    source_id: str,
    source_kind: str,
    charge_c: float,
    charge_position: Vector3,
    sample: Vector3,
    metadata: dict[str, MetadataValue],
) -> SourceContribution:
    displacement = sample - charge_position
    distance = displacement.magnitude()
    if distance <= MIN_SOURCE_DISTANCE_M:
        warning = (
            f"Sample is at or within {MIN_SOURCE_DISTANCE_M:g} m of source {source_id}; "
            "singular point-charge contribution was bounded to zero."
        )
        return _zero_contribution(source_id, source_kind, [warning], metadata)
    potential = COULOMB_CONSTANT * charge_c / distance
    field = displacement.scale(COULOMB_CONSTANT * charge_c / distance**3)
    return _contribution(source_id, source_kind, potential, field, [], metadata)


def _ring_contribution(
    source: RingSource,
    sample: Vector3,
    segment_count: int,
) -> SourceContribution:
    charge_c = _ring_charge_c(source)
    center = Vector3.from_position(source.position)
    axis_u, axis_v, _unit_normal = orthonormal_basis_from_normal(
        Vector3.from_position(source.normal)
    )
    dq = charge_c / segment_count
    potential = 0.0
    field = ZERO_VECTOR
    warnings: list[str] = []
    for index in range(segment_count):
        angle = 2.0 * math.pi * (index + 0.5) / segment_count
        charge_position = center + axis_u.scale(math.cos(angle) * source.radius_m)
        charge_position = charge_position + axis_v.scale(math.sin(angle) * source.radius_m)
        partial = _point_charge_contribution(
            source_id=source.id,
            source_kind=source.kind,
            charge_c=dq,
            charge_position=charge_position,
            sample=sample,
            metadata={"method": "discrete-ring-segment"},
        )
        potential += partial.potential_v
        field = field + Vector3.from_sample(partial.field_v_per_m)
        warnings.extend(partial.warnings)
    metadata: dict[str, MetadataValue] = {
        "method": "discrete-ring",
        "segments": segment_count,
        "radius_m": source.radius_m,
    }
    return _contribution(
        source.id, source.kind, potential, field, _unique_warnings(warnings), metadata
    )


def _line_segment_contribution(
    source: LineSegmentSource,
    sample: Vector3,
    segment_count: int,
) -> SourceContribution:
    charge_c = _line_charge_c(source)
    center = Vector3.from_position(source.position)
    axis = Vector3.from_position(source.orientation).normalized()
    dq = charge_c / segment_count
    step = source.length_m / segment_count
    start_offset = -0.5 * source.length_m + 0.5 * step
    potential = 0.0
    field = ZERO_VECTOR
    warnings = [
        (
            f"Source {source.id} line_segment uses a {segment_count}-segment numerical "
            "approximation; analytic finite-line precision is not claimed."
        )
    ]
    for index in range(segment_count):
        charge_position = center + axis.scale(start_offset + index * step)
        partial = _point_charge_contribution(
            source_id=source.id,
            source_kind=source.kind,
            charge_c=dq,
            charge_position=charge_position,
            sample=sample,
            metadata={"method": "discrete-line-segment"},
        )
        potential += partial.potential_v
        field = field + Vector3.from_sample(partial.field_v_per_m)
        warnings.extend(partial.warnings)
    metadata: dict[str, MetadataValue] = {
        "method": "discrete-line-segment",
        "segments": segment_count,
        "length_m": source.length_m,
    }
    return _contribution(
        source.id, source.kind, potential, field, _unique_warnings(warnings), metadata
    )


def _disk_contribution(
    source: DiskSource,
    sample: Vector3,
    radial_segments: int,
    angular_segments: int,
) -> SourceContribution:
    charge_c = _disk_charge_c(source)
    surface_density = charge_c / (math.pi * source.radius_m**2)
    center = Vector3.from_position(source.position)
    axis_u, axis_v, _unit_normal = orthonormal_basis_from_normal(
        Vector3.from_position(source.normal)
    )
    dr = source.radius_m / radial_segments
    dtheta = 2.0 * math.pi / angular_segments
    potential = 0.0
    field = ZERO_VECTOR
    warnings = [
        (
            f"Source {source.id} disk uses a {radial_segments}x{angular_segments} "
            "midpoint numerical approximation; analytic disk precision is not claimed."
        )
    ]
    for radial_index in range(radial_segments):
        radius = (radial_index + 0.5) * dr
        dq = surface_density * radius * dr * dtheta
        for angular_index in range(angular_segments):
            angle = (angular_index + 0.5) * dtheta
            charge_position = center + axis_u.scale(math.cos(angle) * radius)
            charge_position = charge_position + axis_v.scale(math.sin(angle) * radius)
            partial = _point_charge_contribution(
                source_id=source.id,
                source_kind=source.kind,
                charge_c=dq,
                charge_position=charge_position,
                sample=sample,
                metadata={"method": "discrete-disk-patch"},
            )
            potential += partial.potential_v
            field = field + Vector3.from_sample(partial.field_v_per_m)
            warnings.extend(partial.warnings)
    metadata: dict[str, MetadataValue] = {
        "method": "discrete-disk",
        "radial_segments": radial_segments,
        "angular_segments": angular_segments,
        "radius_m": source.radius_m,
    }
    return _contribution(
        source.id, source.kind, potential, field, _unique_warnings(warnings), metadata
    )


def _infinite_plane_contribution(
    source: InfinitePlaneSource,
    sample: Vector3,
) -> SourceContribution:
    normal = Vector3.from_position(source.normal).normalized()
    displacement = sample - Vector3.from_position(source.position)
    signed_distance = displacement.dot(normal)
    field_scale = source.surface_charge_density_c_per_m2 / (2.0 * EPSILON_0)
    warnings = [
        (
            f"Source {source.id} infinite_plane potential uses V=0 at the plane; "
            "the absolute potential of an infinite plane has arbitrary reference."
        )
    ]
    if abs(signed_distance) <= MIN_SOURCE_DISTANCE_M:
        field = ZERO_VECTOR
        warnings.append(
            f"Sample lies on source {source.id} infinite_plane; discontinuous field was "
            "bounded to zero at the surface."
        )
    else:
        field = normal.scale(field_scale if signed_distance > 0.0 else -field_scale)
    potential = -field_scale * abs(signed_distance)
    metadata: dict[str, MetadataValue] = {"method": "analytic-infinite-plane"}
    return _contribution(source.id, source.kind, potential, field, warnings, metadata)


def _spherical_shell_contribution(
    source: SphericalShellSource,
    sample: Vector3,
) -> SourceContribution:
    charge_c = _shell_charge_c(source)
    center = Vector3.from_position(source.position)
    displacement = sample - center
    distance = displacement.magnitude()
    warnings: list[str] = []
    if distance < source.radius_m:
        potential = COULOMB_CONSTANT * charge_c / source.radius_m
        field = ZERO_VECTOR
        metadata: dict[str, MetadataValue] = {
            "method": "analytic-spherical-shell",
            "region": "inside",
        }
        return _contribution(source.id, source.kind, potential, field, warnings, metadata)
    if abs(distance - source.radius_m) <= MIN_SOURCE_DISTANCE_M:
        warnings.append(
            f"Sample is on source {source.id} spherical_shell; surface field is discontinuous."
        )
    if distance <= MIN_SOURCE_DISTANCE_M:
        potential = COULOMB_CONSTANT * charge_c / source.radius_m
        field = ZERO_VECTOR
    else:
        potential = COULOMB_CONSTANT * charge_c / distance
        field = displacement.scale(COULOMB_CONSTANT * charge_c / distance**3)
    metadata = {"method": "analytic-spherical-shell", "region": "outside"}
    return _contribution(source.id, source.kind, potential, field, warnings, metadata)


def _ring_charge_c(source: RingSource) -> float:
    if source.charge_c is not None:
        return source.charge_c
    return source.linear_charge_density_c_per_m * (2.0 * math.pi * source.radius_m)


def _line_charge_c(source: LineSegmentSource) -> float:
    if source.charge_c is not None:
        return source.charge_c
    return source.linear_charge_density_c_per_m * source.length_m


def _disk_charge_c(source: DiskSource) -> float:
    if source.charge_c is not None:
        return source.charge_c
    return source.surface_charge_density_c_per_m2 * math.pi * source.radius_m**2


def _shell_charge_c(source: SphericalShellSource) -> float:
    if source.charge_c is not None:
        return source.charge_c
    return source.surface_charge_density_c_per_m2 * 4.0 * math.pi * source.radius_m**2


def _zero_contribution(
    source_id: str,
    source_kind: str,
    warnings: list[str],
    metadata: dict[str, MetadataValue],
) -> SourceContribution:
    return _contribution(source_id, source_kind, 0.0, ZERO_VECTOR, warnings, metadata)


def _contribution(
    source_id: str,
    source_kind: str,
    potential: float,
    field: Vector3,
    warnings: list[str],
    metadata: dict[str, MetadataValue],
) -> SourceContribution:
    return SourceContribution(
        source_id=source_id,
        source_kind=source_kind,
        potential_v=potential,
        field_v_per_m=FieldVector.from_vector(field),
        field_magnitude_v_per_m=field.magnitude(),
        warnings=warnings,
        metadata=metadata,
    )


def _unique_warnings(warnings: Iterable[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for warning in warnings:
        if warning not in seen:
            unique.append(warning)
            seen.add(warning)
    return unique
