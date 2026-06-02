from em_workbench.physics.compute.runtime import probe_runtime


def test_runtime_probe_always_reports_cpu_and_cuda_state() -> None:
    status = probe_runtime()

    assert status.cpu.logical_processors >= 1
    assert status.cpu.description
    assert isinstance(status.cuda.installed, bool)
    assert isinstance(status.cuda.available, bool)
    if not status.cuda.available:
        assert status.cuda.device_name is None
        assert status.cuda.fallback_reason
