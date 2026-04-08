from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from promo.presentation import app as app_module
from promo.shared.config import load_config


def test_load_config_enforces_safe_production_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("PROMO_ENVIRONMENT", "production")
    monkeypatch.setenv("PROMO_DATABASE_DSN", "sqlite+pysqlite:///tmp/promo.sqlite3")
    monkeypatch.setenv("PROMO_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("PROMO_WEB_AUTO_CREATE_SCHEMA", "0")
    monkeypatch.setenv("PROMO_WEB_PROXY_HEADERS", "1")
    monkeypatch.setenv("PROMO_WEB_FORWARDED_ALLOW_IPS", "127.0.0.1")
    monkeypatch.setenv("PROMO_AUTONOMOUS_RUNTIME_ENABLED", "1")
    monkeypatch.setenv("PROMO_AUTONOMOUS_MAINTENANCE_ENABLED", "1")
    monkeypatch.setenv("PROMO_MAINTENANCE_INTERVAL_SECONDS", "60")

    config = load_config()

    assert config.storage.root_path == storage_root
    assert config.web.auto_create_schema is False
    assert config.web.proxy_headers is True
    assert config.web.forwarded_allow_ips == "127.0.0.1"
    assert config.runtime.autonomous_runtime_enabled is True
    assert config.runtime.autonomous_maintenance_enabled is True
    assert config.runtime.maintenance_interval_seconds == 60.0


def test_load_config_rejects_relative_storage_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROMO_DATABASE_DSN", "sqlite+pysqlite:///tmp/promo.sqlite3")
    monkeypatch.setenv("PROMO_STORAGE_ROOT", "relative/storage")

    with pytest.raises(ValueError, match="absolute path"):
        load_config()


def test_load_config_rejects_production_auto_schema(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PROMO_ENVIRONMENT", "production")
    monkeypatch.setenv("PROMO_DATABASE_DSN", "sqlite+pysqlite:///tmp/promo.sqlite3")
    monkeypatch.setenv("PROMO_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("PROMO_WEB_AUTO_CREATE_SCHEMA", "1")

    with pytest.raises(ValueError, match="AUTO_CREATE_SCHEMA"):
        load_config()


def test_run_server_uses_proxy_header_runtime_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PROMO_DATABASE_DSN", "sqlite+pysqlite:///tmp/promo.sqlite3")
    monkeypatch.setenv("PROMO_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("PROMO_WEB_PROXY_HEADERS", "1")
    monkeypatch.setenv("PROMO_WEB_FORWARDED_ALLOW_IPS", "127.0.0.1")
    captured: dict[str, object] = {}

    def fake_run(app_ref: str, **kwargs) -> None:
        captured["app_ref"] = app_ref
        captured.update(kwargs)

    monkeypatch.setattr(app_module.uvicorn, "run", fake_run)

    exit_code = app_module.run_server([])

    assert exit_code == 0
    assert captured["app_ref"] == "promo.presentation.app:create_app"
    assert captured["factory"] is True
    assert captured["proxy_headers"] is True
    assert captured["forwarded_allow_ips"] == "127.0.0.1"


def test_prepare_runtime_dirs_script_creates_expected_storage_tree(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    script = Path("deployment/scripts/prepare_runtime_dirs.sh")
    env = dict(os.environ)
    env["PROMO_STORAGE_ROOT"] = str(storage_root)

    subprocess.run([str(script)], cwd=Path.cwd(), env=env, check=True)

    assert (storage_root / "uploads" / "tmp").is_dir()
    assert (storage_root / "runs").is_dir()


def test_deployment_artifacts_exist_and_reference_expected_runtime_boundary() -> None:
    env_example = Path("deployment/env/promo.env.example").read_text(encoding="utf-8")
    service = Path("deployment/systemd/promo.service").read_text(encoding="utf-8")
    nginx = Path("deployment/nginx/promo.conf").read_text(encoding="utf-8")
    logrotate = Path("deployment/logrotate/promo").read_text(encoding="utf-8")
    runtime_smoke = Path("deployment/scripts/runtime_smoke.sh").read_text(encoding="utf-8")
    release_check = Path("deployment/scripts/release_readiness_check.sh").read_text(encoding="utf-8")

    assert "PROMO_WEB_AUTO_CREATE_SCHEMA=0" in env_example
    assert "PROMO_STORAGE_ROOT=/var/lib/promo/storage" in env_example
    assert "ExecStart=/srv/promo/venv/bin/python -m promo.presentation" in service
    assert "EnvironmentFile=/etc/promo/promo.env" in service
    assert "ReadWritePaths=/var/lib/promo/storage" in service
    assert "proxy_pass http://127.0.0.1:8000;" in nginx
    assert "client_max_body_size 40m;" in nginx
    assert "systemd-journald" in logrotate
    assert "/health" in runtime_smoke
    assert "PROMO_ENVIRONMENT must be production" in release_check
    assert "PROMO_WEB_AUTO_CREATE_SCHEMA must be 0" in release_check
    assert 'grep -Eq "^EnvironmentFile="' in release_check
    assert "prepare_runtime_dirs.sh" in release_check
    assert "runtime_smoke.sh" in release_check
