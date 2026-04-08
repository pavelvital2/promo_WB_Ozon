from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class HistoryItemViewModel:
    run_id: int
    public_run_number: str
    store_id: int
    store_name: str
    store_marketplace: str
    store_status: str
    initiated_by_user_id: int
    initiated_by_username: str
    operation_type: str
    lifecycle_status: str
    business_result: str | None
    module_code: str
    started_at_utc: datetime
    finished_at_utc: datetime | None
    short_result_text: str | None
    original_filenames: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class HistoryPageViewModel:
    items: tuple[HistoryItemViewModel, ...]
    total_items: int
    page: int
    page_size: int

