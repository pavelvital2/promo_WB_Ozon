from __future__ import annotations

from dataclasses import dataclass, field, replace
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING

from promo.shared.errors import ValidationFailedError
from promo.shared.logging import get_logger
from promo.shared.persistence.logging import RepositoryLogger

if TYPE_CHECKING:
    from promo.shared.persistence.wiring import PersistenceAppContext


@dataclass(slots=True)
class InProcessRunWorkerRuntime:
    app_context: "PersistenceAppContext"
    idle_timeout_seconds: float = 0.25
    join_timeout_seconds: float = 2.0
    commit_visibility_retry_seconds: float = 0.05
    max_run_visibility_retries: int = 3
    _stop_event: Event = field(init=False, repr=False)
    _thread_lock: Lock = field(init=False, repr=False)
    _thread: Thread | None = field(init=False, default=None, repr=False)
    _logger: object = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._stop_event = Event()
        self._thread_lock = Lock()
        self._logger = get_logger("promo.runs.runtime")

    def start(self) -> None:
        with self._thread_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = Thread(
                target=self._run_loop,
                name="promo-run-worker",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._thread_lock:
            thread = self._thread
            self._stop_event.set()
        if thread is not None:
            thread.join(timeout=self.join_timeout_seconds)

    def is_running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            job = self.app_context.run_queue.wait_for_job(timeout=self.idle_timeout_seconds)
            if job is None:
                continue
            try:
                with self.app_context.request_scope(commit=True) as bundle:
                    bundle.runs.execute_run(job.run_id, phase=job.phase)
            except ValidationFailedError as exc:
                if exc.details.get("run_id") == job.run_id and job.attempt < self.max_run_visibility_retries:
                    if self._stop_event.wait(self.commit_visibility_retry_seconds):
                        break
                    self.app_context.run_queue.enqueue(replace(job, attempt=job.attempt + 1))
                    continue
                self._persist_system_error(
                    run_id=job.run_id,
                    phase=job.phase,
                    reason="run_lookup_failed",
                    exception_type=exc.__class__.__name__,
                    error_message=str(exc),
                )
                self._logger.exception(
                    "run_worker_execution_failed run_id=%s phase=%s",
                    job.run_id,
                    job.phase,
                )
            except Exception as exc:  # noqa: BLE001
                self._persist_system_error(
                    run_id=job.run_id,
                    phase=job.phase,
                    reason="unexpected_worker_exception",
                    exception_type=exc.__class__.__name__,
                    error_message=str(exc),
                )
                self._finalize_run_failure(
                    run_id=job.run_id,
                    phase=job.phase,
                    error_message="Run failed inside worker runtime",
                    error_type=exc.__class__.__name__,
                )
                self._logger.exception(
                    "run_worker_execution_failed run_id=%s phase=%s",
                    job.run_id,
                    job.phase,
                )

    def _finalize_run_failure(self, *, run_id: int, phase: str | None, error_message: str, error_type: str) -> None:
        try:
            with self.app_context.request_scope(commit=True) as bundle:
                bundle.runs.finalize_runtime_execution_failure(
                    run_id,
                    phase=phase,
                    error_message=error_message,
                    error_type=error_type,
                )
        except Exception:  # noqa: BLE001
            self._logger.exception(
                "run_worker_failure_finalization_failed run_id=%s phase=%s",
                run_id,
                phase,
            )

    def _persist_system_error(
        self,
        *,
        run_id: int,
        phase: str | None,
        reason: str,
        exception_type: str,
        error_message: str,
    ) -> None:
        try:
            with self.app_context.request_scope(commit=True) as bundle:
                logger = RepositoryLogger(
                    bundle.uow.repositories.logs,
                    clock=self.app_context.clock,
                    fallback=get_logger("promo.runs.runtime"),
                )
                logger.error(
                    "system_error run_id=%s runtime_component=%s phase=%s reason=%s exception_type=%s error_message=%s",
                    run_id,
                    "run_worker",
                    phase or "",
                    reason,
                    exception_type,
                    error_message.strip().replace(" ", "_"),
                )
        except Exception:  # noqa: BLE001
            self._logger.exception(
                "run_worker_system_error_persist_failed run_id=%s phase=%s",
                run_id,
                phase,
            )
