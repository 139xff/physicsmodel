"""FastAPI application shell for the EM Workbench browser surface."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from em_workbench.models import Position, Preset, PresetSummary, Scene, SceneValidationResponse
from em_workbench.physics.compute.contracts import ComputeStatus
from em_workbench.physics.compute.runtime import probe_runtime
from em_workbench.physics.dynamics import TestCharge, TrajectoryResponse, simulate_trajectory
from em_workbench.physics.solver import FieldEvaluationResponse, SolverQuality, evaluate_scene
from em_workbench.presets import get_preset, list_presets


def _project_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _project_root()
WEB_ROOT = PROJECT_ROOT / "web"
VENDOR_MANIFEST_PATH = WEB_ROOT / "vendor" / "manifest.json"


class HealthResponse(BaseModel):
    """Stable readiness response for the browser shell."""

    status: str
    service: str
    module: str


class ProductConfig(BaseModel):
    """Product identity presented to the static client."""

    name: str
    module: str


class ThreeRuntimeConfig(BaseModel):
    """Locally served browser runtime paths."""

    version: str
    module_url: str
    orbit_controls_url: str


class RuntimeConfig(BaseModel):
    """Browser-runtime delivery configuration."""

    delivery: str
    manifest_url: str
    three: ThreeRuntimeConfig


class AppConfig(BaseModel):
    """Stable application-shell contract exposed to the browser."""

    product: ProductConfig
    supported_views: list[str]
    capabilities: dict[str, str]
    runtime: RuntimeConfig


class FieldEvaluateRequest(BaseModel):
    """Batch field-evaluation request from the static client."""

    request_id: str = Field(min_length=1)
    scene: Scene
    sample_points: list[Position] = Field(min_length=1)
    quality: SolverQuality = "preview"


class TrajectoryEvaluateRequest(BaseModel):
    """Test-charge trajectory request from the static client."""

    request_id: str = Field(min_length=1)
    scene: Scene
    particle: TestCharge
    dt_s: float = Field(gt=0)
    steps: int = Field(ge=1, le=5000)
    quality: SolverQuality = "preview"
    record_every: int = Field(default=1, ge=1)


def _vendor_version() -> str:
    manifest = json.loads(VENDOR_MANIFEST_PATH.read_text(encoding="utf-8"))
    return str(manifest["version"])


app = FastAPI(
    title="EM Workbench",
    description="Static Electrostatics application shell",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return service availability without implying solver availability."""
    return HealthResponse(
        status="ok",
        service="em-workbench",
        module="static-electrostatics",
    )


@app.get("/api/config", response_model=AppConfig)
def config() -> AppConfig:
    """Return browser-shell identity and local runtime locations."""
    return AppConfig(
        product=ProductConfig(name="EM Workbench", module="Static Electrostatics"),
        supported_views=["2D", "3D"],
        capabilities={
            "scene_editing": "available",
            "solver": "available",
            "interaction": "available",
        },
        runtime=RuntimeConfig(
            delivery="local-vendor",
            manifest_url="/vendor/manifest.json",
            three=ThreeRuntimeConfig(
                version=_vendor_version(),
                module_url="/vendor/three.module.js",
                orbit_controls_url="/vendor/controls/OrbitControls.js",
            ),
        ),
    )


@app.get("/api/presets", response_model=list[PresetSummary])
def presets() -> list[PresetSummary]:
    """Return loadable scene presets without solver output."""
    return list_presets()


@app.get("/api/compute/status", response_model=ComputeStatus)
def compute_status() -> ComputeStatus:
    """Return CPU availability and optional CUDA runtime details."""
    return probe_runtime()


@app.get("/api/presets/{preset_id}", response_model=Preset)
def preset_detail(preset_id: str) -> Preset:
    """Return an editable scene JSON payload for one preset."""
    try:
        return get_preset(preset_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Preset not found.") from error


@app.post("/api/scene/validate", response_model=SceneValidationResponse)
def validate_scene(scene: Scene) -> SceneValidationResponse:
    """Validate and normalize a scene without persisting or solving it."""
    return SceneValidationResponse(
        valid=True,
        scene=scene,
        source_count=len(scene.sources),
        source_kinds=[source.kind for source in scene.sources],
    )


@app.post("/api/field/evaluate", response_model=FieldEvaluationResponse)
def evaluate_field(request: FieldEvaluateRequest) -> FieldEvaluationResponse:
    """Evaluate electrostatic potential and field at one or more sample points."""
    return evaluate_scene(
        request.scene,
        request.sample_points,
        quality=request.quality,
        request_id=request.request_id,
    )


@app.post("/api/field/trajectory", response_model=TrajectoryResponse)
def evaluate_trajectory(request: TrajectoryEvaluateRequest) -> TrajectoryResponse:
    """Simulate a test charge moving through the scene's electrostatic field."""
    return simulate_trajectory(
        request.scene,
        request.particle,
        dt_s=request.dt_s,
        steps=request.steps,
        quality=request.quality,
        record_every=request.record_every,
        request_id=request.request_id,
    )


app.mount("/", StaticFiles(directory=WEB_ROOT, html=True), name="workspace")
