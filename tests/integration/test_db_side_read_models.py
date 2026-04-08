from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from promo.audit.contracts import DetailAuditQuery
from promo.auth.presentation import LoginForm
from promo.history.contracts import HistoryQuery
from promo.logs.contracts import LogsQuery
from promo.shared.config import AppConfig, DatabaseConfig, RetentionConfig, StorageConfig, WebConfig
from promo.shared.contracts.audit import RunDetailAuditDTO, RunSummaryAuditDTO
from promo.shared.contracts.logs import SystemLogDTO
from promo.shared.contracts.runs import RunDTO
from promo.shared.contracts.users import PermissionDTO, RoleDTO, UserDTO, UserPermissionDTO
from promo.shared.db import build_engine
from promo.shared.enums import RoleCode
from promo.shared.persistence.http import build_http_controllers
from promo.shared.persistence.repositories import RunDetailAuditRepository, RunFileRepository, RunRepository, RunSummaryAuditRepository, SystemLogRepository
from promo.shared.persistence.wiring import build_app_context, create_schema
from promo.stores.presentation import StoreCreateForm
from promo.shared.enums import MarketplaceCode


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        app_name="promo-db-read-test",
        environment="test",
        timezone="UTC",
        database=DatabaseConfig(dsn=f"sqlite+pysqlite:///{tmp_path / 'promo-db-read.sqlite3'}"),
        storage=StorageConfig(root_path=tmp_path / "storage"),
        retention=RetentionConfig(),
        log_level="INFO",
        web=WebConfig(auto_create_schema=False),
    )


def _seed_reference_data(app_context) -> None:
    with app_context.request_scope(commit=True) as bundle:
        bundle.uow.repositories.roles.add(RoleDTO(id=1, code=RoleCode.ADMIN.value, name="Администратор"))
        bundle.uow.repositories.roles.add(RoleDTO(id=2, code=RoleCode.MANAGER.value, name="Менеджер"))
        bundle.uow.repositories.permissions.add(PermissionDTO(id=1, code="create_store", name="create_store"))
        bundle.uow.repositories.permissions.add(PermissionDTO(id=2, code="edit_store", name="edit_store"))
        bundle.uow.repositories.users.add(
            UserDTO(
                id=1,
                username="admin",
                password_hash=app_context.password_hasher.hash_password("admin-pass"),
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
                password_hash=app_context.password_hasher.hash_password("manager-pass"),
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


def test_history_logs_and_audit_use_db_side_query_adapters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config(tmp_path)
    engine = build_engine(config.database.dsn)
    create_schema(engine)
    app = build_app_context(config, clock=lambda: _dt("2026-04-07T12:00:00+00:00"))
    controllers = build_http_controllers(app)
    _seed_reference_data(app)

    admin_session = controllers.auth.login(LoginForm(username="admin", password="admin-pass"))
    with app.request_scope() as bundle:
        admin_context = bundle.auth.current_session_context(admin_session.session_token)
    store = controllers.stores.create_store(
        admin_context,
        StoreCreateForm(name="VitalEmb", marketplace=MarketplaceCode.WB, wb_threshold_percent=60, wb_fallback_no_promo_percent=40, wb_fallback_over_threshold_percent=25),
    )
    controllers.access.grant_user_store_access(admin_context, user_id=2, store_id=store.id)

    with app.request_scope(commit=True) as bundle:
        started_at = _dt("2026-04-07T11:00:00+00:00")
        run = bundle.uow.repositories.runs.add(
            RunDTO(
                id=1,
                public_run_number="RUN-000001",
                store_id=store.id,
                initiated_by_user_id=2,
                operation_type="process",
                lifecycle_status="completed",
                business_result="completed",
                module_code="wb",
                input_set_signature="sig-1",
                started_at_utc=started_at,
                finished_at_utc=started_at + timedelta(minutes=1),
                short_result_text="process ok",
                result_file_id=None,
                validation_was_auto_before_process=True,
                created_at_utc=started_at,
                updated_at_utc=started_at + timedelta(minutes=1),
            )
        )
        bundle.uow.repositories.run_summary_audits.add(
            RunSummaryAuditDTO(id=1, run_id=run.id, audit_json={"run_id": run.id}, created_at_utc=started_at + timedelta(minutes=1))
        )
        bundle.uow.repositories.run_detail_audits.add(
            RunDetailAuditDTO(
                id=1,
                run_id=run.id,
                row_number=7,
                entity_key_1="sku-7",
                entity_key_2=None,
                severity="warning",
                decision_reason="price_adjusted",
                message="detail row seven",
                audit_payload_json={"row_number": 7},
                created_at_utc=started_at + timedelta(minutes=1),
            )
        )
        bundle.uow.repositories.logs.add(
            SystemLogDTO(
                id=100,
                event_time_utc=started_at + timedelta(minutes=1),
                user_id=2,
                store_id=store.id,
                run_id=run.id,
                module_code="wb",
                event_type="process_finished",
                severity="info",
                message="process finished",
                payload_json={"business_result": "completed"},
            )
        )

    manager_session = controllers.auth.login(LoginForm(username="manager", password="manager-pass"))
    with app.request_scope() as bundle:
        manager_context = bundle.auth.current_session_context(manager_session.session_token)

    def _explode_list(self):
        raise AssertionError("Repository.list() should not be used on DB-backed read-side")

    monkeypatch.setattr(RunRepository, "list", _explode_list)
    monkeypatch.setattr(RunFileRepository, "list", _explode_list)
    monkeypatch.setattr(RunSummaryAuditRepository, "list", _explode_list)
    monkeypatch.setattr(RunDetailAuditRepository, "list", _explode_list)
    monkeypatch.setattr(SystemLogRepository, "list", _explode_list)

    history = controllers.history.list_history(
        manager_context,
        HistoryQuery(page=1, page_size=25, search="VitalEmb", sort_field="started_at_utc", descending=True),
    )
    assert history.total_items == 1
    assert history.items[0].public_run_number == "RUN-000001"

    logs = controllers.logs.list_logs(
        admin_context,
        LogsQuery(page=1, page_size=25, search="RUN-000001", sort_field="event_time_utc", descending=False),
    )
    assert logs.total_items >= 1
    assert any(item.public_run_number == "RUN-000001" for item in logs.items)

    detail = controllers.audit.list_detail(
        manager_context,
        1,
        DetailAuditQuery(page=1, page_size=25, search="seven", sort_field="row_number", descending=False),
    )
    assert detail.total_items == 1
    assert detail.items[0].row_number == 7

    run_page = controllers.audit.get_run_page(
        manager_context,
        1,
        DetailAuditQuery(page=1, page_size=25, severity="warning", sort_field="row_number", descending=False),
    )
    assert run_page.run.public_run_number == "RUN-000001"
    assert run_page.detail_audit.total_items == 1
