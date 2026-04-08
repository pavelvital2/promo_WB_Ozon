from __future__ import annotations

from datetime import UTC, datetime
from typing import Generic, TypeVar

import pytest

from promo.access.policy import AccessPolicy
from promo.auth.service import AuthService, InMemorySessionStore
from promo.shared.contracts.stores import StoreDTO, UserStoreAccessDTO
from promo.shared.contracts.users import PermissionDTO, RoleDTO, UserDTO, UserPermissionDTO
from promo.shared.enums import RoleCode
from promo.shared.errors import PermissionDeniedError
from promo.shared.security.passwords import ScryptPasswordHasher
from promo.users.contracts import UserDirectoryDependencies
from promo.users.presentation import UserCreateForm, UserEditForm
from promo.users.service import UserDirectoryService, UserManagementService


T = TypeVar("T")


class MemoryRepository(Generic[T]):
    def __init__(self, items: list[T] | None = None) -> None:
        self._items: dict[int, T] = {}
        for item in items or []:
            self.add(item)

    def get(self, key: int) -> T | None:
        return self._items.get(key)

    def list(self) -> tuple[T, ...]:
        return tuple(self._items.values())

    def add(self, entity: T) -> T:
        self._items[getattr(entity, "id")] = entity
        return entity

    def add_many(self, entities: list[T]) -> tuple[T, ...]:
        return tuple(self.add(entity) for entity in entities)

    def update(self, entity: T) -> T:
        self._items[getattr(entity, "id")] = entity
        return entity

    def delete(self, key: int) -> None:
        self._items.pop(key, None)


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _seed_environment():
    hasher = ScryptPasswordHasher()
    roles = MemoryRepository(
        [
            RoleDTO(id=1, code=RoleCode.ADMIN.value, name="Администратор"),
            RoleDTO(id=2, code=RoleCode.MANAGER_LEAD.value, name="Управляющий"),
            RoleDTO(id=3, code=RoleCode.MANAGER.value, name="Менеджер"),
        ]
    )
    permissions = MemoryRepository(
        [
            PermissionDTO(id=1, code="create_store", name="create_store"),
            PermissionDTO(id=2, code="edit_store", name="edit_store"),
        ]
    )
    users = MemoryRepository(
        [
            UserDTO(
                id=1,
                username="admin",
                password_hash=hasher.hash_password("admin-pass"),
                role_id=1,
                is_blocked=False,
                created_at_utc=_dt("2026-04-07T10:00:00+00:00"),
                updated_at_utc=_dt("2026-04-07T10:00:00+00:00"),
                last_login_at_utc=None,
            ),
            UserDTO(
                id=2,
                username="manager",
                password_hash=hasher.hash_password("manager-pass"),
                role_id=3,
                is_blocked=False,
                created_at_utc=_dt("2026-04-07T10:00:00+00:00"),
                updated_at_utc=_dt("2026-04-07T10:00:00+00:00"),
                last_login_at_utc=None,
            ),
        ]
    )
    stores = MemoryRepository([])
    user_permissions = MemoryRepository([])
    user_store_access = MemoryRepository([])
    deps = UserDirectoryDependencies(
        users=users,
        roles=roles,
        permissions=permissions,
        user_permissions=user_permissions,
        stores=stores,
        user_store_access=user_store_access,
    )
    directory = UserDirectoryService(deps, clock=lambda: _dt("2026-04-07T12:00:00+00:00"))
    auth = AuthService(
        user_directory=directory,
        session_store=InMemorySessionStore(),
        password_hasher=hasher,
        policy=AccessPolicy(),
        clock=lambda: _dt("2026-04-07T12:00:00+00:00"),
    )
    service = UserManagementService(
        deps,
        password_hasher=hasher,
        policy=AccessPolicy(),
        clock=lambda: _dt("2026-04-07T12:00:00+00:00"),
    )
    admin_context = auth.login("admin", "admin-pass").context
    manager_context = auth.login("manager", "manager-pass").context
    return service, admin_context, manager_context, users, user_permissions, user_store_access


def test_admin_can_create_edit_block_and_manage_permissions() -> None:
    service, admin_context, _, users, user_permissions, user_store_access = _seed_environment()
    user_store_access.add(UserStoreAccessDTO(id=1, user_id=2, store_id=77, created_at_utc=_dt("2026-04-07T12:00:00+00:00")))

    created = service.create_user(
        admin_context,
        UserCreateForm(username="new-user", password="new-pass", role_code=RoleCode.MANAGER.value, permission_codes=("create_store",)),
    )
    assert created.username == "new-user"
    assert created.permission_codes == ("create_store",)

    edited = service.edit_user(admin_context, created.id, UserEditForm(username="renamed-user", role_code=RoleCode.MANAGER_LEAD.value))
    assert edited.username == "renamed-user"
    assert edited.role_code == RoleCode.MANAGER_LEAD.value

    granted = service.assign_permission(admin_context, created.id, "edit_store")
    assert set(granted.permission_codes) == {"create_store", "edit_store"}

    revoked = service.remove_permission(admin_context, created.id, "create_store")
    assert revoked.permission_codes == ("edit_store",)

    blocked = service.block_user(admin_context, created.id)
    assert blocked.is_blocked is True
    unblocked = service.unblock_user(admin_context, created.id)
    assert unblocked.is_blocked is False

    listed = service.list_users(admin_context)
    assert listed.total_items == 3
    assert users.get(created.id) is not None
    assert len(user_permissions.list()) == 1


def test_non_admin_is_denied_for_user_management_actions() -> None:
    service, _, manager_context, _, _, _ = _seed_environment()

    with pytest.raises(PermissionDeniedError):
        service.list_users(manager_context)
    with pytest.raises(PermissionDeniedError):
        service.create_user(
            manager_context,
            UserCreateForm(username="denied-user", password="denied-pass", role_code=RoleCode.MANAGER.value),
        )
