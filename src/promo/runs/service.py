from __future__ import annotations

import hashlib
from threading import Condition
from collections import deque
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Callable

from promo.access.contracts import SessionContextDTO
from promo.access.policy import AccessPolicy
from promo.file_storage.service import FileStorageService
from promo.runs.contracts import RunExecutionJob, RunExecutionResult, RunExecutionStrategy, RunLookupGateway, RunServiceDependencies
from promo.runs.presentation import RunFileViewModel, RunPageViewModel, RunPollingViewModel
from promo.shared.clock import utc_now
from promo.shared.contracts.audit import RunDetailAuditDTO, RunSummaryAuditDTO
from promo.shared.contracts.files import TemporaryUploadedFileDTO
from promo.shared.contracts.runs import RunDTO, RunFileDTO
from promo.shared.contracts.stores import StoreDTO
from promo.shared.enums import BusinessResult, ErrorCode, FileRole, ModuleCode, OperationType, RunLifecycleStatus, StoreStatus, UnavailableReason
from promo.shared.errors import ActiveRunConflictError, AppError, ValidationFailedError
from promo.shared.logging import get_logger
from promo.temp_files.service import MAX_WB_PROMO_FILES, MAX_WB_TOTAL_SIZE_BYTES, WB_PRICE_FILE_KIND, WB_PROMO_FILE_KIND

OLD_RESULT_REMOVED_ON_NEW_SUCCESS_EVENT = "old_result_removed_on_new_success"
CHECK_STARTED_EVENT = "check_started"
CHECK_FINISHED_EVENT = "check_finished"
PROCESS_STARTED_EVENT = "process_started"
PROCESS_FINISHED_EVENT = "process_finished"
PROCESS_FINISHED_WITH_WARNINGS_EVENT = "process_finished_with_warnings"
PROCESS_ERROR_EVENT = "process_error"
RUN_TIMEOUT_SECONDS_CHECK = 300
RUN_TIMEOUT_SECONDS_PROCESS = 600


@dataclass(slots=True, frozen=True)
class RunLockState:
    store_id: int
    module_code: str
    run_id: int


class InMemoryRunLockManager:
    def __init__(self) -> None:
        self._locks: dict[tuple[int, str], int] = {}

    def has_active_run(self, store_id: int, module_code: ModuleCode) -> bool:
        return (store_id, module_code.value) in self._locks

    def acquire(self, store_id: int, module_code: ModuleCode, run_id: int) -> None:
        key = (store_id, module_code.value)
        current = self._locks.get(key)
        if current is not None and current != run_id:
            raise ActiveRunConflictError("Active run conflict", {"store_id": store_id, "module_code": module_code.value, "run_id": current})
        self._locks[key] = run_id

    def release(self, store_id: int, module_code: ModuleCode, run_id: int) -> None:
        key = (store_id, module_code.value)
        if self._locks.get(key) == run_id:
            self._locks.pop(key, None)

    def release_by_run(self, run: RunDTO) -> None:
        self.release(run.store_id, ModuleCode(run.module_code), run.id)


class RunExecutionQueue:
    def __init__(self) -> None:
        self._jobs: deque[RunExecutionJob] = deque()
        self._condition = Condition()

    def enqueue(self, job: RunExecutionJob) -> RunExecutionJob:
        with self._condition:
            self._jobs.append(job)
            self._condition.notify()
        return job

    def dequeue(self) -> RunExecutionJob | None:
        with self._condition:
            if not self._jobs:
                return None
            return self._jobs.popleft()

    def wait_for_job(self, timeout: float | None = None) -> RunExecutionJob | None:
        with self._condition:
            if not self._jobs:
                self._condition.wait(timeout=timeout)
            if not self._jobs:
                return None
            return self._jobs.popleft()

    def list_pending(self) -> tuple[RunExecutionJob, ...]:
        with self._condition:
            return tuple(self._jobs)


class SkeletonRunExecutionStrategy:
    def validate(self, run: RunDTO, store: StoreDTO, files: tuple[RunFileDTO, ...]) -> RunExecutionResult:
        return self._build_result(run, files, validation_phase=True)

    def execute(self, run: RunDTO, store: StoreDTO, files: tuple[RunFileDTO, ...]) -> RunExecutionResult:
        return self._build_result(run, files, validation_phase=False)

    def _build_result(self, run: RunDTO, files: tuple[RunFileDTO, ...], validation_phase: bool) -> RunExecutionResult:
        short_result_text = f"{run.operation_type} completed for {len(files)} files"
        if validation_phase and run.operation_type == OperationType.PROCESS.value:
            short_result_text = f"{run.operation_type} validation completed for {len(files)} files"
        business_result = (
            BusinessResult.CHECK_PASSED.value
            if run.operation_type == OperationType.CHECK.value
            else BusinessResult.COMPLETED.value
        )
        summary_json = {
            "operation_type": run.operation_type,
            "module_code": run.module_code,
            "processed_files": len(files),
            "warnings": 0,
            "validation_phase": validation_phase,
        }
        return RunExecutionResult(
            business_result=business_result,
            short_result_text=short_result_text,
            summary_json=summary_json,
        )


class MarketplaceRunExecutionStrategy:
    def __init__(self, file_storage: FileStorageService) -> None:
        self._file_storage = file_storage

    def validate(self, run: RunDTO, store: StoreDTO, files: tuple[RunFileDTO, ...]) -> RunExecutionResult:
        return self._dispatch(run, store, files, validate_only=True)

    def execute(self, run: RunDTO, store: StoreDTO, files: tuple[RunFileDTO, ...]) -> RunExecutionResult:
        return self._dispatch(run, store, files, validate_only=False)

    def _dispatch(self, run: RunDTO, store: StoreDTO, files: tuple[RunFileDTO, ...], validate_only: bool) -> RunExecutionResult:
        module_code = ModuleCode(run.module_code)
        if module_code == ModuleCode.WB:
            from promo.wb.service import WBExecutionStrategy

            strategy = WBExecutionStrategy(self._file_storage)
            return strategy.validate(run, store, files) if validate_only else strategy.execute(run, store, files)
        if module_code == ModuleCode.OZON:
            from promo.ozon.service import OzonExecutionStrategy

            strategy = OzonExecutionStrategy(self._file_storage)
            return strategy.validate(run, store, files) if validate_only else strategy.execute(run, store, files)
        raise ValidationFailedError("Unsupported module code", {"module_code": run.module_code})


class RunService:
    def __init__(
        self,
        dependencies: RunServiceDependencies,
        policy: AccessPolicy | None = None,
        clock: Callable[[], datetime] = utc_now,
        lock_manager: InMemoryRunLockManager | None = None,
        execution_strategy: RunExecutionStrategy | None = None,
        queue: RunExecutionQueue | None = None,
        logger=None,
    ) -> None:
        self._dependencies = dependencies
        self._policy = policy or AccessPolicy()
        self._clock = clock
        self._lock_manager = lock_manager or InMemoryRunLockManager()
        self._execution_strategy = execution_strategy or MarketplaceRunExecutionStrategy(dependencies.file_storage)
        self._queue = queue or RunExecutionQueue()
        self._logger = logger or get_logger(__name__)

    def create_check_run(self, context: SessionContextDTO, store_id: int) -> RunDTO:
        return self._create_run(context, store_id, OperationType.CHECK)

    def create_process_run(self, context: SessionContextDTO, store_id: int) -> RunDTO:
        return self._create_run(context, store_id, OperationType.PROCESS)

    def has_active_run(self, store_id: int, module_code: ModuleCode) -> bool:
        return self._lock_manager.has_active_run(store_id, module_code)

    def drain_pending_jobs(self, limit: int | None = None) -> int:
        if limit is not None and limit < 1:
            raise ValidationFailedError("Drain limit must be >= 1", {"limit": limit})
        processed = 0
        while limit is None or processed < limit:
            job = self._queue.dequeue()
            if job is None:
                break
            self.execute_run(job.run_id, phase=job.phase)
            processed += 1
        return processed

    def execute_run(self, run_id: int, phase: str | None = None) -> RunDTO:
        run = self._get_run(run_id)
        if run.lifecycle_status in {RunLifecycleStatus.COMPLETED.value, RunLifecycleStatus.FAILED.value}:
            return run
        store = self._get_store_for_execution(run.store_id)
        files = self._load_run_files(run_id)

        try:
            if run.operation_type == OperationType.CHECK.value:
                run = self._transition(run, RunLifecycleStatus.CHECKING.value)
                result = self._execution_strategy.validate(run, store, files)
            else:
                if phase == "validate" or run.lifecycle_status == RunLifecycleStatus.CREATED.value:
                    run = self._transition(run, RunLifecycleStatus.VALIDATING.value)
                    self._execution_strategy.validate(run, store, files)
                    self._queue.enqueue(RunExecutionJob(run_id=run.id, phase="execute"))
                    self._logger.info("process_validated run_id=%s store_id=%s module_code=%s", run.id, run.store_id, run.module_code)
                    return run
                run = self._transition(run, RunLifecycleStatus.PROCESSING.value)
                result = self._execution_strategy.execute(run, store, files)

            self._persist_audits(run, result)
            run = self._finalize_success(run, result)
            return run
        except ValidationFailedError as exc:
            return self._finalize_failure(
                run,
                business_result=BusinessResult.VALIDATION_FAILED.value if run.operation_type == OperationType.PROCESS.value else BusinessResult.CHECK_FAILED.value,
                message=str(exc),
                details=exc.details,
            )
        except Exception as exc:  # noqa: BLE001
            return self._finalize_failure(
                run,
                business_result=BusinessResult.FAILED.value if run.operation_type == OperationType.PROCESS.value else BusinessResult.CHECK_FAILED.value,
                message=str(exc),
                details=None,
            )

    def reconcile_timed_out_runs(self) -> int:
        now = self._clock()
        reconciled = 0
        for run in sorted(self._dependencies.runs.list(), key=lambda item: item.id):
            if run.lifecycle_status in {RunLifecycleStatus.COMPLETED.value, RunLifecycleStatus.FAILED.value}:
                continue
            timeout_seconds = self._hard_timeout_seconds(run)
            started_at = run.started_at_utc
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=UTC)
            if (now - started_at).total_seconds() <= timeout_seconds:
                continue
            business_result = BusinessResult.FAILED.value if run.operation_type == OperationType.PROCESS.value else BusinessResult.CHECK_FAILED.value
            details = {
                "maintenance_task": "timeout_reconciliation",
                "timed_out_lifecycle_status": run.lifecycle_status,
                "timeout_seconds": timeout_seconds,
                "started_at_utc": started_at.isoformat(),
                "reconciled_at_utc": now.isoformat(),
            }
            self._finalize_failure(
                run,
                business_result=business_result,
                message="Run exceeded hard timeout",
                details=details,
            )
            self._logger.error(
                "system_error run_id=%s store_id=%s module_code=%s public_run_number=%s maintenance_task=%s reason=%s timeout_seconds=%s timed_out_lifecycle_status=%s",
                run.id,
                run.store_id,
                run.module_code,
                run.public_run_number,
                "timeout_reconciliation",
                "hard_timeout",
                timeout_seconds,
                run.lifecycle_status,
            )
            reconciled += 1
        return reconciled

    def finalize_runtime_execution_failure(
        self,
        run_id: int,
        *,
        phase: str | None,
        error_message: str,
        error_type: str,
    ) -> RunDTO | None:
        run = self._dependencies.runs.get(run_id)
        if run is None:
            return None
        if run.lifecycle_status in {RunLifecycleStatus.COMPLETED.value, RunLifecycleStatus.FAILED.value}:
            return run
        business_result = BusinessResult.FAILED.value if run.operation_type == OperationType.PROCESS.value else BusinessResult.CHECK_FAILED.value
        return self._finalize_failure(
            run,
            business_result=business_result,
            message=error_message,
            details={
                "runtime_component": "run_worker",
                "failure_phase": phase or "",
                "reason": "unexpected_worker_exception",
                "exception_type": error_type,
            },
        )

    def get_run_status(self, run_id: int) -> RunPollingViewModel:
        run = self._get_run(run_id)
        return self._to_polling_view(run)

    def get_run_page(self, run_id: int) -> RunPageViewModel:
        run = self._get_run(run_id)
        summary = self._find_summary_audit(run_id)
        detail_count = sum(1 for item in self._dependencies.run_detail_audits.list() if item.run_id == run_id)
        files = tuple(self._to_file_view_model(item) for item in self._load_run_files(run_id))
        return RunPageViewModel(
            run=self._to_polling_view(run),
            summary_audit_json=summary.audit_json if summary is not None else None,
            detail_row_count=detail_count,
            files=files,
        )

    def lock_manager(self) -> InMemoryRunLockManager:
        return self._lock_manager

    def pending_jobs(self) -> tuple[RunExecutionJob, ...]:
        return self._queue.list_pending()

    def _create_run(self, context: SessionContextDTO, store_id: int, operation_type: OperationType) -> RunDTO:
        store = self._get_store(store_id)
        module_code = ModuleCode(store.marketplace)
        decision = self._policy.can_use_store_in_run(context, store, module_code, self._lock_manager)
        if not decision.allowed:
            if decision.reason_code == "active_run_conflict":
                raise ActiveRunConflictError("Active run conflict", decision.details)
            raise ValidationFailedError("Store cannot be used for run", decision.details)

        temp_files = self._load_active_temp_files(context.user.id, store_id, module_code)
        self._validate_run_input_set(module_code, temp_files)

        now = self._clock()
        run = RunDTO(
            id=self._next_run_id(),
            public_run_number=self._next_public_run_number(),
            store_id=store_id,
            initiated_by_user_id=context.user.id,
            operation_type=operation_type.value,
            lifecycle_status=RunLifecycleStatus.CREATED.value,
            business_result=None,
            module_code=module_code.value,
            input_set_signature=self._build_input_set_signature(temp_files),
            started_at_utc=now,
            finished_at_utc=None,
            short_result_text=None,
            result_file_id=None,
            validation_was_auto_before_process=operation_type == OperationType.PROCESS,
            created_at_utc=now,
            updated_at_utc=now,
        )
        self._dependencies.runs.add(run)
        copied_files: tuple[RunFileDTO, ...] = ()
        try:
            self._lock_manager.acquire(store_id, module_code, run.id)
            copied_files = self._copy_input_files(run, temp_files)
            queue_phase = "validate" if operation_type == OperationType.PROCESS else "execute"
            self._queue.enqueue(RunExecutionJob(run_id=run.id, phase=queue_phase))
        except Exception:
            for copied_file in copied_files:
                self._dependencies.file_storage.delete_relative_path(copied_file.storage_relative_path)
                self._dependencies.run_files.delete(copied_file.id)
            self._dependencies.runs.delete(run.id)
            self._lock_manager.release(store_id, module_code, run.id)
            raise
        self._logger.info(
            "%s user_id=%s store_id=%s run_id=%s module_code=%s public_run_number=%s",
            CHECK_STARTED_EVENT if operation_type == OperationType.CHECK else PROCESS_STARTED_EVENT,
            context.user.id,
            run.store_id,
            run.id,
            run.module_code,
            run.public_run_number,
        )
        return run

    def _copy_input_files(self, run: RunDTO, temp_files: tuple[TemporaryUploadedFileDTO, ...]) -> tuple[RunFileDTO, ...]:
        created: list[RunFileDTO] = []
        module_code = ModuleCode(run.module_code)
        for index, temp_file in enumerate(sorted(temp_files, key=lambda item: item.id)):
            copied_at = self._clock()
            source_path = self._dependencies.file_storage.root_path / temp_file.storage_relative_path
            stored = self._dependencies.file_storage.copy_to_run_input(
                source_path=source_path,
                module_code=module_code.value,
                store_id=run.store_id,
                public_run_number=run.public_run_number,
                original_filename=temp_file.original_filename,
                mime_type=temp_file.mime_type,
                created_at_utc=copied_at,
            )
            file_role = self._pick_file_role(module_code, temp_file, index)
            run_file = RunFileDTO(
                id=self._next_run_file_id(),
                run_id=run.id,
                file_role=file_role,
                original_filename=temp_file.original_filename,
                stored_filename=stored.stored_filename,
                storage_relative_path=stored.storage_relative_path,
                mime_type=temp_file.mime_type,
                file_size_bytes=stored.file_size_bytes,
                file_sha256=stored.file_sha256,
                uploaded_at_utc=copied_at,
                expires_at_utc=copied_at + timedelta(days=5),
                is_available=True,
                unavailable_reason=None,
                created_at_utc=copied_at,
            )
            created.append(self._dependencies.run_files.add(run_file))
        return tuple(created)

    def _pick_file_role(self, module_code: ModuleCode, temp_file: TemporaryUploadedFileDTO, index: int) -> str:
        if module_code == ModuleCode.OZON:
            return FileRole.OZON_INPUT.value
        return FileRole.WB_PRICE_INPUT.value if temp_file.wb_file_kind == WB_PRICE_FILE_KIND else FileRole.WB_PROMO_INPUT.value

    def _transition(self, run: RunDTO, lifecycle_status: str) -> RunDTO:
        updated = replace(run, lifecycle_status=lifecycle_status, updated_at_utc=self._clock())
        return self._dependencies.runs.update(updated)

    def _finalize_success(self, run: RunDTO, result: RunExecutionResult) -> RunDTO:
        summary = RunSummaryAuditDTO(
            id=self._next_summary_id(),
            run_id=run.id,
            audit_json=result.summary_json,
            created_at_utc=self._clock(),
        )
        self._dependencies.run_summary_audits.add(summary)
        result_file = result.result_file
        if result_file is not None and result_file.id <= 0:
            result_file = replace(result_file, id=self._next_run_file_id())
        updated = replace(
            run,
            lifecycle_status=RunLifecycleStatus.COMPLETED.value,
            business_result=result.business_result,
            short_result_text=result.short_result_text,
            result_file_id=result_file.id if result_file is not None else run.result_file_id,
            finished_at_utc=self._clock(),
            updated_at_utc=self._clock(),
        )
        self._dependencies.runs.update(updated)
        if result_file is not None:
            self._dependencies.run_files.add(result_file)
        self._apply_result_supersede(updated)
        self._lock_manager.release_by_run(updated)
        self._log_run_success(updated)
        return updated

    def _finalize_failure(self, run: RunDTO, business_result: str, message: str, details: object | None) -> RunDTO:
        summary = RunSummaryAuditDTO(
            id=self._next_summary_id(),
            run_id=run.id,
            audit_json={"error": message, "details": details},
            created_at_utc=self._clock(),
        )
        self._dependencies.run_summary_audits.add(summary)
        updated = replace(
            run,
            lifecycle_status=RunLifecycleStatus.FAILED.value,
            business_result=business_result,
            short_result_text=message,
            finished_at_utc=self._clock(),
            updated_at_utc=self._clock(),
        )
        self._dependencies.runs.update(updated)
        self._lock_manager.release_by_run(updated)
        self._log_run_failure(updated, details)
        return updated

    def _persist_audits(self, run: RunDTO, result: RunExecutionResult) -> None:
        if result.detail_rows:
            for detail in result.detail_rows:
                if detail.id <= 0:
                    detail = replace(detail, id=self._next_detail_id())
                self._dependencies.run_detail_audits.add(detail)

    def _load_active_temp_files(self, uploaded_by_user_id: int, store_id: int, module_code: ModuleCode) -> tuple[TemporaryUploadedFileDTO, ...]:
        items = [
            item
            for item in self._dependencies.temporary_files.list()
            if item.uploaded_by_user_id == uploaded_by_user_id
            and item.store_id == store_id
            and item.module_code == module_code.value
            and item.is_active_in_current_set
        ]
        return tuple(sorted(items, key=lambda item: item.id))

    def _load_run_files(self, run_id: int) -> tuple[RunFileDTO, ...]:
        return tuple(sorted((item for item in self._dependencies.run_files.list() if item.run_id == run_id), key=lambda item: item.id))

    def _get_run(self, run_id: int) -> RunDTO:
        run = self._dependencies.runs.get(run_id)
        if run is None:
            raise ValidationFailedError("Run not found", {"run_id": run_id})
        return run

    def _get_store(self, store_id: int) -> StoreDTO:
        store = self._dependencies.stores.get(store_id)
        if store is None:
            raise ValidationFailedError("Store not found", {"store_id": store_id})
        if store.status == StoreStatus.ARCHIVED.value:
            raise ValidationFailedError("Archived store cannot be used", {"store_id": store_id})
        return store

    def _get_store_for_execution(self, store_id: int) -> StoreDTO:
        store = self._dependencies.stores.get(store_id)
        if store is None:
            raise ValidationFailedError("Store not found", {"store_id": store_id})
        return store

    def _build_input_set_signature(self, files: tuple[TemporaryUploadedFileDTO, ...]) -> str:
        payload = "|".join(
            f"{item.file_sha256}:{item.file_size_bytes}:{item.original_filename}:{item.wb_file_kind or ''}"
            for item in files
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _validate_run_input_set(self, module_code: ModuleCode, temp_files: tuple[TemporaryUploadedFileDTO, ...]) -> None:
        if module_code == ModuleCode.OZON:
            if len(temp_files) != 1:
                raise AppError(
                    ErrorCode.FILE_LIMIT_EXCEEDED,
                    "Ozon run requires exactly one file",
                    {"module_code": module_code.value, "file_count": len(temp_files), "required_file_count": 1},
                )
            return

        price_files = [item for item in temp_files if item.wb_file_kind == WB_PRICE_FILE_KIND]
        promo_files = [item for item in temp_files if item.wb_file_kind == WB_PROMO_FILE_KIND]
        if len(price_files) != 1 or not (1 <= len(promo_files) <= MAX_WB_PROMO_FILES):
            raise AppError(
                ErrorCode.FILE_LIMIT_EXCEEDED,
                "WB run requires exactly one price file and between one and twenty promo files",
                {
                    "module_code": module_code.value,
                    "price_file_count": len(price_files),
                    "promo_file_count": len(promo_files),
                    "required_price_file_count": 1,
                    "max_promo_file_count": MAX_WB_PROMO_FILES,
                },
            )
        total_size = sum(item.file_size_bytes for item in temp_files)
        if total_size > MAX_WB_TOTAL_SIZE_BYTES:
            raise AppError(
                ErrorCode.FILE_LIMIT_EXCEEDED,
                "WB file set exceeds total size limit",
                {
                    "module_code": module_code.value,
                    "total_file_size_bytes": total_size,
                    "max_total_file_size_bytes": MAX_WB_TOTAL_SIZE_BYTES,
                },
            )

    def _to_file_view_model(self, item: RunFileDTO) -> RunFileViewModel:
        return RunFileViewModel(
            id=item.id,
            run_id=item.run_id,
            file_role=item.file_role,
            original_filename=item.original_filename,
            stored_filename=item.stored_filename,
            storage_relative_path=item.storage_relative_path,
            mime_type=item.mime_type,
            file_size_bytes=item.file_size_bytes,
            file_sha256=item.file_sha256,
            uploaded_at_utc=item.uploaded_at_utc,
            expires_at_utc=item.expires_at_utc,
            is_available=item.is_available,
            unavailable_reason=item.unavailable_reason,
        )

    def _to_polling_view(self, run: RunDTO) -> RunPollingViewModel:
        result_file = self._resolve_result_file_for_run(run)
        return RunPollingViewModel(
            id=run.id,
            public_run_number=run.public_run_number,
            store_id=run.store_id,
            operation_type=run.operation_type,
            lifecycle_status=run.lifecycle_status,
            execution_phase=self._execution_phase(run),
            business_result=run.business_result,
            module_code=run.module_code,
            short_result_text=run.short_result_text,
            result_file_id=run.result_file_id,
            result_file_is_available=None if result_file is None else result_file.is_available,
            result_file_unavailable_reason=None if result_file is None else result_file.unavailable_reason,
            is_locked=self._lock_manager.has_active_run(run.store_id, ModuleCode(run.module_code)),
            updated_at_utc=run.updated_at_utc,
        )

    def _resolve_result_file_for_run(self, run: RunDTO) -> RunFileDTO | None:
        if run.result_file_id is not None:
            linked = self._dependencies.run_files.get(run.result_file_id)
            if linked is not None and linked.run_id == run.id:
                return linked
        result_roles = {FileRole.WB_RESULT_OUTPUT.value, FileRole.OZON_RESULT_OUTPUT.value}
        candidates = [item for item in self._load_run_files(run.id) if item.file_role in result_roles]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.id)

    def _apply_result_supersede(self, run: RunDTO) -> None:
        if run.operation_type != OperationType.PROCESS.value:
            return
        current_result_file = self._resolve_result_file_for_run(run)
        if current_result_file is None:
            return

        successful_runs = self._successful_process_runs_for_line(run.store_id, run.module_code)
        if len(successful_runs) < 2:
            return

        winner = max(
            successful_runs,
            key=lambda item: (
                item.finished_at_utc or item.updated_at_utc,
                item.id,
            ),
        )
        winner_result_file = self._resolve_result_file_for_run(winner)
        if winner_result_file is None:
            return

        for candidate in successful_runs:
            if candidate.id == winner.id:
                continue
            candidate_result_file = self._resolve_result_file_for_run(candidate)
            if candidate_result_file is None or not candidate_result_file.is_available:
                continue
            superseded_file = self.mark_run_file_unavailable(candidate_result_file.id, UnavailableReason.SUPERSEDED.value)
            self._logger.info(
                "%s run_id=%s store_id=%s module_code=%s superseded_run_id=%s superseded_result_file_id=%s superseded_storage_path=%s replacement_run_id=%s replacement_result_file_id=%s replacement_storage_path=%s reason=%s",
                OLD_RESULT_REMOVED_ON_NEW_SUCCESS_EVENT,
                candidate.id,
                candidate.store_id,
                candidate.module_code,
                candidate.id,
                superseded_file.id,
                superseded_file.storage_relative_path,
                winner.id,
                winner_result_file.id,
                winner_result_file.storage_relative_path,
                UnavailableReason.SUPERSEDED.value,
            )

    def _log_run_success(self, run: RunDTO) -> None:
        result_file = self._resolve_result_file_for_run(run)
        event_type = CHECK_FINISHED_EVENT
        log_method = self._logger.info
        if run.operation_type == OperationType.PROCESS.value:
            event_type = PROCESS_FINISHED_EVENT
            if run.business_result == BusinessResult.COMPLETED_WITH_WARNINGS.value:
                event_type = PROCESS_FINISHED_WITH_WARNINGS_EVENT
                log_method = self._logger.warning
        elif run.business_result == BusinessResult.CHECK_PASSED_WITH_WARNINGS.value:
            log_method = self._logger.warning

        log_method(
            "%s run_id=%s store_id=%s module_code=%s public_run_number=%s business_result=%s result_file_id=%s short_result_text=%s",
            event_type,
            run.id,
            run.store_id,
            run.module_code,
            run.public_run_number,
            run.business_result or "",
            "" if result_file is None else result_file.id,
            self._compact_log_value(run.short_result_text),
        )

    def _log_run_failure(self, run: RunDTO, details: object | None) -> None:
        event_type = PROCESS_ERROR_EVENT if run.operation_type == OperationType.PROCESS.value else CHECK_FINISHED_EVENT
        log_method = self._logger.error if run.operation_type == OperationType.PROCESS.value else self._logger.warning
        log_method(
            "%s run_id=%s store_id=%s module_code=%s public_run_number=%s business_result=%s error_message=%s error_details=%s",
            event_type,
            run.id,
            run.store_id,
            run.module_code,
            run.public_run_number,
            run.business_result or "",
            self._compact_log_value(run.short_result_text),
            self._compact_log_value(details),
        )

    def _successful_process_runs_for_line(self, store_id: int, module_code: str) -> tuple[RunDTO, ...]:
        successful_results = {
            BusinessResult.COMPLETED.value,
            BusinessResult.COMPLETED_WITH_WARNINGS.value,
        }
        items = [
            item
            for item in self._dependencies.runs.list()
            if item.store_id == store_id
            and item.module_code == module_code
            and item.operation_type == OperationType.PROCESS.value
            and item.business_result in successful_results
            and item.result_file_id is not None
        ]
        return tuple(items)

    def _execution_phase(self, run: RunDTO) -> str:
        if run.operation_type == OperationType.PROCESS.value:
            if run.lifecycle_status == RunLifecycleStatus.CREATED.value:
                return "queued"
            if run.lifecycle_status == RunLifecycleStatus.VALIDATING.value:
                return "validating"
            if run.lifecycle_status == RunLifecycleStatus.PROCESSING.value:
                return "processing"
            return "finalized"
        if run.lifecycle_status == RunLifecycleStatus.CREATED.value:
            return "queued"
        if run.lifecycle_status == RunLifecycleStatus.CHECKING.value:
            return "checking"
        return "finalized"

    def mark_run_file_unavailable(self, run_file_id: int, unavailable_reason: str) -> RunFileDTO:
        run_file = self._dependencies.run_files.get(run_file_id)
        if run_file is None:
            raise ValidationFailedError("Run file not found", {"run_file_id": run_file_id})
        updated = replace(run_file, is_available=False, unavailable_reason=unavailable_reason)
        return self._dependencies.run_files.update(updated)

    def supersede_run_file(self, run_file_id: int) -> RunFileDTO:
        return self.mark_run_file_unavailable(run_file_id, UnavailableReason.SUPERSEDED.value)

    def _find_summary_audit(self, run_id: int) -> RunSummaryAuditDTO | None:
        for item in self._dependencies.run_summary_audits.list():
            if item.run_id == run_id:
                return item
        return None

    def _next_run_id(self) -> int:
        return max((item.id for item in self._dependencies.runs.list()), default=0) + 1

    def _next_public_run_number(self) -> str:
        return f"RUN-{self._next_run_id():06d}"

    def _next_run_file_id(self) -> int:
        return max((item.id for item in self._dependencies.run_files.list()), default=0) + 1

    def _next_summary_id(self) -> int:
        return max((item.id for item in self._dependencies.run_summary_audits.list()), default=0) + 1

    def _next_detail_id(self) -> int:
        return max((item.id for item in self._dependencies.run_detail_audits.list()), default=0) + 1

    def _hard_timeout_seconds(self, run: RunDTO) -> int:
        if run.operation_type == OperationType.PROCESS.value:
            return RUN_TIMEOUT_SECONDS_PROCESS
        return RUN_TIMEOUT_SECONDS_CHECK

    def _compact_log_value(self, value: object | None) -> str:
        if value in (None, ""):
            return ""
        return str(value).strip().replace(" ", "_")
