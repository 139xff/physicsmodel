from em_workbench.physics.compute.runtime import probe_runtime
from em_workbench.physics.compute.warmup import ComputeWarmup


def test_runtime_probe_always_reports_cpu_and_cuda_state() -> None:
    status = probe_runtime()

    assert status.cpu.logical_processors >= 1
    assert status.cpu.description
    assert isinstance(status.cuda.installed, bool)
    assert isinstance(status.cuda.available, bool)
    if not status.cuda.available:
        assert status.cuda.device_name is None
        assert status.cuda.fallback_reason


def test_runtime_probe_cuda_availability_implies_device_details() -> None:
    status = probe_runtime()

    if status.cuda.available:
        assert status.cuda.device_name
        assert status.cuda.compute_capability


def test_warmup_moves_from_idle_to_ready() -> None:
    warmup = ComputeWarmup(run_cpu=lambda: None, run_cuda=lambda: None)

    warmup.start()
    warmup.join(timeout=5)

    assert warmup.status().state == "ready"
