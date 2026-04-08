from __future__ import annotations

from datetime import UTC, datetime
from typing import Generic, TypeVar

import pytest

from promo.access.contracts import SessionContextDTO
from promo.access.handlers import list_user_store_access_handler, menu_visibility_handler, no_store_state_handler
from promo.access.policy import AccessPolicy
from promo.access.service import AccessService, AccessServiceDependencies
from promo.auth.contracts import SessionRecordDTO
from promo.auth.service import AuthService, InMemorySessionStore
from promo.shared.contracts.stores import StoreDTO, UserStoreAccessDTO
from promo.shared.contracts.users import PermissionDTO, RoleDTO, UserDTO, UserPermissionDTO
from promo.shared.enums import MarketplaceCode, RoleCode
from promo.shared.errors import AccessDeniedError, PermissionDeniedError
from promo.shared.security.passwords import ScryptPasswordHasher
from promo.stores.contracts import StoreServiceDependencies
from promo.stores.handlers import archive_store_handler, create_store_handler, restore_store_handler
from promo.stores.presentation import StoreCreateForm, StoreEditForm, StoreSettingsForm
from promo.stores.service import StoresService
from promo.users.contracts import UserDirectoryDependencies
from promo.users.service import UserDirectoryService


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
                created_at_utc=_dt("2026-04-06T10:00:00+00:00"),
                updated_at_utc=_dt("2026-04-06T10:00:00+00:00"),
                last_login_at_utc=None,
            ),
            UserDTO(
                id=2,
                username="lead",
                password_hash=hasher.hash_password("lead-pass"),
                role_id=2,
                is_blocked=False,
                created_at_utc=_dt("2026-04-06T10:00:00+00:00"),
                updated_at_utc=_dt("2026-04-06T10:00:00+00:00"),
                last_login_at_utc=None,
            ),
            UserDTO(
                id=3,
                username="manager",
                password_hash=hasher.hash_password("manager-pass"),
                role_id=3,
                is_blocked=False,
                created_at_utc=_dt("2026-04-06T10:00:00+00:00"),
                updated_at_utc=_dt("2026-04-06T10:00:00+00:00"),
                last_login_at_utc=None,
            ),
            UserDTO(
                id=4,
                username="blocked",
                password_hash=hasher.hash_password("blocked-pass"),
                role_id=3,
                is_blocked=True,
                created_at_utc=_dt("2026-04-06T10:00:00+00:00"),
                updated_at_utc=_dt("2026-04-06T10:00:00+00:00"),
                last_login_at_utc=None,
            ),
        ]
    )
    user_permissions = MemoryRepository(
        [
            UserPermissionDTO(id=1, user_id=2, permission_id=1, created_at_utc=_dt("2026-04-06T10:00:00+00:00")),
            UserPermissionDTO(id=2, user_id=2, permission_id=2, created_at_utc=_dt("2026-04-06T10:00:00+00:00")),
        ]
    )
    stores = MemoryRepository([])
    user_store_access = MemoryRepository([])

    user_directory = UserDirectoryService(
        UserDirectoryDependencies(
            users=users,
            roles=roles,
            permissions=permissions,
            user_permissions=user_permissions,
            stores=stores,
            user_store_access=user_store_access,
        ),
        clock=lambda: _dt("2026-04-06T12:00:00+00:00"),
    )
    session_store = InMemorySessionStore()
    policy = AccessPolicy()
    auth_service = AuthService(
        user_directory=user_directory,
        session_store=session_store,
        password_hasher=hasher,
        policy=policy,
        clock=lambda: _dt("2026-04-06T12:00:00+00:00"),
    )
    access_service = AccessService(
        AccessServiceDependencies(
            users=users,
            stores=stores,
            user_store_access=user_store_access,
            user_directory=user_directory,
        ),
        policy=policy,
        clock=lambda: _dt("2026-04-06T12:00:00+00:00"),
    )
    stores_service = StoresService(
        StoreServiceDependencies(stores=stores, user_store_access=user_store_access),
        policy=policy,
        clock=lambda: _dt("2026-04-06T12:00:00+00:00"),
    )
    return auth_service, access_service, stores_service, users, stores, user_store_access


def test_blocked_user_login_is_denied() -> None:
    auth_service, _, _, _, _, _ = _seed_environment()
    with pytest.raises(AccessDeniedError):
        auth_service.login("blocked", "blocked-pass")


def test_no_store_visibility_then_admin_grants_access() -> None:
    auth_service, access_service, stores_service, users, stores, user_store_access = _seed_environment()

    manager_login = auth_service.login("manager", "manager-pass")
    initial_context = auth_service.current_session_context(manager_login.session_token)
    visibility = menu_visibility_handler(access_service, initial_context)
    no_store_state = no_store_state_handler(access_service, initial_context)

    assert initial_context.has_accessible_stores is False
    assert visibility.show_no_store_state is True
    assert visibility.show_create_store_cta is False
    assert no_store_state is not None
    assert no_store_state.message == "Нет доступных магазинов"

    admin_login = auth_service.login("admin", "admin-pass")
    admin_context = auth_service.current_session_context(admin_login.session_token)
    created_store = create_store_handler(
        stores_service,
        admin_context,
        StoreCreateForm(
            name="VitalEmb",
            marketplace=MarketplaceCode.WB,
            wb_threshold_percent=60,
            wb_fallback_no_promo_percent=40,
            wb_fallback_over_threshold_percent=25,
        ),
    )
    access_service.grant_user_store_access(admin_context, user_id=3, store_id=created_store.id)

    refreshed_context = auth_service.current_session_context(manager_login.session_token)
    refreshed_visibility = menu_visibility_handler(access_service, refreshed_context)
    direct_context = access_service.load_session_context_by_user_id(3)

    assert refreshed_context.has_accessible_stores is True
    assert refreshed_context.accessible_store_count == 1
    assert direct_context.has_accessible_stores is True
    assert refreshed_visibility.show_no_store_state is False
    assert refreshed_visibility.show_history is True
    assert len(user_store_access.list()) == 1
    assert stores.get(created_store.id) is not None


def test_manager_cannot_archive_store_but_admin_can_restore() -> None:
    auth_service, access_service, stores_service, _, _, _ = _seed_environment()

    admin_login = auth_service.login("admin", "admin-pass")
    admin_context = auth_service.current_session_context(admin_login.session_token)
    created_store = create_store_handler(
        stores_service,
        admin_context,
        StoreCreateForm(
            name="AnotherStore",
            marketplace=MarketplaceCode.WB,
            wb_threshold_percent=50,
            wb_fallback_no_promo_percent=35,
            wb_fallback_over_threshold_percent=20,
        ),
    )

    lead_login = auth_service.login("lead", "lead-pass")
    lead_context = auth_service.current_session_context(lead_login.session_token)
    with pytest.raises(PermissionDeniedError):
        archive_store_handler(stores_service, lead_context, created_store.id)

    archived = stores_service.archive_store(admin_context, created_store.id)
    restored = restore_store_handler(stores_service, admin_context, archived.id)

    assert archived.status == "archived"
    assert restored.status == "active"


def test_user_store_access_listing_is_admin_only() -> None:
    auth_service, access_service, stores_service, _, _, _ = _seed_environment()

    admin_login = auth_service.login("admin", "admin-pass")
    admin_context = auth_service.current_session_context(admin_login.session_token)
    created_store = create_store_handler(
        stores_service,
        admin_context,
        StoreCreateForm(
            name="ScopedStore",
            marketplace=MarketplaceCode.WB,
            wb_threshold_percent=55,
            wb_fallback_no_promo_percent=40,
            wb_fallback_over_threshold_percent=30,
        ),
    )
    access_service.grant_user_store_access(admin_context, user_id=3, store_id=created_store.id)

    manager_login = auth_service.login("manager", "manager-pass")
    manager_context = auth_service.current_session_context(manager_login.session_token)
    with pytest.raises(PermissionDeniedError):
        list_user_store_access_handler(access_service, manager_context, user_id=3)

    admin_access = list_user_store_access_handler(access_service, admin_context, user_id=3)
    assert len(admin_access) == 1


def test_logging_side_effects_for_auth_store_and_access(caplog: pytest.LogCaptureFixture) -> None:
    auth_service, access_service, stores_service, _, _, _ = _seed_environment()

    with caplog.at_level("INFO"):
        admin_login = auth_service.login("admin", "admin-pass")
        admin_context = auth_service.current_session_context(admin_login.session_token)
        created_store = create_store_handler(
            stores_service,
            admin_context,
            StoreCreateForm(
                name="LoggedStore",
                marketplace=MarketplaceCode.WB,
                wb_threshold_percent=60,
                wb_fallback_no_promo_percent=35,
                wb_fallback_over_threshold_percent=20,
            ),
        )
        stores_service.edit_store(admin_context, created_store.id, StoreEditForm(name="LoggedStore2"))
        stores_service.update_store_settings(
            admin_context,
            created_store.id,
            StoreSettingsForm(
                wb_threshold_percent=61,
                wb_fallback_no_promo_percent=36,
                wb_fallback_over_threshold_percent=21,
            ),
        )
        archived = stores_service.archive_store(admin_context, created_store.id)
        stores_service.restore_store(admin_context, archived.id)
        access_service.grant_user_store_access(admin_context, user_id=3, store_id=created_store.id)
        access_service.revoke_user_store_access(admin_context, user_id=3, store_id=created_store.id)
        auth_service.logout(admin_login.session_token)

    messages = "\n".join(record.message for record in caplog.records)
    assert "successful_login" in messages
    assert "logout" in messages
    assert "store_created" in messages
    assert "store_updated" in messages
    assert "store_settings_changed" in messages
    assert "store_archived" in messages
    assert "store_restored" in messages
    assert "access_granted" in messages
    assert "access_revoked" in messages
