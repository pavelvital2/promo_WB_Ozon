from __future__ import annotations

from promo.access.contracts import SessionContextDTO
from promo.access.presentation import (
    MenuVisibilityViewModel,
    NoStoreStateViewModel,
    UserStoreAccessViewModel,
)
from promo.access.service import AccessService


def menu_visibility_handler(service: AccessService, context: SessionContextDTO) -> MenuVisibilityViewModel:
    visibility = service.build_menu_visibility(context)
    return MenuVisibilityViewModel(
        show_dashboard=visibility.show_dashboard,
        show_users=visibility.show_users,
        show_stores=visibility.show_stores,
        show_logs=visibility.show_logs,
        show_history=visibility.show_history,
        show_wb=visibility.show_wb,
        show_ozon=visibility.show_ozon,
        show_no_store_state=visibility.show_no_store_state,
        show_create_store_cta=visibility.show_create_store_cta,
        accessible_store_count=visibility.accessible_store_count,
    )


def no_store_state_handler(service: AccessService, context: SessionContextDTO) -> NoStoreStateViewModel | None:
    state = service.build_no_store_state(context)
    if state is None:
        return None
    return NoStoreStateViewModel(
        message=state.message,
        show_create_store_cta=state.show_create_store_cta,
        can_create_store=state.can_create_store,
    )


def list_user_store_access_handler(service: AccessService, actor: SessionContextDTO, user_id: int) -> tuple[UserStoreAccessViewModel, ...]:
    return tuple(
        UserStoreAccessViewModel(
            id=item.id,
            user_id=item.user_id,
            store_id=item.store_id,
            created_at_utc=item.created_at_utc,
        )
        for item in service.list_user_store_access(actor, user_id)
    )
