from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock, RLock

import numpy as np

from em_workbench.physics.compute.packed_scene import PackedScene
from em_workbench.physics.solver import COULOMB_CONSTANT, EPSILON_0, MIN_SOURCE_DISTANCE_M

MIN_SOURCE_DISTANCE_SQ = MIN_SOURCE_DISTANCE_M**2
CUDA_CHUNK_SIZE = 65_536
THREADS_PER_BLOCK = 128


class CudaUnavailable(RuntimeError):
    """Raised when optional CUDA execution cannot run safely."""


def load_cuda():
    try:
        from numba import cuda
    except Exception as error:
        raise CudaUnavailable(f"CUDA package unavailable: {error}") from error
    if not cuda.is_available():
        raise CudaUnavailable("CUDA runtime unavailable.")
    return cuda


@dataclass(frozen=True)
class DevicePackedScene:
    cache_key: str
    element_positions: object
    element_charges: object
    plane_positions: object
    plane_normals: object
    plane_densities: object
    shell_positions: object
    shell_radii: object
    shell_charges: object


class DeviceSceneCache:
    def __init__(self, limit: int = 8) -> None:
        self.limit = limit
        self._items: OrderedDict[str, DevicePackedScene] = OrderedDict()
        self._lock = RLock()

    def get_or_copy(self, packed: PackedScene, cuda) -> tuple[DevicePackedScene, bool]:
        with self._lock:
            cached = self._items.get(packed.cache_key)
            if cached is not None:
                self._items.move_to_end(packed.cache_key)
                return cached, True
            copied = DevicePackedScene(
                cache_key=packed.cache_key,
                element_positions=cuda.to_device(packed.element_positions),
                element_charges=cuda.to_device(packed.element_charges),
                plane_positions=cuda.to_device(packed.plane_positions),
                plane_normals=cuda.to_device(packed.plane_normals),
                plane_densities=cuda.to_device(packed.plane_densities),
                shell_positions=cuda.to_device(packed.shell_positions),
                shell_radii=cuda.to_device(packed.shell_radii),
                shell_charges=cuda.to_device(packed.shell_charges),
            )
            self._items[packed.cache_key] = copied
            self._items.move_to_end(packed.cache_key)
            while len(self._items) > self.limit:
                self._items.popitem(last=False)
            return copied, False

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


def build_totals_kernel(cuda):
    @cuda.jit
    def kernel(
        points,
        element_positions,
        element_charges,
        plane_positions,
        plane_normals,
        plane_densities,
        shell_positions,
        shell_radii,
        shell_charges,
        potential,
        field,
    ):
        sample_index = cuda.grid(1)
        if sample_index >= points.shape[0]:
            return
        potential[sample_index] = 0.0
        field[sample_index, 0] = 0.0
        field[sample_index, 1] = 0.0
        field[sample_index, 2] = 0.0
        x = points[sample_index, 0]
        y = points[sample_index, 1]
        z = points[sample_index, 2]
        for element_index in range(element_positions.shape[0]):
            dx = x - element_positions[element_index, 0]
            dy = y - element_positions[element_index, 1]
            dz = z - element_positions[element_index, 2]
            distance_sq = dx * dx + dy * dy + dz * dz
            if distance_sq > MIN_SOURCE_DISTANCE_SQ:
                distance = math.sqrt(distance_sq)
                scale = COULOMB_CONSTANT * element_charges[element_index]
                potential[sample_index] += scale / distance
                field_scale = scale / (distance_sq * distance)
                field[sample_index, 0] += dx * field_scale
                field[sample_index, 1] += dy * field_scale
                field[sample_index, 2] += dz * field_scale

        for plane_index in range(plane_positions.shape[0]):
            dx = x - plane_positions[plane_index, 0]
            dy = y - plane_positions[plane_index, 1]
            dz = z - plane_positions[plane_index, 2]
            signed_distance = (
                dx * plane_normals[plane_index, 0]
                + dy * plane_normals[plane_index, 1]
                + dz * plane_normals[plane_index, 2]
            )
            plane_scale = plane_densities[plane_index] / (2.0 * EPSILON_0)
            potential[sample_index] -= plane_scale * abs(signed_distance)
            if abs(signed_distance) > MIN_SOURCE_DISTANCE_M:
                direction = 1.0 if signed_distance > 0.0 else -1.0
                field[sample_index, 0] += (
                    direction * plane_scale * plane_normals[plane_index, 0]
                )
                field[sample_index, 1] += (
                    direction * plane_scale * plane_normals[plane_index, 1]
                )
                field[sample_index, 2] += (
                    direction * plane_scale * plane_normals[plane_index, 2]
                )

        for shell_index in range(shell_positions.shape[0]):
            dx = x - shell_positions[shell_index, 0]
            dy = y - shell_positions[shell_index, 1]
            dz = z - shell_positions[shell_index, 2]
            distance_sq = dx * dx + dy * dy + dz * dz
            distance = math.sqrt(distance_sq)
            shell_scale = COULOMB_CONSTANT * shell_charges[shell_index]
            if distance < shell_radii[shell_index]:
                potential[sample_index] += shell_scale / shell_radii[shell_index]
            elif distance > MIN_SOURCE_DISTANCE_M:
                potential[sample_index] += shell_scale / distance
                field_scale = shell_scale / (distance_sq * distance)
                field[sample_index, 0] += dx * field_scale
                field[sample_index, 1] += dy * field_scale
                field[sample_index, 2] += dz * field_scale
    return kernel


_TOTALS_KERNEL = None
_TOTALS_KERNEL_LOCK = Lock()


def _totals_kernel(cuda):
    global _TOTALS_KERNEL
    with _TOTALS_KERNEL_LOCK:
        if _TOTALS_KERNEL is None:
            _TOTALS_KERNEL = build_totals_kernel(cuda)
        return _TOTALS_KERNEL


def evaluate_totals_cuda(
    packed: PackedScene,
    points: np.ndarray,
    *,
    device_cache: DeviceSceneCache,
) -> tuple[np.ndarray, np.ndarray, bool]:
    cuda = load_cuda()
    prepared = np.ascontiguousarray(points, dtype=packed.dtype)
    if prepared.ndim != 2 or prepared.shape[1] != 3:
        raise ValueError("Sample points must have shape (sample_count, 3).")
    device_scene, cache_hit = device_cache.get_or_copy(packed, cuda)
    potential = np.empty(prepared.shape[0], dtype=packed.dtype)
    field = np.empty((prepared.shape[0], 3), dtype=packed.dtype)
    kernel = _totals_kernel(cuda)
    for start in range(0, prepared.shape[0], CUDA_CHUNK_SIZE):
        stop = min(start + CUDA_CHUNK_SIZE, prepared.shape[0])
        chunk = prepared[start:stop]
        points_device = cuda.to_device(chunk)
        potential_device = cuda.device_array(chunk.shape[0], dtype=packed.dtype)
        field_device = cuda.device_array((chunk.shape[0], 3), dtype=packed.dtype)
        blocks_per_grid = (chunk.shape[0] + THREADS_PER_BLOCK - 1) // THREADS_PER_BLOCK
        kernel[blocks_per_grid, THREADS_PER_BLOCK](
            points_device,
            device_scene.element_positions,
            device_scene.element_charges,
            device_scene.plane_positions,
            device_scene.plane_normals,
            device_scene.plane_densities,
            device_scene.shell_positions,
            device_scene.shell_radii,
            device_scene.shell_charges,
            potential_device,
            field_device,
        )
        cuda.synchronize()
        potential[start:stop] = potential_device.copy_to_host()
        field[start:stop] = field_device.copy_to_host()
    return potential, field, cache_hit
