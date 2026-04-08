from __future__ import annotations

import argparse
import base64
import traceback
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated
from urllib.parse import quote

import uvicorn
from fastapi import Depends, FastAPI, Header, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from promo.access.contracts import SessionContextDTO
from promo.audit.contracts import DetailAuditQuery
from promo.auth.presentation import ChangeOwnPasswordForm, LoginForm
from promo.history.contracts import HistoryQuery
from promo.logs.contracts import LogsQuery
from promo.runs.runtime import InProcessRunWorkerRuntime
from promo.shared.config import AppConfig, load_config
from promo.shared.contracts.logs import SystemLogDTO
from promo.shared.enums import MarketplaceCode, ModuleCode
from promo.shared.enums import ErrorCode
from promo.shared.errors import AccessDeniedError, AppError, ValidationFailedError
from promo.shared.logging import configure_logging
from promo.shared.persistence.logging import RepositoryLogger
from promo.shared.persistence.http import build_http_controllers, build_internal_controllers
from promo.shared.persistence.wiring import PersistenceAppContext, build_app_context, create_schema
from promo.stores.presentation import StoreCreateForm, StoreEditForm, StoreSettingsForm
from promo.system_maintenance.runtime import InProcessMaintenanceSchedulerRuntime
from promo.temp_files.contracts import TemporaryFileUploadForm
from promo.users.presentation import UserCreateForm, UserEditForm
from promo.presentation.schemas import (
    ChangePasswordRequest,
    DetailAuditQueryParams,
    HistoryQueryParams,
    LoginRequest,
    LogsQueryParams,
    RunCreateRequest,
    StoreCreateRequest,
    StoreEditRequest,
    StoreSettingsRequest,
    TempFileUploadRequest,
    UserCreateRequest,
    UserEditRequest,
)
from promo.presentation.serialization import to_payload
from promo.presentation.ui import (
    SESSION_COOKIE_NAME,
    UiPageState,
    dashboard_page,
    error_page,
    history_page,
    login_page,
    logs_page,
    password_page,
    processing_page,
    run_page as render_run_page,
    stores_page,
    store_form_page,
    users_page,
    user_form_page,
)


def create_app(
    config: AppConfig | None = None,
    *,
    app_context: PersistenceAppContext | None = None,
    autonomous_runtime: bool | None = None,
    autonomous_maintenance: bool | None = None,
) -> FastAPI:
    resolved = config or load_config()
    resolved.validate()
    configure_logging(resolved.log_level)
    context = app_context or build_app_context(resolved)
    if resolved.web.auto_create_schema:
        create_schema(context.engine)

    app = FastAPI(title=resolved.app_name)
    app.state.config = resolved
    app.state.app_context = context
    app.state.controllers = build_http_controllers(context)
    app.state.internal_operations = build_internal_controllers(context)
    app.state.run_worker_runtime = InProcessRunWorkerRuntime(context)
    app.state.maintenance_runtime = InProcessMaintenanceSchedulerRuntime(
        context,
        interval_seconds=resolved.runtime.maintenance_interval_seconds,
    )
    default_runtime_enabled = resolved.runtime.autonomous_runtime_enabled and resolved.environment != "test"
    default_maintenance_enabled = resolved.runtime.autonomous_maintenance_enabled and resolved.environment != "test"
    app.state.autonomous_runtime_enabled = default_runtime_enabled if autonomous_runtime is None else autonomous_runtime
    app.state.autonomous_maintenance_enabled = default_maintenance_enabled if autonomous_maintenance is None else autonomous_maintenance

    if app.state.autonomous_runtime_enabled:
        app.state.run_worker_runtime.start()
    if app.state.autonomous_maintenance_enabled:
        app.state.maintenance_runtime.start()

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError):
        status_code = _status_code_for_error(exc)
        return JSONResponse(content=to_payload(exc.to_dict()), status_code=status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(_: Request, exc: RequestValidationError):
        payload = {
            "error_code": ErrorCode.VALIDATION_FAILED.value,
            "error_message": "Request validation failed",
            "details": {
                "validation_error": "request_validation_failed",
                "validation_errors": exc.errors(),
            },
        }
        return JSONResponse(content=to_payload(payload), status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception):
        _persist_system_error(request, exc)
        payload = {
            "error_code": ErrorCode.SYSTEM_ERROR.value,
            "error_message": "Unexpected system error",
            "details": {
                "exception_type": exc.__class__.__name__,
                "request_path": str(request.url.path),
                "request_method": request.method,
            },
        }
        return JSONResponse(content=to_payload(payload), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "app_name": resolved.app_name,
            "environment": resolved.environment,
        }

    def shutdown_runtime() -> None:
        app.state.run_worker_runtime.stop()
        app.state.maintenance_runtime.stop()

    app.router.add_event_handler("shutdown", shutdown_runtime)

    @app.post("/api/auth/login")
    def login(payload: LoginRequest):
        return to_payload(
            app.state.controllers.auth.login(
                LoginForm(username=payload.username, password=payload.password)
            )
        )

    @app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
    def logout(session_token: Annotated[str, Header(alias="X-Session-Token")]) -> Response:
        app.state.controllers.auth.logout(session_token)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/api/auth/change-password")
    def change_password(
        payload: ChangePasswordRequest,
        session_token: Annotated[str, Header(alias="X-Session-Token")],
    ):
        return to_payload(
            app.state.controllers.auth.change_own_password(
                session_token,
                ChangeOwnPasswordForm(
                    current_password=payload.current_password,
                    new_password=payload.new_password,
                ),
            )
        )

    @app.get("/api/me")
    def get_me(
        context: Annotated[SessionContextDTO, Depends(_require_session_context)],
        session_token: Annotated[str, Header(alias="X-Session-Token")],
    ):
        menu = app.state.controllers.access.menu_visibility(context)
        no_store_state = app.state.controllers.access.no_store_state(context)
        return to_payload(
            {
                "context": app.state.controllers.auth.current_session(session_token),
                "menu_visibility": menu,
                "no_store_state": no_store_state,
            }
        )

    @app.get("/api/users")
    def list_users(context: Annotated[SessionContextDTO, Depends(_require_session_context)]):
        return to_payload(app.state.controllers.users.list_users(context))

    @app.get("/api/users/{user_id}")
    def get_user(user_id: int, context: Annotated[SessionContextDTO, Depends(_require_session_context)]):
        return to_payload(app.state.controllers.users.get_user(context, user_id))

    @app.post("/api/users")
    def create_user(payload: UserCreateRequest, context: Annotated[SessionContextDTO, Depends(_require_session_context)]):
        return to_payload(
            app.state.controllers.users.create_user(
                context,
                UserCreateForm(
                    username=payload.username,
                    password=payload.password,
                    role_code=payload.role_code,
                    permission_codes=payload.permission_codes,
                ),
            )
        )

    @app.patch("/api/users/{user_id}")
    def edit_user(
        user_id: int,
        payload: UserEditRequest,
        context: Annotated[SessionContextDTO, Depends(_require_session_context)],
    ):
        return to_payload(
            app.state.controllers.users.edit_user(
                context,
                user_id,
                UserEditForm(username=payload.username, role_code=payload.role_code),
            )
        )

    @app.post("/api/users/{user_id}/block")
    def block_user(user_id: int, context: Annotated[SessionContextDTO, Depends(_require_session_context)]):
        return to_payload(app.state.controllers.users.block_user(context, user_id))

    @app.post("/api/users/{user_id}/unblock")
    def unblock_user(user_id: int, context: Annotated[SessionContextDTO, Depends(_require_session_context)]):
        return to_payload(app.state.controllers.users.unblock_user(context, user_id))

    @app.post("/api/users/{user_id}/permissions/{permission_code}")
    def assign_permission(
        user_id: int,
        permission_code: str,
        context: Annotated[SessionContextDTO, Depends(_require_session_context)],
    ):
        return to_payload(app.state.controllers.users.assign_permission(context, user_id, permission_code))

    @app.delete("/api/users/{user_id}/permissions/{permission_code}")
    def remove_permission(
        user_id: int,
        permission_code: str,
        context: Annotated[SessionContextDTO, Depends(_require_session_context)],
    ):
        return to_payload(app.state.controllers.users.remove_permission(context, user_id, permission_code))

    @app.get("/api/access/users/{user_id}/stores")
    def list_user_store_access(
        user_id: int,
        context: Annotated[SessionContextDTO, Depends(_require_session_context)],
    ):
        return to_payload(app.state.controllers.access.list_user_store_access(context, user_id))

    @app.post("/api/access/users/{user_id}/stores/{store_id}")
    def grant_user_store_access(
        user_id: int,
        store_id: int,
        context: Annotated[SessionContextDTO, Depends(_require_session_context)],
    ):
        return to_payload(app.state.controllers.access.grant_user_store_access(context, user_id, store_id))

    @app.delete("/api/access/users/{user_id}/stores/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
    def revoke_user_store_access(
        user_id: int,
        store_id: int,
        context: Annotated[SessionContextDTO, Depends(_require_session_context)],
    ) -> Response:
        app.state.controllers.access.revoke_user_store_access(context, user_id, store_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/api/stores")
    def list_stores(context: Annotated[SessionContextDTO, Depends(_require_session_context)]):
        return to_payload(app.state.controllers.stores.list_stores(context))

    @app.get("/api/stores/{store_id}")
    def get_store(store_id: int, context: Annotated[SessionContextDTO, Depends(_require_session_context)]):
        return to_payload(app.state.controllers.stores.get_store(context, store_id))

    @app.post("/api/stores")
    def create_store(payload: StoreCreateRequest, context: Annotated[SessionContextDTO, Depends(_require_session_context)]):
        return to_payload(
            app.state.controllers.stores.create_store(
                context,
                StoreCreateForm(
                    name=payload.name,
                    marketplace=MarketplaceCode(payload.marketplace),
                    wb_threshold_percent=payload.wb_threshold_percent,
                    wb_fallback_no_promo_percent=payload.wb_fallback_no_promo_percent,
                    wb_fallback_over_threshold_percent=payload.wb_fallback_over_threshold_percent,
                ),
            )
        )

    @app.patch("/api/stores/{store_id}")
    def edit_store(
        store_id: int,
        payload: StoreEditRequest,
        context: Annotated[SessionContextDTO, Depends(_require_session_context)],
    ):
        return to_payload(app.state.controllers.stores.edit_store(context, store_id, StoreEditForm(name=payload.name)))

    @app.patch("/api/stores/{store_id}/settings")
    def update_store_settings(
        store_id: int,
        payload: StoreSettingsRequest,
        context: Annotated[SessionContextDTO, Depends(_require_session_context)],
    ):
        return to_payload(
            app.state.controllers.stores.update_settings(
                context,
                store_id,
                StoreSettingsForm(
                    wb_threshold_percent=payload.wb_threshold_percent,
                    wb_fallback_no_promo_percent=payload.wb_fallback_no_promo_percent,
                    wb_fallback_over_threshold_percent=payload.wb_fallback_over_threshold_percent,
                ),
            )
        )

    @app.post("/api/stores/{store_id}/archive")
    def archive_store(store_id: int, context: Annotated[SessionContextDTO, Depends(_require_session_context)]):
        return to_payload(app.state.controllers.stores.archive_store(context, store_id))

    @app.post("/api/stores/{store_id}/restore")
    def restore_store(store_id: int, context: Annotated[SessionContextDTO, Depends(_require_session_context)]):
        return to_payload(app.state.controllers.stores.restore_store(context, store_id))

    @app.get("/api/temp-files")
    def list_temp_files(
        store_id: int,
        module_code: str,
        context: Annotated[SessionContextDTO, Depends(_require_session_context)],
    ):
        return to_payload(app.state.controllers.temp_files.list_active(context, store_id, ModuleCode(module_code)))

    @app.post("/api/temp-files")
    def upload_temp_file(
        store_id: int,
        module_code: str,
        payload: TempFileUploadRequest,
        context: Annotated[SessionContextDTO, Depends(_require_session_context)],
    ):
        return to_payload(
            app.state.controllers.temp_files.upload(
                context,
                store_id,
                ModuleCode(module_code),
                TemporaryFileUploadForm(
                    original_filename=payload.original_filename,
                    content=_decode_base64(payload.content_base64),
                    mime_type=payload.mime_type,
                    wb_file_kind=payload.wb_file_kind,
                ),
            )
        )

    @app.patch("/api/temp-files/{file_id}")
    def replace_temp_file(
        file_id: int,
        payload: TempFileUploadRequest,
        context: Annotated[SessionContextDTO, Depends(_require_session_context)],
    ):
        return to_payload(
            app.state.controllers.temp_files.replace(
                context,
                file_id,
                TemporaryFileUploadForm(
                    original_filename=payload.original_filename,
                    content=_decode_base64(payload.content_base64),
                    mime_type=payload.mime_type,
                    wb_file_kind=payload.wb_file_kind,
                ),
            )
        )

    @app.delete("/api/temp-files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_temp_file(file_id: int, context: Annotated[SessionContextDTO, Depends(_require_session_context)]) -> Response:
        app.state.controllers.temp_files.delete(context, file_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/api/runs/check")
    def create_check_run(payload: RunCreateRequest, context: Annotated[SessionContextDTO, Depends(_require_session_context)]):
        return to_payload(app.state.controllers.runs.create_check(context, payload.store_id))

    @app.post("/api/runs/process")
    def create_process_run(payload: RunCreateRequest, context: Annotated[SessionContextDTO, Depends(_require_session_context)]):
        return to_payload(app.state.controllers.runs.create_process(context, payload.store_id))

    @app.get("/api/runs/{run_id}/status")
    def get_run_status(run_id: int, context: Annotated[SessionContextDTO, Depends(_require_session_context)]):
        return to_payload(app.state.controllers.runs.get_status(run_id, context))

    @app.get("/api/runs/{run_id}")
    def get_run_page(
        run_id: int,
        context: Annotated[SessionContextDTO, Depends(_require_session_context)],
        page: int = Query(default=1),
        page_size: int = Query(default=50),
        search: str | None = Query(default=None),
        severity: str | None = Query(default=None),
        decision_reason: str | None = Query(default=None),
        row_number_from: int | None = Query(default=None),
        row_number_to: int | None = Query(default=None),
        has_entity_key_1: bool | None = Query(default=None),
        sort_field: str = Query(default="row_number"),
        descending: bool = Query(default=False),
    ):
        return to_payload(
            app.state.controllers.audit.get_run_page(
                context,
                run_id,
                DetailAuditQuery(
                    page=page,
                    page_size=page_size,
                    search=search,
                    severity=severity,
                    decision_reason=decision_reason,
                    row_number_from=row_number_from,
                    row_number_to=row_number_to,
                    has_entity_key_1=has_entity_key_1,
                    sort_field=sort_field,
                    descending=descending,
                ),
            )
        )

    @app.get("/api/run-files/{run_file_id}/download")
    def download_run_file(
        run_file_id: int,
        request: Request,
        context: Annotated[SessionContextDTO, Depends(_require_download_session_context)],
    ) -> Response:
        run_file = _load_accessible_run_file(request, context, run_file_id)
        absolute_path = request.app.state.app_context.file_storage.root_path / run_file.storage_relative_path
        return Response(
            content=absolute_path.read_bytes(),
            media_type=run_file.mime_type,
            headers={
                "Content-Disposition": _attachment_content_disposition(run_file.original_filename),
            },
        )

    @app.get("/api/audit/runs/{run_id}/detail")
    def list_detail_audit(
        run_id: int,
        params: Annotated[DetailAuditQueryParams, Depends()],
        context: Annotated[SessionContextDTO, Depends(_require_session_context)],
    ):
        return to_payload(
            app.state.controllers.audit.list_detail(
                context,
                run_id,
                DetailAuditQuery(**params.model_dump()),
            )
        )

    @app.get("/api/history")
    def list_history(
        params: Annotated[HistoryQueryParams, Depends()],
        context: Annotated[SessionContextDTO, Depends(_require_session_context)],
    ):
        return to_payload(app.state.controllers.history.list_history(context, HistoryQuery(**params.model_dump())))

    @app.get("/api/logs")
    def list_logs(
        params: Annotated[LogsQueryParams, Depends()],
        context: Annotated[SessionContextDTO, Depends(_require_session_context)],
    ):
        return to_payload(app.state.controllers.logs.list_logs(context, LogsQuery(**params.model_dump())))

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def root(request: Request):
        state = _load_ui_state(request)
        if state is None:
            return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)

    @app.get("/login", response_class=HTMLResponse, include_in_schema=False)
    def ui_login(request: Request):
        if _load_ui_state(request) is not None:
            return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        return HTMLResponse(login_page())

    @app.get("/logout", response_class=HTMLResponse, include_in_schema=False)
    def ui_logout(request: Request):
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if token:
            try:
                request.app.state.controllers.auth.logout(token)
            except AppError:
                pass
        response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")
        return response

    @app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
    def ui_dashboard(request: Request):
        state = _require_ui_state(request)
        if isinstance(state, Response):
            return state
        return HTMLResponse(dashboard_page(state.page_state))

    @app.get("/profile/password", response_class=HTMLResponse, include_in_schema=False)
    def ui_change_password(request: Request):
        state = _require_ui_state(request)
        if isinstance(state, Response):
            return state
        return HTMLResponse(password_page(state.page_state))

    @app.get("/users", response_class=HTMLResponse, include_in_schema=False)
    def ui_users(request: Request):
        state = _require_ui_state(request)
        if isinstance(state, Response):
            return state
        try:
            listing = request.app.state.controllers.users.list_users(state.context)
            users = tuple(
                request.app.state.controllers.users.get_user(state.context, item.id)
                for item in listing.items
            )
        except AppError as exc:
            return _html_error_response(state, exc)
        return HTMLResponse(users_page(state.page_state, users))

    @app.get("/users/create", response_class=HTMLResponse, include_in_schema=False)
    def ui_create_user(request: Request):
        state = _require_ui_state(request)
        if isinstance(state, Response):
            return state
        if not state.page_state.menu.show_users:
            return HTMLResponse(error_page("Доступ запрещён", "Раздел недоступен", state=state.page_state), status_code=403)
        return HTMLResponse(
            user_form_page(
                state.page_state,
                title="Создать пользователя",
                api_path="/api/users",
                method="POST",
            )
        )

    @app.get("/users/{user_id}/edit", response_class=HTMLResponse, include_in_schema=False)
    def ui_edit_user(user_id: int, request: Request):
        state = _require_ui_state(request)
        if isinstance(state, Response):
            return state
        try:
            user = request.app.state.controllers.users.get_user(state.context, user_id)
        except AppError as exc:
            return _html_error_response(state.page_state, exc)
        return HTMLResponse(
            user_form_page(
                state.page_state,
                title=f"Редактировать {user.username}",
                api_path=f"/api/users/{user.id}",
                method="PATCH",
                user=user,
            )
        )

    @app.get("/stores", response_class=HTMLResponse, include_in_schema=False)
    def ui_stores(request: Request):
        state = _require_ui_state(request)
        if isinstance(state, Response):
            return state
        try:
            stores = request.app.state.controllers.stores.list_stores(state.context)
        except AppError as exc:
            return _html_error_response(state.page_state, exc)
        return HTMLResponse(stores_page(state.page_state, stores))

    @app.get("/stores/create", response_class=HTMLResponse, include_in_schema=False)
    def ui_create_store(request: Request):
        state = _require_ui_state(request)
        if isinstance(state, Response):
            return state
        if not state.page_state.menu.show_stores:
            return HTMLResponse(error_page("Доступ запрещён", "Раздел недоступен", state=state.page_state), status_code=403)
        return HTMLResponse(
            store_form_page(
                state.page_state,
                title="Создать магазин",
                api_path="/api/stores",
                method="POST",
            )
        )

    @app.get("/stores/{store_id}/edit", response_class=HTMLResponse, include_in_schema=False)
    def ui_edit_store(store_id: int, request: Request):
        state = _require_ui_state(request)
        if isinstance(state, Response):
            return state
        try:
            store = request.app.state.controllers.stores.get_store(state.context, store_id)
            users = request.app.state.controllers.users.list_users(state.context) if state.context.is_admin else None
            assigned_users = ()
            available_users = ()
            if users is not None:
                user_details: list = [
                    request.app.state.controllers.users.get_user(state.context, item.id)
                    for item in users.items
                ]
                assigned: list = []
                for item in users.items:
                    detail = next(user for user in user_details if user.id == item.id)
                    if any(access.store_id == store.id for access in detail.store_access):
                        assigned.append(detail)
                assigned_users = tuple(assigned)
                available_users = tuple(user_details)
        except AppError as exc:
            return _html_error_response(state.page_state, exc)
        return HTMLResponse(
            store_form_page(
                state.page_state,
                title=f"Редактировать {store.name}",
                api_path=f"/api/stores/{store.id}",
                method="PATCH",
                store=store,
                assigned_users=assigned_users,
                available_users=available_users,
            )
        )

    @app.get("/processing/wb", response_class=HTMLResponse, include_in_schema=False)
    def ui_processing_wb(request: Request, store_id: int | None = Query(default=None), run_public: str | None = Query(default=None)):
        return _render_processing_page(request, marketplace=MarketplaceCode.WB, title="Wildberries Processing", store_id=store_id, run_public=run_public)

    @app.get("/processing/ozon", response_class=HTMLResponse, include_in_schema=False)
    def ui_processing_ozon(request: Request, store_id: int | None = Query(default=None), run_public: str | None = Query(default=None)):
        return _render_processing_page(request, marketplace=MarketplaceCode.OZON, title="Ozon Processing", store_id=store_id, run_public=run_public)

    @app.get("/runs", response_class=HTMLResponse, include_in_schema=False)
    def ui_history(
        request: Request,
        page: int = Query(default=1),
        page_size: int = Query(default=50),
        search: str | None = Query(default=None),
        store_id: int | None = Query(default=None),
        initiated_by_user_id: int | None = Query(default=None),
        marketplace: str | None = Query(default=None),
        module_code: str | None = Query(default=None),
        operation_type: str | None = Query(default=None),
        lifecycle_status: str | None = Query(default=None),
        business_result: str | None = Query(default=None),
        store_status: str | None = Query(default=None),
        started_from_utc: str | None = Query(default=None),
        started_to_utc: str | None = Query(default=None),
        sort_field: str = Query(default="started_at_utc"),
        descending: bool = Query(default=True),
    ):
        state = _require_ui_state(request)
        if isinstance(state, Response):
            return state
        try:
            history = request.app.state.controllers.history.list_history(
                state.context,
                HistoryQuery(
                    page=page,
                    page_size=page_size,
                    search=search,
                    store_id=store_id,
                    initiated_by_user_id=initiated_by_user_id,
                    marketplace=marketplace,
                    module_code=module_code,
                    operation_type=operation_type,
                    lifecycle_status=lifecycle_status,
                    business_result=business_result,
                    store_status=store_status,
                    started_from_utc=None if not started_from_utc else _parse_datetime_query(started_from_utc),
                    started_to_utc=None if not started_to_utc else _parse_datetime_query(started_to_utc),
                    sort_field=sort_field,
                    descending=descending,
                ),
            )
        except AppError as exc:
            return _html_error_response(state.page_state, exc)
        return HTMLResponse(
            history_page(
                state.page_state,
                history,
                current_query={
                    "search": search,
                    "store_id": store_id,
                    "initiated_by_user_id": initiated_by_user_id,
                    "marketplace": marketplace,
                    "module_code": module_code,
                    "operation_type": operation_type,
                    "lifecycle_status": lifecycle_status,
                    "business_result": business_result,
                    "store_status": store_status,
                    "started_from_utc": started_from_utc,
                    "started_to_utc": started_to_utc,
                    "sort_field": sort_field,
                    "descending": descending,
                    "page_size": page_size,
                },
            )
        )

    @app.get("/logs", response_class=HTMLResponse, include_in_schema=False)
    def ui_logs(
        request: Request,
        page: int = Query(default=1),
        page_size: int = Query(default=50),
        search: str | None = Query(default=None),
        user_id: int | None = Query(default=None),
        store_id: int | None = Query(default=None),
        module_code: str | None = Query(default=None),
        event_type: str | None = Query(default=None),
        severity: str | None = Query(default=None),
        run_id: int | None = Query(default=None),
        public_run_number: str | None = Query(default=None),
        event_from_utc: str | None = Query(default=None),
        event_to_utc: str | None = Query(default=None),
        sort_field: str = Query(default="event_time_utc"),
        descending: bool = Query(default=True),
    ):
        state = _require_ui_state(request)
        if isinstance(state, Response):
            return state
        try:
            logs = request.app.state.controllers.logs.list_logs(
                state.context,
                LogsQuery(
                    page=page,
                    page_size=page_size,
                    search=search,
                    user_id=user_id,
                    store_id=store_id,
                    module_code=module_code,
                    event_type=event_type,
                    severity=severity,
                    run_id=run_id,
                    public_run_number=public_run_number,
                    event_from_utc=None if not event_from_utc else _parse_datetime_query(event_from_utc),
                    event_to_utc=None if not event_to_utc else _parse_datetime_query(event_to_utc),
                    sort_field=sort_field,
                    descending=descending,
                ),
            )
        except AppError as exc:
            return _html_error_response(state.page_state, exc)
        return HTMLResponse(
            logs_page(
                state.page_state,
                logs,
                current_query={
                    "search": search,
                    "user_id": user_id,
                    "store_id": store_id,
                    "module_code": module_code,
                    "event_type": event_type,
                    "severity": severity,
                    "run_id": run_id,
                    "public_run_number": public_run_number,
                    "event_from_utc": event_from_utc,
                    "event_to_utc": event_to_utc,
                    "sort_field": sort_field,
                    "descending": descending,
                    "page_size": page_size,
                },
            )
        )

    @app.get("/runs/{public_run_number}", response_class=HTMLResponse, include_in_schema=False)
    def ui_run_page(
        public_run_number: str,
        request: Request,
        page: int = Query(default=1),
        page_size: int = Query(default=50),
        search: str | None = Query(default=None),
        severity: str | None = Query(default=None),
        decision_reason: str | None = Query(default=None),
        row_number_from: int | None = Query(default=None),
        row_number_to: int | None = Query(default=None),
        has_entity_key_1: bool | None = Query(default=None),
        sort_field: str = Query(default="row_number"),
        descending: bool = Query(default=False),
    ):
        state = _require_ui_state(request)
        if isinstance(state, Response):
            return state
        try:
            run = _find_run_by_public_number(request, state.context, public_run_number)
            if run is None:
                raise ValidationFailedError("Run not found", {"public_run_number": public_run_number}, status_code=status.HTTP_404_NOT_FOUND)
            run_model = request.app.state.controllers.audit.get_run_page(
                state.context,
                run.run_id,
                DetailAuditQuery(
                    page=page,
                    page_size=page_size,
                    search=search,
                    severity=severity,
                    decision_reason=decision_reason,
                    row_number_from=row_number_from,
                    row_number_to=row_number_to,
                    has_entity_key_1=has_entity_key_1,
                    sort_field=sort_field,
                    descending=descending,
                ),
            )
        except AppError as exc:
            return _html_error_response(state.page_state, exc)
        return HTMLResponse(
            render_run_page(
                state.page_state,
                run_model,
                current_query={
                    "search": search,
                    "severity": severity,
                    "decision_reason": decision_reason,
                    "row_number_from": row_number_from,
                    "row_number_to": row_number_to,
                    "has_entity_key_1": has_entity_key_1,
                    "sort_field": sort_field,
                    "descending": descending,
                    "page_size": page_size,
                },
            )
        )

    return app


def run_server(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="promo-web")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args(argv)

    config = load_config()
    host = args.host or config.web.host
    port = args.port or config.web.port
    uvicorn.run(
        "promo.presentation.app:create_app",
        factory=True,
        host=host,
        port=port,
        proxy_headers=config.web.proxy_headers,
        forwarded_allow_ips=config.web.forwarded_allow_ips,
    )
    return 0


def main() -> int:
    return run_server()


@dataclass(slots=True, frozen=True)
class _UiRequestState:
    context: SessionContextDTO
    page_state: UiPageState


def _load_ui_state(request: Request) -> _UiRequestState | None:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token:
        return None
    try:
        with request.app.state.app_context.request_scope() as bundle:
            context = bundle.auth.current_session_context(session_token)
            menu = bundle.access.build_menu_visibility(context)
            no_store_state = bundle.access.build_no_store_state(context)
    except AppError:
        return None
    return _UiRequestState(
        context=context,
        page_state=UiPageState(
            username=context.user.username,
            role_name=context.role.name,
            menu=menu,
            no_store_state=no_store_state,
        ),
    )


def _require_ui_state(request: Request) -> _UiRequestState | Response:
    state = _load_ui_state(request)
    if state is None:
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    return state


def _html_error_response(state: UiPageState | _UiRequestState, exc: AppError) -> HTMLResponse:
    page_state = state.page_state if isinstance(state, _UiRequestState) else state
    return HTMLResponse(
        error_page(exc.error_message, exc.error_message, state=page_state),
        status_code=_status_code_for_error(exc),
    )


def _active_processing_stores(request: Request, context: SessionContextDTO, marketplace: MarketplaceCode):
    stores = request.app.state.controllers.stores.list_stores(context)
    return tuple(
        item for item in stores.items
        if item.marketplace == marketplace.value and item.status == "active"
    )


def _find_run_by_public_number(request: Request, context: SessionContextDTO, public_run_number: str):
    return request.app.state.controllers.history.get_history_item_by_public_run_number(context, public_run_number)


def _render_processing_page(
    request: Request,
    *,
    marketplace: MarketplaceCode,
    title: str,
    store_id: int | None,
    run_public: str | None,
) -> HTMLResponse | Response:
    state = _require_ui_state(request)
    if isinstance(state, Response):
        return state
    stores = _active_processing_stores(request, state.context, marketplace)
    temp_files = None
    run_page = None
    selected_store_id = store_id
    module_code = ModuleCode(marketplace.value)
    try:
        if selected_store_id is None and stores:
            selected_store_id = stores[0].id
        if selected_store_id is not None:
            temp_files = request.app.state.controllers.temp_files.list_active(state.context, selected_store_id, module_code)
        if run_public:
            run = _find_run_by_public_number(request, state.context, run_public)
            if run is not None:
                run_page = request.app.state.controllers.audit.get_run_page(
                    state.context,
                    run.run_id,
                    DetailAuditQuery(page=1, page_size=25),
                )
    except AppError as exc:
        return _html_error_response(state.page_state, exc)
    return HTMLResponse(
        processing_page(
            state.page_state,
            title=title,
            module_code=module_code.value,
            stores=stores,
            selected_store_id=selected_store_id,
            temp_files=temp_files,
            run_page=run_page,
        )
    )


def _require_session_context(
    request: Request,
    session_token: Annotated[str | None, Header(alias="X-Session-Token")] = None,
) -> SessionContextDTO:
    session_token = _resolve_session_token(
        request=request,
        header_session_token=session_token,
        allow_cookie_fallback=False,
    )
    with request.app.state.app_context.request_scope() as bundle:
        return bundle.auth.current_session_context(session_token)


def _require_download_session_context(
    request: Request,
    session_token: Annotated[str | None, Header(alias="X-Session-Token")] = None,
) -> SessionContextDTO:
    session_token = _resolve_session_token(
        request=request,
        header_session_token=session_token,
        allow_cookie_fallback=True,
    )
    with request.app.state.app_context.request_scope() as bundle:
        return bundle.auth.current_session_context(session_token)


def _resolve_session_token(
    *,
    request: Request,
    header_session_token: str | None,
    allow_cookie_fallback: bool,
) -> str:
    if header_session_token:
        return header_session_token
    if allow_cookie_fallback:
        cookie_session_token = request.cookies.get(SESSION_COOKIE_NAME)
        if cookie_session_token:
            return cookie_session_token
    raise AccessDeniedError(
        "Missing X-Session-Token header",
        {"auth_error": "missing_session_token", "header": "X-Session-Token"},
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


def _attachment_content_disposition(original_filename: str) -> str:
    fallback_name = "".join(
        character if 32 <= ord(character) < 127 and character not in {'"', "\\"} else "_"
        for character in original_filename
    ).strip(" .")
    if not fallback_name:
        fallback_name = "download"
    encoded_name = quote(original_filename, safe="")
    return f"""attachment; filename="{fallback_name}"; filename*=UTF-8''{encoded_name}"""


def _decode_base64(value: str) -> bytes:
    try:
        return base64.b64decode(value.encode("utf-8"), validate=True)
    except Exception as exc:  # noqa: BLE001
        raise ValidationFailedError(
            "Invalid base64 file content",
            {"field": "content_base64", "validation_error": "invalid_base64"},
            status_code=status.HTTP_400_BAD_REQUEST,
        ) from exc


def _parse_datetime_query(value: str):
    normalized = value.strip()
    if not normalized:
        return None
    try:
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValidationFailedError(
            "Invalid datetime query parameter",
            {"value": value, "validation_error": "invalid_datetime_query"},
        ) from exc


def _status_code_for_error(error: AppError) -> int:
    if error.http_status is not None:
        return error.http_status
    error_code = error.error_code
    if error_code in {ErrorCode.ACCESS_DENIED, ErrorCode.PERMISSION_DENIED}:
        return status.HTTP_403_FORBIDDEN
    if error_code == ErrorCode.ACTIVE_RUN_CONFLICT:
        return status.HTTP_409_CONFLICT
    return status.HTTP_400_BAD_REQUEST


def _persist_system_error(request: Request, exc: Exception) -> None:
    app_context = request.app.state.app_context
    try:
        with app_context.request_scope(commit=True) as bundle:
            logs_repo = bundle.uow.repositories.logs
            next_id = max((item.id for item in logs_repo.list()), default=0) + 1
            logs_repo.add(
                SystemLogDTO(
                    id=next_id,
                    event_time_utc=app_context.clock(),
                    user_id=None,
                    store_id=None,
                    run_id=None,
                    module_code=None,
                    event_type=ErrorCode.SYSTEM_ERROR.value,
                    severity="error",
                    message=f"system_error request_method={request.method} request_path={request.url.path} exception_type={exc.__class__.__name__}",
                    payload_json={
                        "request_method": request.method,
                        "request_path": str(request.url.path),
                        "exception_type": exc.__class__.__name__,
                        "error_message": str(exc),
                        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-4000:],
                    },
                )
            )
    except Exception:
        return


def _load_accessible_run_file(request: Request, context: SessionContextDTO, run_file_id: int):
    with request.app.state.app_context.request_scope(commit=True) as bundle:
        run_file = bundle.uow.repositories.run_files.get(run_file_id)
        if run_file is None:
            raise ValidationFailedError("Run file not found", {"run_file_id": run_file_id}, status_code=status.HTTP_404_NOT_FOUND)
        run = bundle.uow.repositories.runs.get(run_file.run_id)
        if run is None:
            raise ValidationFailedError("Run not found", {"run_id": run_file.run_id}, status_code=status.HTTP_404_NOT_FOUND)
        store = bundle.uow.repositories.stores.get(run.store_id)
        if store is None:
            raise ValidationFailedError("Store not found", {"store_id": run.store_id}, status_code=status.HTTP_404_NOT_FOUND)
        decision = request.app.state.app_context.policy.can_access_store(context, store)
        if not decision.allowed:
            raise AccessDeniedError("Run file is not accessible", {"run_file_id": run_file_id, "store_id": run.store_id})
        if not run_file.is_available:
            raise ValidationFailedError(
                "Run file is unavailable",
                {
                    "run_file_id": run_file.id,
                    "run_id": run.id,
                    "store_id": run.store_id,
                    "unavailable_reason": run_file.unavailable_reason,
                },
                status_code=status.HTTP_410_GONE,
            )
        absolute_path = request.app.state.app_context.file_storage.root_path / run_file.storage_relative_path
        if not absolute_path.exists():
            raise ValidationFailedError(
                "Run file not found",
                {"run_file_id": run_file.id, "storage_path": run_file.storage_relative_path},
                status_code=status.HTTP_404_NOT_FOUND,
            )
        event_type = "result_downloaded" if run_file.file_role.endswith("_result_output") else "source_file_downloaded"
        logger = RepositoryLogger(bundle.uow.repositories.logs, clock=request.app.state.app_context.clock)
        logger.info(
            "%s user_id=%s store_id=%s run_id=%s module_code=%s file_metadata_id=%s file_role=%s storage_path=%s",
            event_type,
            context.user.id,
            run.store_id,
            run.id,
            run.module_code,
            run_file.id,
            run_file.file_role,
            run_file.storage_relative_path,
        )
        return run_file


if __name__ == "__main__":
    raise SystemExit(main())
