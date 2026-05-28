"""Typed scene contracts for editable electrostatic source configurations."""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

SourceKind = Literal[
    "point",
    "line_segment",
    "ring",
    "disk",
    "infinite_plane",
    "spherical_shell",
]

PositiveMeters = Annotated[FiniteFloat, Field(gt=0)]


class StrictModel(BaseModel):
    """Base model that rejects accidental contract drift."""

    model_config = ConfigDict(extra="forbid", strict=True)


class Position(StrictModel):
    """Three-dimensional position in SI meters."""

    x: FiniteFloat
    y: FiniteFloat
    z: FiniteFloat
    unit: Literal["m"] = "m"


class UnitVector3(StrictModel):
    """Dimensionless vector normalized on ingestion."""

    x: FiniteFloat
    y: FiniteFloat
    z: FiniteFloat

    @model_validator(mode="after")
    def normalize(self) -> UnitVector3:
        components = (self.x, self.y, self.z)
        max_abs = max(abs(component) for component in components)
        if not math.isfinite(max_abs):
            raise ValueError("Direction vector components must be finite.")
        if max_abs == 0.0:
            raise ValueError("Direction vector cannot be zero.")
        scaled = tuple(component / max_abs for component in components)
        scaled_magnitude = math.hypot(*scaled)
        if not math.isfinite(scaled_magnitude) or scaled_magnitude == 0.0:
            raise ValueError("Direction vector magnitude must be finite and nonzero.")
        self.x = scaled[0] / scaled_magnitude
        self.y = scaled[1] / scaled_magnitude
        self.z = scaled[2] / scaled_magnitude
        return self


class SourceBase(StrictModel):
    """Common editable source fields."""

    id: Annotated[str, Field(min_length=1)]
    kind: SourceKind
    label: Annotated[str, Field(min_length=1)]
    position: Position


def _require_exactly_one_charge_parameter(
    source_kind: str,
    values: list[tuple[str, float | None]],
) -> None:
    provided = [name for name, value in values if value is not None]
    if len(provided) != 1:
        choices = ", ".join(name for name, _value in values)
        raise ValueError(f"{source_kind} sources require exactly one of {choices}.")


class PointChargeSource(SourceBase):
    """Discrete point charge with total charge in coulombs."""

    kind: Literal["point"]
    charge_c: FiniteFloat


class LineSegmentSource(SourceBase):
    """Uniform charged line segment."""

    kind: Literal["line_segment"]
    orientation: UnitVector3
    length_m: PositiveMeters
    charge_c: FiniteFloat | None = None
    linear_charge_density_c_per_m: FiniteFloat | None = None

    @model_validator(mode="after")
    def validate_charge_parameter(self) -> LineSegmentSource:
        _require_exactly_one_charge_parameter(
            "line_segment",
            [
                ("charge_c", self.charge_c),
                ("linear_charge_density_c_per_m", self.linear_charge_density_c_per_m),
            ],
        )
        return self


class RingSource(SourceBase):
    """Uniform charged circular ring with arbitrary normal direction."""

    kind: Literal["ring"]
    normal: UnitVector3
    radius_m: PositiveMeters
    charge_c: FiniteFloat | None = None
    linear_charge_density_c_per_m: FiniteFloat | None = None

    @model_validator(mode="after")
    def validate_charge_parameter(self) -> RingSource:
        _require_exactly_one_charge_parameter(
            "ring",
            [
                ("charge_c", self.charge_c),
                ("linear_charge_density_c_per_m", self.linear_charge_density_c_per_m),
            ],
        )
        return self


class DiskSource(SourceBase):
    """Uniform charged disk with arbitrary normal direction."""

    kind: Literal["disk"]
    normal: UnitVector3
    radius_m: PositiveMeters
    charge_c: FiniteFloat | None = None
    surface_charge_density_c_per_m2: FiniteFloat | None = None

    @model_validator(mode="after")
    def validate_charge_parameter(self) -> DiskSource:
        _require_exactly_one_charge_parameter(
            "disk",
            [
                ("charge_c", self.charge_c),
                ("surface_charge_density_c_per_m2", self.surface_charge_density_c_per_m2),
            ],
        )
        return self


class InfinitePlaneSource(SourceBase):
    """Uniform infinite plane; display extent is visual only."""

    kind: Literal["infinite_plane"]
    normal: UnitVector3
    display_extent_m: PositiveMeters
    surface_charge_density_c_per_m2: FiniteFloat
    physical_model: Literal["infinite"] = "infinite"


class SphericalShellSource(SourceBase):
    """Uniform spherical shell; rotation is not part of the physical contract."""

    kind: Literal["spherical_shell"]
    radius_m: PositiveMeters
    charge_c: FiniteFloat | None = None
    surface_charge_density_c_per_m2: FiniteFloat | None = None

    @model_validator(mode="after")
    def validate_charge_parameter(self) -> SphericalShellSource:
        _require_exactly_one_charge_parameter(
            "spherical_shell",
            [
                ("charge_c", self.charge_c),
                ("surface_charge_density_c_per_m2", self.surface_charge_density_c_per_m2),
            ],
        )
        return self


ElectrostaticSource = Annotated[
    PointChargeSource
    | LineSegmentSource
    | RingSource
    | DiskSource
    | InfinitePlaneSource
    | SphericalShellSource,
    Field(discriminator="kind"),
]


class Scene(StrictModel):
    """Editable electrostatic scene JSON shared by presets and API validation."""

    schema_version: Literal[1] = 1
    id: Annotated[str, Field(min_length=1)]
    title: Annotated[str, Field(min_length=1)]
    sources: list[ElectrostaticSource] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_source_ids(self) -> Scene:
        seen: set[str] = set()
        for source in self.sources:
            if source.id in seen:
                raise ValueError(f"Duplicate source id: {source.id}.")
            seen.add(source.id)
        return self


class PresetSummary(StrictModel):
    """Stable preset index payload."""

    id: Annotated[str, Field(min_length=1)]
    title: Annotated[str, Field(min_length=1)]
    description: Annotated[str, Field(min_length=1)]
    source_count: int
    source_kinds: list[SourceKind]


class Preset(StrictModel):
    """Editable preset scene payload."""

    id: Annotated[str, Field(min_length=1)]
    title: Annotated[str, Field(min_length=1)]
    description: Annotated[str, Field(min_length=1)]
    scene: Scene

    def to_summary(self) -> PresetSummary:
        return PresetSummary(
            id=self.id,
            title=self.title,
            description=self.description,
            source_count=len(self.scene.sources),
            source_kinds=[source.kind for source in self.scene.sources],
        )


class SceneValidationResponse(StrictModel):
    """Positive validation response; invalid scenes use FastAPI's 422 response."""

    valid: Literal[True]
    scene: Scene
    source_count: int
    source_kinds: list[SourceKind]
