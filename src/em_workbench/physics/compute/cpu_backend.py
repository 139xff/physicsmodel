from __future__ import annotations

import math

import numpy as np
from numba import njit, prange

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


@njit(cache=True)
def _enforce_hard_sphere_contacts(
    previous_position,
    position,
    velocity,
    hard_sphere_positions,
    hard_sphere_radii,
):
    contacted = False
    for sphere_index in range(hard_sphere_positions.shape[0]):
        radius = hard_sphere_radii[sphere_index]
        center_x = hard_sphere_positions[sphere_index, 0]
        center_y = hard_sphere_positions[sphere_index, 1]
        center_z = hard_sphere_positions[sphere_index, 2]
        dx = position[0] - center_x
        dy = position[1] - center_y
        dz = position[2] - center_z
        radius_sq = radius * radius
        distance_sq = dx * dx + dy * dy + dz * dz
        contact_x = position[0]
        contact_y = position[1]
        contact_z = position[2]
        has_contact = False

        motion_x = position[0] - previous_position[0]
        motion_y = position[1] - previous_position[1]
        motion_z = position[2] - previous_position[2]
        motion_sq = motion_x * motion_x + motion_y * motion_y + motion_z * motion_z
        if motion_sq > 1.0e-30:
            previous_dx = previous_position[0] - center_x
            previous_dy = previous_position[1] - center_y
            previous_dz = previous_position[2] - center_z
            previous_distance_offset = (
                previous_dx * previous_dx
                + previous_dy * previous_dy
                + previous_dz * previous_dz
                - radius_sq
            )
            b = 2.0 * (previous_dx * motion_x + previous_dy * motion_y + previous_dz * motion_z)
            discriminant = b * b - 4.0 * motion_sq * previous_distance_offset
            if discriminant >= 0.0:
                root = math.sqrt(discriminant)
                first = (-b - root) / (2.0 * motion_sq)
                second = (-b + root) / (2.0 * motion_sq)
                contact_t = -1.0
                if first >= 0.0 and first <= 1.0:
                    contact_t = first
                elif (
                    previous_distance_offset < 0.0
                    and second >= 0.0
                    and second <= 1.0
                ):
                    contact_t = second
                if contact_t >= 0.0:
                    contact_x = previous_position[0] + motion_x * contact_t
                    contact_y = previous_position[1] + motion_y * contact_t
                    contact_z = previous_position[2] + motion_z * contact_t
                    has_contact = True

        if not has_contact and distance_sq < radius_sq:
            has_contact = True

        if not has_contact:
            continue
        contacted = True

        contact_dx = contact_x - center_x
        contact_dy = contact_y - center_y
        contact_dz = contact_z - center_z
        contact_distance_sq = (
            contact_dx * contact_dx + contact_dy * contact_dy + contact_dz * contact_dz
        )
        if contact_distance_sq <= MIN_SOURCE_DISTANCE_SQ:
            velocity_magnitude = math.sqrt(
                velocity[0] * velocity[0] + velocity[1] * velocity[1] + velocity[2] * velocity[2]
            )
            if velocity_magnitude > 0.0:
                nx = -velocity[0] / velocity_magnitude
                ny = -velocity[1] / velocity_magnitude
                nz = -velocity[2] / velocity_magnitude
            else:
                nx = 1.0
                ny = 0.0
                nz = 0.0
        else:
            contact_distance = math.sqrt(contact_distance_sq)
            nx = contact_dx / contact_distance
            ny = contact_dy / contact_distance
            nz = contact_dz / contact_distance

        position[0] = center_x + nx * radius
        position[1] = center_y + ny * radius
        position[2] = center_z + nz * radius

        normal_velocity = velocity[0] * nx + velocity[1] * ny + velocity[2] * nz
        if normal_velocity < 0.0:
            velocity[0] -= 2.0 * normal_velocity * nx
            velocity[1] -= 2.0 * normal_velocity * ny
            velocity[2] -= 2.0 * normal_velocity * nz
    return contacted


@njit(cache=True)
def _correct_velocity_for_mechanical_energy(
    velocity,
    potential,
    particle_charge,
    particle_mass,
    target_energy,
):
    kinetic = target_energy - particle_charge * potential
    if kinetic < 0.0:
        kinetic = 0.0
    target_speed_sq = 2.0 * kinetic / particle_mass
    current_speed_sq = (
        velocity[0] * velocity[0]
        + velocity[1] * velocity[1]
        + velocity[2] * velocity[2]
    )
    if current_speed_sq <= 0.0:
        return
    scale = math.sqrt(target_speed_sq / current_speed_sq)
    velocity[0] *= scale
    velocity[1] *= scale
    velocity[2] *= scale


@njit(cache=True)
def _field_at_single(
    point,
    element_positions,
    element_charges,
    plane_positions,
    plane_normals,
    plane_densities,
    shell_positions,
    shell_radii,
    shell_charges,
):
    potential = 0.0
    field = np.zeros(3, dtype=point.dtype)
    x = point[0]
    y = point[1]
    z = point[2]
    for element_index in range(element_positions.shape[0]):
        dx = x - element_positions[element_index, 0]
        dy = y - element_positions[element_index, 1]
        dz = z - element_positions[element_index, 2]
        distance_sq = dx * dx + dy * dy + dz * dz
        if distance_sq <= MIN_SOURCE_DISTANCE_SQ:
            continue
        distance = math.sqrt(distance_sq)
        scale = COULOMB_CONSTANT * element_charges[element_index]
        potential += scale / distance
        field_scale = scale / (distance_sq * distance)
        field[0] += dx * field_scale
        field[1] += dy * field_scale
        field[2] += dz * field_scale

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
        potential -= plane_scale * abs(signed_distance)
        if abs(signed_distance) > MIN_SOURCE_DISTANCE_M:
            direction = 1.0 if signed_distance > 0.0 else -1.0
            field[0] += direction * plane_scale * plane_normals[plane_index, 0]
            field[1] += direction * plane_scale * plane_normals[plane_index, 1]
            field[2] += direction * plane_scale * plane_normals[plane_index, 2]

    for shell_index in range(shell_positions.shape[0]):
        dx = x - shell_positions[shell_index, 0]
        dy = y - shell_positions[shell_index, 1]
        dz = z - shell_positions[shell_index, 2]
        distance_sq = dx * dx + dy * dy + dz * dz
        distance = math.sqrt(distance_sq)
        shell_scale = COULOMB_CONSTANT * shell_charges[shell_index]
        if distance < shell_radii[shell_index]:
            potential += shell_scale / shell_radii[shell_index]
        elif distance > MIN_SOURCE_DISTANCE_M:
            potential += shell_scale / distance
            field_scale = shell_scale / (distance_sq * distance)
            field[0] += dx * field_scale
            field[1] += dy * field_scale
            field[2] += dz * field_scale
    return potential, field


@njit(cache=True)
def _field_line_direction(
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
    point = np.empty(3, dtype=element_positions.dtype)
    point[0] = x
    point[1] = y
    point[2] = 0.0
    _potential, field = _field_at_single(
        point,
        element_positions,
        element_charges,
        plane_positions,
        plane_normals,
        plane_densities,
        shell_positions,
        shell_radii,
        shell_charges,
    )
    magnitude = math.sqrt(field[0] * field[0] + field[1] * field[1])
    if not math.isfinite(magnitude) or magnitude < FIELD_LINE_MIN_FIELD:
        return False, 0.0, 0.0
    return True, field[0] * trace_direction / magnitude, field[1] * trace_direction / magnitude


@njit(cache=True)
def _rk4_field_line_step(
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
    valid, k1x, k1y = _field_line_direction(
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
    valid, k2x, k2y = _field_line_direction(
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
    valid, k3x, k3y = _field_line_direction(
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
    valid, k4x, k4y = _field_line_direction(
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


@njit(cache=True, parallel=True)
def _trace_field_lines_kernel(
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
    field_line_base_step_m,
    field_line_min_step_m,
    field_line_max_step_m,
    field_line_max_steps,
    field_line_max_points,
):
    candidate_count = seeds.shape[0]
    points = np.empty((candidate_count, field_line_max_steps + 1, 2), dtype=seeds.dtype)
    point_counts = np.zeros(candidate_count, dtype=np.int32)
    stop_codes = np.full(candidate_count, STOP_MAX_STEPS, dtype=np.int32)
    terminal_indexes = np.full(candidate_count, -1, dtype=np.int32)
    min_direction_dots = np.ones(candidate_count, dtype=seeds.dtype)
    for candidate_index in prange(candidate_count):
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
        step_size = field_line_base_step_m
        min_direction_dot = 1.0
        for _step in range(field_line_max_steps):
            next_valid = False
            blocked_by_reversal = False
            next_x = x
            next_y = y
            direction_x = 0.0
            direction_y = 0.0
            direction_dot = 1.0
            for _attempt in range(6):
                valid, full_x, full_y, full_direction_x, full_direction_y = (
                    _rk4_field_line_step(
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
                if step_size > field_line_min_step_m:
                    half_step = step_size * 0.5
                    valid, half_x, half_y, _half_direction_x, _half_direction_y = (
                        _rk4_field_line_step(
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
                    )
                    if valid:
                        valid, second_x, second_y, _second_direction_x, _second_direction_y = (
                            _rk4_field_line_step(
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
                        step_size = max(field_line_min_step_m, step_size * 0.5)
                        continue
                    step_error = math.hypot(full_x - second_x, full_y - second_y)
                    allowed_error = max(
                        FIELD_LINE_ADAPT_ERROR_MIN_M,
                        step_size * FIELD_LINE_ADAPT_ERROR_FRACTION,
                    )
                    if step_error > allowed_error:
                        step_size = max(field_line_min_step_m, step_size * 0.5)
                        continue
                    next_x = second_x
                    next_y = second_y
                if direction_dot < FIELD_LINE_ADAPT_RETRY_DOT and step_size > field_line_min_step_m:
                    step_size = max(field_line_min_step_m, step_size * 0.5)
                    continue
                next_valid = True
                break
            if not next_valid:
                stop_codes[candidate_index] = (
                    STOP_DIRECTION_REVERSAL if blocked_by_reversal else STOP_FIELD_NULL
                )
                break
            near_previous = False
            for prior_index in range(max(0, point_count - 8)):
                dx = next_x - points[candidate_index, prior_index, 0]
                dy = next_y - points[candidate_index, prior_index, 1]
                if math.sqrt(dx * dx + dy * dy) < FIELD_LINE_SELF_APPROACH_M:
                    near_previous = True
                    break
            if near_previous:
                stop_codes[candidate_index] = STOP_SELF_APPROACH
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
            if point_count >= field_line_max_points:
                stop_codes[candidate_index] = STOP_POINT_BUDGET
                break
            if direction_dot > FIELD_LINE_ADAPT_GROW_DOT:
                step_size = min(field_line_max_step_m, step_size * 1.35)
            elif direction_dot < FIELD_LINE_ADAPT_SHRINK_DOT:
                step_size = max(field_line_min_step_m, step_size * 0.7)
            margin = field_line_max_step_m * 2.0
            if (
                x < bounds[0] - margin
                or x > bounds[1] + margin
                or y < bounds[2] - margin
                or y > bounds[3] + margin
            ):
                stop_codes[candidate_index] = STOP_VIEW_BOUNDARY
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
                terminal_indexes[candidate_index] = terminal_source_indexes[nearest_index]
                terminal_sign = -1.0 if trace_direction > 0.0 else 1.0
                source_sign = 1.0 if terminal_charges[nearest_index] >= 0.0 else -1.0
                stop_codes[candidate_index] = (
                    STOP_OPPOSITE_CHARGE if source_sign == terminal_sign else STOP_SAME_CHARGE
                )
                break
        point_counts[candidate_index] = point_count
        min_direction_dots[candidate_index] = min_direction_dot
    return points, point_counts, stop_codes, terminal_indexes, min_direction_dots


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
        sample_potential, sample_field = _field_at_single(
            points[sample_index],
            element_positions,
            element_charges,
            plane_positions,
            plane_normals,
            plane_densities,
            shell_positions,
            shell_radii,
            shell_charges,
        )
        potential[sample_index] = sample_potential
        field[sample_index] = sample_field
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


@njit(cache=True)
def _trajectory_kernel(
    initial_position,
    initial_velocity,
    particle_charge,
    particle_mass,
    charge_over_mass,
    dt_s,
    half_dt_s,
    sixth_dt_s,
    two,
    steps,
    record_every,
    element_positions,
    element_charges,
    plane_positions,
    plane_normals,
    plane_densities,
    shell_positions,
    shell_radii,
    shell_charges,
    hard_sphere_positions,
    hard_sphere_radii,
):
    record_count = steps // record_every + 2
    times = np.empty(record_count, dtype=initial_position.dtype)
    positions = np.empty((record_count, 3), dtype=initial_position.dtype)
    velocities = np.empty((record_count, 3), dtype=initial_position.dtype)
    fields = np.empty((record_count, 3), dtype=initial_position.dtype)
    position = initial_position.copy()
    velocity = initial_velocity.copy()
    time_s = dt_s * 0
    record_index = 0
    potential, field = _field_at_single(
        position,
        element_positions,
        element_charges,
        plane_positions,
        plane_normals,
        plane_densities,
        shell_positions,
        shell_radii,
        shell_charges,
    )
    target_energy = (
        particle_charge * potential
        + 0.5
        * particle_mass
        * (velocity[0] * velocity[0] + velocity[1] * velocity[1] + velocity[2] * velocity[2])
    )
    times[record_index] = time_s
    positions[record_index] = position
    velocities[record_index] = velocity
    fields[record_index] = field
    record_index += 1
    for step in range(1, steps + 1):
        _potential, field = _field_at_single(
            position,
            element_positions,
            element_charges,
            plane_positions,
            plane_normals,
            plane_densities,
            shell_positions,
            shell_radii,
            shell_charges,
        )
        k1x = velocity
        k1v = field * charge_over_mass
        _potential, field = _field_at_single(
            position + k1x * half_dt_s,
            element_positions,
            element_charges,
            plane_positions,
            plane_normals,
            plane_densities,
            shell_positions,
            shell_radii,
            shell_charges,
        )
        k2x = velocity + k1v * half_dt_s
        k2v = field * charge_over_mass
        _potential, field = _field_at_single(
            position + k2x * half_dt_s,
            element_positions,
            element_charges,
            plane_positions,
            plane_normals,
            plane_densities,
            shell_positions,
            shell_radii,
            shell_charges,
        )
        k3x = velocity + k2v * half_dt_s
        k3v = field * charge_over_mass
        _potential, field = _field_at_single(
            position + k3x * dt_s,
            element_positions,
            element_charges,
            plane_positions,
            plane_normals,
            plane_densities,
            shell_positions,
            shell_radii,
            shell_charges,
        )
        k4x = velocity + k3v * dt_s
        k4v = field * charge_over_mass
        previous_position = position.copy()
        position = position + (k1x + two * k2x + two * k3x + k4x) * sixth_dt_s
        velocity = velocity + (k1v + two * k2v + two * k3v + k4v) * sixth_dt_s
        contacted = _enforce_hard_sphere_contacts(
            previous_position,
            position,
            velocity,
            hard_sphere_positions,
            hard_sphere_radii,
        )
        if contacted:
            potential, _field_after_contact = _field_at_single(
                position,
                element_positions,
                element_charges,
                plane_positions,
                plane_normals,
                plane_densities,
                shell_positions,
                shell_radii,
                shell_charges,
            )
            _correct_velocity_for_mechanical_energy(
                velocity,
                potential,
                particle_charge,
                particle_mass,
                target_energy,
            )
        time_s += dt_s
        if step % record_every == 0 or step == steps:
            _potential, field = _field_at_single(
                position,
                element_positions,
                element_charges,
                plane_positions,
                plane_normals,
                plane_densities,
                shell_positions,
                shell_radii,
                shell_charges,
            )
            times[record_index] = time_s
            positions[record_index] = position
            velocities[record_index] = velocity
            fields[record_index] = field
            record_index += 1
    return (
        times[:record_index],
        positions[:record_index],
        velocities[:record_index],
        fields[:record_index],
    )


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


def evaluate_trajectory_cpu(
    packed: PackedScene,
    initial_position: np.ndarray,
    initial_velocity: np.ndarray,
    *,
    particle_charge: float,
    particle_mass: float,
    charge_over_mass: float,
    dt_s: float,
    steps: int,
    record_every: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    scalar_type = packed.dtype.type
    prepared_dt_s = scalar_type(dt_s)
    return _trajectory_kernel(
        np.ascontiguousarray(initial_position, dtype=packed.dtype),
        np.ascontiguousarray(initial_velocity, dtype=packed.dtype),
        scalar_type(particle_charge),
        scalar_type(particle_mass),
        scalar_type(charge_over_mass),
        prepared_dt_s,
        scalar_type(prepared_dt_s * scalar_type(0.5)),
        scalar_type(prepared_dt_s * scalar_type(1.0 / 6.0)),
        scalar_type(2.0),
        steps,
        record_every,
        packed.element_positions,
        packed.element_charges,
        packed.plane_positions,
        packed.plane_normals,
        packed.plane_densities,
        packed.shell_positions,
        packed.shell_radii,
        packed.shell_charges,
        packed.hard_sphere_positions,
        packed.hard_sphere_radii,
    )


def evaluate_field_lines_cpu(
    packed: PackedScene,
    seeds: np.ndarray,
    trace_directions: np.ndarray,
    seed_source_indexes: np.ndarray,
    terminal_positions: np.ndarray,
    terminal_charges: np.ndarray,
    terminal_source_indexes: np.ndarray,
    *,
    bounds: tuple[float, float, float, float],
) -> FieldLineKernelResult:
    prepared_bounds = np.asarray(bounds, dtype=packed.dtype)
    points, point_counts, stop_codes, terminal_indexes, min_direction_dots = (
        _trace_field_lines_kernel(
            np.ascontiguousarray(seeds, dtype=packed.dtype),
            np.ascontiguousarray(trace_directions, dtype=packed.dtype),
            np.ascontiguousarray(seed_source_indexes, dtype=np.int32),
            np.ascontiguousarray(terminal_positions, dtype=packed.dtype),
            np.ascontiguousarray(terminal_charges, dtype=packed.dtype),
            np.ascontiguousarray(terminal_source_indexes, dtype=np.int32),
            prepared_bounds,
            packed.element_positions,
            packed.element_charges,
            packed.plane_positions,
            packed.plane_normals,
            packed.plane_densities,
            packed.shell_positions,
            packed.shell_radii,
            packed.shell_charges,
            packed.dtype.type(FIELD_LINE_BASE_STEP_M),
            packed.dtype.type(FIELD_LINE_MIN_STEP_M),
            packed.dtype.type(FIELD_LINE_MAX_STEP_M),
            FIELD_LINE_MAX_STEPS,
            FIELD_LINE_MAX_POINTS,
        )
    )
    return FieldLineKernelResult(
        points=points,
        point_counts=point_counts,
        stop_codes=stop_codes,
        terminal_source_indexes=terminal_indexes,
        min_direction_dots=min_direction_dots,
    )
