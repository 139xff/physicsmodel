from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock, RLock

import numpy as np

from em_workbench.physics.compute.field_lines import (
    FIELD_LINE_ADAPT_ERROR_FRACTION,
    FIELD_LINE_ADAPT_ERROR_MIN_M,
    FIELD_LINE_ADAPT_GROW_DOT,
    FIELD_LINE_ADAPT_RETRY_DOT,
    FIELD_LINE_ADAPT_SHRINK_DOT,
    FIELD_LINE_BASE_STEP_M,
    FIELD_LINE_ENDPOINT_MARGIN_M,
    FIELD_LINE_MAX_POINTS,
    FIELD_LINE_MAX_STEP_M,
    FIELD_LINE_MAX_STEPS,
    FIELD_LINE_MIN_FIELD,
    FIELD_LINE_MIN_STEP_M,
    FIELD_LINE_REVERSAL_DOT_LIMIT,
    FIELD_LINE_SELF_APPROACH_M,
    FIELD_LINE_START_RADIUS_M,
    STOP_DIRECTION_REVERSAL,
    STOP_FIELD_NULL,
    STOP_MAX_STEPS,
    STOP_OPPOSITE_CHARGE,
    STOP_POINT_BUDGET,
    STOP_SAME_CHARGE,
    STOP_SELF_APPROACH,
    STOP_VIEW_BOUNDARY,
    FieldLineKernelResult,
)
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


def build_field_lines_kernel(cuda):
    @cuda.jit(device=True)
    def direction_at(
        x,
        y,
        trace_direction,
        element_positions,
        element_charges,
        plane_positions,
        plane_normals,
        plane_densities,
        shell_positions,
        shell_radii,
        shell_charges,
    ):
        field_x = 0.0
        field_y = 0.0
        for element_index in range(element_positions.shape[0]):
            dx = x - element_positions[element_index, 0]
            dy = y - element_positions[element_index, 1]
            dz = -element_positions[element_index, 2]
            distance_sq = dx * dx + dy * dy + dz * dz
            if distance_sq > MIN_SOURCE_DISTANCE_SQ:
                distance = math.sqrt(distance_sq)
                field_scale = (
                    COULOMB_CONSTANT * element_charges[element_index] / (distance_sq * distance)
                )
                field_x += dx * field_scale
                field_y += dy * field_scale
        for plane_index in range(plane_positions.shape[0]):
            dx = x - plane_positions[plane_index, 0]
            dy = y - plane_positions[plane_index, 1]
            dz = -plane_positions[plane_index, 2]
            signed_distance = (
                dx * plane_normals[plane_index, 0]
                + dy * plane_normals[plane_index, 1]
                + dz * plane_normals[plane_index, 2]
            )
            if abs(signed_distance) > MIN_SOURCE_DISTANCE_M:
                direction = 1.0 if signed_distance > 0.0 else -1.0
                plane_scale = plane_densities[plane_index] / (2.0 * EPSILON_0)
                field_x += direction * plane_scale * plane_normals[plane_index, 0]
                field_y += direction * plane_scale * plane_normals[plane_index, 1]
        for shell_index in range(shell_positions.shape[0]):
            dx = x - shell_positions[shell_index, 0]
            dy = y - shell_positions[shell_index, 1]
            dz = -shell_positions[shell_index, 2]
            distance_sq = dx * dx + dy * dy + dz * dz
            distance = math.sqrt(distance_sq)
            if distance >= shell_radii[shell_index] and distance > MIN_SOURCE_DISTANCE_M:
                field_scale = (
                    COULOMB_CONSTANT * shell_charges[shell_index] / (distance_sq * distance)
                )
                field_x += dx * field_scale
                field_y += dy * field_scale
        magnitude = math.sqrt(field_x * field_x + field_y * field_y)
        if not math.isfinite(magnitude) or magnitude < FIELD_LINE_MIN_FIELD:
            return False, 0.0, 0.0
        return True, field_x * trace_direction / magnitude, field_y * trace_direction / magnitude

    @cuda.jit(device=True)
    def rk4_step(
        x,
        y,
        trace_direction,
        step_size,
        element_positions,
        element_charges,
        plane_positions,
        plane_normals,
        plane_densities,
        shell_positions,
        shell_radii,
        shell_charges,
    ):
        valid, k1x, k1y = direction_at(
            x,
            y,
            trace_direction,
            element_positions,
            element_charges,
            plane_positions,
            plane_normals,
            plane_densities,
            shell_positions,
            shell_radii,
            shell_charges,
        )
        if not valid:
            return False, x, y, 0.0, 0.0
        half_step = step_size * 0.5
        valid, k2x, k2y = direction_at(
            x + k1x * half_step,
            y + k1y * half_step,
            trace_direction,
            element_positions,
            element_charges,
            plane_positions,
            plane_normals,
            plane_densities,
            shell_positions,
            shell_radii,
            shell_charges,
        )
        if not valid:
            return False, x, y, 0.0, 0.0
        valid, k3x, k3y = direction_at(
            x + k2x * half_step,
            y + k2y * half_step,
            trace_direction,
            element_positions,
            element_charges,
            plane_positions,
            plane_normals,
            plane_densities,
            shell_positions,
            shell_radii,
            shell_charges,
        )
        if not valid:
            return False, x, y, 0.0, 0.0
        valid, k4x, k4y = direction_at(
            x + k3x * step_size,
            y + k3y * step_size,
            trace_direction,
            element_positions,
            element_charges,
            plane_positions,
            plane_normals,
            plane_densities,
            shell_positions,
            shell_radii,
            shell_charges,
        )
        if not valid:
            return False, x, y, 0.0, 0.0
        sixth_step = step_size / 6.0
        return (
            True,
            x + sixth_step * (k1x + 2.0 * k2x + 2.0 * k3x + k4x),
            y + sixth_step * (k1y + 2.0 * k2y + 2.0 * k3y + k4y),
            k1x,
            k1y,
        )

    @cuda.jit
    def kernel(
        seeds,
        trace_directions,
        seed_source_indexes,
        terminal_positions,
        terminal_charges,
        terminal_source_indexes,
        bounds,
        element_positions,
        element_charges,
        plane_positions,
        plane_normals,
        plane_densities,
        shell_positions,
        shell_radii,
        shell_charges,
        points,
        point_counts,
        stop_codes,
        terminal_indexes,
        min_direction_dots,
    ):
        candidate_index = cuda.grid(1)
        if candidate_index >= seeds.shape[0]:
            return
        x = seeds[candidate_index, 0]
        y = seeds[candidate_index, 1]
        trace_direction = trace_directions[candidate_index]
        seed_source_index = seed_source_indexes[candidate_index]
        points[candidate_index, 0, 0] = x
        points[candidate_index, 0, 1] = y
        point_count = 1
        previous_x = 0.0
        previous_y = 0.0
        has_previous = False
        step_size = FIELD_LINE_BASE_STEP_M
        min_direction_dot = 1.0
        stop_code = STOP_MAX_STEPS
        terminal_source_index = -1
        for _step in range(FIELD_LINE_MAX_STEPS):
            next_valid = False
            blocked_by_reversal = False
            next_x = x
            next_y = y
            direction_x = 0.0
            direction_y = 0.0
            direction_dot = 1.0
            for _attempt in range(6):
                valid, full_x, full_y, full_direction_x, full_direction_y = rk4_step(
                    x,
                    y,
                    trace_direction,
                    step_size,
                    element_positions,
                    element_charges,
                    plane_positions,
                    plane_normals,
                    plane_densities,
                    shell_positions,
                    shell_radii,
                    shell_charges,
                )
                if not valid:
                    break
                direction_dot = (
                    previous_x * full_direction_x + previous_y * full_direction_y
                    if has_previous
                    else 1.0
                )
                if direction_dot < FIELD_LINE_REVERSAL_DOT_LIMIT:
                    blocked_by_reversal = True
                    break
                next_x = full_x
                next_y = full_y
                direction_x = full_direction_x
                direction_y = full_direction_y
                if step_size > FIELD_LINE_MIN_STEP_M:
                    half_step = step_size * 0.5
                    valid, half_x, half_y, _half_direction_x, _half_direction_y = rk4_step(
                        x,
                        y,
                        trace_direction,
                        half_step,
                        element_positions,
                        element_charges,
                        plane_positions,
                        plane_normals,
                        plane_densities,
                        shell_positions,
                        shell_radii,
                        shell_charges,
                    )
                    if valid:
                        valid, second_x, second_y, _second_direction_x, _second_direction_y = (
                            rk4_step(
                                half_x,
                                half_y,
                                trace_direction,
                                half_step,
                                element_positions,
                                element_charges,
                                plane_positions,
                                plane_normals,
                                plane_densities,
                                shell_positions,
                                shell_radii,
                                shell_charges,
                            )
                        )
                    if not valid:
                        step_size = max(FIELD_LINE_MIN_STEP_M, step_size * 0.5)
                        continue
                    step_error = math.hypot(full_x - second_x, full_y - second_y)
                    allowed_error = max(
                        FIELD_LINE_ADAPT_ERROR_MIN_M,
                        step_size * FIELD_LINE_ADAPT_ERROR_FRACTION,
                    )
                    if step_error > allowed_error:
                        step_size = max(FIELD_LINE_MIN_STEP_M, step_size * 0.5)
                        continue
                    next_x = second_x
                    next_y = second_y
                if direction_dot < FIELD_LINE_ADAPT_RETRY_DOT and step_size > FIELD_LINE_MIN_STEP_M:
                    step_size = max(FIELD_LINE_MIN_STEP_M, step_size * 0.5)
                    continue
                next_valid = True
                break
            if not next_valid:
                stop_code = STOP_DIRECTION_REVERSAL if blocked_by_reversal else STOP_FIELD_NULL
                break
            near_previous = False
            for prior_index in range(max(0, point_count - 8)):
                dx = next_x - points[candidate_index, prior_index, 0]
                dy = next_y - points[candidate_index, prior_index, 1]
                if math.sqrt(dx * dx + dy * dy) < FIELD_LINE_SELF_APPROACH_M:
                    near_previous = True
                    break
            if near_previous:
                stop_code = STOP_SELF_APPROACH
                break
            x = next_x
            y = next_y
            points[candidate_index, point_count, 0] = x
            points[candidate_index, point_count, 1] = y
            point_count += 1
            previous_x = direction_x
            previous_y = direction_y
            has_previous = True
            min_direction_dot = min(min_direction_dot, direction_dot)
            if point_count >= FIELD_LINE_MAX_POINTS:
                stop_code = STOP_POINT_BUDGET
                break
            if direction_dot > FIELD_LINE_ADAPT_GROW_DOT:
                step_size = min(FIELD_LINE_MAX_STEP_M, step_size * 1.35)
            elif direction_dot < FIELD_LINE_ADAPT_SHRINK_DOT:
                step_size = max(FIELD_LINE_MIN_STEP_M, step_size * 0.7)
            margin = FIELD_LINE_MAX_STEP_M * 2.0
            if (
                x < bounds[0] - margin
                or x > bounds[1] + margin
                or y < bounds[2] - margin
                or y > bounds[3] + margin
            ):
                stop_code = STOP_VIEW_BOUNDARY
                break
            nearest_index = -1
            nearest_distance = math.inf
            for terminal_index in range(terminal_positions.shape[0]):
                if terminal_source_indexes[terminal_index] == seed_source_index:
                    continue
                dx = x - terminal_positions[terminal_index, 0]
                dy = y - terminal_positions[terminal_index, 1]
                distance = math.sqrt(dx * dx + dy * dy)
                if (
                    distance <= FIELD_LINE_START_RADIUS_M + FIELD_LINE_ENDPOINT_MARGIN_M
                    and distance < nearest_distance
                ):
                    nearest_index = terminal_index
                    nearest_distance = distance
            if nearest_index >= 0:
                terminal_source_index = terminal_source_indexes[nearest_index]
                terminal_sign = -1.0 if trace_direction > 0.0 else 1.0
                source_sign = 1.0 if terminal_charges[nearest_index] >= 0.0 else -1.0
                stop_code = (
                    STOP_OPPOSITE_CHARGE if source_sign == terminal_sign else STOP_SAME_CHARGE
                )
                break
        point_counts[candidate_index] = point_count
        stop_codes[candidate_index] = stop_code
        terminal_indexes[candidate_index] = terminal_source_index
        min_direction_dots[candidate_index] = min_direction_dot

    return kernel


_FIELD_LINES_KERNEL = None
_FIELD_LINES_KERNEL_LOCK = Lock()


def _field_lines_kernel(cuda):
    global _FIELD_LINES_KERNEL
    with _FIELD_LINES_KERNEL_LOCK:
        if _FIELD_LINES_KERNEL is None:
            _FIELD_LINES_KERNEL = build_field_lines_kernel(cuda)
        return _FIELD_LINES_KERNEL


def evaluate_field_lines_cuda(
    packed: PackedScene,
    seeds: np.ndarray,
    trace_directions: np.ndarray,
    seed_source_indexes: np.ndarray,
    terminal_positions: np.ndarray,
    terminal_charges: np.ndarray,
    terminal_source_indexes: np.ndarray,
    *,
    bounds: tuple[float, float, float, float],
    device_cache: DeviceSceneCache,
) -> tuple[FieldLineKernelResult, bool]:
    cuda = load_cuda()
    device_scene, cache_hit = device_cache.get_or_copy(packed, cuda)
    prepared_seeds = np.ascontiguousarray(seeds, dtype=packed.dtype)
    candidate_count = prepared_seeds.shape[0]
    points_device = cuda.device_array(
        (candidate_count, FIELD_LINE_MAX_STEPS + 1, 2),
        dtype=packed.dtype,
    )
    point_counts_device = cuda.device_array(candidate_count, dtype=np.int32)
    stop_codes_device = cuda.device_array(candidate_count, dtype=np.int32)
    terminal_indexes_device = cuda.device_array(candidate_count, dtype=np.int32)
    min_direction_dots_device = cuda.device_array(candidate_count, dtype=packed.dtype)
    blocks_per_grid = (candidate_count + THREADS_PER_BLOCK - 1) // THREADS_PER_BLOCK
    _field_lines_kernel(cuda)[blocks_per_grid, THREADS_PER_BLOCK](
        cuda.to_device(prepared_seeds),
        cuda.to_device(np.ascontiguousarray(trace_directions, dtype=packed.dtype)),
        cuda.to_device(np.ascontiguousarray(seed_source_indexes, dtype=np.int32)),
        cuda.to_device(np.ascontiguousarray(terminal_positions, dtype=packed.dtype)),
        cuda.to_device(np.ascontiguousarray(terminal_charges, dtype=packed.dtype)),
        cuda.to_device(np.ascontiguousarray(terminal_source_indexes, dtype=np.int32)),
        cuda.to_device(np.asarray(bounds, dtype=packed.dtype)),
        device_scene.element_positions,
        device_scene.element_charges,
        device_scene.plane_positions,
        device_scene.plane_normals,
        device_scene.plane_densities,
        device_scene.shell_positions,
        device_scene.shell_radii,
        device_scene.shell_charges,
        points_device,
        point_counts_device,
        stop_codes_device,
        terminal_indexes_device,
        min_direction_dots_device,
    )
    cuda.synchronize()
    return (
        FieldLineKernelResult(
            points=points_device.copy_to_host(),
            point_counts=point_counts_device.copy_to_host(),
            stop_codes=stop_codes_device.copy_to_host(),
            terminal_source_indexes=terminal_indexes_device.copy_to_host(),
            min_direction_dots=min_direction_dots_device.copy_to_host(),
        ),
        cache_hit,
    )
