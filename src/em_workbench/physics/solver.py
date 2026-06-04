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
from em_workbench.physics.compute.contracts import BackendPolicy, ExecutionMetadata
from em_workbench.physics.integration import (
    disk_charge_c,
    disk_elements,
    line_charge_c,
    line_segment_elements,
    ring_charge_c,
    ring_elements,
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
    execution: ExecutionMetadata | None = None


def evaluate_scene(
    scene: Scene,
    sample_points: Iterable[Position | dict[str, float] | tuple[float, float, float]],
    *,
    quality: SolverQuality = "preview",
    request_id: str | None = None,
    backend: BackendPolicy = "auto",
) -> FieldEvaluationResponse:
    """Evaluate a scene through the selected high-performance backend."""
    from em_workbench.physics.compute.dispatcher import DEFAULT_COMPUTE_SERVICE

    return DEFAULT_COMPUTE_SERVICE.evaluate_scene(
        scene,
        sample_points,
        quality=quality,
        request_id=request_id,
        backend=backend,
    )


def evaluate_scene_scalar(
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
    center = Vector3.from_position(source.position)
    _axis_u, _axis_v, unit_normal = orthonormal_basis_from_normal(
        Vector3.from_position(source.normal)
    )
    potential = 0.0
    field = ZERO_VECTOR
    warnings: list[str] = [
        (
            f"Source {source.id} ring uses {segment_count} point-charge nodes for "
            "quadrature integration; this finite-segment approximation preserves the "
            "near-singular trend but does not claim analytic precision off axis."
        )
    ]
    if _sample_is_near_ring(source, sample, center, unit_normal):
        warnings.append(
            f"Sample is near source {source.id} ring geometry; quadrature result is near "
            "singular and should be treated as a limitation."
        )
    for element in ring_elements(source, segment_count):
        partial = _point_charge_contribution(
            source_id=source.id,
            source_kind=source.kind,
            charge_c=element.charge_c,
            charge_position=element.position,
            sample=sample,
            metadata={"method": "integrated-ring-node"},
        )
        potential += partial.potential_v
        field = field + Vector3.from_sample(partial.field_v_per_m)
        warnings.extend(partial.warnings)
    metadata: dict[str, MetadataValue] = {
        "method": "integrated-ring",
        "quadrature": "uniform-azimuthal",
        "integration_nodes": segment_count,
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
    center = Vector3.from_position(source.position)
    axis = Vector3.from_position(source.orientation).normalized()
    potential = 0.0
    field = ZERO_VECTOR
    warnings = [
        (
            f"Source {source.id} line_segment uses {segment_count} Gauss-Legendre "
            "point-charge nodes for quadrature integration; numerical approximation "
            "near the charged segment is intentionally left steep."
        )
    ]
    if _sample_is_near_line_segment(source, sample, center, axis):
        warnings.append(
            f"Sample is near source {source.id} line_segment geometry; quadrature result "
            "is near singular and should be treated as a limitation."
        )
    for element in line_segment_elements(source, segment_count):
        partial = _point_charge_contribution(
            source_id=source.id,
            source_kind=source.kind,
            charge_c=element.charge_c,
            charge_position=element.position,
            sample=sample,
            metadata={"method": "integrated-line-segment-node"},
        )
        potential += partial.potential_v
        field = field + Vector3.from_sample(partial.field_v_per_m)
        warnings.extend(partial.warnings)
    metadata: dict[str, MetadataValue] = {
        "method": "integrated-line-segment",
        "quadrature": "gauss-legendre",
        "integration_nodes": segment_count,
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
    potential = 0.0
    field = ZERO_VECTOR
    integration_nodes = radial_segments * angular_segments
    warnings = [
        (
            f"Source {source.id} disk uses {radial_segments}x{angular_segments} "
            "Gauss-Legendre radial by uniform-azimuthal point-charge nodes for "
            "quadrature integration; numerical approximation near the disk is "
            "intentionally left steep."
        )
    ]
    for element in disk_elements(source, radial_segments, angular_segments):
        partial = _point_charge_contribution(
            source_id=source.id,
            source_kind=source.kind,
            charge_c=element.charge_c,
            charge_position=element.position,
            sample=sample,
            metadata={"method": "integrated-disk-node"},
        )
        potential += partial.potential_v
        field = field + Vector3.from_sample(partial.field_v_per_m)
        warnings.extend(partial.warnings)
    metadata: dict[str, MetadataValue] = {
        "method": "integrated-disk",
        "quadrature": "gauss-legendre-radial-uniform-azimuthal",
        "integration_nodes": integration_nodes,
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
    return ring_charge_c(source)


def _line_charge_c(source: LineSegmentSource) -> float:
    return line_charge_c(source)


def _disk_charge_c(source: DiskSource) -> float:
    return disk_charge_c(source)


def _shell_charge_c(source: SphericalShellSource) -> float:
    if source.charge_c is not None:
        return source.charge_c
    return source.surface_charge_density_c_per_m2 * 4.0 * math.pi * source.radius_m**2


def _sample_is_near_ring(
    source: RingSource,
    sample: Vector3,
    center: Vector3,
    unit_normal: Vector3,
) -> bool:
    displacement = sample - center
    plane_distance = displacement.dot(unit_normal)
    in_plane = displacement - unit_normal.scale(plane_distance)
    radial_distance = in_plane.magnitude()
    return (
        abs(plane_distance) <= MIN_SOURCE_DISTANCE_M
        and abs(radial_distance - source.radius_m) <= MIN_SOURCE_DISTANCE_M
    )


def _sample_is_near_line_segment(
    source: LineSegmentSource,
    sample: Vector3,
    center: Vector3,
    axis: Vector3,
) -> bool:
    displacement = sample - center
    projected_distance = displacement.dot(axis)
    nearest_axis_point = center + axis.scale(projected_distance)
    perpendicular_distance = (sample - nearest_axis_point).magnitude()
    half_length = 0.5 * source.length_m
    return (
        perpendicular_distance <= MIN_SOURCE_DISTANCE_M
        and -half_length - MIN_SOURCE_DISTANCE_M
        <= projected_distance
        <= half_length + MIN_SOURCE_DISTANCE_M
    )


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
