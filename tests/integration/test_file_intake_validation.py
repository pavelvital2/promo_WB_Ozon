from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from promo.runs.service import SkeletonRunExecutionStrategy
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
        app_name="promo-file-intake-test",
        environment="test",
        timezone="UTC",
        database=DatabaseConfig(dsn=f"sqlite+pysqlite:///{tmp_path / 'promo-file-intake.sqlite3'}"),
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
        execution_strategy_factory=lambda storage: SkeletonRunExecutionStrategy(),
    )
    _seed(app_context)
    app = create_app(config, app_context=app_context)
    return app_context, TestClient(app)


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["session_token"]


def _headers(session_token: str) -> dict[str, str]:
    return {"X-Session-Token": session_token}


def test_wb_run_creation_rejects_missing_price_file_via_http_surface(tmp_path: Path) -> None:
    app_context, client = _build_system(tmp_path)

    admin_token = _login(client, "admin", "admin-pass")
    manager_token = _login(client, "manager", "manager-pass")

    with app_context.request_scope(commit=True) as bundle:
        admin_context = bundle.auth.current_session_context(admin_token)
        store = bundle.stores.create_store(
            admin_context,
            StoreCreateForm(
                name="WBComposition",
                marketplace=MarketplaceCode.WB,
                wb_threshold_percent=60,
                wb_fallback_no_promo_percent=40,
                wb_fallback_over_threshold_percent=25,
            ),
        )
        bundle.access.grant_user_store_access(admin_context, user_id=2, store_id=store.id)

    upload = client.post(
        f"/api/temp-files?store_id={store.id}&module_code=wb",
        headers=_headers(manager_token),
        json={
            "original_filename": "promo.xlsx",
            "content_base64": base64.b64encode(b"promo").decode("utf-8"),
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "wb_file_kind": "promo",
        },
    )
    assert upload.status_code == 200

    run = client.post(
        "/api/runs/check",
        headers=_headers(manager_token),
        json={"store_id": store.id},
    )
    assert run.status_code == 400
    payload = run.json()
    assert payload["error_code"] == "file_limit_exceeded"
    assert payload["details"]["price_file_count"] == 0
    assert payload["details"]["promo_file_count"] == 1
