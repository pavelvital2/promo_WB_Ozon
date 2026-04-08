from __future__ import annotations

from dataclasses import replace

from promo.access.contracts import AccessibleStoreDTO, SessionContextDTO
from promo.access.policy import AccessPolicy
from promo.shared.clock import utc_now
from promo.shared.contracts.stores import UserStoreAccessDTO
from promo.shared.contracts.users import PermissionDTO, RoleDTO, UserDTO, UserPermissionDTO
from promo.shared.enums import MarketplaceCode, RoleCode, StoreStatus
from promo.shared.errors import PermissionDeniedError, ValidationFailedError
from promo.shared.logging import get_logger
from promo.shared.security.passwords import PasswordHasher
from promo.users.contracts import UserDirectoryDependencies, UserIdentitySnapshotDTO
from promo.users.presentation import (
    UserCreateForm,
    UserDetailViewModel,
    UserEditForm,
    UserListViewModel,
    UserPermissionViewModel,
    UserStoreAccessAssignmentViewModel,
    UserSummaryViewModel,
)


class UserDirectoryService:
    def __init__(self, dependencies: UserDirectoryDependencies, clock=utc_now) -> None:
        self._dependencies = dependencies
        self._clock = clock

    def find_user_by_username(self, username: str) -> UserDTO | None:
        normalized = username.strip()
        for user in self._dependencies.users.list():
            if user.username.casefold() == normalized.casefold():
                return user
        return None

    def load_identity(self, user_id: int) -> UserIdentitySnapshotDTO | None:
        user = self._dependencies.users.get(user_id)
        if user is None:
            return None

        role = self._dependencies.roles.get(user.role_id)
        if role is None:
            raise ValidationFailedError("Role not found", {"role_id": user.role_id})

        permissions = self._load_permissions(user.id)
        accessible_stores = self._load_accessible_stores(user, role)
        return UserIdentitySnapshotDTO(
            user=user,
            role=role,
            permissions=permissions,
            accessible_stores=accessible_stores,
        )

    def load_identity_by_username(self, username: str) -> UserIdentitySnapshotDTO | None:
        user = self.find_user_by_username(username)
        if user is None:
            return None
        return self.load_identity(user.id)

    def mark_last_login(self, user_id: int) -> UserDTO:
        user = self._dependencies.users.get(user_id)
        if user is None:
            raise ValidationFailedError("User not found", {"user_id": user_id})
        now = self._clock()
        updated = replace(user, last_login_at_utc=now, updated_at_utc=now)
        return self._dependencies.users.update(updated)

    def change_password(self, user_id: int, password_hash: str) -> UserDTO:
        user = self._dependencies.users.get(user_id)
        if user is None:
            raise ValidationFailedError("User not found", {"user_id": user_id})
        updated = replace(user, password_hash=password_hash, updated_at_utc=self._clock())
        return self._dependencies.users.update(updated)

    def list_user_summaries(self) -> UserListViewModel:
        summaries = tuple(
            UserSummaryViewModel(
                id=snapshot.user.id,
                username=snapshot.user.username,
                role_code=snapshot.role.code,
                role_name=snapshot.role.name,
                is_blocked=snapshot.user.is_blocked,
                accessible_store_count=len(snapshot.accessible_stores),
            )
            for snapshot in sorted(
                (snapshot for snapshot in (self.load_identity(user.id) for user in self._dependencies.users.list()) if snapshot is not None),
                key=lambda item: item.user.username,
            )
        )
        return UserListViewModel(items=summaries, total_items=len(summaries))

    def _load_permissions(self, user_id: int) -> tuple[PermissionDTO, ...]:
        permission_ids = {
            item.permission_id
            for item in self._dependencies.user_permissions.list()
            if item.user_id == user_id
        }
        permissions = [
            permission
            for permission in self._dependencies.permissions.list()
            if permission.id in permission_ids
        ]
        return tuple(sorted(permissions, key=lambda item: item.id))

    def _load_accessible_stores(self, user: UserDTO, role: RoleDTO) -> tuple[AccessibleStoreDTO, ...]:
        if role.code == RoleCode.ADMIN:
            stores = [
                AccessibleStoreDTO(
                    id=store.id,
                    name=store.name,
                    marketplace=MarketplaceCode(store.marketplace),
                    status=StoreStatus(store.status),
                )
                for store in self._dependencies.stores.list()
            ]
            return tuple(sorted(stores, key=lambda item: item.id))

        store_ids = {
            access.store_id
            for access in self._dependencies.user_store_access.list()
            if access.user_id == user.id
        }
        stores = [
            AccessibleStoreDTO(
                id=store.id,
                name=store.name,
                marketplace=MarketplaceCode(store.marketplace),
                status=StoreStatus(store.status),
            )
            for store in self._dependencies.stores.list()
            if store.id in store_ids
        ]
        return tuple(sorted(stores, key=lambda item: item.id))


class UserManagementService:
    def __init__(
        self,
        dependencies: UserDirectoryDependencies,
        password_hasher: PasswordHasher,
        policy: AccessPolicy | None = None,
        clock=utc_now,
        logger=None,
    ) -> None:
        self._dependencies = dependencies
        self._password_hasher = password_hasher
        self._policy = policy or AccessPolicy()
        self._clock = clock
        self._logger = logger or get_logger(__name__)
        self._directory = UserDirectoryService(dependencies, clock=clock)

    def list_users(self, actor: SessionContextDTO) -> UserListViewModel:
        self._ensure_admin(actor)
        return self._directory.list_user_summaries()

    def get_user(self, actor: SessionContextDTO, user_id: int) -> UserDetailViewModel:
        self._ensure_admin(actor)
        snapshot = self._load_snapshot(user_id)
        return self._to_detail_view_model(snapshot)

    def create_user(self, actor: SessionContextDTO, form: UserCreateForm) -> UserDetailViewModel:
        self._ensure_admin(actor)
        username = form.username.strip()
        self._validate_username(username)
        self._validate_password(form.password)
        if self._directory.find_user_by_username(username) is not None:
            raise ValidationFailedError("Username is already taken", {"username": username})

        role = self._resolve_role(form.role_code)
        permission_codes = tuple(dict.fromkeys(code.strip() for code in form.permission_codes if code.strip()))
        permissions = tuple(self._resolve_permission(code) for code in permission_codes)
        now = self._clock()
        user = self._dependencies.users.add(
            UserDTO(
                id=self._next_user_id(),
                username=username,
                password_hash=self._password_hasher.hash_password(form.password),
                role_id=role.id,
                is_blocked=False,
                created_at_utc=now,
                updated_at_utc=now,
                last_login_at_utc=None,
            )
        )
        self._replace_permissions(user.id, permissions)
        self._logger.info(
            "user_created user_id=%s target_user_id=%s role_code=%s",
            actor.user.id,
            user.id,
            role.code,
        )
        return self.get_user(actor, user.id)

    def edit_user(self, actor: SessionContextDTO, user_id: int, form: UserEditForm) -> UserDetailViewModel:
        self._ensure_admin(actor)
        user = self._require_user(user_id)
        username = user.username if form.username is None else form.username.strip()
        self._validate_username(username)
        existing = self._directory.find_user_by_username(username)
        if existing is not None and existing.id != user_id:
            raise ValidationFailedError("Username is already taken", {"username": username})

        role_id = user.role_id
        role_code = None
        if form.role_code is not None:
            role = self._resolve_role(form.role_code)
            role_id = role.id
            role_code = role.code

        updated = self._dependencies.users.update(
            replace(
                user,
                username=username,
                role_id=role_id,
                updated_at_utc=self._clock(),
            )
        )
        self._logger.info(
            "user_updated user_id=%s target_user_id=%s role_code=%s update_action=%s",
            actor.user.id,
            updated.id,
            role_code or self._dependencies.roles.get(updated.role_id).code,
            "profile_edit",
        )
        return self.get_user(actor, updated.id)

    def block_user(self, actor: SessionContextDTO, user_id: int) -> UserDetailViewModel:
        self._ensure_admin(actor)
        user = self._require_user(user_id)
        if user.is_blocked:
            return self.get_user(actor, user_id)
        self._dependencies.users.update(replace(user, is_blocked=True, updated_at_utc=self._clock()))
        self._logger.info("user_blocked user_id=%s target_user_id=%s", actor.user.id, user_id)
        return self.get_user(actor, user_id)

    def unblock_user(self, actor: SessionContextDTO, user_id: int) -> UserDetailViewModel:
        self._ensure_admin(actor)
        user = self._require_user(user_id)
        if not user.is_blocked:
            return self.get_user(actor, user_id)
        self._dependencies.users.update(replace(user, is_blocked=False, updated_at_utc=self._clock()))
        self._logger.info("user_unblocked user_id=%s target_user_id=%s", actor.user.id, user_id)
        return self.get_user(actor, user_id)

    def assign_permission(self, actor: SessionContextDTO, user_id: int, permission_code: str) -> UserDetailViewModel:
        self._ensure_admin(actor)
        user = self._require_user(user_id)
        permission = self._resolve_permission(permission_code)
        existing = self._find_user_permission(user.id, permission.id)
        if existing is None:
            self._dependencies.user_permissions.add(
                UserPermissionDTO(
                    id=self._next_user_permission_id(),
                    user_id=user.id,
                    permission_id=permission.id,
                    created_at_utc=self._clock(),
                )
            )
            self._logger.info(
                "user_updated user_id=%s target_user_id=%s permission_code=%s update_action=%s",
                actor.user.id,
                user.id,
                permission.code,
                "permission_grant",
            )
        return self.get_user(actor, user.id)

    def remove_permission(self, actor: SessionContextDTO, user_id: int, permission_code: str) -> UserDetailViewModel:
        self._ensure_admin(actor)
        user = self._require_user(user_id)
        permission = self._resolve_permission(permission_code)
        existing = self._find_user_permission(user.id, permission.id)
        if existing is not None:
            self._dependencies.user_permissions.delete(existing.id)
            self._logger.info(
                "user_updated user_id=%s target_user_id=%s permission_code=%s update_action=%s",
                actor.user.id,
                user.id,
                permission.code,
                "permission_revoke",
            )
        return self.get_user(actor, user.id)

    def _load_snapshot(self, user_id: int) -> UserIdentitySnapshotDTO:
        snapshot = self._directory.load_identity(user_id)
        if snapshot is None:
            raise ValidationFailedError("User not found", {"user_id": user_id})
        return snapshot

    def _to_detail_view_model(self, snapshot: UserIdentitySnapshotDTO) -> UserDetailViewModel:
        store_access = tuple(
            UserStoreAccessAssignmentViewModel(
                id=item.id,
                store_id=item.store_id,
                created_at_utc=item.created_at_utc,
            )
            for item in sorted(
                (item for item in self._dependencies.user_store_access.list() if item.user_id == snapshot.user.id),
                key=lambda item: item.id,
            )
        )
        permissions = tuple(
            UserPermissionViewModel(
                id=item.id,
                code=item.code,
                name=item.name,
                description=item.description,
            )
            for item in snapshot.permissions
        )
        return UserDetailViewModel(
            id=snapshot.user.id,
            username=snapshot.user.username,
            role_id=snapshot.role.id,
            role_code=snapshot.role.code,
            role_name=snapshot.role.name,
            is_blocked=snapshot.user.is_blocked,
            permission_codes=tuple(item.code for item in snapshot.permissions),
            permissions=permissions,
            store_access=store_access,
            accessible_store_count=len(snapshot.accessible_stores),
            created_at_utc=snapshot.user.created_at_utc,
            updated_at_utc=snapshot.user.updated_at_utc,
            last_login_at_utc=snapshot.user.last_login_at_utc,
        )

    def _ensure_admin(self, actor: SessionContextDTO) -> None:
        decision = self._policy.can_view_users(actor)
        if not decision.allowed:
            raise PermissionDeniedError("Admin only", decision.details)

    def _resolve_role(self, role_code: str) -> RoleDTO:
        normalized = role_code.strip()
        for item in self._dependencies.roles.list():
            if item.code == normalized:
                return item
        raise ValidationFailedError("Role not found", {"role_code": normalized})

    def _resolve_permission(self, permission_code: str) -> PermissionDTO:
        normalized = permission_code.strip()
        for item in self._dependencies.permissions.list():
            if item.code == normalized:
                return item
        raise ValidationFailedError("Permission not found", {"permission_code": normalized})

    def _replace_permissions(self, user_id: int, permissions: tuple[PermissionDTO, ...]) -> None:
        current = [item for item in self._dependencies.user_permissions.list() if item.user_id == user_id]
        for item in current:
            self._dependencies.user_permissions.delete(item.id)
        next_id = self._next_user_permission_id()
        now = self._clock()
        for permission in permissions:
            self._dependencies.user_permissions.add(
                UserPermissionDTO(
                    id=next_id,
                    user_id=user_id,
                    permission_id=permission.id,
                    created_at_utc=now,
                )
            )
            next_id += 1

    def _find_user_permission(self, user_id: int, permission_id: int) -> UserPermissionDTO | None:
        for item in self._dependencies.user_permissions.list():
            if item.user_id == user_id and item.permission_id == permission_id:
                return item
        return None

    def _require_user(self, user_id: int) -> UserDTO:
        user = self._dependencies.users.get(user_id)
        if user is None:
            raise ValidationFailedError("User not found", {"user_id": user_id})
        return user

    def _validate_username(self, username: str) -> None:
        if not username:
            raise ValidationFailedError("Username is required")
        if len(username) < 3:
            raise ValidationFailedError("Username must be at least 3 characters long")

    def _validate_password(self, password: str) -> None:
        if not password.strip():
            raise ValidationFailedError("Password is required")
        if len(password) < 5:
            raise ValidationFailedError("Password must be at least 5 characters long")

    def _next_user_id(self) -> int:
        return max((item.id for item in self._dependencies.users.list()), default=0) + 1

    def _next_user_permission_id(self) -> int:
        return max((item.id for item in self._dependencies.user_permissions.list()), default=0) + 1
