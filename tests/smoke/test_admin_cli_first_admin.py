from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from promo.presentation.app import create_app
from promo.shared.config import AppConfig, DatabaseConfig, RetentionConfig, StorageConfig, WebConfig
from promo.shared.enums import RoleCode
from promo.shared.persistence.wiring import build_app_context


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        app_name="promo-cli-smoke",
        environment="test",
        timezone="UTC",
        database=DatabaseConfig(dsn=f"sqlite+pysqlite:///{tmp_path / 'promo-cli-smoke.sqlite3'}"),
        storage=StorageConfig(root_path=tmp_path / "storage"),
        retention=RetentionConfig(),
        log_level="INFO",
        web=WebConfig(auto_create_schema=False),
    )


def _run_cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd() / "src")
    env["PROMO_DATABASE_DSN"] = f"sqlite+pysqlite:///{tmp_path / 'promo-cli-smoke.sqlite3'}"
    env["PROMO_STORAGE_ROOT"] = str(tmp_path / "storage")
    env["PROMO_WEB_AUTO_CREATE_SCHEMA"] = "0"
    return subprocess.run(
        [sys.executable, "-m", "promo", *args],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_create_first_admin_cli_path_persists_user(tmp_path: Path) -> None:
    created = _run_cli(tmp_path, "create-first-admin", "--username", "admin", "--password", "admin-pass")
    duplicate = _run_cli(tmp_path, "create-first-admin", "--username", "second", "--password", "second-pass")

    assert created.returncode == 0
    assert duplicate.returncode == 0

    created_payload = ast.literal_eval(created.stdout.strip())
    duplicate_payload = ast.literal_eval(duplicate.stdout.strip())
    assert created_payload["status"] == "created"
    assert duplicate_payload["status"] == "already_exists"

    config = _config(tmp_path)
    app = build_app_context(config)
    with app.request_scope() as bundle:
        roles = bundle.uow.repositories.roles.list()
        users = bundle.uow.repositories.users.list()
        admin_role = next(item for item in roles if item.code == RoleCode.ADMIN.value)
        admin_user = next(item for item in users if item.username == "admin")

    assert admin_user.role_id == admin_role.id
    assert not admin_user.is_blocked


def test_create_first_admin_cli_validation_fails_cleanly(tmp_path: Path) -> None:
    invalid = _run_cli(tmp_path, "create-first-admin", "--username", "  ", "--password", "123")
    assert invalid.returncode == 1
    payload = ast.literal_eval(invalid.stdout.strip())
    assert payload["status"] == "validation_failed"


def test_first_admin_bootstrap_is_not_exposed_via_web_surface(tmp_path: Path) -> None:
    config = _config(tmp_path)
    app_context = build_app_context(config)
    app = create_app(config, app_context=app_context)
    client = TestClient(app)

    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/bootstrap/first-admin" not in paths
