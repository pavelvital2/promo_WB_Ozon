from __future__ import annotations

import base64
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from promo.shared.config import AppConfig, DatabaseConfig, RetentionConfig, StorageConfig, WebConfig
from promo.shared.contracts.users import PermissionDTO, RoleDTO, UserDTO, UserPermissionDTO
from promo.shared.db import build_engine
from promo.shared.enums import RoleCode
from promo.shared.persistence.wiring import build_app_context, create_schema
from promo.presentation.app import create_app
from promo.stores.presentation import StoreCreateForm
from promo.shared.enums import MarketplaceCode


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        app_name="promo-workbook-safety-test",
        environment="test",
        timezone="UTC",
        database=DatabaseConfig(dsn=f"sqlite+pysqlite:///{tmp_path / 'promo-workbook-safety.sqlite3'}"),
        storage=StorageConfig(root_path=tmp_path / "storage"),
        retention=RetentionConfig(),
        log_level="INFO",
        web=WebConfig(auto_create_schema=False),
    )


def _seed(app_context) -> None:
    hasher = app_context.password_hasher
    with app_context.request_scope(commit=True) as bundle:
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


def _build_system(tmp_path: Path):
    config = _config(tmp_path)
    engine = build_engine(config.database.dsn)
    create_schema(engine)
    app_context = build_app_context(
        config,
        clock=lambda: _dt("2026-04-07T12:00:00+00:00"),
    )
    _seed(app_context)
    app = create_app(config, app_context=app_context)
    return app_context, app, TestClient(app)


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["session_token"]


def _headers(session_token: str) -> dict[str, str]:
    return {"X-Session-Token": session_token}


def _wb_price_with_formula() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Price"
    sheet.append(["Артикул WB", "Текущая цена", "Новая скидка"])
    sheet.append(["1001", 1000, "=1+1"])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _wb_promo() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Promo"
    sheet.append(["Артикул WB", "Плановая цена для акции", "Загружаемая скидка для участия в акции"])
    sheet.append(["1001", 850, 20])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_wb_process_reports_controlled_failure_for_unsafe_save_workbook(tmp_path: Path) -> None:
    app_context, app, client = _build_system(tmp_path)

    admin_token = _login(client, "admin", "admin-pass")
    manager_token = _login(client, "manager", "manager-pass")

    with app_context.request_scope(commit=True) as bundle:
        admin_context = bundle.auth.current_session_context(admin_token)
        store = bundle.stores.create_store(
            admin_context,
            StoreCreateForm(
                name="WBSafety",
                marketplace=MarketplaceCode.WB,
                wb_threshold_percent=60,
                wb_fallback_no_promo_percent=40,
                wb_fallback_over_threshold_percent=25,
            ),
        )
        bundle.access.grant_user_store_access(admin_context, user_id=2, store_id=store.id)

    assert client.post(
        f"/api/temp-files?store_id={store.id}&module_code=wb",
        headers=_headers(manager_token),
        json={
            "original_filename": "price.xlsx",
            "content_base64": base64.b64encode(_wb_price_with_formula()).decode("utf-8"),
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "wb_file_kind": "price",
        },
    ).status_code == 200
    assert client.post(
        f"/api/temp-files?store_id={store.id}&module_code=wb",
        headers=_headers(manager_token),
        json={
            "original_filename": "promo.xlsx",
            "content_base64": base64.b64encode(_wb_promo()).decode("utf-8"),
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "wb_file_kind": "promo",
        },
    ).status_code == 200

    run_response = client.post(
        "/api/runs/process",
        headers=_headers(manager_token),
        json={"store_id": store.id},
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["id"]

    assert app.state.internal_operations.worker_runs.drain_pending(limit=1) == 1
    assert app.state.internal_operations.worker_runs.drain_pending(limit=1) == 1

    status_response = client.get(f"/api/runs/{run_id}/status", headers=_headers(manager_token))
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["lifecycle_status"] == "failed"
    assert payload["business_result"] == "validation_failed"
    assert "cannot be saved safely" in payload["short_result_text"]
