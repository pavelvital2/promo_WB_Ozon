from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from promo.shared.clock import utc_now
from promo.shared.config import AppConfig, load_config
from promo.shared.contracts.users import PermissionDTO, RoleDTO, UserDTO
from promo.shared.enums import PermissionCode, RoleCode
from promo.shared.persistence.wiring import build_app_context, create_schema


@dataclass(slots=True, frozen=True)
class BootstrapOutcome:
    command: str
    status: str
    message: str
    details: dict[str, object] | None = None


def seed_reference_data(
    config: AppConfig | None = None,
    *,
    clock=utc_now,
) -> BootstrapOutcome:
    resolved = config or load_config()
    app = build_app_context(resolved, clock=clock)
    create_schema(app.engine)

    with app.request_scope(commit=True) as bundle:
        seeded_roles = _ensure_roles(bundle.uow.repositories.roles)
        seeded_permissions = _ensure_permissions(bundle.uow.repositories.permissions)

    return BootstrapOutcome(
        command="seed_reference_data",
        status="seeded",
        message="Reference data bootstrap completed.",
        details={
            "roles_seeded": seeded_roles,
            "permissions_seeded": seeded_permissions,
        },
    )


def create_first_admin(
    username: str,
    password: str,
    config: AppConfig | None = None,
    *,
    clock=utc_now,
) -> BootstrapOutcome:
    normalized_username = username.strip()
    validation_error = _validate_credentials(normalized_username, password)
    if validation_error is not None:
        return BootstrapOutcome(
            command="create_first_admin",
            status="validation_failed",
            message=validation_error,
        )

    resolved = config or load_config()
    app = build_app_context(resolved, clock=clock)
    create_schema(app.engine)
    now = clock()

    with app.request_scope(commit=True) as bundle:
        roles_repo = bundle.uow.repositories.roles
        permissions_repo = bundle.uow.repositories.permissions
        users_repo = bundle.uow.repositories.users

        _ensure_roles(roles_repo)
        _ensure_permissions(permissions_repo)
        admin_role = _find_role_by_code(roles_repo.list(), RoleCode.ADMIN.value)
        assert admin_role is not None

        existing_admin = _find_any_admin(users_repo.list(), admin_role.id)
        if existing_admin is not None:
            return BootstrapOutcome(
                command="create_first_admin",
                status="already_exists",
                message="First admin already exists.",
                details={"user_id": existing_admin.id, "username": existing_admin.username},
            )

        username_owner = _find_user_by_username(users_repo.list(), normalized_username)
        if username_owner is not None:
            return BootstrapOutcome(
                command="create_first_admin",
                status="validation_failed",
                message="Username is already taken.",
                details={"username": normalized_username},
            )

        created = users_repo.add(
            UserDTO(
                id=_next_id(users_repo.list()),
                username=normalized_username,
                password_hash=app.password_hasher.hash_password(password),
                role_id=admin_role.id,
                is_blocked=False,
                created_at_utc=now,
                updated_at_utc=now,
                last_login_at_utc=None,
            )
        )

    return BootstrapOutcome(
        command="create_first_admin",
        status="created",
        message="First admin created.",
        details={"user_id": created.id, "username": created.username},
    )


def _validate_credentials(username: str, password: str) -> str | None:
    if not username:
        return "Username must not be blank."
    if len(username) < 3:
        return "Username must be at least 3 characters long."
    if not password.strip():
        return "Password must not be blank."
    if len(password) < 5:
        return "Password must be at least 5 characters long."
    return None


def _ensure_roles(repository) -> int:
    existing = tuple(repository.list())
    required = (
        ("Администратор", RoleCode.ADMIN.value),
        ("Управляющий", RoleCode.MANAGER_LEAD.value),
        ("Менеджер", RoleCode.MANAGER.value),
    )
    next_id = _next_id(existing)
    seeded = 0
    for name, code in required:
        if _find_role_by_code(existing, code) is not None:
            continue
        repository.add(RoleDTO(id=next_id, code=code, name=name))
        next_id += 1
        seeded += 1
        existing = tuple(repository.list())
    return seeded


def _ensure_permissions(repository) -> int:
    existing = tuple(repository.list())
    required = (
        ("create_store", PermissionCode.CREATE_STORE.value),
        ("edit_store", PermissionCode.EDIT_STORE.value),
    )
    next_id = _next_id(existing)
    seeded = 0
    for name, code in required:
        if any(item.code == code for item in existing):
            continue
        repository.add(PermissionDTO(id=next_id, code=code, name=name))
        next_id += 1
        seeded += 1
        existing = tuple(repository.list())
    return seeded


def _find_role_by_code(items: tuple[RoleDTO, ...], code: str) -> RoleDTO | None:
    return next((item for item in items if item.code == code), None)


def _find_any_admin(items: tuple[UserDTO, ...], admin_role_id: int) -> UserDTO | None:
    return next((item for item in items if item.role_id == admin_role_id), None)


def _find_user_by_username(items: tuple[UserDTO, ...], username: str) -> UserDTO | None:
    username_casefold = username.casefold()
    return next((item for item in items if item.username.casefold() == username_casefold), None)


def _next_id(items: tuple[object, ...]) -> int:
    return max((getattr(item, "id") for item in items), default=0) + 1
