"""FastAPI application shell for the EM Workbench browser surface."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
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
            "scene_editing": "planned",
            "solver": "planned",
            "interaction": "planned",
        },
        runtime=RuntimeConfig(
            delivery="local-vendor",
            manifest_url="/vendor/manifest.json",
            three=ThreeRuntimeConfig(
                version=_vendor_version(),
                module_url="/vendor/three.module.js",
                orbit_controls_url="/vendor/OrbitControls.js",
            ),
        ),
    )


app.mount("/", StaticFiles(directory=WEB_ROOT, html=True), name="workspace")
