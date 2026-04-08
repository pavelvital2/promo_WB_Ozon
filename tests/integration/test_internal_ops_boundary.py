from __future__ import annotations

import base64
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from promo.auth.presentation import LoginForm
from promo.runs.service import (
    OLD_RESULT_REMOVED_ON_NEW_SUCCESS_EVENT,
    PROCESS_FINISHED_EVENT,
    PROCESS_STARTED_EVENT,
    SkeletonRunExecutionStrategy,
)
from promo.shared.config import AppConfig, DatabaseConfig, RetentionConfig, RuntimeConfig, StorageConfig, WebConfig
from promo.shared.contracts.users import PermissionDTO, RoleDTO, UserDTO, UserPermissionDTO
from promo.shared.db import build_engine
from promo.shared.enums import MarketplaceCode, ModuleCode, RoleCode
from promo.shared.persistence.wiring import build_app_context, create_schema
from promo.presentation.app import create_app
from promo.shared.persistence.http import build_internal_controllers
from promo.runs.service import RunService
from promo.stores.presentation import StoreCreateForm
from promo.system_maintenance.retention import RUN_FILES_RETENTION_APPLIED_EVENT, TEMPORARY_FILES_AUTO_PURGED_EVENT


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        app_name="promo-integration-test",
        environment="test",
        timezone="UTC",
        database=DatabaseConfig(dsn=f"sqlite+pysqlite:///{tmp_path / 'promo-integration.sqlite3'}"),
        storage=StorageConfig(root_path=tmp_path / "storage"),
        retention=RetentionConfig(),
        runtime=RuntimeConfig(
            autonomous_runtime_enabled=True,
            autonomous_maintenance_enabled=True,
            maintenance_interval_seconds=0.1,
        ),
        log_level="INFO",
        web=WebConfig(auto_create_schema=False),
    )


def _workbook_bytes(builder) -> bytes:
    workbook = Workbook()
    builder(workbook)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _wb_price_bytes() -> bytes:
    def _build(workbook: Workbook) -> None:
        sheet = workbook.active
        sheet.title = "Price"
        sheet.append(["Артикул WB", "Текущая цена", "Новая скидка"])
        sheet.append(["1001", 1000, None])

    return _workbook_bytes(_build)


def _wb_promo_bytes() -> bytes:
    def _build(workbook: Workbook) -> None:
        sheet = workbook.active
        sheet.title = "Promo"
        sheet.append(["Артикул WB", "Плановая цена для акции", "Загружаемая скидка для участия в акции"])
        sheet.append(["1001", 850, 15])

    return _workbook_bytes(_build)


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


def _build_system(tmp_path: Path, *, use_marketplace_strategy: bool = False):
    config = _config(tmp_path)
    engine = build_engine(config.database.dsn)
    create_schema(engine)
    kwargs = {"clock": lambda: _dt("2026-04-07T12:00:00+00:00")}
    if not use_marketplace_strategy:
        kwargs["execution_strategy_factory"] = lambda storage: SkeletonRunExecutionStrategy()
    app_context = build_app_context(config, **kwargs)
    _seed(app_context)
    app = create_app(config, app_context=app_context)
    return app_context, app, TestClient(app)


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["session_token"]


def _headers(session_token: str) -> dict[str, str]:
    return {"X-Session-Token": session_token}


def _wait_for_terminal_status(client: TestClient, session_token: str, run_id: int, *, timeout_seconds: float = 3.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    last_payload: dict[str, object] | None = None
    while time.monotonic() < deadline:
        response = client.get(f"/api/runs/{run_id}/status", headers=_headers(session_token))
        assert response.status_code == 200
        last_payload = response.json()
        if last_payload["lifecycle_status"] in {"completed", "failed"}:
            return last_payload
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} did not reach terminal state within {timeout_seconds} seconds; last_payload={last_payload}")


def test_internal_worker_registry_executes_runs_while_public_ops_routes_stay_closed(tmp_path: Path) -> None:
    app_context, app, client = _build_system(tmp_path)
    internal = build_internal_controllers(app_context)

    admin_token = _login(client, "admin", "admin-pass")
    manager_token = _login(client, "manager", "manager-pass")

    with app_context.request_scope(commit=True) as bundle:
        admin_session = bundle.auth.current_session_context(admin_token)
        store = bundle.stores.create_store(
            admin_session,
            StoreCreateForm(name="BoundaryOzon", marketplace=MarketplaceCode.OZON),
        )
        bundle.access.grant_user_store_access(admin_session, user_id=2, store_id=store.id)

    upload = client.post(
        f"/api/temp-files?store_id={store.id}&module_code=ozon",
        headers=_headers(manager_token),
        json={
            "original_filename": "ozon.xlsx",
            "content_base64": base64.b64encode(b"ozon-bytes").decode("utf-8"),
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
    )
    assert upload.status_code == 200

    run_response = client.post(
        "/api/runs/check",
        headers=_headers(manager_token),
        json={"store_id": store.id},
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["id"]

    assert client.post("/internal/runs/drain").status_code == 404
    assert internal.worker_runs.drain_pending() == 1

    status_response = client.get(f"/api/runs/{run_id}/status", headers=_headers(manager_token))
    assert status_response.status_code == 200
    assert status_response.json()["lifecycle_status"] == "completed"
    assert status_response.json()["business_result"] == "check_passed"
    assert not hasattr(app.state.controllers.runs, "drain_pending")


def test_autonomous_runtime_executes_runs_without_manual_drain(tmp_path: Path) -> None:
    config = _config(tmp_path)
    engine = build_engine(config.database.dsn)
    create_schema(engine)
    app_context = build_app_context(
        config,
        clock=lambda: _dt("2026-04-07T12:00:00+00:00"),
        execution_strategy_factory=lambda storage: SkeletonRunExecutionStrategy(),
    )
    _seed(app_context)
    app = create_app(config, app_context=app_context, autonomous_runtime=True)
    client = TestClient(app)

    admin_token = _login(client, "admin", "admin-pass")
    manager_token = _login(client, "manager", "manager-pass")

    with app_context.request_scope(commit=True) as bundle:
        admin_session = bundle.auth.current_session_context(admin_token)
        store = bundle.stores.create_store(
            admin_session,
            StoreCreateForm(name="AutonomousOzon", marketplace=MarketplaceCode.OZON),
        )
        bundle.access.grant_user_store_access(admin_session, user_id=2, store_id=store.id)

    upload = client.post(
        f"/api/temp-files?store_id={store.id}&module_code=ozon",
        headers=_headers(manager_token),
        json={
            "original_filename": "ozon.xlsx",
            "content_base64": base64.b64encode(b"ozon-bytes").decode("utf-8"),
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
    )
    assert upload.status_code == 200

    run_response = client.post(
        "/api/runs/check",
        headers=_headers(manager_token),
        json={"store_id": store.id},
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["id"]

    final_status = _wait_for_terminal_status(client, manager_token, run_id)
    assert final_status["lifecycle_status"] == "completed"
    assert final_status["business_result"] == "check_passed"
    assert app.state.run_worker_runtime.is_running() is True


def test_autonomous_runtime_processes_multiple_jobs_without_manual_drain(tmp_path: Path) -> None:
    config = _config(tmp_path)
    engine = build_engine(config.database.dsn)
    create_schema(engine)
    app_context = build_app_context(
        config,
        clock=lambda: _dt("2026-04-07T12:00:00+00:00"),
        execution_strategy_factory=lambda storage: SkeletonRunExecutionStrategy(),
    )
    _seed(app_context)
    app = create_app(config, app_context=app_context, autonomous_runtime=True)
    client = TestClient(app)

    admin_token = _login(client, "admin", "admin-pass")
    manager_token = _login(client, "manager", "manager-pass")

    store_ids: list[int] = []
    with app_context.request_scope(commit=True) as bundle:
        admin_session = bundle.auth.current_session_context(admin_token)
        for name in ("AutoMultiOzon1", "AutoMultiOzon2"):
            store = bundle.stores.create_store(
                admin_session,
                StoreCreateForm(name=name, marketplace=MarketplaceCode.OZON),
            )
            bundle.access.grant_user_store_access(admin_session, user_id=2, store_id=store.id)
            store_ids.append(store.id)

    run_ids: list[int] = []
    for store_id in store_ids:
        upload = client.post(
            f"/api/temp-files?store_id={store_id}&module_code=ozon",
            headers=_headers(manager_token),
            json={
                "original_filename": f"ozon-{store_id}.xlsx",
                "content_base64": base64.b64encode(f"ozon-{store_id}".encode("utf-8")).decode("utf-8"),
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            },
        )
        assert upload.status_code == 200
        run_response = client.post(
            "/api/runs/check",
            headers=_headers(manager_token),
            json={"store_id": store_id},
        )
        assert run_response.status_code == 200
        run_ids.append(run_response.json()["id"])

    final_statuses = [_wait_for_terminal_status(client, manager_token, run_id) for run_id in run_ids]
    assert [item["lifecycle_status"] for item in final_statuses] == ["completed", "completed"]
    assert [item["business_result"] for item in final_statuses] == ["check_passed", "check_passed"]
    assert app.state.run_worker_runtime.is_running() is True


def test_autonomous_runtime_survives_unexpected_job_exception_and_processes_next_job(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    engine = build_engine(config.database.dsn)
    create_schema(engine)
    app_context = build_app_context(
        config,
        clock=lambda: _dt("2026-04-07T12:00:00+00:00"),
        execution_strategy_factory=lambda storage: SkeletonRunExecutionStrategy(),
    )
    _seed(app_context)

    original_execute_run = RunService.execute_run
    state = {"failed_run_id": None}

    def flaky_execute_run(self, run_id: int, phase: str | None = None):
        if state["failed_run_id"] is None:
            state["failed_run_id"] = run_id
            raise RuntimeError("boom")
        return original_execute_run(self, run_id, phase=phase)

    monkeypatch.setattr(RunService, "execute_run", flaky_execute_run)
    app = create_app(config, app_context=app_context, autonomous_runtime=True)
    client = TestClient(app)

    admin_token = _login(client, "admin", "admin-pass")
    manager_token = _login(client, "manager", "manager-pass")

    store_ids: list[int] = []
    with app_context.request_scope(commit=True) as bundle:
        admin_session = bundle.auth.current_session_context(admin_token)
        for name in ("RuntimeFailure1", "RuntimeFailure2"):
            store = bundle.stores.create_store(
                admin_session,
                StoreCreateForm(name=name, marketplace=MarketplaceCode.OZON),
            )
            bundle.access.grant_user_store_access(admin_session, user_id=2, store_id=store.id)
            store_ids.append(store.id)

    run_ids: list[int] = []
    for store_id in store_ids:
        upload = client.post(
            f"/api/temp-files?store_id={store_id}&module_code=ozon",
            headers=_headers(manager_token),
            json={
                "original_filename": f"ozon-{store_id}.xlsx",
                "content_base64": base64.b64encode(f"ozon-{store_id}".encode("utf-8")).decode("utf-8"),
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            },
        )
        assert upload.status_code == 200
        run_response = client.post(
            "/api/runs/check",
            headers=_headers(manager_token),
            json={"store_id": store_id},
        )
        assert run_response.status_code == 200
        run_ids.append(run_response.json()["id"])

    first_status = _wait_for_terminal_status(client, manager_token, run_ids[0])
    second_status = _wait_for_terminal_status(client, manager_token, run_ids[1])
    assert first_status["lifecycle_status"] == "failed"
    assert first_status["business_result"] == "check_failed"
    assert second_status["lifecycle_status"] == "completed"
    assert second_status["business_result"] == "check_passed"
    assert app.state.run_worker_runtime.is_running() is True

    logs = client.get(
        "/api/logs?page=1&page_size=50&event_type=system_error",
        headers=_headers(admin_token),
    )
    assert logs.status_code == 200
    assert sum(1 for item in logs.json()["items"] if item["payload_json"]["runtime_component"] == "run_worker") >= 1


def test_internal_maintenance_registry_expires_run_files_and_purges_temp_files(tmp_path: Path) -> None:
    app_context, _, client = _build_system(tmp_path)
    internal = build_internal_controllers(app_context)

    admin_token = _login(client, "admin", "admin-pass")
    manager_token = _login(client, "manager", "manager-pass")

    with app_context.request_scope(commit=True) as bundle:
        admin_session = bundle.auth.current_session_context(admin_token)
        store = bundle.stores.create_store(
            admin_session,
            StoreCreateForm(name="MaintenanceOzon", marketplace=MarketplaceCode.OZON),
        )
        bundle.access.grant_user_store_access(admin_session, user_id=2, store_id=store.id)

    upload = client.post(
        f"/api/temp-files?store_id={store.id}&module_code=ozon",
        headers=_headers(manager_token),
        json={
            "original_filename": "ozon.xlsx",
            "content_base64": base64.b64encode(b"ozon-bytes").decode("utf-8"),
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
    )
    assert upload.status_code == 200
    temp_file_id = upload.json()["id"]

    with app_context.request_scope(commit=True) as bundle:
        temp_file = bundle.uow.repositories.temporary_files.get(temp_file_id)
        assert temp_file is not None
        temp_path = app_context.file_storage.root_path / temp_file.storage_relative_path
        bundle.uow.repositories.temporary_files.update(
            replace(temp_file, expires_at_utc=temp_file.created_at_utc - timedelta(hours=1))
        )

    purge_outcome = internal.maintenance.purge_temporary_files()
    assert purge_outcome.task_name == "purge_temporary_files"
    assert purge_outcome.affected_rows == 1
    assert TEMPORARY_FILES_AUTO_PURGED_EVENT in purge_outcome.event_types
    assert not temp_path.exists()

    with app_context.request_scope() as bundle:
        logs = bundle.uow.repositories.logs.list()
        temp_cleanup_logs = [item for item in logs if item.event_type == TEMPORARY_FILES_AUTO_PURGED_EVENT]
        assert len(temp_cleanup_logs) == 1
        assert temp_cleanup_logs[0].store_id == store.id
        assert temp_cleanup_logs[0].module_code == ModuleCode.OZON.value
        assert temp_cleanup_logs[0].payload_json is not None
        assert temp_cleanup_logs[0].payload_json["file_metadata_id"] == str(temp_file_id)
        assert temp_cleanup_logs[0].payload_json["storage_path"] == temp_file.storage_relative_path
        assert temp_cleanup_logs[0].payload_json["reason"] == "expired"
        assert temp_cleanup_logs[0].payload_json["cleanup_scope"] == "temporary_files_retention"

    reupload = client.post(
        f"/api/temp-files?store_id={store.id}&module_code=ozon",
        headers=_headers(manager_token),
        json={
            "original_filename": "ozon.xlsx",
            "content_base64": base64.b64encode(b"ozon-bytes").decode("utf-8"),
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
    )
    assert reupload.status_code == 200

    run_response = client.post(
        "/api/runs/check",
        headers=_headers(manager_token),
        json={"store_id": store.id},
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["id"]
    assert internal.worker_runs.drain_pending() == 1

    with app_context.request_scope(commit=True) as bundle:
        run_files = [item for item in bundle.uow.repositories.run_files.list() if item.run_id == run_id]
        assert len(run_files) == 1
        run_file = run_files[0]
        bundle.uow.repositories.run_files.update(
            replace(run_file, expires_at_utc=run_file.created_at_utc - timedelta(days=1))
        )

    expire_outcome = internal.maintenance.expire_run_files()
    assert expire_outcome.task_name == "expire_run_files"
    assert expire_outcome.affected_rows == 1
    assert RUN_FILES_RETENTION_APPLIED_EVENT in expire_outcome.event_types

    with app_context.request_scope() as bundle:
        logs = bundle.uow.repositories.logs.list()
        run_cleanup_logs = [item for item in logs if item.event_type == RUN_FILES_RETENTION_APPLIED_EVENT]
        assert len(run_cleanup_logs) == 1
        assert run_cleanup_logs[0].run_id == run_id
        assert run_cleanup_logs[0].payload_json is not None
        assert run_cleanup_logs[0].payload_json["file_metadata_id"] == str(run_file.id)
        assert run_cleanup_logs[0].payload_json["storage_path"] == run_file.storage_relative_path
        assert run_cleanup_logs[0].payload_json["reason"] == "expired"
        assert run_cleanup_logs[0].payload_json["cleanup_scope"] == "run_files_retention"

    download = client.get(
        f"/api/run-files/{run_file.id}/download",
        headers=_headers(manager_token),
    )
    assert download.status_code == 410


def test_second_successful_process_supersedes_old_result_and_persists_log(tmp_path: Path) -> None:
    app_context, _, client = _build_system(tmp_path, use_marketplace_strategy=True)
    internal = build_internal_controllers(app_context)

    admin_token = _login(client, "admin", "admin-pass")
    manager_token = _login(client, "manager", "manager-pass")

    with app_context.request_scope(commit=True) as bundle:
        admin_session = bundle.auth.current_session_context(admin_token)
        store = bundle.stores.create_store(
            admin_session,
            StoreCreateForm(
                name="SupersedeWB",
                marketplace=MarketplaceCode.WB,
                wb_threshold_percent=60,
                wb_fallback_no_promo_percent=40,
                wb_fallback_over_threshold_percent=25,
            ),
        )
        bundle.access.grant_user_store_access(admin_session, user_id=2, store_id=store.id)

    for filename, wb_file_kind, content in (
        ("price.xlsx", "price", _wb_price_bytes()),
        ("promo.xlsx", "promo", _wb_promo_bytes()),
    ):
        upload = client.post(
            f"/api/temp-files?store_id={store.id}&module_code=wb",
            headers=_headers(manager_token),
            json={
                "original_filename": filename,
                "content_base64": base64.b64encode(content).decode("utf-8"),
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "wb_file_kind": wb_file_kind,
            },
        )
        assert upload.status_code == 200

    first_process = client.post(
        "/api/runs/process",
        headers=_headers(manager_token),
        json={"store_id": store.id},
    )
    assert first_process.status_code == 200
    assert internal.worker_runs.drain_pending() == 2

    first_run_page = client.get(
        f"/api/runs/{first_process.json()['id']}",
        headers=_headers(manager_token),
    )
    assert first_run_page.status_code == 200
    first_result_file = next(item for item in first_run_page.json()["files"] if item["file_role"] == "wb_result_output")
    assert first_run_page.json()["run"]["result_file_is_available"] is True

    second_process = client.post(
        "/api/runs/process",
        headers=_headers(manager_token),
        json={"store_id": store.id},
    )
    assert second_process.status_code == 200
    assert internal.worker_runs.drain_pending() == 2

    old_run_page = client.get(
        f"/api/runs/{first_process.json()['id']}",
        headers=_headers(manager_token),
    )
    assert old_run_page.status_code == 200
    assert old_run_page.json()["run"]["result_file_is_available"] is False
    assert old_run_page.json()["run"]["result_file_unavailable_reason"] == "superseded"

    denied_download = client.get(
        f"/api/run-files/{first_result_file['id']}/download",
        headers=_headers(manager_token),
    )
    assert denied_download.status_code == 410

    logs = client.get(
        "/api/logs?page=1&page_size=25&event_type=old_result_removed_on_new_success",
        headers=_headers(admin_token),
    )
    assert logs.status_code == 200
    supersede_logs = logs.json()["items"]
    assert len(supersede_logs) == 1
    assert supersede_logs[0]["event_type"] == OLD_RESULT_REMOVED_ON_NEW_SUCCESS_EVENT
    assert supersede_logs[0]["run_id"] == first_process.json()["id"]
    assert supersede_logs[0]["payload_json"]["replacement_run_id"] == str(second_process.json()["id"])
    assert supersede_logs[0]["payload_json"]["reason"] == "superseded"

    lifecycle_logs = client.get(
        "/api/logs?page=1&page_size=50",
        headers=_headers(admin_token),
    )
    assert lifecycle_logs.status_code == 200
    lifecycle_event_types = [item["event_type"] for item in lifecycle_logs.json()["items"]]
    assert lifecycle_event_types.count(PROCESS_STARTED_EVENT) == 2
    assert lifecycle_event_types.count(PROCESS_FINISHED_EVENT) == 2
    assert "result_downloaded" not in lifecycle_event_types


def test_autonomous_maintenance_runtime_reconciles_timed_out_run_without_manual_invocation(tmp_path: Path) -> None:
    config = _config(tmp_path)
    engine = build_engine(config.database.dsn)
    create_schema(engine)
    app_context = build_app_context(
        config,
        clock=lambda: _dt("2026-04-07T12:00:00+00:00"),
        execution_strategy_factory=lambda storage: SkeletonRunExecutionStrategy(),
    )
    _seed(app_context)
    app = create_app(config, app_context=app_context, autonomous_runtime=False, autonomous_maintenance=True)
    client = TestClient(app)

    admin_token = _login(client, "admin", "admin-pass")
    manager_token = _login(client, "manager", "manager-pass")

    with app_context.request_scope(commit=True) as bundle:
        admin_session = bundle.auth.current_session_context(admin_token)
        store = bundle.stores.create_store(
            admin_session,
            StoreCreateForm(name="TimedOutOzon", marketplace=MarketplaceCode.OZON),
        )
        bundle.access.grant_user_store_access(admin_session, user_id=2, store_id=store.id)

    upload = client.post(
        f"/api/temp-files?store_id={store.id}&module_code=ozon",
        headers=_headers(manager_token),
        json={
            "original_filename": "ozon.xlsx",
            "content_base64": base64.b64encode(b"ozon-bytes").decode("utf-8"),
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
    )
    assert upload.status_code == 200

    run_response = client.post(
        "/api/runs/check",
        headers=_headers(manager_token),
        json={"store_id": store.id},
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["id"]

    with app_context.request_scope(commit=True) as bundle:
        run = bundle.uow.repositories.runs.get(run_id)
        assert run is not None
        bundle.uow.repositories.runs.update(
            replace(
                run,
                started_at_utc=_dt("2026-04-07T06:00:00+00:00"),
                updated_at_utc=_dt("2026-04-07T06:00:00+00:00"),
            )
        )

    final_status = _wait_for_terminal_status(client, manager_token, run_id)
    assert final_status["lifecycle_status"] == "failed"
    assert final_status["business_result"] == "check_failed"
    assert final_status["is_locked"] is False

    logs = client.get(
        "/api/logs?page=1&page_size=25&event_type=system_error&search=%s" % run_response.json()["public_run_number"],
        headers=_headers(admin_token),
    )
    assert logs.status_code == 200
    assert any(
        item["run_id"] == run_id and item["payload_json"]["maintenance_task"] == "timeout_reconciliation"
        for item in logs.json()["items"]
    )
    assert app.state.maintenance_runtime.is_running() is True


def test_autonomous_maintenance_survives_task_exception_and_continues_reconciliation(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    engine = build_engine(config.database.dsn)
    create_schema(engine)
    app_context = build_app_context(
        config,
        clock=lambda: _dt("2026-04-07T12:00:00+00:00"),
        execution_strategy_factory=lambda storage: SkeletonRunExecutionStrategy(),
    )
    _seed(app_context)

    from promo.system_maintenance import runtime as maintenance_runtime_module

    original_purge = maintenance_runtime_module.purge_temporary_files
    state = {"raised": False}

    def flaky_purge(*args, **kwargs):
        if not state["raised"]:
            state["raised"] = True
            raise RuntimeError("purge-boom")
        return original_purge(*args, **kwargs)

    monkeypatch.setattr(maintenance_runtime_module, "purge_temporary_files", flaky_purge)
    app = create_app(config, app_context=app_context, autonomous_runtime=False, autonomous_maintenance=True)
    client = TestClient(app)

    admin_token = _login(client, "admin", "admin-pass")
    manager_token = _login(client, "manager", "manager-pass")

    with app_context.request_scope(commit=True) as bundle:
        admin_session = bundle.auth.current_session_context(admin_token)
        store = bundle.stores.create_store(
            admin_session,
            StoreCreateForm(name="MaintFailureOzon", marketplace=MarketplaceCode.OZON),
        )
        bundle.access.grant_user_store_access(admin_session, user_id=2, store_id=store.id)

    upload = client.post(
        f"/api/temp-files?store_id={store.id}&module_code=ozon",
        headers=_headers(manager_token),
        json={
            "original_filename": "ozon.xlsx",
            "content_base64": base64.b64encode(b"ozon-bytes").decode("utf-8"),
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
    )
    assert upload.status_code == 200

    run_response = client.post(
        "/api/runs/check",
        headers=_headers(manager_token),
        json={"store_id": store.id},
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["id"]

    with app_context.request_scope(commit=True) as bundle:
        run = bundle.uow.repositories.runs.get(run_id)
        assert run is not None
        bundle.uow.repositories.runs.update(
            replace(
                run,
                started_at_utc=_dt("2026-04-07T06:00:00+00:00"),
                updated_at_utc=_dt("2026-04-07T06:00:00+00:00"),
            )
        )

    final_status = _wait_for_terminal_status(client, manager_token, run_id)
    assert final_status["lifecycle_status"] == "failed"
    assert final_status["business_result"] == "check_failed"
    assert app.state.maintenance_runtime.is_running() is True

    logs = client.get(
        "/api/logs?page=1&page_size=50&event_type=system_error",
        headers=_headers(admin_token),
    )
    assert logs.status_code == 200
    payloads = [item["payload_json"] for item in logs.json()["items"] if item["payload_json"]]
    assert any(item.get("runtime_component") == "maintenance_scheduler" and item.get("maintenance_task") == "purge_temporary_files" for item in payloads)
    assert any(item.get("maintenance_task") == "timeout_reconciliation" for item in payloads)
