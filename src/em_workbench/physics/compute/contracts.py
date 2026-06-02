from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

BackendPolicy = Literal["auto", "cpu", "cuda", "scalar"]
EffectiveBackend = Literal["cpu-jit", "cuda", "scalar"]
Precision = Literal["float32", "float64"]
WarmupState = Literal["idle", "warming", "ready", "failed"]


class ComputeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CpuRuntimeStatus(ComputeModel):
    description: str
    physical_cores: int | None
    logical_processors: int


class CudaRuntimeStatus(ComputeModel):
    installed: bool
    available: bool
    device_name: str | None = None
    compute_capability: str | None = None
    fallback_reason: str | None = None


class WarmupStatus(ComputeModel):
    state: WarmupState = "idle"
    failure_reason: str | None = None


class CacheStatus(ComputeModel):
    packed_scenes: int = 0
    packed_scene_limit: int = 16
    device_scenes: int = 0
    device_scene_limit: int = 8
    field_lines: int = 0
    field_line_limit: int = 16


class ComputeStatus(ComputeModel):
    cpu: CpuRuntimeStatus
    cuda: CudaRuntimeStatus
    warmup: WarmupStatus
    cache: CacheStatus
    last_fallback_reason: str | None = None


class ExecutionMetadata(ComputeModel):
    backend_requested: BackendPolicy
    backend_effective: EffectiveBackend
    device: str
    precision: Precision
    scene_cache_hit: bool
    device_cache_hit: bool = False
    warm: bool
    compute_ms: float
    total_ms: float
    fallback_reason: str | None = None


@dataclass(frozen=True)
class TotalFieldArrays:
    potential_v: object
    field_v_per_m: object
