from __future__ import annotations

import math

import numpy as np
from numba import njit, prange

from em_workbench.physics.compute.packed_scene import PackedScene
from em_workbench.physics.solver import COULOMB_CONSTANT, EPSILON_0, MIN_SOURCE_DISTANCE_M

MIN_SOURCE_DISTANCE_SQ = MIN_SOURCE_DISTANCE_M**2


@njit(cache=True, parallel=True)
def _evaluate_totals_kernel(
    points,
    element_positions,
    element_charges,
    plane_positions,
    plane_normals,
    plane_densities,
    shell_positions,
    shell_radii,
    shell_charges,
):
    sample_count = points.shape[0]
    potential = np.zeros(sample_count, dtype=points.dtype)
    field = np.zeros((sample_count, 3), dtype=points.dtype)
    for sample_index in prange(sample_count):
        x = points[sample_index, 0]
        y = points[sample_index, 1]
        z = points[sample_index, 2]
        for element_index in range(element_positions.shape[0]):
            dx = x - element_positions[element_index, 0]
            dy = y - element_positions[element_index, 1]
            dz = z - element_positions[element_index, 2]
            distance_sq = dx * dx + dy * dy + dz * dz
            if distance_sq <= MIN_SOURCE_DISTANCE_SQ:
                continue
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
    return potential, field


@njit(cache=True, parallel=True)
def _evaluate_contributions_kernel(
    points,
    source_count,
    element_positions,
    element_charges,
    element_source_indexes,
    plane_positions,
    plane_normals,
    plane_densities,
    plane_source_indexes,
    shell_positions,
    shell_radii,
    shell_charges,
    shell_source_indexes,
):
    sample_count = points.shape[0]
    contributions = np.zeros((sample_count, source_count, 4), dtype=points.dtype)
    for sample_index in prange(sample_count):
        x = points[sample_index, 0]
        y = points[sample_index, 1]
        z = points[sample_index, 2]
        for element_index in range(element_positions.shape[0]):
            dx = x - element_positions[element_index, 0]
            dy = y - element_positions[element_index, 1]
            dz = z - element_positions[element_index, 2]
            distance_sq = dx * dx + dy * dy + dz * dz
            if distance_sq <= MIN_SOURCE_DISTANCE_SQ:
                continue
            distance = math.sqrt(distance_sq)
            scale = COULOMB_CONSTANT * element_charges[element_index]
            source_index = element_source_indexes[element_index]
            contributions[sample_index, source_index, 0] += scale / distance
            field_scale = scale / (distance_sq * distance)
            contributions[sample_index, source_index, 1] += dx * field_scale
            contributions[sample_index, source_index, 2] += dy * field_scale
            contributions[sample_index, source_index, 3] += dz * field_scale

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
            source_index = plane_source_indexes[plane_index]
            contributions[sample_index, source_index, 0] -= plane_scale * abs(signed_distance)
            if abs(signed_distance) > MIN_SOURCE_DISTANCE_M:
                direction = 1.0 if signed_distance > 0.0 else -1.0
                contributions[sample_index, source_index, 1] += (
                    direction * plane_scale * plane_normals[plane_index, 0]
                )
                contributions[sample_index, source_index, 2] += (
                    direction * plane_scale * plane_normals[plane_index, 1]
                )
                contributions[sample_index, source_index, 3] += (
                    direction * plane_scale * plane_normals[plane_index, 2]
                )

        for shell_index in range(shell_positions.shape[0]):
            dx = x - shell_positions[shell_index, 0]
            dy = y - shell_positions[shell_index, 1]
            dz = z - shell_positions[shell_index, 2]
            distance_sq = dx * dx + dy * dy + dz * dz
            distance = math.sqrt(distance_sq)
            shell_scale = COULOMB_CONSTANT * shell_charges[shell_index]
            source_index = shell_source_indexes[shell_index]
            if distance < shell_radii[shell_index]:
                contributions[sample_index, source_index, 0] += (
                    shell_scale / shell_radii[shell_index]
                )
            elif distance > MIN_SOURCE_DISTANCE_M:
                contributions[sample_index, source_index, 0] += shell_scale / distance
                field_scale = shell_scale / (distance_sq * distance)
                contributions[sample_index, source_index, 1] += dx * field_scale
                contributions[sample_index, source_index, 2] += dy * field_scale
                contributions[sample_index, source_index, 3] += dz * field_scale
    return contributions


def _points_for_packed(packed: PackedScene, points: np.ndarray) -> np.ndarray:
    prepared = np.ascontiguousarray(points, dtype=packed.dtype)
    if prepared.ndim != 2 or prepared.shape[1] != 3:
        raise ValueError("Sample points must have shape (sample_count, 3).")
    return prepared


def evaluate_totals_cpu(packed: PackedScene, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    prepared = _points_for_packed(packed, points)
    return _evaluate_totals_kernel(
        prepared,
        packed.element_positions,
        packed.element_charges,
        packed.plane_positions,
        packed.plane_normals,
        packed.plane_densities,
        packed.shell_positions,
        packed.shell_radii,
        packed.shell_charges,
    )


def evaluate_contributions_cpu(packed: PackedScene, points: np.ndarray) -> np.ndarray:
    prepared = _points_for_packed(packed, points)
    return _evaluate_contributions_kernel(
        prepared,
        len(packed.source_ids),
        packed.element_positions,
        packed.element_charges,
        packed.element_source_indexes,
        packed.plane_positions,
        packed.plane_normals,
        packed.plane_densities,
        packed.plane_source_indexes,
        packed.shell_positions,
        packed.shell_radii,
        packed.shell_charges,
        packed.shell_source_indexes,
    )
