from __future__ import annotations

from promo.access.contracts import SessionContextDTO
from promo.stores.presentation import StoreCreateForm, StoreEditForm, StoreListViewModel, StoreSettingsForm, StoreViewModel
from promo.stores.service import StoresService


def list_stores_handler(service: StoresService, context: SessionContextDTO) -> StoreListViewModel:
    return service.list_stores(context)


def create_store_handler(service: StoresService, context: SessionContextDTO, form: StoreCreateForm) -> StoreViewModel:
    store = service.create_store(context, form)
    return _find_store_view_model(service, context, store.id)


def edit_store_handler(service: StoresService, context: SessionContextDTO, store_id: int, form: StoreEditForm) -> StoreViewModel:
    store = service.edit_store(context, store_id, form)
    return _find_store_view_model(service, context, store.id)


def update_store_settings_handler(service: StoresService, context: SessionContextDTO, store_id: int, form: StoreSettingsForm) -> StoreViewModel:
    store = service.update_store_settings(context, store_id, form)
    return _find_store_view_model(service, context, store.id)


def archive_store_handler(service: StoresService, context: SessionContextDTO, store_id: int) -> StoreViewModel:
    store = service.archive_store(context, store_id)
    return _find_store_view_model(service, context, store.id)


def restore_store_handler(service: StoresService, context: SessionContextDTO, store_id: int) -> StoreViewModel:
    store = service.restore_store(context, store_id)
    return _find_store_view_model(service, context, store.id)


def get_store_handler(service: StoresService, context: SessionContextDTO, store_id: int) -> StoreViewModel:
    store = service.get_store(context, store_id)
    return _find_store_view_model(service, context, store.id)


def _find_store_view_model(service: StoresService, context: SessionContextDTO, store_id: int) -> StoreViewModel:
    stores = service.list_stores(context)
    for item in stores.items:
        if item.id == store_id:
            return item
    raise LookupError(f"Store {store_id} is not visible in the current context")

