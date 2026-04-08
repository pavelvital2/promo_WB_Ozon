from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from promo.file_storage.service import FileStorageService
from promo.shared.contracts.audit import RunDetailAuditDTO, RunSummaryAuditDTO
from promo.shared.contracts.files import TemporaryUploadedFileDTO
from promo.shared.contracts.runs import RunDTO, RunFileDTO
from promo.shared.contracts.stores import StoreDTO
from promo.shared.enums import ModuleCode
from promo.shared.persistence.contracts import Repository


@dataclass(slots=True, frozen=True)
class RunServiceDependencies:
    runs: Repository[RunDTO, int]
    run_files: Repository[RunFileDTO, int]
    run_summary_audits: Repository[RunSummaryAuditDTO, int]
    run_detail_audits: Repository[RunDetailAuditDTO, int]
    stores: Repository[StoreDTO, int]
    temporary_files: Repository[TemporaryUploadedFileDTO, int]
    file_storage: FileStorageService


@dataclass(slots=True, frozen=True)
class RunExecutionJob:
    run_id: int
    phase: str = "execute"
    attempt: int = 0


@dataclass(slots=True, frozen=True)
class RunExecutionResult:
    business_result: str
    short_result_text: str
    summary_json: dict[str, object]
    detail_rows: tuple[RunDetailAuditDTO, ...] = ()
    result_file: RunFileDTO | None = None


@runtime_checkable
class RunExecutionStrategy(Protocol):
    def validate(self, run: RunDTO, store: StoreDTO, files: tuple[RunFileDTO, ...]) -> RunExecutionResult: ...

    def execute(self, run: RunDTO, store: StoreDTO, files: tuple[RunFileDTO, ...]) -> RunExecutionResult: ...


@runtime_checkable
class RunLookupGateway(Protocol):
    def has_active_run(self, store_id: int, module_code: ModuleCode) -> bool: ...
