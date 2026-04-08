from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class UserCreateForm:
    username: str
    password: str
    role_code: str
    permission_codes: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class UserEditForm:
    username: str | None = None
    role_code: str | None = None


@dataclass(slots=True, frozen=True)
class UserPermissionViewModel:
    id: int
    code: str
    name: str
    description: str | None


@dataclass(slots=True, frozen=True)
class UserStoreAccessAssignmentViewModel:
    id: int
    store_id: int
    created_at_utc: datetime


@dataclass(slots=True, frozen=True)
class UserSummaryViewModel:
    id: int
    username: str
    role_code: str
    role_name: str
    is_blocked: bool
    accessible_store_count: int


@dataclass(slots=True, frozen=True)
class UserListViewModel:
    items: tuple[UserSummaryViewModel, ...]
    total_items: int


@dataclass(slots=True, frozen=True)
class UserDetailViewModel:
    id: int
    username: str
    role_id: int
    role_code: str
    role_name: str
    is_blocked: bool
    permission_codes: tuple[str, ...]
    permissions: tuple[UserPermissionViewModel, ...]
    store_access: tuple[UserStoreAccessAssignmentViewModel, ...]
    accessible_store_count: int
    created_at_utc: datetime
    updated_at_utc: datetime
    last_login_at_utc: datetime | None
