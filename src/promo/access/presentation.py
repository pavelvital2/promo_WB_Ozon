from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class AccessibleStoreViewModel:
    id: int
    name: str
    marketplace: str
    status: str


@dataclass(slots=True, frozen=True)
class SessionContextViewModel:
    user_id: int
    username: str
    role_code: str
    role_name: str
    permission_codes: tuple[str, ...]
    accessible_stores: tuple[AccessibleStoreViewModel, ...]
    accessible_store_count: int
    is_admin: bool
    can_create_store: bool
    can_edit_store: bool
    is_blocked: bool


@dataclass(slots=True, frozen=True)
class MenuVisibilityViewModel:
    show_dashboard: bool
    show_users: bool
    show_stores: bool
    show_logs: bool
    show_history: bool
    show_wb: bool
    show_ozon: bool
    show_no_store_state: bool
    show_create_store_cta: bool
    accessible_store_count: int


@dataclass(slots=True, frozen=True)
class NoStoreStateViewModel:
    message: str
    show_create_store_cta: bool
    can_create_store: bool


@dataclass(slots=True, frozen=True)
class UserStoreAccessViewModel:
    id: int
    user_id: int
    store_id: int
    created_at_utc: datetime

