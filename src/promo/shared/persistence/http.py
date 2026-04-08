from __future__ import annotations

from dataclasses import dataclass

from promo.access.contracts import SessionContextDTO
from promo.access.handlers import list_user_store_access_handler, menu_visibility_handler, no_store_state_handler
from promo.access.presentation import MenuVisibilityViewModel, NoStoreStateViewModel, UserStoreAccessViewModel
from promo.audit.contracts import DetailAuditQuery
from promo.audit.handlers import get_run_audit_page_handler, list_detail_audit_handler
from promo.audit.presentation import DetailAuditPageViewModel, RunPageReadModel
from promo.auth.handlers import change_own_password_handler, current_session_handler, login_handler, logout_handler
from promo.auth.presentation import AuthSessionViewModel, ChangeOwnPasswordForm, LoginForm, PasswordChangeViewModel
from promo.history.contracts import HistoryQuery
from promo.history.handlers import list_history_handler
from promo.history.presentation import HistoryPageViewModel
from promo.logs.contracts import LogsQuery
from promo.logs.handlers import list_logs_handler
from promo.logs.presentation import LogsPageViewModel
from promo.runs.handlers import create_check_run_handler, create_process_run_handler, drain_pending_runs_handler, get_run_status_handler
from promo.runs.presentation import RunPollingViewModel
from promo.shared.enums import ModuleCode
from promo.shared.errors import AccessDeniedError, ValidationFailedError
from promo.shared.logging import get_logger
from promo.shared.persistence.logging import RepositoryLogger
from promo.shared.persistence.wiring import PersistenceAppContext
from promo.stores.handlers import (
    archive_store_handler,
    create_store_handler,
    edit_store_handler,
    get_store_handler,
    list_stores_handler,
    restore_store_handler,
    update_store_settings_handler,
)
from promo.stores.presentation import StoreCreateForm, StoreEditForm, StoreListViewModel, StoreSettingsForm, StoreViewModel
from promo.system_maintenance import (
    RunFileRetentionDependencies,
    TemporaryFileRetentionDependencies,
    expire_run_files,
    purge_temporary_files,
)
from promo.system_maintenance.retention import MaintenanceOutcome
from promo.temp_files.contracts import TemporaryFileUploadForm
from promo.temp_files.handlers import delete_temp_file_handler, list_active_temp_files_handler, replace_temp_file_handler, upload_temp_file_handler
from promo.temp_files.presentation import TemporaryFileListViewModel, TemporaryFileViewModel
from promo.users.handlers import (
    block_user_handler,
    create_user_handler,
    edit_user_handler,
    get_user_handler,
    list_users_handler,
    unblock_user_handler,
)
from promo.users.presentation import UserCreateForm, UserDetailViewModel, UserEditForm, UserListViewModel


@dataclass(slots=True)
class AuthController:
    app: PersistenceAppContext

    def login(self, form: LoginForm) -> AuthSessionViewModel:
        with self.app.request_scope(commit=True) as bundle:
            return login_handler(bundle.auth, form)

    def logout(self, session_token: str) -> None:
        with self.app.request_scope(commit=True) as bundle:
            logout_handler(bundle.auth, session_token)

    def current_session(self, session_token: str):
        with self.app.request_scope() as bundle:
            return current_session_handler(bundle.auth, session_token)

    def change_own_password(self, session_token: str, form: ChangeOwnPasswordForm) -> PasswordChangeViewModel:
        with self.app.request_scope(commit=True) as bundle:
            return change_own_password_handler(bundle.auth, session_token, form)


@dataclass(slots=True)
class AccessController:
    app: PersistenceAppContext

    def menu_visibility(self, context: SessionContextDTO) -> MenuVisibilityViewModel:
        with self.app.request_scope() as bundle:
            return menu_visibility_handler(bundle.access, context)

    def no_store_state(self, context: SessionContextDTO) -> NoStoreStateViewModel | None:
        with self.app.request_scope() as bundle:
            return no_store_state_handler(bundle.access, context)

    def list_user_store_access(self, actor: SessionContextDTO, user_id: int) -> tuple[UserStoreAccessViewModel, ...]:
        with self.app.request_scope() as bundle:
            return list_user_store_access_handler(bundle.access, actor, user_id)

    def grant_user_store_access(self, actor: SessionContextDTO, user_id: int, store_id: int):
        with self.app.request_scope(commit=True) as bundle:
            return bundle.access.grant_user_store_access(actor, user_id, store_id)

    def revoke_user_store_access(self, actor: SessionContextDTO, user_id: int, store_id: int) -> None:
        with self.app.request_scope(commit=True) as bundle:
            bundle.access.revoke_user_store_access(actor, user_id, store_id)


@dataclass(slots=True)
class StoresController:
    app: PersistenceAppContext

    def list_stores(self, context: SessionContextDTO) -> StoreListViewModel:
        with self.app.request_scope() as bundle:
            return list_stores_handler(bundle.stores, context)

    def get_store(self, context: SessionContextDTO, store_id: int) -> StoreViewModel:
        with self.app.request_scope() as bundle:
            return get_store_handler(bundle.stores, context, store_id)

    def create_store(self, context: SessionContextDTO, form: StoreCreateForm) -> StoreViewModel:
        with self.app.request_scope(commit=True) as bundle:
            return create_store_handler(bundle.stores, context, form)

    def edit_store(self, context: SessionContextDTO, store_id: int, form: StoreEditForm) -> StoreViewModel:
        with self.app.request_scope(commit=True) as bundle:
            return edit_store_handler(bundle.stores, context, store_id, form)

    def update_settings(self, context: SessionContextDTO, store_id: int, form: StoreSettingsForm) -> StoreViewModel:
        with self.app.request_scope(commit=True) as bundle:
            return update_store_settings_handler(bundle.stores, context, store_id, form)

    def archive_store(self, context: SessionContextDTO, store_id: int) -> StoreViewModel:
        with self.app.request_scope(commit=True) as bundle:
            return archive_store_handler(bundle.stores, context, store_id)

    def restore_store(self, context: SessionContextDTO, store_id: int) -> StoreViewModel:
        with self.app.request_scope(commit=True) as bundle:
            return restore_store_handler(bundle.stores, context, store_id)


@dataclass(slots=True)
class UsersController:
    app: PersistenceAppContext

    def list_users(self, actor: SessionContextDTO) -> UserListViewModel:
        with self.app.request_scope() as bundle:
            return list_users_handler(bundle.users, actor)

    def get_user(self, actor: SessionContextDTO, user_id: int) -> UserDetailViewModel:
        with self.app.request_scope() as bundle:
            return get_user_handler(bundle.users, actor, user_id)

    def create_user(self, actor: SessionContextDTO, form: UserCreateForm) -> UserDetailViewModel:
        with self.app.request_scope(commit=True) as bundle:
            return create_user_handler(bundle.users, actor, form)

    def edit_user(self, actor: SessionContextDTO, user_id: int, form: UserEditForm) -> UserDetailViewModel:
        with self.app.request_scope(commit=True) as bundle:
            return edit_user_handler(bundle.users, actor, user_id, form)

    def block_user(self, actor: SessionContextDTO, user_id: int) -> UserDetailViewModel:
        with self.app.request_scope(commit=True) as bundle:
            return block_user_handler(bundle.users, actor, user_id)

    def unblock_user(self, actor: SessionContextDTO, user_id: int) -> UserDetailViewModel:
        with self.app.request_scope(commit=True) as bundle:
            return unblock_user_handler(bundle.users, actor, user_id)

    def assign_permission(self, actor: SessionContextDTO, user_id: int, permission_code: str) -> UserDetailViewModel:
        with self.app.request_scope(commit=True) as bundle:
            return bundle.users.assign_permission(actor, user_id, permission_code)

    def remove_permission(self, actor: SessionContextDTO, user_id: int, permission_code: str) -> UserDetailViewModel:
        with self.app.request_scope(commit=True) as bundle:
            return bundle.users.remove_permission(actor, user_id, permission_code)


@dataclass(slots=True)
class TemporaryFilesController:
    app: PersistenceAppContext

    def upload(self, context: SessionContextDTO, store_id: int, module_code: ModuleCode, form: TemporaryFileUploadForm) -> TemporaryFileViewModel:
        with self.app.request_scope(commit=True) as bundle:
            self._assert_store_access(bundle, context, store_id)
            return upload_temp_file_handler(bundle.temp_files, context.user.id, store_id, module_code, form)

    def replace(self, context: SessionContextDTO, file_id: int, form: TemporaryFileUploadForm) -> TemporaryFileViewModel:
        with self.app.request_scope(commit=True) as bundle:
            self._assert_temp_file_access(bundle, context, file_id)
            return replace_temp_file_handler(bundle.temp_files, file_id, form)

    def delete(self, context: SessionContextDTO, file_id: int) -> None:
        with self.app.request_scope(commit=True) as bundle:
            self._assert_temp_file_access(bundle, context, file_id)
            delete_temp_file_handler(bundle.temp_files, file_id)

    def list_active(self, context: SessionContextDTO, store_id: int, module_code: ModuleCode) -> TemporaryFileListViewModel:
        with self.app.request_scope() as bundle:
            self._assert_store_access(bundle, context, store_id)
            return list_active_temp_files_handler(bundle.temp_files, context.user.id, store_id, module_code)

    def _assert_temp_file_access(self, bundle, context: SessionContextDTO, file_id: int) -> None:
        file_record = bundle.uow.repositories.temporary_files.get(file_id)
        if file_record is None:
            raise ValidationFailedError("Temporary file not found", {"file_id": file_id})
        self._assert_store_access(bundle, context, file_record.store_id)
        if not context.is_admin and file_record.uploaded_by_user_id != context.user.id:
            raise AccessDeniedError(
                "Temporary file is not accessible",
                {"file_id": file_id, "store_id": file_record.store_id, "uploaded_by_user_id": file_record.uploaded_by_user_id},
            )

    def _assert_store_access(self, bundle, context: SessionContextDTO, store_id: int) -> None:
        store = bundle.uow.repositories.stores.get(store_id)
        if store is None:
            raise ValidationFailedError("Store not found", {"store_id": store_id})
        decision = self.app.policy.can_access_store(context, store)
        if not decision.allowed:
            raise AccessDeniedError("Store is not accessible", {"store_id": store_id})


@dataclass(slots=True)
class RunsController:
    app: PersistenceAppContext

    def create_check(self, context: SessionContextDTO, store_id: int):
        with self.app.request_scope(commit=True) as bundle:
            return create_check_run_handler(bundle.runs, context, store_id)

    def create_process(self, context: SessionContextDTO, store_id: int):
        with self.app.request_scope(commit=True) as bundle:
            return create_process_run_handler(bundle.runs, context, store_id)

    def get_status(self, run_id: int, context: SessionContextDTO | None = None) -> RunPollingViewModel:
        with self.app.request_scope() as bundle:
            if context is not None:
                bundle.audit.get_run_page(
                    context,
                    run_id,
                    DetailAuditQuery(page=1, page_size=25),
                )
            return get_run_status_handler(bundle.runs, run_id)


@dataclass(slots=True)
class WorkerRunsController:
    app: PersistenceAppContext

    def drain_pending(self, limit: int | None = None) -> int:
        with self.app.request_scope(commit=True) as bundle:
            return drain_pending_runs_handler(bundle.runs, limit)

    def supersede_run_file(self, run_file_id: int):
        with self.app.request_scope(commit=True) as bundle:
            return bundle.runs.supersede_run_file(run_file_id)

    def mark_run_file_unavailable(self, run_file_id: int, unavailable_reason: str):
        with self.app.request_scope(commit=True) as bundle:
            return bundle.runs.mark_run_file_unavailable(run_file_id, unavailable_reason)


@dataclass(slots=True)
class AuditController:
    app: PersistenceAppContext

    def get_run_page(self, context: SessionContextDTO, run_id: int, query: DetailAuditQuery | None = None) -> RunPageReadModel:
        with self.app.request_scope() as bundle:
            return get_run_audit_page_handler(bundle.audit, context, run_id, query)

    def list_detail(self, context: SessionContextDTO, run_id: int, query: DetailAuditQuery) -> DetailAuditPageViewModel:
        with self.app.request_scope() as bundle:
            return list_detail_audit_handler(bundle.audit, context, run_id, query)


@dataclass(slots=True)
class HistoryController:
    app: PersistenceAppContext

    def list_history(self, context: SessionContextDTO, query: HistoryQuery) -> HistoryPageViewModel:
        with self.app.request_scope() as bundle:
            return list_history_handler(bundle.history, context, query)

    def get_history_item_by_public_run_number(self, context: SessionContextDTO, public_run_number: str):
        with self.app.request_scope() as bundle:
            return bundle.history.get_history_item_by_public_run_number(context, public_run_number)


@dataclass(slots=True)
class LogsController:
    app: PersistenceAppContext

    def list_logs(self, context: SessionContextDTO, query: LogsQuery) -> LogsPageViewModel:
        with self.app.request_scope() as bundle:
            return list_logs_handler(bundle.logs, context, query)


@dataclass(slots=True)
class HttpControllerRegistry:
    auth: AuthController
    access: AccessController
    users: UsersController
    stores: StoresController
    temp_files: TemporaryFilesController
    runs: RunsController
    audit: AuditController
    history: HistoryController
    logs: LogsController


@dataclass(slots=True)
class MaintenanceController:
    app: PersistenceAppContext

    def reconcile_timed_out_runs(self) -> int:
        with self.app.request_scope(commit=True) as bundle:
            return bundle.runs.reconcile_timed_out_runs()

    def expire_run_files(self) -> MaintenanceOutcome:
        with self.app.request_scope(commit=True) as bundle:
            return expire_run_files(
                dependencies=RunFileRetentionDependencies(
                    run_files=bundle.uow.repositories.run_files,
                    file_storage=self.app.file_storage,
                    logger=RepositoryLogger(
                        bundle.uow.repositories.logs,
                        clock=self.app.clock,
                        fallback=get_logger("promo.system_maintenance"),
                    ),
                ),
                clock=self.app.clock,
            )

    def purge_temporary_files(self) -> MaintenanceOutcome:
        with self.app.request_scope(commit=True) as bundle:
            return purge_temporary_files(
                dependencies=TemporaryFileRetentionDependencies(
                    temporary_files=bundle.uow.repositories.temporary_files,
                    file_storage=self.app.file_storage,
                    logger=RepositoryLogger(
                        bundle.uow.repositories.logs,
                        clock=self.app.clock,
                        fallback=get_logger("promo.system_maintenance"),
                    ),
                ),
                clock=self.app.clock,
            )


@dataclass(slots=True)
class InternalControllerRegistry:
    worker_runs: WorkerRunsController
    maintenance: MaintenanceController


def build_http_controllers(app: PersistenceAppContext) -> HttpControllerRegistry:
    return HttpControllerRegistry(
        auth=AuthController(app),
        access=AccessController(app),
        users=UsersController(app),
        stores=StoresController(app),
        temp_files=TemporaryFilesController(app),
        runs=RunsController(app),
        audit=AuditController(app),
        history=HistoryController(app),
        logs=LogsController(app),
    )


def build_internal_controllers(app: PersistenceAppContext) -> InternalControllerRegistry:
    return InternalControllerRegistry(
        worker_runs=WorkerRunsController(app),
        maintenance=MaintenanceController(app),
    )
