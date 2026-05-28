"""Small vector helpers for pure electrostatic calculations."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Vector3:
    """Immutable three-component vector in SI coordinates."""

    x: float
    y: float
    z: float

    @classmethod
    def from_components(cls, x: float, y: float, z: float) -> Vector3:
        return cls(float(x), float(y), float(z))

    @classmethod
    def from_position(cls, position: Any) -> Vector3:
        return cls.from_components(position.x, position.y, position.z)

    @classmethod
    def from_sample(cls, sample: Any) -> Vector3:
        if hasattr(sample, "x") and hasattr(sample, "y") and hasattr(sample, "z"):
            return cls.from_components(sample.x, sample.y, sample.z)
        if isinstance(sample, Mapping):
            return cls.from_components(sample["x"], sample["y"], sample["z"])
        if isinstance(sample, Sequence) and len(sample) == 3:
            return cls.from_components(sample[0], sample[1], sample[2])
        raise TypeError("Sample points must provide x, y, z coordinates.")

    def __add__(self, other: Vector3) -> Vector3:
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vector3) -> Vector3:
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __neg__(self) -> Vector3:
        return Vector3(-self.x, -self.y, -self.z)

    def scale(self, scalar: float) -> Vector3:
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)

    def dot(self, other: Vector3) -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: Vector3) -> Vector3:
        return Vector3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def magnitude(self) -> float:
        return math.sqrt(self.magnitude_squared())

    def magnitude_squared(self) -> float:
        return self.dot(self)

    def normalized(self) -> Vector3:
        max_abs = max(abs(self.x), abs(self.y), abs(self.z))
        if max_abs == 0.0:
            raise ValueError("Cannot normalize a zero vector.")
        scaled = Vector3(self.x / max_abs, self.y / max_abs, self.z / max_abs)
        scaled_magnitude = scaled.magnitude()
        return Vector3(
            scaled.x / scaled_magnitude,
            scaled.y / scaled_magnitude,
            scaled.z / scaled_magnitude,
        )

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}


ZERO_VECTOR = Vector3(0.0, 0.0, 0.0)


def orthonormal_basis_from_normal(normal: Vector3) -> tuple[Vector3, Vector3, Vector3]:
    """Return right-handed in-plane axes plus the normalized input normal."""
    unit_normal = normal.normalized()
    reference = Vector3(1.0, 0.0, 0.0)
    if abs(unit_normal.dot(reference)) > 0.9:
        reference = Vector3(0.0, 1.0, 0.0)
    axis_u = unit_normal.cross(reference).normalized()
    axis_v = unit_normal.cross(axis_u).normalized()
    return axis_u, axis_v, unit_normal
