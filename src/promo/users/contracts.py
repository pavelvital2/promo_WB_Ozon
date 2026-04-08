from __future__ import annotations

from dataclasses import dataclass

from promo.access.contracts import AccessibleStoreDTO
from promo.shared.contracts.stores import StoreDTO, UserStoreAccessDTO
from promo.shared.contracts.users import PermissionDTO, RoleDTO, UserDTO, UserPermissionDTO
from promo.shared.persistence.contracts import Repository


@dataclass(slots=True, frozen=True)
class UserDirectoryDependencies:
    users: Repository[UserDTO, int]
    roles: Repository[RoleDTO, int]
    permissions: Repository[PermissionDTO, int]
    user_permissions: Repository[UserPermissionDTO, int]
    stores: Repository[StoreDTO, int]
    user_store_access: Repository[UserStoreAccessDTO, int]


@dataclass(slots=True, frozen=True)
class UserIdentitySnapshotDTO:
    user: UserDTO
    role: RoleDTO
    permissions: tuple[PermissionDTO, ...]
    accessible_stores: tuple[AccessibleStoreDTO, ...]

