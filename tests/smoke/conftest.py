from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from promo.runs.service import SkeletonRunExecutionStrategy
from promo.shared.config import AppConfig, DatabaseConfig, RetentionConfig, RuntimeConfig, StorageConfig, WebConfig
from promo.shared.contracts.users import PermissionDTO, RoleDTO, UserDTO, UserPermissionDTO
from promo.shared.enums import MarketplaceCode, ModuleCode, RoleCode
from promo.shared.persistence.wiring import build_app_context
from promo.presentation.app import create_app
from promo.presentation.ui import SESSION_COOKIE_NAME


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        app_name="promo-web-test",
        environment="test",
        timezone="UTC",
        database=DatabaseConfig(dsn=f"sqlite+pysqlite:///{tmp_path / 'promo-web.sqlite3'}"),
        storage=StorageConfig(root_path=tmp_path / "storage"),
        retention=RetentionConfig(),
        runtime=RuntimeConfig(
            autonomous_runtime_enabled=True,
            autonomous_maintenance_enabled=True,
            maintenance_interval_seconds=0.1,
        ),
        log_level="INFO",
        web=WebConfig(auto_create_schema=True),
    )


def _seed(app_context) -> None:
    hasher = app_context.password_hasher
    with app_context.request_scope(commit=True) as bundle:
        bundle.uow.repositories.roles.add(RoleDTO(id=1, code=RoleCode.ADMIN.value, name="Администратор"))
        bundle.uow.repositories.roles.add(RoleDTO(id=2, code=RoleCode.MANAGER_LEAD.value, name="Управляющий"))
        bundle.uow.repositories.roles.add(RoleDTO(id=3, code=RoleCode.MANAGER.value, name="Менеджер"))
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
                role_id=3,
                is_blocked=False,
                created_at_utc=_dt("2026-04-07T10:00:00+00:00"),
                updated_at_utc=_dt("2026-04-07T10:00:00+00:00"),
                last_login_at_utc=None,
            )
        )
        bundle.uow.repositories.users.add(
            UserDTO(
                id=3,
                username="blocked-manager",
                password_hash=hasher.hash_password("blocked-pass"),
                role_id=3,
                is_blocked=True,
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


@dataclass(slots=True)
class AppHarness:
    client: TestClient
    app_context: object
    internal_operations: object

    def login_response(self, username: str, password: str):
        return self.client.post("/api/auth/login", json={"username": username, "password": password})

    def login(self, username: str, password: str) -> str:
        response = self.login_response(username, password)
        assert response.status_code == 200
        return response.json()["session_token"]

    def headers(self, session_token: str) -> dict[str, str]:
        return {"X-Session-Token": session_token}

    def use_ui_session(self, session_token: str) -> None:
        self.client.cookies.set(SESSION_COOKIE_NAME, session_token)

    def session_context(self, session_token: str):
        with self.app_context.request_scope() as bundle:
            return bundle.auth.current_session_context(session_token)

    def grant_store_access(self, session_token: str, user_id: int, store_id: int) -> None:
        response = self.client.post(
            f"/api/access/users/{user_id}/stores/{store_id}",
            headers=self.headers(session_token),
        )
        assert response.status_code == 200

    def internal_drain_runs(self, limit: int | None = None) -> int:
        return self.internal_operations.worker_runs.drain_pending(limit)

    def wait_for_run_completion(
        self,
        session_token: str,
        run_id: int,
        *,
        timeout_seconds: float = 3.0,
        poll_interval_seconds: float = 0.05,
    ) -> dict[str, object]:
        deadline = time.monotonic() + timeout_seconds
        last_payload: dict[str, object] | None = None
        while time.monotonic() < deadline:
            response = self.client.get(
                f"/api/runs/{run_id}/status",
                headers=self.headers(session_token),
            )
            assert response.status_code == 200
            last_payload = response.json()
            if last_payload["lifecycle_status"] in {"completed", "failed"}:
                return last_payload
            time.sleep(poll_interval_seconds)
        raise AssertionError(f"run {run_id} did not reach terminal state within {timeout_seconds} seconds; last_payload={last_payload}")

    def mark_run_file_superseded(self, run_file_id: int) -> None:
        self.internal_operations.worker_runs.supersede_run_file(run_file_id)

    def expire_run_files(self):
        return self.internal_operations.maintenance.expire_run_files()

    def purge_temporary_files(self):
        return self.internal_operations.maintenance.purge_temporary_files()

    def create_store(
        self,
        session_token: str,
        *,
        name: str,
        marketplace: str,
        wb_threshold_percent: int | None = None,
        wb_fallback_no_promo_percent: int | None = None,
        wb_fallback_over_threshold_percent: int | None = None,
    ) -> dict[str, object]:
        response = self.client.post(
            "/api/stores",
            headers=self.headers(session_token),
            json={
                "name": name,
                "marketplace": marketplace,
                "wb_threshold_percent": wb_threshold_percent,
                "wb_fallback_no_promo_percent": wb_fallback_no_promo_percent,
                "wb_fallback_over_threshold_percent": wb_fallback_over_threshold_percent,
            },
        )
        assert response.status_code == 200
        return response.json()

    def upload_temp_file(
        self,
        session_token: str,
        *,
        store_id: int,
        module_code: ModuleCode,
        original_filename: str,
        content: bytes,
        mime_type: str = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        wb_file_kind: str | None = None,
    ):
        return self.client.post(
            f"/api/temp-files?store_id={store_id}&module_code={module_code.value}",
            headers=self.headers(session_token),
            json={
                "original_filename": original_filename,
                "content_base64": base64.b64encode(content).decode("utf-8"),
                "mime_type": mime_type,
                "wb_file_kind": wb_file_kind,
            },
        )


@pytest.fixture
def app_harness(tmp_path: Path) -> AppHarness:
    return _build_harness(tmp_path, use_marketplace_strategy=False)


@pytest.fixture
def marketplace_app_harness(tmp_path: Path) -> AppHarness:
    return _build_harness(tmp_path, use_marketplace_strategy=True)


@pytest.fixture
def autonomous_app_harness(tmp_path: Path) -> AppHarness:
    return _build_harness(tmp_path, use_marketplace_strategy=False, autostart_runtime=True)


@pytest.fixture
def autonomous_maintenance_app_harness(tmp_path: Path) -> AppHarness:
    return _build_harness(tmp_path, use_marketplace_strategy=False, autostart_maintenance=True)


def _build_harness(
    tmp_path: Path,
    *,
    use_marketplace_strategy: bool,
    autostart_runtime: bool = False,
    autostart_maintenance: bool = False,
) -> AppHarness:
    config = _config(tmp_path)
    kwargs = {"clock": lambda: _dt("2026-04-07T12:00:00+00:00")}
    if not use_marketplace_strategy:
        kwargs["execution_strategy_factory"] = lambda storage: SkeletonRunExecutionStrategy()
    app_context = build_app_context(config, **kwargs)
    app = create_app(
        config,
        app_context=app_context,
        autonomous_runtime=autostart_runtime,
        autonomous_maintenance=autostart_maintenance,
    )
    _seed(app_context)
    return AppHarness(
        client=TestClient(app),
        app_context=app_context,
        internal_operations=app.state.internal_operations,
    )


def _workbook_bytes(builder) -> bytes:
    workbook = Workbook()
    builder(workbook)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def wb_price_bytes() -> bytes:
    def _build(workbook: Workbook) -> None:
        sheet = workbook.active
        sheet.title = "Price"
        sheet.append(["Артикул WB", "Текущая цена", "Новая скидка"])
        sheet.append(["1001", 1000, None])
        sheet.append(["1002", 500, None])

    return _workbook_bytes(_build)


@pytest.fixture
def wb_promo_bytes() -> bytes:
    def _build(workbook: Workbook) -> None:
        sheet = workbook.active
        sheet.title = "Promo"
        sheet.append(["Артикул WB", "Плановая цена для акции", "Загружаемая скидка для участия в акции"])
        sheet.append(["1001", 850, 20])
        sheet.append(["1002", 300, 40])

    return _workbook_bytes(_build)


@pytest.fixture
def ozon_workbook_bytes() -> bytes:
    def _build(workbook: Workbook) -> None:
        sheet = workbook.active
        sheet.title = "Товары и цены"
        sheet["J2"] = "Минимальная цена"
        sheet["K2"] = "Участвуем в акции"
        sheet["L2"] = "Цена для акции"
        sheet["O2"] = "Цена до скидки"
        sheet["P2"] = "Цена с max скидкой"
        sheet["R2"] = "Остаток"
        sheet["A4"] = "sku-1"
        sheet["J4"] = 700
        sheet["O4"] = 900
        sheet["P4"] = 650
        sheet["R4"] = 4

    return _workbook_bytes(_build)
