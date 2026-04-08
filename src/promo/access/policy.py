from __future__ import annotations

from dataclasses import dataclass

from promo.access.contracts import (
    AccessibleStoreDTO,
    MenuVisibilityDTO,
    NoStoreStateDTO,
    PolicyDecisionDTO,
    SessionContextDTO,
)
from promo.shared.contracts.stores import StoreDTO
from promo.shared.contracts.users import PermissionDTO, RoleDTO, UserDTO
from promo.shared.enums import ModuleCode, PermissionCode, RoleCode, StoreStatus


@dataclass(slots=True, frozen=True)
class SessionContextInputDTO:
    user: UserDTO
    role: RoleDTO
    permissions: tuple[PermissionDTO, ...]
    accessible_stores: tuple[AccessibleStoreDTO, ...]


class AccessPolicy:
    def build_session_context(self, snapshot: SessionContextInputDTO) -> SessionContextDTO:
        is_admin = snapshot.role.code == RoleCode.ADMIN
        permission_codes = {permission.code for permission in snapshot.permissions}
        can_create_store = is_admin or PermissionCode.CREATE_STORE in permission_codes
        can_edit_store = is_admin or PermissionCode.EDIT_STORE in permission_codes
        return SessionContextDTO(
            user=snapshot.user,
            role=snapshot.role,
            permissions=snapshot.permissions,
            accessible_stores=snapshot.accessible_stores,
            is_admin=is_admin,
            can_create_store=can_create_store,
            can_edit_store=can_edit_store,
            is_blocked=snapshot.user.is_blocked,
        )

    def can_view_users(self, context: SessionContextDTO) -> PolicyDecisionDTO:
        if context.is_admin:
            return PolicyDecisionDTO(True, "admin_override")
        return PolicyDecisionDTO(False, "users_hidden")

    def can_view_logs(self, context: SessionContextDTO) -> PolicyDecisionDTO:
        if context.is_admin:
            return PolicyDecisionDTO(True, "admin_override")
        return PolicyDecisionDTO(False, "logs_hidden")

    def can_view_history(self, context: SessionContextDTO) -> PolicyDecisionDTO:
        if context.is_admin or context.has_accessible_stores:
            return PolicyDecisionDTO(True, "has_store_scope")
        return PolicyDecisionDTO(False, "no_accessible_stores")

    def can_view_stores_section(self, context: SessionContextDTO) -> PolicyDecisionDTO:
        if context.is_admin or context.can_create_store or context.can_edit_store:
            return PolicyDecisionDTO(True, "store_capability_present")
        return PolicyDecisionDTO(False, "no_store_capability")

    def can_access_store(self, context: SessionContextDTO, store: StoreDTO) -> PolicyDecisionDTO:
        if context.is_admin:
            return PolicyDecisionDTO(True, "admin_override")
        if any(access_store.id == store.id for access_store in context.accessible_stores):
            return PolicyDecisionDTO(True, "store_access_granted")
        return PolicyDecisionDTO(False, "store_not_accessible", {"store_id": store.id})

    def can_create_store(self, context: SessionContextDTO) -> PolicyDecisionDTO:
        if context.can_create_store:
            return PolicyDecisionDTO(True, "permission_granted")
        return PolicyDecisionDTO(False, "missing_permission", {"permission": PermissionCode.CREATE_STORE.value})

    def can_edit_store(self, context: SessionContextDTO, store: StoreDTO) -> PolicyDecisionDTO:
        if store.status == StoreStatus.ARCHIVED.value:
            return PolicyDecisionDTO(False, "store_archived", {"store_id": store.id})
        if context.is_admin:
            return PolicyDecisionDTO(True, "admin_override")
        if not context.can_edit_store:
            return PolicyDecisionDTO(False, "missing_permission", {"permission": PermissionCode.EDIT_STORE.value})
        if any(access_store.id == store.id for access_store in context.accessible_stores):
            return PolicyDecisionDTO(True, "store_access_granted")
        return PolicyDecisionDTO(False, "store_not_accessible", {"store_id": store.id})

    def can_archive_store(self, context: SessionContextDTO, store: StoreDTO) -> PolicyDecisionDTO:
        if not context.is_admin:
            return PolicyDecisionDTO(False, "admin_only")
        if store.status == StoreStatus.ARCHIVED.value:
            return PolicyDecisionDTO(False, "store_archived", {"store_id": store.id})
        return PolicyDecisionDTO(True, "admin_override")

    def can_restore_store(self, context: SessionContextDTO, store: StoreDTO) -> PolicyDecisionDTO:
        if not context.is_admin:
            return PolicyDecisionDTO(False, "admin_only")
        if store.status != StoreStatus.ARCHIVED.value:
            return PolicyDecisionDTO(False, "store_not_archived", {"store_id": store.id})
        return PolicyDecisionDTO(True, "admin_override")

    def can_manage_user_store_access(self, context: SessionContextDTO) -> PolicyDecisionDTO:
        if context.is_admin:
            return PolicyDecisionDTO(True, "admin_override")
        return PolicyDecisionDTO(False, "admin_only")

    def can_use_store_in_run(
        self,
        context: SessionContextDTO,
        store: StoreDTO,
        module_code: ModuleCode,
        run_lookup: object | None = None,
    ) -> PolicyDecisionDTO:
        if store.status == StoreStatus.ARCHIVED.value:
            return PolicyDecisionDTO(False, "archived_store_forbidden", {"store_id": store.id, "module_code": module_code.value})

        access_decision = self.can_access_store(context, store)
        if not access_decision.allowed:
            return PolicyDecisionDTO(False, "permission_denied", {"store_id": store.id, "module_code": module_code.value})

        if run_lookup is not None and hasattr(run_lookup, "has_active_run"):
            if run_lookup.has_active_run(store.id, module_code):
                return PolicyDecisionDTO(False, "active_run_conflict", {"store_id": store.id, "module_code": module_code.value})

        return PolicyDecisionDTO(True, "allowed")

    def build_menu_visibility(self, context: SessionContextDTO) -> MenuVisibilityDTO:
        store_markets = {store.marketplace.value for store in context.accessible_stores}
        return MenuVisibilityDTO(
            show_users=context.is_admin,
            show_stores=context.is_admin or context.can_create_store or context.can_edit_store,
            show_logs=context.is_admin,
            show_history=context.is_admin or context.has_accessible_stores,
            show_wb=context.is_admin or "wb" in store_markets,
            show_ozon=context.is_admin or "ozon" in store_markets,
            show_no_store_state=not context.is_admin and not context.has_accessible_stores,
            show_create_store_cta=context.can_create_store,
            accessible_store_count=context.accessible_store_count,
        )

    def build_no_store_state(self, context: SessionContextDTO) -> NoStoreStateDTO | None:
        if context.is_admin or context.has_accessible_stores:
            return None
        return NoStoreStateDTO(
            message="Нет доступных магазинов",
            show_create_store_cta=context.can_create_store,
            can_create_store=context.can_create_store,
        )
