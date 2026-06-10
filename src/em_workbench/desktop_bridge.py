"""Desktop bridge methods shared by Qt and tests."""

from __future__ import annotations

import json
from concurrent.futures import Future, ThreadPoolExecutor
from threading import RLock
from uuid import uuid4

from pydantic import BaseModel, Field

from em_workbench.app import (
    FieldLineEvaluateRequest,
    ScatteringEvaluateRequest,
    TrajectoryEvaluateRequest,
    compute_status,
    config,
)
from em_workbench.models import Position, Preset, PresetSummary, Scene
from em_workbench.physics.compute.field_lines import FieldLineResponse, trace_field_lines
from em_workbench.physics.dynamics import TrajectoryResponse, simulate_trajectory
from em_workbench.physics.scattering import ScatterResponse, simulate_scattering
from em_workbench.physics.solver import FieldEvaluationResponse, SolverQuality, evaluate_scene
from em_workbench.presets import get_preset, list_presets


class DesktopFieldEvaluateRequest(BaseModel):
    """Field-evaluation request accepted by the desktop bridge."""

    request_id: str = Field(min_length=1)
    scene: Scene
    sample_points: list[Position] = Field(min_length=1)
    quality: SolverQuality = "preview"


class DesktopPresetRequest(BaseModel):
    """Preset lookup request accepted by the desktop bridge."""

    preset_id: str = Field(min_length=1)


def _status_json(_payload: str = "") -> str:
    return compute_status().model_dump_json()


def _evaluate_field_json(payload: str) -> str:
    request = DesktopFieldEvaluateRequest.model_validate_json(payload)
    result = evaluate_scene(
        request.scene,
        request.sample_points,
        quality=request.quality,
        request_id=request.request_id,
    )
    return result.model_dump_json()


def _evaluate_trajectory_json(payload: str) -> str:
    request = TrajectoryEvaluateRequest.model_validate_json(payload)
    result = simulate_trajectory(
        request.scene,
        request.particle,
        dt_s=request.dt_s,
        steps=request.steps,
        quality=request.quality,
        record_every=request.record_every,
        request_id=request.request_id,
    )
    return result.model_dump_json()


def _evaluate_field_lines_json(payload: str) -> str:
    request = FieldLineEvaluateRequest.model_validate_json(payload)
    result = trace_field_lines(
        request.scene,
        request.bounds,
        request_id=request.request_id,
        quality=request.quality,
        density=request.density,
        display_max_count=request.display_max_count,
        backend=request.backend,
    )
    return result.model_dump_json()


def _evaluate_scattering_json(payload: str) -> str:
    request = ScatteringEvaluateRequest.model_validate_json(payload)
    result = simulate_scattering(
        request.nucleus,
        request.beam,
        scene=request.scene,
        dt_s=request.dt_s,
        max_steps=request.max_steps,
        exit_radius_m=request.exit_radius_m,
        record_every=request.record_every,
        request_id=request.request_id,
        quality=request.quality,
        backend=request.backend,
    )
    return result.model_dump_json()


class DesktopComputeQueue:
    """Serialize desktop compute work away from the Qt UI thread."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="em-compute")
        self._futures: dict[str, Future[str]] = {}
        self._lock = RLock()

    def submit(self, method: str, payload: str) -> str:
        ticket = uuid4().hex
        future = self._executor.submit(self._invoke, method, payload)
        with self._lock:
            self._futures[ticket] = future
        return ticket

    def poll(self, ticket: str) -> str:
        with self._lock:
            future = self._futures.get(ticket)
        if future is None:
            return json.dumps({"state": "missing"})
        if not future.done():
            return json.dumps({"state": "pending"})
        with self._lock:
            self._futures.pop(ticket, None)
        try:
            return json.dumps({"state": "ready", "result": future.result()})
        except Exception as error:
            return json.dumps({"state": "failed", "error": str(error)})

    def wait(self, ticket: str, *, timeout_s: float) -> str:
        with self._lock:
            future = self._futures.get(ticket)
        if future is None:
            raise KeyError(f"Unknown desktop compute ticket: {ticket}")
        result = future.result(timeout=timeout_s)
        with self._lock:
            self._futures.pop(ticket, None)
        return result

    @staticmethod
    def _invoke(method: str, payload: str) -> str:
        methods = {
            "status": _status_json,
            "evaluateField": _evaluate_field_json,
            "evaluateTrajectory": _evaluate_trajectory_json,
            "evaluateFieldLines": _evaluate_field_lines_json,
            "evaluateScattering": _evaluate_scattering_json,
        }
        try:
            invoke = methods[method]
        except KeyError as error:
            raise ValueError(f"Unsupported desktop compute method: {method}") from error
        return invoke(payload)


class WorkbenchDesktopBridge:
    """Pure Python bridge backing the standalone desktop runtime."""

    def __init__(self) -> None:
        self._compute_queue = DesktopComputeQueue()

    def config(self, _payload: str = "") -> str:
        return config().model_dump_json()

    def list_presets(self, _payload: str = "") -> str:
        return _json_list(list_presets())

    def get_preset(self, payload: str) -> str:
        request = DesktopPresetRequest.model_validate_json(payload)
        return get_preset(request.preset_id).model_dump_json()

    def evaluate_field(self, payload: str) -> str:
        return _evaluate_field_json(payload)

    def evaluate_trajectory(self, payload: str) -> str:
        return _evaluate_trajectory_json(payload)

    def evaluate_field_lines(self, payload: str) -> str:
        return _evaluate_field_lines_json(payload)

    def compute_status(self, payload: str = "") -> str:
        return _status_json(payload)

    def submit_compute(self, payload: str) -> str:
        request = json.loads(payload)
        method = str(request["method"])
        method_payload = request.get("payload")
        encoded_payload = (
            method_payload
            if isinstance(method_payload, str)
            else json.dumps(method_payload, ensure_ascii=False)
            if method_payload is not None
            else ""
        )
        return self._compute_queue.submit(method, encoded_payload)

    def poll_compute(self, ticket: str) -> str:
        return self._compute_queue.poll(ticket)

    def evaluate_scattering(self, payload: str) -> str:
        return _evaluate_scattering_json(payload)


def _json_list(
    items: (
        list[PresetSummary]
        | list[Preset]
        | list[FieldEvaluationResponse]
        | list[TrajectoryResponse]
        | list[FieldLineResponse]
        | list[ScatterResponse]
    ),
) -> str:
    return json.dumps([item.model_dump(mode="json") for item in items], ensure_ascii=False)
