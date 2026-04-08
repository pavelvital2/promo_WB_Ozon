from __future__ import annotations

from dataclasses import replace

from promo.access.contracts import SessionContextDTO
from promo.access.policy import AccessPolicy
from promo.shared.contracts.stores import StoreDTO, UserStoreAccessDTO
from promo.shared.clock import utc_now
from promo.shared.enums import MarketplaceCode, StoreStatus
from promo.shared.errors import ArchivedStoreForbiddenError, PermissionDeniedError, ValidationFailedError
from promo.shared.logging import get_logger
from promo.stores.contracts import StoreServiceDependencies
from promo.stores.presentation import StoreCreateForm, StoreEditForm, StoreListViewModel, StoreSettingsForm, StoreViewModel


class StoresService:
    def __init__(
        self,
        dependencies: StoreServiceDependencies,
        policy: AccessPolicy | None = None,
        clock=utc_now,
        logger=None,
    ) -> None:
        self._dependencies = dependencies
        self._policy = policy or AccessPolicy()
        self._clock = clock
        self._logger = logger or get_logger(__name__)

    def list_stores(self, context: SessionContextDTO) -> StoreListViewModel:
        stores = self._visible_stores(context)
        return StoreListViewModel(
            items=tuple(self._to_view_model(context, store) for store in stores),
            total_items=len(stores),
        )

    def get_store(self, context: SessionContextDTO, store_id: int) -> StoreDTO:
        store = self._dependencies.stores.get(store_id)
        if store is None:
            raise ValidationFailedError("Store not found", {"store_id": store_id})
        decision = self._policy.can_access_store(context, store)
        if not decision.allowed:
            raise PermissionDeniedError("Store not accessible", decision.details)
        return store

    def create_store(self, context: SessionContextDTO, form: StoreCreateForm) -> StoreDTO:
        decision = self._policy.can_create_store(context)
        if not decision.allowed:
            raise PermissionDeniedError("Store creation denied", decision.details)

        name = form.name.strip()
        if not name:
            raise ValidationFailedError("Store name is required")
        self._validate_marketplace_fields(form)
        self._ensure_unique_name(form.marketplace.value, name)

        now = self._clock()
        store = StoreDTO(
            id=self._next_store_id(),
            name=name,
            marketplace=form.marketplace.value,
            status=StoreStatus.ACTIVE.value,
            wb_threshold_percent=form.wb_threshold_percent if form.marketplace == MarketplaceCode.WB else None,
            wb_fallback_no_promo_percent=form.wb_fallback_no_promo_percent if form.marketplace == MarketplaceCode.WB else None,
            wb_fallback_over_threshold_percent=form.wb_fallback_over_threshold_percent if form.marketplace == MarketplaceCode.WB else None,
            created_by_user_id=context.user.id,
            created_at_utc=now,
            updated_at_utc=now,
            archived_at_utc=None,
            archived_by_user_id=None,
        )
        created = self._dependencies.stores.add(store)
        if not context.is_admin:
            self._ensure_creator_access(context.user.id, created.id)
        self._logger.info(
            "store_created user_id=%s store_id=%s marketplace=%s",
            context.user.id,
            created.id,
            created.marketplace,
        )
        return created

    def edit_store(self, context: SessionContextDTO, store_id: int, form: StoreEditForm) -> StoreDTO:
        store = self.get_store(context, store_id)
        decision = self._policy.can_edit_store(context, store)
        if not decision.allowed:
            raise PermissionDeniedError("Store edit denied", decision.details)
        if store.status == StoreStatus.ARCHIVED.value:
            raise ArchivedStoreForbiddenError(details={"store_id": store_id})

        name = form.name.strip()
        if not name:
            raise ValidationFailedError("Store name is required")
        self._ensure_unique_name(store.marketplace, name, exclude_store_id=store.id)

        updated = replace(store, name=name, updated_at_utc=self._clock())
        saved = self._dependencies.stores.update(updated)
        self._logger.info(
            "store_updated user_id=%s store_id=%s",
            context.user.id,
            saved.id,
        )
        return saved

    def update_store_settings(self, context: SessionContextDTO, store_id: int, form: StoreSettingsForm) -> StoreDTO:
        store = self.get_store(context, store_id)
        decision = self._policy.can_edit_store(context, store)
        if not decision.allowed:
            raise PermissionDeniedError("Store settings edit denied", decision.details)
        if store.marketplace != MarketplaceCode.WB.value:
            raise ValidationFailedError("Store settings are WB-only", {"store_id": store_id})

        updated = replace(
            store,
            wb_threshold_percent=form.wb_threshold_percent,
            wb_fallback_no_promo_percent=form.wb_fallback_no_promo_percent,
            wb_fallback_over_threshold_percent=form.wb_fallback_over_threshold_percent,
            updated_at_utc=self._clock(),
        )
        saved = self._dependencies.stores.update(updated)
        self._logger.info(
            "store_settings_changed user_id=%s store_id=%s",
            context.user.id,
            saved.id,
        )
        return saved

    def archive_store(self, context: SessionContextDTO, store_id: int) -> StoreDTO:
        store = self._dependencies.stores.get(store_id)
        if store is None:
            raise ValidationFailedError("Store not found", {"store_id": store_id})
        decision = self._policy.can_archive_store(context, store)
        if not decision.allowed:
            raise PermissionDeniedError("Store archive denied", decision.details)

        updated = replace(
            store,
            status=StoreStatus.ARCHIVED.value,
            archived_at_utc=self._clock(),
            archived_by_user_id=context.user.id,
            updated_at_utc=self._clock(),
        )
        saved = self._dependencies.stores.update(updated)
        self._logger.info(
            "store_archived user_id=%s store_id=%s",
            context.user.id,
            saved.id,
        )
        return saved

    def restore_store(self, context: SessionContextDTO, store_id: int) -> StoreDTO:
        store = self._dependencies.stores.get(store_id)
        if store is None:
            raise ValidationFailedError("Store not found", {"store_id": store_id})
        decision = self._policy.can_restore_store(context, store)
        if not decision.allowed:
            raise PermissionDeniedError("Store restore denied", decision.details)

        updated = replace(
            store,
            status=StoreStatus.ACTIVE.value,
            archived_at_utc=None,
            archived_by_user_id=None,
            updated_at_utc=self._clock(),
        )
        saved = self._dependencies.stores.update(updated)
        self._logger.info(
            "store_restored user_id=%s store_id=%s",
            context.user.id,
            saved.id,
        )
        return saved

    def _visible_stores(self, context: SessionContextDTO) -> list[StoreDTO]:
        if context.is_admin:
            return sorted(self._dependencies.stores.list(), key=lambda item: item.id)
        store_ids = {store.id for store in context.accessible_stores}
        stores = [store for store in self._dependencies.stores.list() if store.id in store_ids]
        return sorted(stores, key=lambda item: item.id)

    def _to_view_model(self, context: SessionContextDTO, store: StoreDTO) -> StoreViewModel:
        can_edit = self._policy.can_edit_store(context, store).allowed
        can_archive = self._policy.can_archive_store(context, store).allowed
        can_restore = self._policy.can_restore_store(context, store).allowed
        return StoreViewModel(
            id=store.id,
            name=store.name,
            marketplace=store.marketplace,
            status=store.status,
            wb_threshold_percent=store.wb_threshold_percent,
            wb_fallback_no_promo_percent=store.wb_fallback_no_promo_percent,
            wb_fallback_over_threshold_percent=store.wb_fallback_over_threshold_percent,
            created_by_user_id=store.created_by_user_id,
            created_at_utc=store.created_at_utc,
            updated_at_utc=store.updated_at_utc,
            archived_at_utc=store.archived_at_utc,
            archived_by_user_id=store.archived_by_user_id,
            can_edit=can_edit,
            can_archive=can_archive,
            can_restore=can_restore,
        )

    def _ensure_unique_name(self, marketplace: str, name: str, exclude_store_id: int | None = None) -> None:
        for store in self._dependencies.stores.list():
            if exclude_store_id is not None and store.id == exclude_store_id:
                continue
            if store.marketplace == marketplace and store.name == name:
                raise ValidationFailedError("Store name must be unique within marketplace", {"marketplace": marketplace, "name": name})

    def _validate_marketplace_fields(self, form: StoreCreateForm) -> None:
        if form.marketplace == MarketplaceCode.WB:
            if form.wb_threshold_percent is None or form.wb_fallback_no_promo_percent is None or form.wb_fallback_over_threshold_percent is None:
                raise ValidationFailedError("WB store settings are required")
            return
        if any(
            value is not None
            for value in (
                form.wb_threshold_percent,
                form.wb_fallback_no_promo_percent,
                form.wb_fallback_over_threshold_percent,
            )
        ):
            raise ValidationFailedError("Ozon stores do not use WB settings")

    def _ensure_creator_access(self, user_id: int, store_id: int) -> None:
        existing = self._find_access(user_id, store_id)
        if existing is not None:
            return
        self._dependencies.user_store_access.add(
            UserStoreAccessDTO(
                id=self._next_access_id(),
                user_id=user_id,
                store_id=store_id,
                created_at_utc=self._clock(),
            )
        )

    def _find_access(self, user_id: int, store_id: int) -> UserStoreAccessDTO | None:
        for item in self._dependencies.user_store_access.list():
            if item.user_id == user_id and item.store_id == store_id:
                return item
        return None

    def _next_store_id(self) -> int:
        return max((store.id for store in self._dependencies.stores.list()), default=0) + 1

    def _next_access_id(self) -> int:
        return max((item.id for item in self._dependencies.user_store_access.list()), default=0) + 1
