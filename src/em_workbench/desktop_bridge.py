"""Desktop bridge methods shared by Qt and tests."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from em_workbench.app import TrajectoryEvaluateRequest, config
from em_workbench.models import Position, Preset, PresetSummary, Scene
from em_workbench.physics.dynamics import TrajectoryResponse, simulate_trajectory
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


class WorkbenchDesktopBridge:
    """Pure Python bridge backing the standalone desktop runtime."""

    def config(self, _payload: str = "") -> str:
        return config().model_dump_json()

    def list_presets(self, _payload: str = "") -> str:
        return _json_list(list_presets())

    def get_preset(self, payload: str) -> str:
        request = DesktopPresetRequest.model_validate_json(payload)
        return get_preset(request.preset_id).model_dump_json()

    def evaluate_field(self, payload: str) -> str:
        request = DesktopFieldEvaluateRequest.model_validate_json(payload)
        result = evaluate_scene(
            request.scene,
            request.sample_points,
            quality=request.quality,
            request_id=request.request_id,
        )
        return result.model_dump_json()

    def evaluate_trajectory(self, payload: str) -> str:
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


def _json_list(
    items: (
        list[PresetSummary]
        | list[Preset]
        | list[FieldEvaluationResponse]
        | list[TrajectoryResponse]
    ),
) -> str:
    return json.dumps([item.model_dump(mode="json") for item in items], ensure_ascii=False)
