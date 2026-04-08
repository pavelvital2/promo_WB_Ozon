from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class StoreDTO:
    id: int
    name: str
    marketplace: str
    status: str
    wb_threshold_percent: int | None
    wb_fallback_no_promo_percent: int | None
    wb_fallback_over_threshold_percent: int | None
    created_by_user_id: int
    created_at_utc: datetime
    updated_at_utc: datetime
    archived_at_utc: datetime | None = None
    archived_by_user_id: int | None = None


@dataclass(slots=True, frozen=True)
class UserStoreAccessDTO:
    id: int
    user_id: int
    store_id: int
    created_at_utc: datetime

