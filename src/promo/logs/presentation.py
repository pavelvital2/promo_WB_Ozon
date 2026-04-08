from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class LogItemViewModel:
    id: int
    event_time_utc: datetime
    user_id: int | None
    username: str | None
    store_id: int | None
    store_name: str | None
    run_id: int | None
    public_run_number: str | None
    module_code: str | None
    event_type: str
    severity: str
    message: str
    payload_json: dict[str, object] | None


@dataclass(slots=True, frozen=True)
class LogsPageViewModel:
    items: tuple[LogItemViewModel, ...]
    total_items: int
    page: int
    page_size: int

