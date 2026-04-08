from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from promo.access.contracts import SessionContextDTO
from promo.auth.presentation import LoginForm
from promo.history.contracts import HistoryQuery
from promo.logs.contracts import LogsQuery
from promo.runs.service import SkeletonRunExecutionStrategy
from promo.shared.config import AppConfig, DatabaseConfig, RetentionConfig, StorageConfig, WebConfig
from promo.shared.contracts.users import PermissionDTO, RoleDTO, UserDTO, UserPermissionDTO
from promo.shared.db import build_engine
from promo.shared.enums import MarketplaceCode, ModuleCode, RoleCode
from promo.shared.errors import AccessDeniedError
from promo.shared.persistence.http import build_http_controllers, build_internal_controllers
from promo.shared.persistence.wiring import build_app_context, create_schema
from promo.presentation.app import create_app
from promo.stores.presentation import StoreCreateForm
from promo.temp_files.contracts import TemporaryFileUploadForm


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _build_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        app_name="promo-test",
        environment="test",
        timezone="UTC",
        database=DatabaseConfig(dsn=f"sqlite+pysqlite:///{tmp_path / 'promo.sqlite3'}"),
        storage=StorageConfig(root_path=tmp_path / "storage"),
        retention=RetentionConfig(),
        log_level="INFO",
        web=WebConfig(auto_create_schema=False),
    )


def _seed_reference_data(app, *, hasher) -> None:
    with app.request_scope(commit=True) as bundle:
        bundle.uow.repositories.roles.add(RoleDTO(id=1, code=RoleCode.ADMIN.value, name="Администратор"))
        bundle.uow.repositories.roles.add(RoleDTO(id=2, code=RoleCode.MANAGER.value, name="Менеджер"))
        bundle.uow.repositories.permissions.add(PermissionDTO(id=1, code="create_store", name="create_store"))
        bundle.uow.repositories.permissions.add(PermissionDTO(id=2, code="edit_store", name="edit_store"))
        bundle.uow.repositories.users.add(
            UserDTO(
                id=1,
                username="admin",
                password_hash=hasher.hash_password("admin-pass"),
                role_id=1,
                is_blocked=False,
                created_at_utc=_dt("2026-04-07T10:00:00+00:00"),
                updated_at_utc=_dt("2026-04-07T10:00:00+00:00"),
                last_login_at_utc=None,
            )
        )
        bundle.uow.repositories.users.add(
            UserDTO(
                id=2,
                username="manager",
                password_hash=hasher.hash_password("manager-pass"),
                role_id=2,
                is_blocked=False,
                created_at_utc=_dt("2026-04-07T10:00:00+00:00"),
                updated_at_utc=_dt("2026-04-07T10:00:00+00:00"),
                last_login_at_utc=None,
            )
        )
        bundle.uow.repositories.user_permissions.add(
            UserPermissionDTO(id=1, user_id=1, permission_id=1, created_at_utc=_dt("2026-04-07T10:00:00+00:00"))
        )
        bundle.uow.repositories.user_permissions.add(
            UserPermissionDTO(id=2, user_id=1, permission_id=2, created_at_utc=_dt("2026-04-07T10:00:00+00:00"))
        )


def _load_context(app, session_token: str) -> SessionContextDTO:
    with app.request_scope() as bundle:
        return bundle.auth.current_session_context(session_token)


def test_persistence_backed_auth_store_access_and_logs(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    engine = build_engine(config.database.dsn)
    create_schema(engine)
    app = build_app_context(
        config,
        clock=lambda: _dt("2026-04-07T12:00:00+00:00"),
        execution_strategy_factory=lambda storage: SkeletonRunExecutionStrategy(),
    )
    controllers = build_http_controllers(app)
    internal = build_internal_controllers(app)
    _seed_reference_data(app, hasher=app.password_hasher)

    admin_session = controllers.auth.login(LoginForm(username="admin", password="admin-pass"))
    admin_context = _load_context(app, admin_session.session_token)

    created_store = controllers.stores.create_store(
        admin_context,
        StoreCreateForm(
            name="VitalEmb",
            marketplace=MarketplaceCode.WB,
            wb_threshold_percent=60,
            wb_fallback_no_promo_percent=40,
            wb_fallback_over_threshold_percent=25,
        ),
    )
    controllers.access.grant_user_store_access(admin_context, user_id=2, store_id=created_store.id)

    manager_session = controllers.auth.login(LoginForm(username="manager", password="manager-pass"))
    manager_context = _load_context(app, manager_session.session_token)

    assert manager_context.has_accessible_stores is True
    assert manager_context.accessible_store_count == 1

    logs_page = controllers.logs.list_logs(admin_context, LogsQuery(page=1, page_size=50, sort_field="event_time_utc", descending=True))
    event_types = {item.event_type for item in logs_page.items}
    assert "successful_login" in event_types
    assert "store_created" in event_types
    assert "access_granted" in event_types


def test_persistence_backed_temp_files_runs_and_read_side(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    engine = build_engine(config.database.dsn)
    create_schema(engine)
    app = build_app_context(
        config,
        clock=lambda: _dt("2026-04-07T12:00:00+00:00"),
        execution_strategy_factory=lambda storage: SkeletonRunExecutionStrategy(),
    )
    controllers = build_http_controllers(app)
    internal = build_internal_controllers(app)
    _seed_reference_data(app, hasher=app.password_hasher)

    admin_session = controllers.auth.login(LoginForm(username="admin", password="admin-pass"))
    admin_context = _load_context(app, admin_session.session_token)
    created_store = controllers.stores.create_store(
        admin_context,
        StoreCreateForm(
            name="OzonShop",
            marketplace=MarketplaceCode.OZON,
        ),
    )
    controllers.access.grant_user_store_access(admin_context, user_id=2, store_id=created_store.id)

    manager_session = controllers.auth.login(LoginForm(username="manager", password="manager-pass"))
    manager_context = _load_context(app, manager_session.session_token)

    uploaded = controllers.temp_files.upload(
        manager_context,
        store_id=created_store.id,
        module_code=ModuleCode.OZON,
        form=TemporaryFileUploadForm(
            original_filename="ozon.xlsx",
            content=b"ozon-bytes",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    )
    run = controllers.runs.create_check(manager_context, created_store.id)
    processed = internal.worker_runs.drain_pending()
    polling = controllers.runs.get_status(run.id, manager_context)
    history = controllers.history.list_history(manager_context, HistoryQuery(page=1, page_size=50, sort_field="started_at_utc", descending=True))
    audit_page = controllers.audit.get_run_page(manager_context, run.id)

    assert uploaded.original_filename == "ozon.xlsx"
    assert processed == 1
    assert polling.lifecycle_status == "completed"
    assert history.total_items == 1
    assert history.items[0].public_run_number == run.public_run_number
    assert audit_page.summary_audit_json is not None
    assert audit_page.run.run_id == run.id
    assert not hasattr(controllers.runs, "get_page")
    assert not hasattr(controllers.runs, "drain_pending")
    assert hasattr(internal.worker_runs, "drain_pending")

    logs_page = controllers.logs.list_logs(admin_context, LogsQuery(page=1, page_size=50, sort_field="event_time_utc", descending=True))
    event_types = {item.event_type for item in logs_page.items}
    assert "file_uploaded" in event_types
    assert "check_started" in event_types
    assert "check_finished" in event_types


def test_temp_files_controller_requires_actor_context_and_store_scope(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    engine = build_engine(config.database.dsn)
    create_schema(engine)
    app = build_app_context(
        config,
        clock=lambda: _dt("2026-04-07T12:00:00+00:00"),
        execution_strategy_factory=lambda storage: SkeletonRunExecutionStrategy(),
    )
    controllers = build_http_controllers(app)
    build_internal_controllers(app)
    _seed_reference_data(app, hasher=app.password_hasher)

    admin_session = controllers.auth.login(LoginForm(username="admin", password="admin-pass"))
    admin_context = _load_context(app, admin_session.session_token)
    manager_session = controllers.auth.login(LoginForm(username="manager", password="manager-pass"))
    manager_context = _load_context(app, manager_session.session_token)

    created_store = controllers.stores.create_store(
        admin_context,
        StoreCreateForm(
            name="ScopedTempFiles",
            marketplace=MarketplaceCode.WB,
            wb_threshold_percent=60,
            wb_fallback_no_promo_percent=40,
            wb_fallback_over_threshold_percent=25,
        ),
    )

    with pytest.raises(AccessDeniedError):
        controllers.temp_files.upload(
            manager_context,
            store_id=created_store.id,
            module_code=ModuleCode.WB,
            form=TemporaryFileUploadForm(
                original_filename="blocked.xlsx",
                content=b"blocked",
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                wb_file_kind="price",
            ),
        )

    controllers.access.grant_user_store_access(admin_context, user_id=2, store_id=created_store.id)
    manager_context = _load_context(app, manager_session.session_token)

    uploaded = controllers.temp_files.upload(
        manager_context,
        store_id=created_store.id,
        module_code=ModuleCode.WB,
        form=TemporaryFileUploadForm(
            original_filename="allowed.xlsx",
            content=b"allowed",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            wb_file_kind="price",
        ),
    )
    active = controllers.temp_files.list_active(manager_context, created_store.id, ModuleCode.WB)
    assert active.total_items == 1
    assert active.items[0].id == uploaded.id

    admin_uploaded = controllers.temp_files.upload(
        admin_context,
        store_id=created_store.id,
        module_code=ModuleCode.WB,
        form=TemporaryFileUploadForm(
            original_filename="admin.xlsx",
            content=b"admin",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            wb_file_kind="price",
        ),
    )

    with pytest.raises(AccessDeniedError):
        controllers.temp_files.delete(manager_context, admin_uploaded.id)


def test_web_app_runtime_autostart_is_explicit_in_test_environment(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    engine = build_engine(config.database.dsn)
    create_schema(engine)
    app_context = build_app_context(
        config,
        clock=lambda: _dt("2026-04-07T12:00:00+00:00"),
        execution_strategy_factory=lambda storage: SkeletonRunExecutionStrategy(),
    )

    default_app = create_app(config, app_context=app_context)
    assert default_app.state.autonomous_runtime_enabled is False
    assert default_app.state.run_worker_runtime.is_running() is False
    assert default_app.state.autonomous_maintenance_enabled is False
    assert default_app.state.maintenance_runtime.is_running() is False

    runtime_app = create_app(config, app_context=app_context, autonomous_runtime=True)
    assert runtime_app.state.autonomous_runtime_enabled is True
    assert runtime_app.state.run_worker_runtime.is_running() is True
    runtime_app.state.run_worker_runtime.stop()

    maintenance_app = create_app(config, app_context=app_context, autonomous_maintenance=True)
    assert maintenance_app.state.autonomous_maintenance_enabled is True
    assert maintenance_app.state.maintenance_runtime.is_running() is True
    maintenance_app.state.maintenance_runtime.stop()
