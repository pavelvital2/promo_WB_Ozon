from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from promo.shared.contracts.users import PermissionDTO, RoleDTO, UserDTO
from promo.shared.enums import MarketplaceCode, ModuleCode, PermissionCode, StoreStatus


@dataclass(slots=True, frozen=True)
class AccessibleStoreDTO:
    id: int
    name: str
    marketplace: MarketplaceCode
    status: StoreStatus


@dataclass(slots=True, frozen=True)
class SessionContextDTO:
    user: UserDTO
    role: RoleDTO
    permissions: tuple[PermissionDTO, ...]
    accessible_stores: tuple[AccessibleStoreDTO, ...]
    is_admin: bool
    can_create_store: bool
    can_edit_store: bool
    is_blocked: bool

    @property
    def accessible_store_count(self) -> int:
        return len(self.accessible_stores)

    @property
    def has_accessible_stores(self) -> bool:
        return bool(self.accessible_stores)


@dataclass(slots=True, frozen=True)
class PolicyDecisionDTO:
    allowed: bool
    reason_code: str | None = None
    details: dict[str, object] | None = None


@dataclass(slots=True, frozen=True)
class MenuVisibilityDTO:
    show_dashboard: bool = True
    show_users: bool = False
    show_stores: bool = False
    show_logs: bool = False
    show_history: bool = False
    show_wb: bool = False
    show_ozon: bool = False
    show_no_store_state: bool = False
    show_create_store_cta: bool = False
    accessible_store_count: int = 0


@dataclass(slots=True, frozen=True)
class NoStoreStateDTO:
    message: str
    show_create_store_cta: bool
    can_create_store: bool


@runtime_checkable
class RunLookupGateway(Protocol):
    def has_active_run(self, store_id: int, module_code: ModuleCode) -> bool: ...


@dataclass(slots=True, frozen=True)
class VisibilityContextDTO:
    menu_visibility: MenuVisibilityDTO
    no_store_state: NoStoreStateDTO | None
    evaluated_at_utc: datetime

