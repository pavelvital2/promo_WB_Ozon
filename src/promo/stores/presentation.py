from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from promo.shared.enums import MarketplaceCode


@dataclass(slots=True, frozen=True)
class StoreCreateForm:
    name: str
    marketplace: MarketplaceCode
    wb_threshold_percent: int | None = None
    wb_fallback_no_promo_percent: int | None = None
    wb_fallback_over_threshold_percent: int | None = None


@dataclass(slots=True, frozen=True)
class StoreEditForm:
    name: str


@dataclass(slots=True, frozen=True)
class StoreSettingsForm:
    wb_threshold_percent: int
    wb_fallback_no_promo_percent: int
    wb_fallback_over_threshold_percent: int


@dataclass(slots=True, frozen=True)
class StoreViewModel:
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
    archived_at_utc: datetime | None
    archived_by_user_id: int | None
    can_edit: bool
    can_archive: bool
    can_restore: bool


@dataclass(slots=True, frozen=True)
class StoreListViewModel:
    items: tuple[StoreViewModel, ...]
    total_items: int

