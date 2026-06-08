from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
from pydantic import FiniteFloat, model_validator

from em_workbench.models import Scene
from em_workbench.physics.compute.contracts import (
    BackendPolicy,
    ComputeModel,
    ExecutionMetadata,
)
from em_workbench.physics.compute.packed_scene import PackedScene
from em_workbench.physics.solver import SolverQuality

FIELD_LINE_TARGET_TOTAL_CHARGE_RAYS = 96
FIELD_LINE_MIN_CHARGE_RAYS = 24
FIELD_LINE_MAX_CHARGE_RAYS = 64
FIELD_LINE_MAX_PAIR_DISPLAY_COUNT = 72
FIELD_LINE_START_RADIUS_M = 0.005
FIELD_LINE_ENDPOINT_MARGIN_M = 0.0015
FIELD_LINE_BASE_STEP_M = 0.004
FIELD_LINE_MIN_STEP_M = 0.0008
FIELD_LINE_MAX_STEP_M = 0.008
FIELD_LINE_MAX_STEPS = 2400
FIELD_LINE_MAX_POINTS = 2200
FIELD_LINE_MIN_FIELD = 1e-15
FIELD_LINE_REVERSAL_DOT_LIMIT = -0.2
FIELD_LINE_ADAPT_RETRY_DOT = 0.985
FIELD_LINE_ADAPT_GROW_DOT = 0.998
FIELD_LINE_ADAPT_SHRINK_DOT = 0.992
FIELD_LINE_ADAPT_ERROR_MIN_M = 0.0012
FIELD_LINE_ADAPT_ERROR_FRACTION = 0.035
FIELD_LINE_SELF_APPROACH_M = 0.006
FIELD_LINE_MIN_RENDER_POINTS = 4
FIELD_LINE_DIRECTION_DOT_MIN = 0.2

STOP_MAX_STEPS = 0
STOP_FIELD_NULL = 1
STOP_DIRECTION_REVERSAL = 2
STOP_SELF_APPROACH = 3
STOP_POINT_BUDGET = 4
STOP_VIEW_BOUNDARY = 5
STOP_OPPOSITE_CHARGE = 6
STOP_SAME_CHARGE = 7

STOP_REASONS = {
    STOP_MAX_STEPS: "max-steps",
    STOP_FIELD_NULL: "field-null",
    STOP_DIRECTION_REVERSAL: "direction-reversal",
    STOP_SELF_APPROACH: "self-approach",
    STOP_POINT_BUDGET: "point-budget",
    STOP_VIEW_BOUNDARY: "view-boundary",
    STOP_OPPOSITE_CHARGE: "opposite-charge",
    STOP_SAME_CHARGE: "same-charge",
}

FieldLineTopology = Literal["source-to-source", "source-to-infinity", "infinity-to-source"]


class ViewportBounds(ComputeModel):
    min_x: FiniteFloat
    max_x: FiniteFloat
    min_y: FiniteFloat
    max_y: FiniteFloat

    @model_validator(mode="after")
    def validate_ranges(self) -> ViewportBounds:
        if self.min_x >= self.max_x:
            raise ValueError("min_x must be less than max_x.")
        if self.min_y >= self.max_y:
            raise ValueError("min_y must be less than max_y.")
        return self


class FieldLinePoint(ComputeModel):
    x: FiniteFloat
    y: FiniteFloat


class FieldLineResult(ComputeModel):
    seed_index: int
    source_id: str
    terminal_source_id: str | None = None
    topology: FieldLineTopology
    stop_reason: str
    points: list[FieldLinePoint]
    arrow_anchor: FieldLinePoint
    arrow_direction: FieldLinePoint
    min_direction_dot: FiniteFloat


class FieldLineResponse(ComputeModel):
    request_id: str | None = None
    lines: list[FieldLineResult]
    candidate_line_count: int
    rejected_line_count: int
    conflict_rejected_line_count: int
    display_max_count: int
    execution: ExecutionMetadata


@dataclass(frozen=True)
class FieldLineInputs:
    seeds: np.ndarray
    trace_directions: np.ndarray
    seed_source_indexes: np.ndarray
    seed_source_charges: np.ndarray
    seed_indexes: np.ndarray
    terminal_positions: np.ndarray
    terminal_charges: np.ndarray
    terminal_source_indexes: np.ndarray

    @property
    def candidate_count(self) -> int:
        return int(self.seeds.shape[0])


@dataclass(frozen=True)
class FieldLineKernelResult:
    points: np.ndarray
    point_counts: np.ndarray
    stop_codes: np.ndarray
    terminal_source_indexes: np.ndarray
    min_direction_dots: np.ndarray


def _round_ray_count(value: float) -> int:
    rounded = round(value / 4.0) * 4
    return max(FIELD_LINE_MIN_CHARGE_RAYS, min(FIELD_LINE_MAX_CHARGE_RAYS, rounded))


def _empty_field_line_inputs(dtype: np.dtype) -> FieldLineInputs:
    return FieldLineInputs(
        seeds=np.empty((0, 2), dtype=dtype),
        trace_directions=np.empty(0, dtype=dtype),
        seed_source_indexes=np.empty(0, dtype=np.int32),
        seed_source_charges=np.empty(0, dtype=dtype),
        seed_indexes=np.empty(0, dtype=np.int32),
        terminal_positions=np.empty((0, 2), dtype=dtype),
        terminal_charges=np.empty(0, dtype=dtype),
        terminal_source_indexes=np.empty(0, dtype=np.int32),
    )


def _point_seed_position(source, seed_index: int, ray_count: int) -> tuple[float, float]:
    angle = math.tau * seed_index / ray_count
    return (
        source.position.x + math.cos(angle) * FIELD_LINE_START_RADIUS_M,
        source.position.y + math.sin(angle) * FIELD_LINE_START_RADIUS_M,
    )


def _line_segment_seed_position(source, seed_index: int, ray_count: int) -> tuple[float, float]:
    axis_x = source.orientation.x
    axis_y = source.orientation.y
    axis_magnitude = math.hypot(axis_x, axis_y)
    if axis_magnitude <= 1e-12:
        return _point_seed_position(source, seed_index, ray_count)
    unit_x = axis_x / axis_magnitude
    unit_y = axis_y / axis_magnitude
    normal_x = -unit_y
    normal_y = unit_x
    side_count = max(1, ray_count // 2)
    slot = min(side_count - 1, seed_index // 2)
    offset_along_line = ((slot + 0.5) / side_count) * source.length_m
    side = 1.0 if seed_index % 2 == 0 else -1.0
    return (
        source.position.x
        + unit_x * offset_along_line
        + normal_x * side * FIELD_LINE_START_RADIUS_M,
        source.position.y
        + unit_y * offset_along_line
        + normal_y * side * FIELD_LINE_START_RADIUS_M,
    )


def _radial_source_seed_position(source, seed_index: int, ray_count: int) -> tuple[float, float]:
    angle = math.tau * seed_index / ray_count
    radius = source.radius_m + FIELD_LINE_START_RADIUS_M
    return (
        source.position.x + math.cos(angle) * radius,
        source.position.y + math.sin(angle) * radius,
    )


def _source_seed_position(
    scene: Scene,
    packed: PackedScene,
    source_index: int,
    element_indexes: list[int],
    seed_index: int,
    ray_count: int,
) -> tuple[float, float]:
    source = scene.sources[source_index]
    angle = math.tau * seed_index / ray_count
    if source.kind == "point":
        return _point_seed_position(source, seed_index, ray_count)
    if source.kind == "line_segment":
        return _line_segment_seed_position(source, seed_index, ray_count)
    if source.kind in {"ring", "disk"}:
        return _radial_source_seed_position(source, seed_index, ray_count)
    element_offset = min(
        len(element_indexes) - 1,
        int((seed_index * len(element_indexes)) / ray_count),
    )
    element_position = packed.element_positions[element_indexes[element_offset]]
    origin_x = float(element_position[0])
    origin_y = float(element_position[1])
    if source.kind in {"ring", "disk"}:
        radial_x = origin_x - source.position.x
        radial_y = origin_y - source.position.y
        radial_magnitude = math.hypot(radial_x, radial_y)
        if radial_magnitude > 1e-12:
            return (
                origin_x + (radial_x / radial_magnitude) * FIELD_LINE_START_RADIUS_M,
                origin_y + (radial_y / radial_magnitude) * FIELD_LINE_START_RADIUS_M,
            )
    return (
        origin_x + math.cos(angle) * FIELD_LINE_START_RADIUS_M,
        origin_y + math.sin(angle) * FIELD_LINE_START_RADIUS_M,
    )


def build_field_line_inputs(
    scene: Scene,
    packed: PackedScene,
    *,
    density: float,
    dtype: np.dtype,
) -> FieldLineInputs:
    if density <= 0.0 or density > 4.0:
        raise ValueError("density must be greater than 0 and at most 4.")
    source_element_indexes: dict[int, list[int]] = {}
    source_charges: dict[int, float] = {}
    terminal_positions: list[tuple[float, float]] = []
    terminal_charges: list[float] = []
    terminal_source_indexes: list[int] = []

    for element_index, source_index_value in enumerate(packed.element_source_indexes):
        charge = float(packed.element_charges[element_index])
        if abs(charge) <= 1e-30:
            continue
        source_index = int(source_index_value)
        source_element_indexes.setdefault(source_index, []).append(element_index)
        source_charges[source_index] = source_charges.get(source_index, 0.0) + charge
        position = packed.element_positions[element_index]
        terminal_positions.append((float(position[0]), float(position[1])))
        terminal_charges.append(charge)
        terminal_source_indexes.append(source_index)

    charged_source_indexes = [
        source_index
        for source_index, charge in source_charges.items()
        if abs(charge) > 1e-30 and source_element_indexes.get(source_index)
    ]
    total_abs_charge = sum(
        abs(source_charges[source_index]) for source_index in charged_source_indexes
    )
    if total_abs_charge <= 0.0:
        return _empty_field_line_inputs(dtype)

    seeds: list[tuple[float, float]] = []
    trace_directions: list[float] = []
    seed_source_indexes: list[int] = []
    seed_source_charges: list[float] = []
    seed_indexes: list[int] = []

    for source_index in charged_source_indexes:
        charge = source_charges[source_index]
        element_indexes = source_element_indexes[source_index]
        charge_fraction = abs(charge) / total_abs_charge
        ray_count = _round_ray_count(
            FIELD_LINE_TARGET_TOTAL_CHARGE_RAYS * density * charge_fraction
        )
        trace_direction = 1.0 if charge >= 0.0 else -1.0
        for seed_index in range(ray_count):
            seed_x, seed_y = _source_seed_position(
                scene,
                packed,
                source_index,
                element_indexes,
                seed_index,
                ray_count,
            )
            seeds.append((seed_x, seed_y))
            trace_directions.append(trace_direction)
            seed_source_indexes.append(source_index)
            seed_source_charges.append(charge)
            seed_indexes.append(seed_index)

    return FieldLineInputs(
        seeds=np.asarray(seeds, dtype=dtype).reshape(-1, 2),
        trace_directions=np.asarray(trace_directions, dtype=dtype),
        seed_source_indexes=np.asarray(seed_source_indexes, dtype=np.int32),
        seed_source_charges=np.asarray(seed_source_charges, dtype=dtype),
        seed_indexes=np.asarray(seed_indexes, dtype=np.int32),
        terminal_positions=np.asarray(terminal_positions, dtype=dtype).reshape(-1, 2),
        terminal_charges=np.asarray(terminal_charges, dtype=dtype),
        terminal_source_indexes=np.asarray(terminal_source_indexes, dtype=np.int32),
    )


def _arrow(points: list[FieldLinePoint]) -> tuple[FieldLinePoint, FieldLinePoint]:
    anchor_index = min(len(points) - 2, max(0, round((len(points) - 1) * 0.42)))
    anchor = points[anchor_index]
    next_point = points[anchor_index + 1]
    dx = next_point.x - anchor.x
    dy = next_point.y - anchor.y
    magnitude = math.hypot(dx, dy)
    if magnitude <= 0.0:
        return anchor, FieldLinePoint(x=1.0, y=0.0)
    return anchor, FieldLinePoint(x=dx / magnitude, y=dy / magnitude)


def build_field_line_response(
    scene: Scene,
    inputs: FieldLineInputs,
    result: FieldLineKernelResult,
    *,
    execution: ExecutionMetadata,
    request_id: str | None,
    display_max_count: int,
) -> FieldLineResponse:
    selected_lines: list[FieldLineResult] = []
    line_groups: dict[int, list[FieldLineResult]] = {}
    rejected_line_count = 0
    conflict_rejected_line_count = 0
    for candidate_index in range(inputs.candidate_count):
        stop_code = int(result.stop_codes[candidate_index])
        point_count = int(result.point_counts[candidate_index])
        min_direction_dot = float(result.min_direction_dots[candidate_index])
        if (
            stop_code not in {STOP_VIEW_BOUNDARY, STOP_OPPOSITE_CHARGE}
            or point_count < FIELD_LINE_MIN_RENDER_POINTS
            or min_direction_dot < FIELD_LINE_DIRECTION_DOT_MIN
        ):
            rejected_line_count += 1
            continue
        seed_source_index = int(inputs.seed_source_indexes[candidate_index])
        seed_source = scene.sources[seed_source_index]
        terminal_source_index = int(result.terminal_source_indexes[candidate_index])
        terminal_source = (
            scene.sources[terminal_source_index] if terminal_source_index >= 0 else None
        )
        raw_points = result.points[candidate_index, :point_count]
        seed_source_charge = float(inputs.seed_source_charges[candidate_index])
        if seed_source_charge < 0.0:
            raw_points = raw_points[::-1]
        points = [FieldLinePoint(x=float(point[0]), y=float(point[1])) for point in raw_points]
        if stop_code == STOP_OPPOSITE_CHARGE and terminal_source is not None:
            topology: FieldLineTopology = "source-to-source"
            source_id = seed_source.id
            terminal_source_id = terminal_source.id
        elif seed_source_charge >= 0.0:
            topology = "source-to-infinity"
            source_id = seed_source.id
            terminal_source_id = None
        else:
            topology = "infinity-to-source"
            source_id = seed_source.id
            terminal_source_id = None
        arrow_anchor, arrow_direction = _arrow(points)
        line_groups.setdefault(seed_source_index, []).append(
            FieldLineResult(
                seed_index=int(inputs.seed_indexes[candidate_index]),
                source_id=source_id,
                terminal_source_id=terminal_source_id,
                topology=topology,
                stop_reason=STOP_REASONS[stop_code],
                points=points,
                arrow_anchor=arrow_anchor,
                arrow_direction=arrow_direction,
                min_direction_dot=min_direction_dot,
            )
        )

    pair_counts: dict[tuple[str, str], int] = {}
    group_cursors = {source_index: 0 for source_index in line_groups}
    source_indexes = [
        source_index
        for source_index in range(len(scene.sources))
        if source_index in line_groups
    ]
    searched_any_candidate = True
    while len(selected_lines) < display_max_count and searched_any_candidate:
        searched_any_candidate = False
        for source_index in source_indexes:
            group = line_groups[source_index]
            while group_cursors[source_index] < len(group):
                searched_any_candidate = True
                line = group[group_cursors[source_index]]
                group_cursors[source_index] += 1
                if line.topology == "source-to-source" and line.terminal_source_id:
                    pair_key = tuple(sorted((line.source_id, line.terminal_source_id)))
                    if pair_counts.get(pair_key, 0) >= FIELD_LINE_MAX_PAIR_DISPLAY_COUNT:
                        conflict_rejected_line_count += 1
                        continue
                    pair_counts[pair_key] = pair_counts.get(pair_key, 0) + 1
                selected_lines.append(line)
                break
            if len(selected_lines) >= display_max_count:
                break
    return FieldLineResponse(
        request_id=request_id,
        lines=selected_lines,
        candidate_line_count=inputs.candidate_count,
        rejected_line_count=rejected_line_count,
        conflict_rejected_line_count=conflict_rejected_line_count,
        display_max_count=display_max_count,
        execution=execution,
    )


def trace_field_lines(
    scene: Scene,
    bounds: ViewportBounds,
    *,
    request_id: str | None = None,
    quality: SolverQuality = "preview",
    density: float = 1.0,
    display_max_count: int = 120,
    backend: BackendPolicy = "auto",
) -> FieldLineResponse:
    from em_workbench.physics.compute.dispatcher import DEFAULT_COMPUTE_SERVICE

    return DEFAULT_COMPUTE_SERVICE.trace_field_lines(
        scene,
        bounds,
        request_id=request_id,
        quality=quality,
        density=density,
        display_max_count=display_max_count,
        backend=backend,
    )
