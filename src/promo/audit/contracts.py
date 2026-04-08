from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar, runtime_checkable

from promo.shared.contracts.audit import RunDetailAuditDTO, RunSummaryAuditDTO
from promo.shared.contracts.runs import RunDTO, RunFileDTO
from promo.shared.contracts.stores import StoreDTO
from promo.shared.contracts.users import UserDTO
from promo.shared.persistence.contracts import Repository

T = TypeVar("T")

ALLOWED_PAGE_SIZES = (25, 50, 100)


@dataclass(slots=True, frozen=True)
class PageRequest:
    page: int = 1
    page_size: int = 50
    search: str | None = None
    sort_field: str = ""
    descending: bool = True


@dataclass(slots=True, frozen=True)
class PageResult(Generic[T]):
    items: tuple[T, ...]
    total_items: int
    page: int
    page_size: int


@dataclass(slots=True, frozen=True)
class DetailAuditQuery:
    page: int = 1
    page_size: int = 50
    search: str | None = None
    severity: str | None = None
    decision_reason: str | None = None
    row_number_from: int | None = None
    row_number_to: int | None = None
    has_entity_key_1: bool | None = None
    sort_field: str = "row_number"
    descending: bool = False


@dataclass(slots=True, frozen=True)
class AuditReadDependencies:
    runs: Repository[RunDTO, int]
    run_files: Repository[RunFileDTO, int]
    run_summary_audits: Repository[RunSummaryAuditDTO, int]
    run_detail_audits: Repository[RunDetailAuditDTO, int]
    stores: Repository[StoreDTO, int]
    users: Repository[UserDTO, int]
    query_gateway: "AuditQueryGateway | None" = None


@runtime_checkable
class AuditQueryGateway(Protocol):
    def list_detail_audit(self, run_id: int, query: DetailAuditQuery) -> PageResult[RunDetailAuditDTO]: ...

    def get_summary_audit(self, run_id: int) -> RunSummaryAuditDTO | None: ...

    def list_run_files(self, run_id: int) -> tuple[RunFileDTO, ...]: ...
