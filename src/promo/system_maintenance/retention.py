from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from datetime import UTC, datetime
from typing import Callable

from promo.file_storage.service import FileStorageService
from promo.shared.clock import utc_now
from promo.shared.contracts.files import TemporaryUploadedFileDTO
from promo.shared.contracts.runs import RunFileDTO
from promo.shared.enums import UnavailableReason
from promo.shared.files.policies import RunFileRetentionPolicy, TemporaryFileRetentionPolicy
from promo.shared.logging import get_logger
from promo.shared.persistence.contracts import Repository
@dataclass(slots=True, frozen=True)
class MaintenanceOutcome:
    task_name: str
    affected_rows: int
    run_at_utc: datetime
    event_types: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class RunFileRetentionDependencies:
    run_files: Repository[RunFileDTO, int]
    file_storage: FileStorageService
    logger: object | None = None


@dataclass(slots=True, frozen=True)
class TemporaryFileRetentionDependencies:
    temporary_files: Repository[TemporaryUploadedFileDTO, int]
    file_storage: FileStorageService
    logger: object | None = None


RUN_FILES_RETENTION_APPLIED_EVENT = "run_files_retention_applied"
TEMPORARY_FILES_AUTO_PURGED_EVENT = "temporary_files_auto_purged"


def expire_run_files(
    dependencies: RunFileRetentionDependencies | None = None,
    policy: RunFileRetentionPolicy | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> MaintenanceOutcome:
    policy = policy or RunFileRetentionPolicy()
    now = _coerce_utc(clock())
    if dependencies is None:
        return MaintenanceOutcome(task_name="expire_run_files", affected_rows=0, run_at_utc=now)

    logger = dependencies.logger or get_logger(__name__)
    affected = 0
    events: list[str] = []
    for item in list(dependencies.run_files.list()):
        if not item.is_available:
            continue
        if item.expires_at_utc is None:
            continue
        if _coerce_utc(item.expires_at_utc) > now:
            continue
        dependencies.file_storage.delete_relative_path(item.storage_relative_path)
        dependencies.run_files.update(
            replace(
                item,
                is_available=False,
                unavailable_reason=UnavailableReason.EXPIRED.value,
            )
        )
        logger.info(
            "%s run_id=%s file_metadata_id=%s storage_path=%s reason=%s cleanup_scope=%s",
            RUN_FILES_RETENTION_APPLIED_EVENT,
            item.run_id,
            item.id,
            item.storage_relative_path,
            UnavailableReason.EXPIRED.value,
            "run_files_retention",
        )
        affected += 1
        events.append(RUN_FILES_RETENTION_APPLIED_EVENT)
    return MaintenanceOutcome(task_name="expire_run_files", affected_rows=affected, run_at_utc=now, event_types=tuple(events))


def purge_temporary_files(
    dependencies: TemporaryFileRetentionDependencies | None = None,
    policy: TemporaryFileRetentionPolicy | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> MaintenanceOutcome:
    policy = policy or TemporaryFileRetentionPolicy()
    now = _coerce_utc(clock())
    if dependencies is None:
        return MaintenanceOutcome(task_name="purge_temporary_files", affected_rows=0, run_at_utc=now)

    logger = dependencies.logger or get_logger(__name__)
    affected = 0
    events: list[str] = []
    for item in list(dependencies.temporary_files.list()):
        if _coerce_utc(item.expires_at_utc) > now:
            continue
        dependencies.file_storage.delete_relative_path(item.storage_relative_path)
        logger.info(
            "%s user_id=%s store_id=%s module_code=%s file_metadata_id=%s storage_path=%s reason=%s cleanup_scope=%s",
            TEMPORARY_FILES_AUTO_PURGED_EVENT,
            item.uploaded_by_user_id,
            item.store_id,
            item.module_code,
            item.id,
            item.storage_relative_path,
            "expired",
            "temporary_files_retention",
        )
        dependencies.temporary_files.delete(item.id)
        affected += 1
        events.append(TEMPORARY_FILES_AUTO_PURGED_EVENT)
    return MaintenanceOutcome(task_name="purge_temporary_files", affected_rows=affected, run_at_utc=now, event_types=tuple(events))


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
