from __future__ import annotations

from promo.access.contracts import SessionContextDTO
from promo.users.presentation import UserCreateForm, UserDetailViewModel, UserEditForm, UserListViewModel
from promo.users.service import UserManagementService


def list_users_handler(service: UserManagementService, actor: SessionContextDTO) -> UserListViewModel:
    return service.list_users(actor)


def get_user_handler(service: UserManagementService, actor: SessionContextDTO, user_id: int) -> UserDetailViewModel:
    return service.get_user(actor, user_id)


def create_user_handler(service: UserManagementService, actor: SessionContextDTO, form: UserCreateForm) -> UserDetailViewModel:
    return service.create_user(actor, form)


def edit_user_handler(service: UserManagementService, actor: SessionContextDTO, user_id: int, form: UserEditForm) -> UserDetailViewModel:
    return service.edit_user(actor, user_id, form)


def block_user_handler(service: UserManagementService, actor: SessionContextDTO, user_id: int) -> UserDetailViewModel:
    return service.block_user(actor, user_id)


def unblock_user_handler(service: UserManagementService, actor: SessionContextDTO, user_id: int) -> UserDetailViewModel:
    return service.unblock_user(actor, user_id)
