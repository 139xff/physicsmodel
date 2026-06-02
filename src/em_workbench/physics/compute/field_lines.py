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
from em_workbench.physics.solver import SolverQuality

FIELD_LINE_TARGET_TOTAL_CHARGE_RAYS = 96
FIELD_LINE_MIN_CHARGE_RAYS = 24
FIELD_LINE_MAX_CHARGE_RAYS = 64
FIELD_LINE_MAX_PAIR_DISPLAY_COUNT = 72
FIELD_LINE_START_RADIUS_M = 0.005
FIELD_LINE_ENDPOINT_MARGIN_M = 0.0015
FIELD_LINE_BASE_STEP_M = 0.01
FIELD_LINE_MIN_STEP_M = 0.0012
FIELD_LINE_MAX_STEP_M = 0.025
FIELD_LINE_MAX_STEPS = 1600
FIELD_LINE_MAX_POINTS = 1000
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


def build_field_line_inputs(scene: Scene, *, density: float, dtype: np.dtype) -> FieldLineInputs:
    if density <= 0.0 or density > 4.0:
        raise ValueError("density must be greater than 0 and at most 4.")
    point_sources = [
        (source_index, source)
        for source_index, source in enumerate(scene.sources)
        if source.kind == "point" and abs(source.charge_c) > 1e-30
    ]
    total_abs_charge = sum(abs(source.charge_c) for _index, source in point_sources)
    seeds: list[tuple[float, float]] = []
    trace_directions: list[float] = []
    seed_source_indexes: list[int] = []
    seed_indexes: list[int] = []
    terminal_positions: list[tuple[float, float]] = []
    terminal_charges: list[float] = []
    terminal_source_indexes: list[int] = []

    for source_index, source in point_sources:
        terminal_positions.append((source.position.x, source.position.y))
        terminal_charges.append(source.charge_c)
        terminal_source_indexes.append(source_index)
        charge_fraction = abs(source.charge_c) / total_abs_charge
        ray_count = _round_ray_count(
            FIELD_LINE_TARGET_TOTAL_CHARGE_RAYS * density * charge_fraction
        )
        trace_direction = 1.0 if source.charge_c >= 0.0 else -1.0
        for seed_index in range(ray_count):
            angle = math.tau * seed_index / ray_count
            seeds.append(
                (
                    source.position.x + math.cos(angle) * FIELD_LINE_START_RADIUS_M,
                    source.position.y + math.sin(angle) * FIELD_LINE_START_RADIUS_M,
                )
            )
            trace_directions.append(trace_direction)
            seed_source_indexes.append(source_index)
            seed_indexes.append(seed_index)

    return FieldLineInputs(
        seeds=np.asarray(seeds, dtype=dtype).reshape(-1, 2),
        trace_directions=np.asarray(trace_directions, dtype=dtype),
        seed_source_indexes=np.asarray(seed_source_indexes, dtype=np.int32),
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
    lines: list[FieldLineResult] = []
    rejected_line_count = 0
    conflict_rejected_line_count = 0
    pair_counts: dict[tuple[str, str], int] = {}
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
        if seed_source.charge_c < 0.0:
            raw_points = raw_points[::-1]
        points = [FieldLinePoint(x=float(point[0]), y=float(point[1])) for point in raw_points]
        if stop_code == STOP_OPPOSITE_CHARGE and terminal_source is not None:
            topology: FieldLineTopology = "source-to-source"
            source_id = seed_source.id
            terminal_source_id = terminal_source.id
            pair_key = tuple(sorted((source_id, terminal_source_id)))
            if pair_counts.get(pair_key, 0) >= FIELD_LINE_MAX_PAIR_DISPLAY_COUNT:
                conflict_rejected_line_count += 1
                continue
            pair_counts[pair_key] = pair_counts.get(pair_key, 0) + 1
        elif seed_source.charge_c >= 0.0:
            topology = "source-to-infinity"
            source_id = seed_source.id
            terminal_source_id = None
        else:
            topology = "infinity-to-source"
            source_id = seed_source.id
            terminal_source_id = None
        arrow_anchor, arrow_direction = _arrow(points)
        lines.append(
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
        if len(lines) >= display_max_count:
            break
    return FieldLineResponse(
        request_id=request_id,
        lines=lines,
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
