from __future__ import annotations

from promo.auth.presentation import AuthSessionViewModel, ChangeOwnPasswordForm, LoginForm, PasswordChangeViewModel
from promo.auth.service import AuthService
from promo.access.presentation import AccessibleStoreViewModel, SessionContextViewModel


def _context_view_model(context) -> SessionContextViewModel:
    return SessionContextViewModel(
        user_id=context.user.id,
        username=context.user.username,
        role_code=context.role.code,
        role_name=context.role.name,
        permission_codes=tuple(permission.code for permission in context.permissions),
        accessible_stores=tuple(
            AccessibleStoreViewModel(
                id=store.id,
                name=store.name,
                marketplace=store.marketplace.value,
                status=store.status.value,
            )
            for store in context.accessible_stores
        ),
        accessible_store_count=context.accessible_store_count,
        is_admin=context.is_admin,
        can_create_store=context.can_create_store,
        can_edit_store=context.can_edit_store,
        is_blocked=context.is_blocked,
    )


def login_handler(service: AuthService, form: LoginForm) -> AuthSessionViewModel:
    result = service.login(form.username, form.password)
    return AuthSessionViewModel(
        session_token=result.session_token,
        context=_context_view_model(result.context),
    )


def logout_handler(service: AuthService, session_token: str) -> None:
    service.logout(session_token)


def current_session_handler(service: AuthService, session_token: str) -> SessionContextViewModel:
    context = service.current_session_context(session_token)
    return _context_view_model(context)


def change_own_password_handler(service: AuthService, session_token: str, form: ChangeOwnPasswordForm) -> PasswordChangeViewModel:
    result = service.change_own_password(session_token, form.current_password, form.new_password)
    return PasswordChangeViewModel(user_id=result.user_id, changed_at_utc=result.changed_at_utc)
