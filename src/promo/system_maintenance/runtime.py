from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING

from promo.shared.logging import get_logger
from promo.shared.persistence.logging import RepositoryLogger
from promo.system_maintenance.retention import (
    RunFileRetentionDependencies,
    TemporaryFileRetentionDependencies,
    expire_run_files,
    purge_temporary_files,
)

if TYPE_CHECKING:
    from promo.shared.persistence.wiring import PersistenceAppContext


@dataclass(slots=True)
class InProcessMaintenanceSchedulerRuntime:
    app_context: "PersistenceAppContext"
    interval_seconds: float = 1.0
    join_timeout_seconds: float = 2.0
    _stop_event: Event = field(init=False, repr=False)
    _thread_lock: Lock = field(init=False, repr=False)
    _thread: Thread | None = field(init=False, default=None, repr=False)
    _logger: object = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._stop_event = Event()
        self._thread_lock = Lock()
        self._logger = get_logger("promo.system_maintenance.runtime")

    def start(self) -> None:
        with self._thread_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = Thread(
                target=self._run_loop,
                name="promo-maintenance-runtime",
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

    def run_once(self) -> None:
        self._run_task("purge_temporary_files", self._purge_temporary_files)
        self._run_task("expire_run_files", self._expire_run_files)
        self._run_task("timeout_reconciliation", self._reconcile_timed_out_runs)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception:  # noqa: BLE001
                self._logger.exception("maintenance_scheduler_iteration_failed")
            self._stop_event.wait(self.interval_seconds)

    def _purge_temporary_files(self) -> None:
        with self.app_context.request_scope(commit=True) as bundle:
            purge_temporary_files(
                dependencies=TemporaryFileRetentionDependencies(
                    temporary_files=bundle.uow.repositories.temporary_files,
                    file_storage=self.app_context.file_storage,
                    logger=self._repository_logger(bundle),
                ),
                clock=self.app_context.clock,
            )

    def _expire_run_files(self) -> None:
        with self.app_context.request_scope(commit=True) as bundle:
            expire_run_files(
                dependencies=RunFileRetentionDependencies(
                    run_files=bundle.uow.repositories.run_files,
                    file_storage=self.app_context.file_storage,
                    logger=self._repository_logger(bundle),
                ),
                clock=self.app_context.clock,
            )

    def _reconcile_timed_out_runs(self) -> None:
        with self.app_context.request_scope(commit=True) as bundle:
            bundle.runs.reconcile_timed_out_runs()

    def _run_task(self, task_name: str, operation) -> None:
        try:
            operation()
        except Exception as exc:  # noqa: BLE001
            self._persist_system_error(
                maintenance_task=task_name,
                reason="maintenance_task_failed",
                exception_type=exc.__class__.__name__,
                error_message=str(exc),
            )
            self._logger.exception("maintenance_scheduler_task_failed task=%s", task_name)

    def _persist_system_error(
        self,
        *,
        maintenance_task: str,
        reason: str,
        exception_type: str,
        error_message: str,
    ) -> None:
        try:
            with self.app_context.request_scope(commit=True) as bundle:
                self._repository_logger(bundle).error(
                    "system_error runtime_component=%s maintenance_task=%s reason=%s exception_type=%s error_message=%s",
                    "maintenance_scheduler",
                    maintenance_task,
                    reason,
                    exception_type,
                    error_message.strip().replace(" ", "_"),
                )
        except Exception:  # noqa: BLE001
            self._logger.exception(
                "maintenance_scheduler_system_error_persist_failed task=%s",
                maintenance_task,
            )

    def _repository_logger(self, bundle) -> RepositoryLogger:
        return RepositoryLogger(
            bundle.uow.repositories.logs,
            clock=self.app_context.clock,
            fallback=get_logger("promo.system_maintenance"),
        )
