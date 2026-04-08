from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from promo.shared.db import build_engine
from promo.shared.persistence.wiring import create_schema


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_http(url: str, *, timeout_seconds: float = 10.0) -> str:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1.0) as response:  # noqa: S310
                return response.read().decode("utf-8")
        except URLError:
            time.sleep(0.1)
    raise AssertionError(f"service did not become ready: {url}")


def test_release_readiness_check_passes_against_running_production_like_instance(tmp_path: Path) -> None:
    port = _find_free_port()
    database_path = tmp_path / "promo-release.sqlite3"
    storage_root = tmp_path / "storage"
    env_file = tmp_path / "promo.env"
    env_file.write_text(
        "\n".join(
            [
                "PROMO_APP_NAME=promo-release-test",
                "PROMO_ENVIRONMENT=production",
                f"PROMO_DATABASE_DSN=sqlite+pysqlite:///{database_path}",
                f"PROMO_STORAGE_ROOT={storage_root}",
                "PROMO_TIMEZONE=Europe/Helsinki",
                "PROMO_LOG_LEVEL=INFO",
                "PROMO_WEB_HOST=127.0.0.1",
                f"PROMO_WEB_PORT={port}",
                "PROMO_WEB_AUTO_CREATE_SCHEMA=0",
                "PROMO_WEB_PROXY_HEADERS=1",
                "PROMO_WEB_FORWARDED_ALLOW_IPS=127.0.0.1",
                "PROMO_AUTONOMOUS_RUNTIME_ENABLED=1",
                "PROMO_AUTONOMOUS_MAINTENANCE_ENABLED=1",
                "PROMO_MAINTENANCE_INTERVAL_SECONDS=1",
                "PROMO_TEMPORARY_FILE_TTL_HOURS=24",
                "PROMO_RUN_FILE_RETENTION_DAYS=5",
                "",
            ]
        ),
        encoding="utf-8",
    )

    create_schema(build_engine(f"sqlite+pysqlite:///{database_path}"))

    repo_root = Path.cwd()
    service_copy = tmp_path / "promo.service"
    nginx_copy = tmp_path / "promo.conf"
    service_copy.write_text(
        Path("deployment/systemd/promo.service").read_text(encoding="utf-8").replace(
            "EnvironmentFile=/etc/promo/promo.env",
            f"EnvironmentFile={env_file}",
        ),
        encoding="utf-8",
    )
    nginx_copy.write_text(
        Path("deployment/nginx/promo.conf")
        .read_text(encoding="utf-8")
        .replace("proxy_pass http://127.0.0.1:8000;", f"proxy_pass http://127.0.0.1:{port};"),
        encoding="utf-8",
    )

    env = dict(os.environ)
    env.update(
        {
            "PYTHONPATH": str(repo_root / "src"),
            "PROMO_APP_NAME": "promo-release-test",
            "PROMO_ENVIRONMENT": "production",
            "PROMO_DATABASE_DSN": f"sqlite+pysqlite:///{database_path}",
            "PROMO_STORAGE_ROOT": str(storage_root),
            "PROMO_TIMEZONE": "Europe/Helsinki",
            "PROMO_LOG_LEVEL": "INFO",
            "PROMO_WEB_HOST": "127.0.0.1",
            "PROMO_WEB_PORT": str(port),
            "PROMO_WEB_AUTO_CREATE_SCHEMA": "0",
            "PROMO_WEB_PROXY_HEADERS": "1",
            "PROMO_WEB_FORWARDED_ALLOW_IPS": "127.0.0.1",
            "PROMO_AUTONOMOUS_RUNTIME_ENABLED": "1",
            "PROMO_AUTONOMOUS_MAINTENANCE_ENABLED": "1",
            "PROMO_MAINTENANCE_INTERVAL_SECONDS": "1",
            "PROMO_TEMPORARY_FILE_TTL_HOURS": "24",
            "PROMO_RUN_FILE_RETENTION_DAYS": "5",
        }
    )

    process = subprocess.Popen(  # noqa: S603
        ["/tmp/promo-test-venv/bin/python", "-m", "promo.presentation"],
        cwd=repo_root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        health_payload = _wait_for_http(f"http://127.0.0.1:{port}/health")
        assert '"status":"ok"' in health_payload or '"status": "ok"' in health_payload

        openapi_payload = _wait_for_http(f"http://127.0.0.1:{port}/openapi.json")
        assert "/health" in openapi_payload

        subprocess.run(
            [
                str(repo_root / "deployment/scripts/release_readiness_check.sh"),
                str(env_file),
                str(service_copy),
                str(nginx_copy),
            ],
            cwd=repo_root,
            env=env,
            check=True,
        )
    finally:
        process.terminate()
        process.wait(timeout=10)
