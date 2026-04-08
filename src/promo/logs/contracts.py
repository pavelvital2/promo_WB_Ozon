from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from promo.audit.contracts import PageResult
from promo.logs.presentation import LogItemViewModel
from promo.shared.contracts.logs import SystemLogDTO
from promo.shared.contracts.runs import RunDTO
from promo.shared.contracts.stores import StoreDTO
from promo.shared.contracts.users import UserDTO
from promo.shared.persistence.contracts import Repository


@dataclass(slots=True, frozen=True)
class LogsQuery:
    page: int = 1
    page_size: int = 50
    search: str | None = None
    user_id: int | None = None
    store_id: int | None = None
    module_code: str | None = None
    event_type: str | None = None
    severity: str | None = None
    run_id: int | None = None
    public_run_number: str | None = None
    event_from_utc: datetime | None = None
    event_to_utc: datetime | None = None
    sort_field: str = "event_time_utc"
    descending: bool = True


@dataclass(slots=True, frozen=True)
class LogsReadDependencies:
    logs: Repository[SystemLogDTO, int]
    runs: Repository[RunDTO, int]
    stores: Repository[StoreDTO, int]
    users: Repository[UserDTO, int]
    query_gateway: "LogsQueryGateway | None" = None


@runtime_checkable
class LogsQueryGateway(Protocol):
    def list_logs(self, query: LogsQuery) -> PageResult[LogItemViewModel]: ...
