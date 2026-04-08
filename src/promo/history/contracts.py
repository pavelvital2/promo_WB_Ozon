from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from promo.audit.contracts import PageResult
from promo.history.presentation import HistoryItemViewModel
from promo.shared.contracts.runs import RunDTO, RunFileDTO
from promo.shared.contracts.stores import StoreDTO
from promo.shared.contracts.users import UserDTO
from promo.shared.persistence.contracts import Repository


@dataclass(slots=True, frozen=True)
class HistoryQuery:
    page: int = 1
    page_size: int = 50
    search: str | None = None
    store_id: int | None = None
    initiated_by_user_id: int | None = None
    marketplace: str | None = None
    module_code: str | None = None
    operation_type: str | None = None
    lifecycle_status: str | None = None
    business_result: str | None = None
    store_status: str | None = None
    started_from_utc: datetime | None = None
    started_to_utc: datetime | None = None
    sort_field: str = "started_at_utc"
    descending: bool = True


@dataclass(slots=True, frozen=True)
class HistoryReadDependencies:
    runs: Repository[RunDTO, int]
    run_files: Repository[RunFileDTO, int]
    stores: Repository[StoreDTO, int]
    users: Repository[UserDTO, int]
    query_gateway: "HistoryQueryGateway | None" = None


@runtime_checkable
class HistoryQueryGateway(Protocol):
    def list_history(
        self,
        query: HistoryQuery,
        accessible_store_ids: tuple[int, ...] | None,
    ) -> PageResult[HistoryItemViewModel]: ...

    def get_history_item_by_public_run_number(
        self,
        public_run_number: str,
        accessible_store_ids: tuple[int, ...] | None,
    ) -> HistoryItemViewModel | None: ...
