from __future__ import annotations

from collections.abc import Callable
from threading import RLock, Thread

from em_workbench.physics.compute.contracts import WarmupStatus


class ComputeWarmup:
    def __init__(self, run_cpu: Callable[[], None], run_cuda: Callable[[], None]) -> None:
        self._run_cpu = run_cpu
        self._run_cuda = run_cuda
        self._status = WarmupStatus()
        self._thread: Thread | None = None
        self._lock = RLock()

    def start(self) -> None:
        with self._lock:
            if self._status.state != "idle":
                return
            self._status = WarmupStatus(state="warming")
            self._thread = Thread(target=self._run, name="em-compute-warmup", daemon=True)
            self._thread.start()

    def join(self, timeout: float | None = None) -> None:
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def status(self) -> WarmupStatus:
        with self._lock:
            return self._status.model_copy()

    def _run(self) -> None:
        try:
            self._run_cpu()
            self._run_cuda()
        except Exception as error:
            with self._lock:
                self._status = WarmupStatus(state="failed", failure_reason=str(error))
            return
        with self._lock:
            self._status = WarmupStatus(state="ready")
