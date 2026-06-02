from __future__ import annotations

import math
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

import numpy as np

from em_workbench.models import Position, Scene
from em_workbench.physics.compute.contracts import (
    BackendPolicy,
    CudaRuntimeStatus,
    ExecutionMetadata,
)
from em_workbench.physics.compute.cpu_backend import (
    evaluate_contributions_cpu,
    evaluate_totals_cpu,
)
from em_workbench.physics.compute.cuda_backend import (
    CudaUnavailable,
    DeviceSceneCache,
    evaluate_totals_cuda,
)
from em_workbench.physics.compute.packed_scene import PackedScene, PackedSceneCache
from em_workbench.physics.compute.runtime import _cpu_status, _cuda_status
from em_workbench.physics.solver import (
    COULOMB_CONSTANT,
    EPSILON_0,
    MIN_SOURCE_DISTANCE_M,
    RESULT_VERSION,
    FieldEvaluationResponse,
    FieldSampleResult,
    FieldVector,
    MetadataValue,
    SolverQuality,
    SourceContribution,
    _sample_is_near_line_segment,
    _sample_is_near_ring,
    _settings_for_quality,
    _unique_warnings,
    evaluate_scene_scalar,
)
from em_workbench.physics.vectors import Vector3

MIN_SOURCE_DISTANCE_SQ = MIN_SOURCE_DISTANCE_M**2
CUDA_BATCH_SAMPLE_THRESHOLD = 128
CUDA_FIELD_LINE_THRESHOLD = 24


@dataclass(frozen=True)
class TotalFieldResult:
    potential_v: np.ndarray
    field_v_per_m: np.ndarray
    execution: ExecutionMetadata


class ComputeService:
    def __init__(
        self,
        *,
        packed_scene_cache: PackedSceneCache | None = None,
        device_scene_cache: DeviceSceneCache | None = None,
        cuda_probe: Callable[[], CudaRuntimeStatus] | None = None,
    ) -> None:
        self.packed_scene_cache = packed_scene_cache or PackedSceneCache()
        self.device_scene_cache = device_scene_cache or DeviceSceneCache()
        self.cuda_probe = cuda_probe or _cuda_status
        self._cpu_warm = False
        self._cuda_warm = False

    def evaluate_totals(
        self,
        scene: Scene,
        sample_points: Iterable[Position | dict[str, float] | tuple[float, float, float]],
        *,
        quality: SolverQuality = "preview",
        backend: BackendPolicy = "auto",
    ) -> TotalFieldResult:
        started = time.perf_counter()
        vectors = [Vector3.from_sample(sample) for sample in sample_points]
        if backend == "scalar":
            scalar = evaluate_scene_scalar(scene, vectors, quality=quality)
            potential = np.asarray([sample.potential_v for sample in scalar.samples])
            field = np.asarray(
                [
                    [sample.field_v_per_m.x, sample.field_v_per_m.y, sample.field_v_per_m.z]
                    for sample in scalar.samples
                ]
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            return TotalFieldResult(
                potential_v=potential,
                field_v_per_m=field,
                execution=self._execution_metadata(
                    backend_requested=backend,
                    backend_effective="scalar",
                    precision="float64",
                    scene_cache_hit=False,
                    warm=True,
                    compute_ms=elapsed_ms,
                    total_ms=elapsed_ms,
                ),
            )

        packed, cache_hit = self.packed_scene_cache.get_or_compile(scene, quality=quality)
        points = self._points_array(vectors, packed)
        effective_backend, fallback_reason, cuda_status = self._select_backend(
            operation="field",
            sample_count=len(vectors),
            backend=backend,
        )
        if effective_backend == "cuda":
            warm = self._cuda_warm
            compute_started = time.perf_counter()
            try:
                potential, field, device_cache_hit = evaluate_totals_cuda(
                    packed,
                    points,
                    device_cache=self.device_scene_cache,
                )
            except Exception as error:
                effective_backend = "cpu-jit"
                fallback_reason = self._cuda_failure_reason(error)
            else:
                compute_ms = (time.perf_counter() - compute_started) * 1000.0
                self._cuda_warm = True
                return TotalFieldResult(
                    potential_v=potential,
                    field_v_per_m=field,
                    execution=self._execution_metadata(
                        backend_requested=backend,
                        backend_effective="cuda",
                        device=(cuda_status.device_name if cuda_status else None) or "CUDA",
                        precision=self._precision(packed),
                        scene_cache_hit=cache_hit,
                        device_cache_hit=device_cache_hit,
                        warm=warm,
                        compute_ms=compute_ms,
                        total_ms=(time.perf_counter() - started) * 1000.0,
                    ),
                )

        warm = self._cpu_warm
        compute_started = time.perf_counter()
        potential, field = evaluate_totals_cpu(packed, points)
        compute_ms = (time.perf_counter() - compute_started) * 1000.0
        self._cpu_warm = True
        return TotalFieldResult(
            potential_v=potential,
            field_v_per_m=field,
            execution=self._execution_metadata(
                backend_requested=backend,
                backend_effective="cpu-jit",
                precision=self._precision(packed),
                scene_cache_hit=cache_hit,
                warm=warm,
                compute_ms=compute_ms,
                total_ms=(time.perf_counter() - started) * 1000.0,
                fallback_reason=fallback_reason,
            ),
        )

    def evaluate_scene(
        self,
        scene: Scene,
        sample_points: Iterable[Position | dict[str, float] | tuple[float, float, float]],
        *,
        quality: SolverQuality = "preview",
        request_id: str | None = None,
        backend: BackendPolicy = "auto",
    ) -> FieldEvaluationResponse:
        started = time.perf_counter()
        vectors = [Vector3.from_sample(sample) for sample in sample_points]
        if backend == "scalar":
            scalar = evaluate_scene_scalar(
                scene,
                vectors,
                quality=quality,
                request_id=request_id,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            return scalar.model_copy(
                update={
                    "execution": self._execution_metadata(
                        backend_requested=backend,
                        backend_effective="scalar",
                        precision="float64",
                        scene_cache_hit=False,
                        warm=True,
                        compute_ms=elapsed_ms,
                        total_ms=elapsed_ms,
                    )
                }
            )

        settings = _settings_for_quality(quality)
        packed, cache_hit = self.packed_scene_cache.get_or_compile(scene, quality=quality)
        points = self._points_array(vectors, packed)
        warm = self._cpu_warm
        compute_started = time.perf_counter()
        contribution_values = evaluate_contributions_cpu(packed, points)
        compute_ms = (time.perf_counter() - compute_started) * 1000.0
        self._cpu_warm = True
        samples = [
            self._sample_result(scene, packed, vector, values, settings)
            for vector, values in zip(vectors, contribution_values, strict=True)
        ]
        warnings = _unique_warnings(warning for sample in samples for warning in sample.warnings)
        return FieldEvaluationResponse(
            request_id=request_id,
            result_version=RESULT_VERSION,
            quality=quality,
            sample_count=len(samples),
            samples=samples,
            warnings=warnings,
            metadata=self._response_metadata(quality, settings),
            execution=self._execution_metadata(
                backend_requested=backend,
                backend_effective="cpu-jit",
                precision=self._precision(packed),
                scene_cache_hit=cache_hit,
                warm=warm,
                compute_ms=compute_ms,
                total_ms=(time.perf_counter() - started) * 1000.0,
            ),
        )

    @staticmethod
    def _points_array(vectors: list[Vector3], packed: PackedScene) -> np.ndarray:
        return np.asarray(
            [[vector.x, vector.y, vector.z] for vector in vectors],
            dtype=packed.dtype,
        )

    @staticmethod
    def _precision(packed: PackedScene) -> str:
        return "float32" if packed.dtype == np.dtype(np.float32) else "float64"

    @staticmethod
    def _response_metadata(
        quality: SolverQuality,
        settings: dict[str, int],
    ) -> dict[str, MetadataValue]:
        return {
            "quality": quality,
            "epsilon0_f_per_m": EPSILON_0,
            "coulomb_constant_n_m2_per_c2": COULOMB_CONSTANT,
            "min_source_distance_m": MIN_SOURCE_DISTANCE_M,
            **settings,
        }

    @staticmethod
    def _execution_metadata(
        *,
        backend_requested: BackendPolicy,
        backend_effective: str,
        device: str | None = None,
        precision: str,
        scene_cache_hit: bool,
        device_cache_hit: bool = False,
        warm: bool,
        compute_ms: float,
        total_ms: float,
        fallback_reason: str | None = None,
    ) -> ExecutionMetadata:
        return ExecutionMetadata(
            backend_requested=backend_requested,
            backend_effective=backend_effective,
            device=device or _cpu_status().description,
            precision=precision,
            scene_cache_hit=scene_cache_hit,
            device_cache_hit=device_cache_hit,
            warm=warm,
            compute_ms=compute_ms,
            total_ms=total_ms,
            fallback_reason=fallback_reason,
        )

    def _select_backend(
        self,
        *,
        operation: str,
        sample_count: int,
        backend: BackendPolicy,
    ) -> tuple[str, str | None, CudaRuntimeStatus | None]:
        if backend == "scalar":
            return "scalar", None, None
        if backend == "cpu":
            return "cpu-jit", None, None
        cuda_status = self.cuda_probe()
        if not cuda_status.available:
            return "cpu-jit", cuda_status.fallback_reason, cuda_status
        if backend == "cuda":
            return "cuda", None, cuda_status
        if operation == "trajectory":
            return "cpu-jit", None, cuda_status
        if operation == "field-lines" or sample_count >= CUDA_BATCH_SAMPLE_THRESHOLD:
            return "cuda", None, cuda_status
        return "cpu-jit", None, cuda_status

    @staticmethod
    def _cuda_failure_reason(error: Exception) -> str:
        if isinstance(error, CudaUnavailable):
            return str(error)
        return f"CUDA execution failed: {error}"

    def _sample_result(
        self,
        scene: Scene,
        packed: PackedScene,
        sample: Vector3,
        values: np.ndarray,
        settings: dict[str, int],
    ) -> FieldSampleResult:
        contributions = [
            self._source_contribution(source, source_index, packed, sample, source_values, settings)
            for source_index, (source, source_values) in enumerate(
                zip(scene.sources, values, strict=True)
            )
        ]
        potential = math.fsum(contribution.potential_v for contribution in contributions)
        field = Vector3(
            math.fsum(contribution.field_v_per_m.x for contribution in contributions),
            math.fsum(contribution.field_v_per_m.y for contribution in contributions),
            math.fsum(contribution.field_v_per_m.z for contribution in contributions),
        )
        warnings = _unique_warnings(
            warning for contribution in contributions for warning in contribution.warnings
        )
        return FieldSampleResult(
            point=Position(x=sample.x, y=sample.y, z=sample.z),
            potential_v=potential,
            field_v_per_m=FieldVector.from_vector(field),
            field_magnitude_v_per_m=field.magnitude(),
            contributions=contributions,
            warnings=warnings,
        )

    def _source_contribution(
        self,
        source,
        source_index: int,
        packed: PackedScene,
        sample: Vector3,
        values: np.ndarray,
        settings: dict[str, int],
    ) -> SourceContribution:
        warnings, metadata = self._source_presentation(
            source,
            source_index,
            packed,
            sample,
            settings,
        )
        field = Vector3(float(values[1]), float(values[2]), float(values[3]))
        return SourceContribution(
            source_id=source.id,
            source_kind=source.kind,
            potential_v=float(values[0]),
            field_v_per_m=FieldVector.from_vector(field),
            field_magnitude_v_per_m=field.magnitude(),
            warnings=warnings,
            metadata=metadata,
        )

    def _source_presentation(
        self,
        source,
        source_index: int,
        packed: PackedScene,
        sample: Vector3,
        settings: dict[str, int],
    ) -> tuple[list[str], dict[str, MetadataValue]]:
        warnings: list[str] = []
        if source.kind == "point":
            metadata: dict[str, MetadataValue] = {"method": "analytic-point"}
        elif source.kind == "ring":
            metadata = {
                "method": "discrete-ring",
                "segments": settings["ring_segments"],
                "radius_m": source.radius_m,
            }
            warnings.append(
                f"Source {source.id} ring uses a {settings['ring_segments']}-segment "
                "finite-segment approximation; analytic ring precision is not claimed off axis."
            )
            center = Vector3.from_position(source.position)
            normal = Vector3.from_position(source.normal).normalized()
            if _sample_is_near_ring(source, sample, center, normal):
                warnings.append(
                    f"Sample is near source {source.id} ring geometry; finite-segment result is "
                    "near singular and should be treated as a limitation."
                )
        elif source.kind == "line_segment":
            metadata = {
                "method": "discrete-line-segment",
                "segments": settings["line_segments"],
                "length_m": source.length_m,
            }
            warnings.append(
                f"Source {source.id} line_segment uses a {settings['line_segments']}-segment "
                "numerical approximation; analytic finite-line precision is not claimed."
            )
            center = Vector3.from_position(source.position)
            axis = Vector3.from_position(source.orientation).normalized()
            if _sample_is_near_line_segment(source, sample, center, axis):
                warnings.append(
                    f"Sample is near source {source.id} line_segment geometry; finite-segment "
                    "result is near singular and should be treated as a limitation."
                )
        elif source.kind == "disk":
            metadata = {
                "method": "discrete-disk",
                "radial_segments": settings["disk_radial_segments"],
                "angular_segments": settings["disk_angular_segments"],
                "radius_m": source.radius_m,
            }
            warnings.append(
                f"Source {source.id} disk uses a {settings['disk_radial_segments']}x"
                f"{settings['disk_angular_segments']} midpoint numerical approximation; "
                "analytic disk precision is not claimed."
            )
        elif source.kind == "infinite_plane":
            metadata = {"method": "analytic-infinite-plane"}
            normal = Vector3.from_position(source.normal).normalized()
            signed_distance = (sample - Vector3.from_position(source.position)).dot(normal)
            warnings.append(
                f"Source {source.id} infinite_plane potential uses V=0 at the plane; "
                "the absolute potential of an infinite plane has arbitrary reference."
            )
            if abs(signed_distance) <= MIN_SOURCE_DISTANCE_M:
                warnings.append(
                    f"Sample lies on source {source.id} infinite_plane; discontinuous field was "
                    "bounded to zero at the surface."
                )
        else:
            displacement = sample - Vector3.from_position(source.position)
            distance = displacement.magnitude()
            metadata = {
                "method": "analytic-spherical-shell",
                "region": "inside" if distance < source.radius_m else "outside",
            }
            if abs(distance - source.radius_m) <= MIN_SOURCE_DISTANCE_M:
                warnings.append(
                    f"Sample is on source {source.id} spherical_shell; surface field is "
                    "discontinuous."
                )

        if source.kind in {"point", "line_segment", "ring", "disk"} and self._is_near_element(
            source_index,
            packed,
            sample,
        ):
            warnings.append(
                f"Sample is at or within {MIN_SOURCE_DISTANCE_M:g} m of source {source.id}; "
                "singular point-charge contribution was bounded to zero."
            )
        return _unique_warnings(warnings), metadata

    @staticmethod
    def _is_near_element(source_index: int, packed: PackedScene, sample: Vector3) -> bool:
        indexes = np.flatnonzero(packed.element_source_indexes == source_index)
        if indexes.size == 0:
            return False
        positions = packed.element_positions[indexes]
        displacement = positions - np.asarray([sample.x, sample.y, sample.z], dtype=packed.dtype)
        return bool(np.any(np.sum(displacement * displacement, axis=1) <= MIN_SOURCE_DISTANCE_SQ))


DEFAULT_COMPUTE_SERVICE = ComputeService()
