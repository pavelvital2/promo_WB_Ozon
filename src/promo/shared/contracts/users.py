from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class RoleDTO:
    id: int
    code: str
    name: str


@dataclass(slots=True, frozen=True)
class PermissionDTO:
    id: int
    code: str
    name: str
    description: str | None = None


@dataclass(slots=True, frozen=True)
class UserDTO:
    id: int
    username: str
    password_hash: str
    role_id: int
    is_blocked: bool
    created_at_utc: datetime
    updated_at_utc: datetime
    last_login_at_utc: datetime | None = None


@dataclass(slots=True, frozen=True)
class UserPermissionDTO:
    id: int
    user_id: int
    permission_id: int
    created_at_utc: datetime
