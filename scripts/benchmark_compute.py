"""Run reproducible scalar, CPU JIT, CUDA, and automatic-dispatch benchmarks."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np

from em_workbench.models import Position, Scene
from em_workbench.physics.compute.contracts import BackendPolicy
from em_workbench.physics.compute.dispatcher import ComputeService
from em_workbench.physics.compute.field_lines import ViewportBounds
from em_workbench.physics.compute.runtime import probe_runtime
from em_workbench.physics.dynamics import TestCharge

TARGETS_MS = {
    "field-preview-400": 100.0,
    "trajectory-preview-400": 300.0,
    "field-lines-preview": 250.0,
}


@dataclass(frozen=True)
class Workload:
    name: str
    invoke: Callable[[ComputeService, BackendPolicy], Any]
    correct: Callable[[Any, Any], dict[str, Any]]


def _scene() -> Scene:
    return Scene.model_validate(
        {
            "id": "benchmark-representative",
            "title": "Benchmark representative scene",
            "sources": [
                {
                    "id": "q1",
                    "kind": "point",
                    "label": "q1",
                    "position": {"x": -0.08, "y": 0.0, "z": 0.0},
                    "charge_c": 2e-9,
                },
                {
                    "id": "q2",
                    "kind": "point",
                    "label": "q2",
                    "position": {"x": 0.08, "y": 0.0, "z": 0.0},
                    "charge_c": -2e-9,
                },
                {
                    "id": "line",
                    "kind": "line_segment",
                    "label": "line",
                    "position": {"x": 0.0, "y": -0.12, "z": 0.0},
                    "orientation": {"x": 1.0, "y": 0.0, "z": 0.0},
                    "length_m": 0.18,
                    "charge_c": 1.5e-9,
                },
                {
                    "id": "ring",
                    "kind": "ring",
                    "label": "ring",
                    "position": {"x": 0.0, "y": 0.1, "z": 0.0},
                    "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                    "radius_m": 0.06,
                    "charge_c": -1.2e-9,
                },
                {
                    "id": "disk",
                    "kind": "disk",
                    "label": "disk",
                    "position": {"x": 0.0, "y": 0.0, "z": -0.08},
                    "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                    "radius_m": 0.08,
                    "charge_c": 1e-9,
                },
            ],
        }
    )


def _particle() -> TestCharge:
    return TestCharge.model_validate(
        {
            "charge_c": -1e-9,
            "mass_kg": 6e-6,
            "position": {"x": 0.0, "y": 0.20, "z": 0.0},
            "velocity": {"x": 0.02, "y": 0.0, "z": 0.0},
        }
    )


def _grid_points(side: int) -> list[Position]:
    return [
        Position(
            x=-0.3 + 0.6 * x_index / max(1, side - 1),
            y=-0.3 + 0.6 * y_index / max(1, side - 1),
            z=0.04,
        )
        for y_index in range(side)
        for x_index in range(side)
    ]


def _field_correct(result, reference) -> dict[str, Any]:
    potential_error = float(np.max(np.abs(result.potential_v - reference.potential_v)))
    field_error = float(np.max(np.abs(result.field_v_per_m - reference.field_v_per_m)))
    return {
        "passed": bool(
            np.allclose(result.potential_v, reference.potential_v, rtol=2e-5, atol=5e-5)
            and np.allclose(result.field_v_per_m, reference.field_v_per_m, rtol=2e-5, atol=1e-3)
        ),
        "potential_max_abs_error": potential_error,
        "field_max_abs_error": field_error,
    }


def _trajectory_correct(result, reference) -> dict[str, Any]:
    result_position = result.samples[-1].position
    reference_position = reference.samples[-1].position
    result_velocity = result.samples[-1].velocity
    reference_velocity = reference.samples[-1].velocity
    position_error = max(
        abs(result_position.x - reference_position.x),
        abs(result_position.y - reference_position.y),
        abs(result_position.z - reference_position.z),
    )
    velocity_error = max(
        abs(result_velocity.x - reference_velocity.x),
        abs(result_velocity.y - reference_velocity.y),
        abs(result_velocity.z - reference_velocity.z),
    )
    return {
        "passed": position_error <= 1e-5 and velocity_error <= 1e-5,
        "position_max_abs_error": position_error,
        "velocity_max_abs_error": velocity_error,
    }


def _field_lines_correct(result, reference) -> dict[str, Any]:
    topology = {line.topology for line in result.lines}
    reference_topology = {line.topology for line in reference.lines}
    return {
        "passed": bool(
            result.candidate_line_count == reference.candidate_line_count
            and abs(len(result.lines) - len(reference.lines)) <= 4
            and topology == reference_topology
        ),
        "candidate_line_count": result.candidate_line_count,
        "display_line_count": len(result.lines),
        "reference_display_line_count": len(reference.lines),
        "topology": sorted(topology),
    }


def _workloads(*, include_refined: bool) -> list[Workload]:
    scene = _scene()
    particle = _particle()
    bounds = ViewportBounds(min_x=-0.2, max_x=0.2, min_y=-0.2, max_y=0.2)
    workloads: list[Workload] = []
    qualities = ["preview", "refined"] if include_refined else ["preview"]
    for quality in qualities:
        for side in (5, 20):
            points = _grid_points(side)
            workloads.append(
                Workload(
                    name=f"field-{quality}-{len(points)}",
                    invoke=lambda service, backend, points=points, quality=quality: (
                        service.evaluate_totals(scene, points, quality=quality, backend=backend)
                    ),
                    correct=_field_correct,
                )
            )
    for steps in (100, 400):
        workloads.append(
            Workload(
                name=f"trajectory-preview-{steps}",
                invoke=lambda service, backend, steps=steps: service.simulate_trajectory(
                    scene,
                    particle,
                    dt_s=0.001,
                    steps=steps,
                    quality="preview",
                    backend=backend,
                ),
                correct=_trajectory_correct,
            )
        )
    workloads.append(
        Workload(
            name="field-lines-preview",
            invoke=lambda service, backend: service.trace_field_lines(
                scene,
                bounds,
                quality="preview",
                backend=backend,
            ),
            correct=_field_lines_correct,
        )
    )
    return workloads


def _timed(invoke: Callable[[], Any]) -> tuple[float, Any]:
    started = time.perf_counter()
    result = invoke()
    return (time.perf_counter() - started) * 1000.0, result


def run_benchmarks(
    *,
    backends: list[BackendPolicy],
    warm_runs: int,
    include_refined: bool,
) -> dict[str, Any]:
    if warm_runs < 1:
        raise ValueError("warm_runs must be at least 1.")
    runtime = probe_runtime()
    workloads = _workloads(include_refined=include_refined)
    references: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    for backend in backends:
        service = ComputeService()
        for workload in workloads:
            invoke = partial(workload.invoke, service, backend)
            cold_ms, result = _timed(invoke)
            if backend == "scalar":
                references[workload.name] = result
            reference = references.get(workload.name)
            if reference is None:
                reference = workload.invoke(ComputeService(), "scalar")
                references[workload.name] = reference
            warm_ms = [_timed(invoke)[0] for _ in range(warm_runs)]
            target_ms = TARGETS_MS.get(workload.name)
            warm_median_ms = statistics.median(warm_ms)
            records.append(
                {
                    "name": workload.name,
                    "backend_requested": backend,
                    "backend_effective": result.execution.backend_effective,
                    "precision": result.execution.precision,
                    "fallback_reason": result.execution.fallback_reason,
                    "cold_ms": cold_ms,
                    "warm_ms": warm_ms,
                    "warm_median_ms": warm_median_ms,
                    "target_ms": target_ms,
                    "target_met": target_ms is None or warm_median_ms <= target_ms,
                    "correctness": workload.correct(result, reference),
                }
            )
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu": runtime.cpu.model_dump(mode="json"),
            "cuda": runtime.cuda.model_dump(mode="json"),
        },
        "config": {
            "backends": backends,
            "warm_runs": warm_runs,
            "include_refined": include_refined,
        },
        "records": records,
        "summary": {
            "correctness_passed": all(record["correctness"]["passed"] for record in records),
            "auto_targets_met": all(
                record["target_met"]
                for record in records
                if record["backend_requested"] == "auto"
            ),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend",
        action="append",
        choices=["scalar", "cpu", "cuda", "auto"],
        dest="backends",
    )
    parser.add_argument("--warm-runs", type=int, default=5)
    parser.add_argument("--include-refined", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_benchmarks(
        backends=args.backends or ["auto"],
        warm_runs=args.warm_runs,
        include_refined=args.include_refined,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output is None:
        print(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote benchmark report to {args.output}")
    return 0 if report["summary"]["correctness_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
