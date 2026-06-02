from __future__ import annotations

import hashlib
import math
from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock

import numpy as np

from em_workbench.models import Scene
from em_workbench.physics.solver import (
    _disk_charge_c,
    _line_charge_c,
    _ring_charge_c,
    _settings_for_quality,
    _shell_charge_c,
)
from em_workbench.physics.vectors import Vector3, orthonormal_basis_from_normal


def dtype_for_quality(quality: str) -> np.dtype:
    return np.dtype(np.float32 if quality == "preview" else np.float64)


@dataclass(frozen=True)
class PackedScene:
    cache_key: str
    dtype: np.dtype
    source_ids: tuple[str, ...]
    element_positions: np.ndarray
    element_charges: np.ndarray
    element_source_indexes: np.ndarray
    plane_positions: np.ndarray
    plane_normals: np.ndarray
    plane_densities: np.ndarray
    plane_source_indexes: np.ndarray
    shell_positions: np.ndarray
    shell_radii: np.ndarray
    shell_charges: np.ndarray
    shell_source_indexes: np.ndarray


def _readonly(array: np.ndarray) -> np.ndarray:
    array.flags.writeable = False
    return array


def _cache_key(scene: Scene, quality: str, dtype: np.dtype) -> str:
    payload = f"{quality}|{dtype.str}|{scene.model_dump_json()}".encode()
    return hashlib.sha256(payload).hexdigest()


def _vector_array(values: list[Vector3], dtype: np.dtype) -> np.ndarray:
    return _readonly(
        np.asarray([[value.x, value.y, value.z] for value in values], dtype=dtype).reshape(-1, 3)
    )


def _scalar_array(values: list[float], dtype: np.dtype) -> np.ndarray:
    return _readonly(np.asarray(values, dtype=dtype))


def _index_array(values: list[int]) -> np.ndarray:
    return _readonly(np.asarray(values, dtype=np.int32))


def compile_scene(scene: Scene, *, quality: str) -> PackedScene:
    settings = _settings_for_quality(quality)
    dtype = dtype_for_quality(quality)
    element_positions: list[Vector3] = []
    element_charges: list[float] = []
    element_source_indexes: list[int] = []
    plane_positions: list[Vector3] = []
    plane_normals: list[Vector3] = []
    plane_densities: list[float] = []
    plane_source_indexes: list[int] = []
    shell_positions: list[Vector3] = []
    shell_radii: list[float] = []
    shell_charges: list[float] = []
    shell_source_indexes: list[int] = []

    for source_index, source in enumerate(scene.sources):
        center = Vector3.from_position(source.position)
        if source.kind == "point":
            element_positions.append(center)
            element_charges.append(source.charge_c)
            element_source_indexes.append(source_index)
        elif source.kind == "line_segment":
            total_charge = _line_charge_c(source)
            axis = Vector3.from_position(source.orientation).normalized()
            for index in range(settings["line_segments"]):
                offset = (
                    -0.5 * source.length_m
                    + (index + 0.5) * source.length_m / settings["line_segments"]
                )
                element_positions.append(center + axis.scale(offset))
                element_charges.append(total_charge / settings["line_segments"])
                element_source_indexes.append(source_index)
        elif source.kind == "ring":
            total_charge = _ring_charge_c(source)
            axis_u, axis_v, _unit_normal = orthonormal_basis_from_normal(
                Vector3.from_position(source.normal)
            )
            for index in range(settings["ring_segments"]):
                angle = 2.0 * math.pi * (index + 0.5) / settings["ring_segments"]
                point = center + axis_u.scale(math.cos(angle) * source.radius_m)
                point = point + axis_v.scale(math.sin(angle) * source.radius_m)
                element_positions.append(point)
                element_charges.append(total_charge / settings["ring_segments"])
                element_source_indexes.append(source_index)
        elif source.kind == "disk":
            total_charge = _disk_charge_c(source)
            surface_density = total_charge / (math.pi * source.radius_m**2)
            axis_u, axis_v, _unit_normal = orthonormal_basis_from_normal(
                Vector3.from_position(source.normal)
            )
            dr = source.radius_m / settings["disk_radial_segments"]
            dtheta = 2.0 * math.pi / settings["disk_angular_segments"]
            for radial_index in range(settings["disk_radial_segments"]):
                radius = (radial_index + 0.5) * dr
                dq = surface_density * radius * dr * dtheta
                for angular_index in range(settings["disk_angular_segments"]):
                    angle = (angular_index + 0.5) * dtheta
                    point = center + axis_u.scale(math.cos(angle) * radius)
                    point = point + axis_v.scale(math.sin(angle) * radius)
                    element_positions.append(point)
                    element_charges.append(dq)
                    element_source_indexes.append(source_index)
        elif source.kind == "infinite_plane":
            plane_positions.append(center)
            plane_normals.append(Vector3.from_position(source.normal).normalized())
            plane_densities.append(source.surface_charge_density_c_per_m2)
            plane_source_indexes.append(source_index)
        elif source.kind == "spherical_shell":
            shell_positions.append(center)
            shell_radii.append(source.radius_m)
            shell_charges.append(_shell_charge_c(source))
            shell_source_indexes.append(source_index)

    return PackedScene(
        cache_key=_cache_key(scene, quality, dtype),
        dtype=dtype,
        source_ids=tuple(source.id for source in scene.sources),
        element_positions=_vector_array(element_positions, dtype),
        element_charges=_scalar_array(element_charges, dtype),
        element_source_indexes=_index_array(element_source_indexes),
        plane_positions=_vector_array(plane_positions, dtype),
        plane_normals=_vector_array(plane_normals, dtype),
        plane_densities=_scalar_array(plane_densities, dtype),
        plane_source_indexes=_index_array(plane_source_indexes),
        shell_positions=_vector_array(shell_positions, dtype),
        shell_radii=_scalar_array(shell_radii, dtype),
        shell_charges=_scalar_array(shell_charges, dtype),
        shell_source_indexes=_index_array(shell_source_indexes),
    )


class PackedSceneCache:
    def __init__(self, limit: int = 16) -> None:
        self.limit = limit
        self._items: OrderedDict[str, PackedScene] = OrderedDict()
        self._lock = RLock()

    def get_or_compile(self, scene: Scene, *, quality: str) -> tuple[PackedScene, bool]:
        dtype = dtype_for_quality(quality)
        key = _cache_key(scene, quality, dtype)
        with self._lock:
            cached = self._items.get(key)
            if cached is not None:
                self._items.move_to_end(key)
                return cached, True
        packed = compile_scene(scene, quality=quality)
        with self._lock:
            self._items[key] = packed
            self._items.move_to_end(key)
            while len(self._items) > self.limit:
                self._items.popitem(last=False)
        return packed, False

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
