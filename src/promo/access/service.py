from __future__ import annotations

from dataclasses import dataclass

from promo.access.contracts import MenuVisibilityDTO, NoStoreStateDTO, SessionContextDTO
from promo.access.policy import AccessPolicy
from promo.shared.contracts.stores import StoreDTO, UserStoreAccessDTO
from promo.shared.contracts.users import UserDTO
from promo.shared.errors import PermissionDeniedError, ValidationFailedError
from promo.shared.logging import get_logger
from promo.shared.persistence.contracts import Repository
from promo.users.service import UserDirectoryService


@dataclass(slots=True, frozen=True)
class AccessServiceDependencies:
    users: Repository[UserDTO, int]
    stores: Repository[StoreDTO, int]
    user_store_access: Repository[UserStoreAccessDTO, int]
    user_directory: UserDirectoryService


class AccessService:
    def __init__(
        self,
        dependencies: AccessServiceDependencies,
        policy: AccessPolicy | None = None,
        clock=None,
        logger=None,
    ) -> None:
        self._dependencies = dependencies
        self._policy = policy or AccessPolicy()
        from promo.shared.clock import utc_now

        self._clock = clock or utc_now
        self._logger = logger or get_logger(__name__)

    def grant_user_store_access(self, actor: SessionContextDTO, user_id: int, store_id: int) -> UserStoreAccessDTO:
        self._ensure_admin(actor)
        user = self._dependencies.users.get(user_id)
        if user is None:
            raise ValidationFailedError("User not found", {"user_id": user_id})
        store = self._dependencies.stores.get(store_id)
        if store is None:
            raise ValidationFailedError("Store not found", {"store_id": store_id})
        existing = self._find_access(user_id, store_id)
        if existing is not None:
            return existing
        access = UserStoreAccessDTO(
            id=self._next_access_id(),
            user_id=user_id,
            store_id=store_id,
            created_at_utc=self._clock(),
        )
        created = self._dependencies.user_store_access.add(access)
        self._logger.info(
            "access_granted user_id=%s target_user_id=%s store_id=%s",
            actor.user.id,
            user_id,
            store_id,
        )
        return created

    def revoke_user_store_access(self, actor: SessionContextDTO, user_id: int, store_id: int) -> None:
        self._ensure_admin(actor)
        existing = self._find_access(user_id, store_id)
        if existing is None:
            return
        self._dependencies.user_store_access.delete(existing.id)
        self._logger.info(
            "access_revoked user_id=%s target_user_id=%s store_id=%s",
            actor.user.id,
            user_id,
            store_id,
        )

    def list_user_store_access(self, actor: SessionContextDTO, user_id: int) -> tuple[UserStoreAccessDTO, ...]:
        self._ensure_admin(actor)
        return tuple(sorted((item for item in self._dependencies.user_store_access.list() if item.user_id == user_id), key=lambda item: item.id))

    def build_menu_visibility(self, context: SessionContextDTO) -> MenuVisibilityDTO:
        return self._policy.build_menu_visibility(context)

    def build_no_store_state(self, context: SessionContextDTO) -> NoStoreStateDTO | None:
        return self._policy.build_no_store_state(context)

    def load_session_context_by_user_id(self, user_id: int) -> SessionContextDTO:
        snapshot = self._dependencies.user_directory.load_identity(user_id)
        if snapshot is None:
            raise ValidationFailedError("User not found", {"user_id": user_id})
        return self._policy.build_session_context(snapshot)

    def _ensure_admin(self, context: SessionContextDTO) -> None:
        decision = self._policy.can_manage_user_store_access(context)
        if not decision.allowed:
            raise PermissionDeniedError("Admin only", decision.details)

    def _find_access(self, user_id: int, store_id: int) -> UserStoreAccessDTO | None:
        for item in self._dependencies.user_store_access.list():
            if item.user_id == user_id and item.store_id == store_id:
                return item
        return None

    def _next_access_id(self) -> int:
        items = self._dependencies.user_store_access.list()
        return max((item.id for item in items), default=0) + 1
