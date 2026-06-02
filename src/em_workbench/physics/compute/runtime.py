from __future__ import annotations

import os
import platform

from em_workbench.physics.compute.contracts import (
    CacheStatus,
    ComputeStatus,
    CpuRuntimeStatus,
    CudaRuntimeStatus,
    WarmupStatus,
)


def _cpu_status() -> CpuRuntimeStatus:
    logical = os.cpu_count() or 1
    return CpuRuntimeStatus(
        description=platform.processor() or platform.machine() or "CPU",
        physical_cores=None,
        logical_processors=logical,
    )


def _cuda_status() -> CudaRuntimeStatus:
    try:
        from numba import cuda
    except Exception as error:
        return CudaRuntimeStatus(
            installed=False,
            available=False,
            fallback_reason=f"CUDA package unavailable: {error}",
        )
    try:
        if not cuda.is_available():
            return CudaRuntimeStatus(
                installed=True,
                available=False,
                fallback_reason="CUDA runtime unavailable.",
            )
        device = cuda.get_current_device()
        capability = ".".join(str(part) for part in device.compute_capability)
        return CudaRuntimeStatus(
            installed=True,
            available=True,
            device_name=(
                device.name.decode() if isinstance(device.name, bytes) else str(device.name)
            ),
            compute_capability=capability,
        )
    except Exception as error:
        return CudaRuntimeStatus(
            installed=True,
            available=False,
            fallback_reason=f"CUDA probe failed: {error}",
        )


def probe_runtime(
    *,
    warmup: WarmupStatus | None = None,
    cache: CacheStatus | None = None,
    last_fallback_reason: str | None = None,
) -> ComputeStatus:
    return ComputeStatus(
        cpu=_cpu_status(),
        cuda=_cuda_status(),
        warmup=warmup or WarmupStatus(),
        cache=cache or CacheStatus(),
        last_fallback_reason=last_fallback_reason,
    )
