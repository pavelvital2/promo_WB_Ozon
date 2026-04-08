from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TEMPORARY_FILE_TTL_HOURS = 24
DEFAULT_RUN_FILE_RETENTION_DAYS = 5
DEFAULT_TIMEZONE = "Europe/Helsinki"
DEFAULT_STORAGE_ROOT = "/var/lib/promo/storage"
DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 8000


@dataclass(slots=True, frozen=True)
class DatabaseConfig:
    dsn: str


@dataclass(slots=True, frozen=True)
class StorageConfig:
    root_path: Path


@dataclass(slots=True, frozen=True)
class RetentionConfig:
    temporary_file_ttl_hours: int = DEFAULT_TEMPORARY_FILE_TTL_HOURS
    run_file_retention_days: int = DEFAULT_RUN_FILE_RETENTION_DAYS


@dataclass(slots=True, frozen=True)
class WebConfig:
    host: str = DEFAULT_WEB_HOST
    port: int = DEFAULT_WEB_PORT
    auto_create_schema: bool = False
    proxy_headers: bool = True
    forwarded_allow_ips: str = "127.0.0.1"


@dataclass(slots=True, frozen=True)
class RuntimeConfig:
    autonomous_runtime_enabled: bool = True
    autonomous_maintenance_enabled: bool = True
    maintenance_interval_seconds: float = 60.0


@dataclass(slots=True, frozen=True)
class AppConfig:
    app_name: str
    environment: str
    timezone: str
    database: DatabaseConfig
    storage: StorageConfig
    retention: RetentionConfig
    log_level: str
    web: WebConfig
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)

    def validate(self) -> None:
        if not self.storage.root_path.is_absolute():
            raise ValueError("PROMO_STORAGE_ROOT must be an absolute path")
        if self.retention.temporary_file_ttl_hours <= 0:
            raise ValueError("PROMO_TEMPORARY_FILE_TTL_HOURS must be greater than zero")
        if self.retention.run_file_retention_days <= 0:
            raise ValueError("PROMO_RUN_FILE_RETENTION_DAYS must be greater than zero")
        if self.runtime.maintenance_interval_seconds <= 0:
            raise ValueError("PROMO_MAINTENANCE_INTERVAL_SECONDS must be greater than zero")
        if self.environment.lower() == "production" and self.web.auto_create_schema:
            raise ValueError("PROMO_WEB_AUTO_CREATE_SCHEMA must be disabled in production")


def load_config() -> AppConfig:
    dsn = os.getenv("PROMO_DATABASE_DSN", "postgresql+psycopg://promo:promo@localhost:5432/promo")
    storage_root = Path(os.getenv("PROMO_STORAGE_ROOT", DEFAULT_STORAGE_ROOT))
    config = AppConfig(
        app_name=os.getenv("PROMO_APP_NAME", "promo"),
        environment=os.getenv("PROMO_ENVIRONMENT", "development"),
        timezone=os.getenv("PROMO_TIMEZONE", DEFAULT_TIMEZONE),
        database=DatabaseConfig(dsn=dsn),
        storage=StorageConfig(root_path=storage_root),
        retention=RetentionConfig(
            temporary_file_ttl_hours=int(os.getenv("PROMO_TEMPORARY_FILE_TTL_HOURS", str(DEFAULT_TEMPORARY_FILE_TTL_HOURS))),
            run_file_retention_days=int(os.getenv("PROMO_RUN_FILE_RETENTION_DAYS", str(DEFAULT_RUN_FILE_RETENTION_DAYS))),
        ),
        log_level=os.getenv("PROMO_LOG_LEVEL", "INFO"),
        web=WebConfig(
            host=os.getenv("PROMO_WEB_HOST", DEFAULT_WEB_HOST),
            port=int(os.getenv("PROMO_WEB_PORT", str(DEFAULT_WEB_PORT))),
            auto_create_schema=os.getenv("PROMO_WEB_AUTO_CREATE_SCHEMA", "0") in {"1", "true", "True"},
            proxy_headers=os.getenv("PROMO_WEB_PROXY_HEADERS", "1") not in {"0", "false", "False"},
            forwarded_allow_ips=os.getenv("PROMO_WEB_FORWARDED_ALLOW_IPS", "127.0.0.1"),
        ),
        runtime=RuntimeConfig(
            autonomous_runtime_enabled=os.getenv("PROMO_AUTONOMOUS_RUNTIME_ENABLED", "1") not in {"0", "false", "False"},
            autonomous_maintenance_enabled=os.getenv("PROMO_AUTONOMOUS_MAINTENANCE_ENABLED", "1") not in {"0", "false", "False"},
            maintenance_interval_seconds=float(os.getenv("PROMO_MAINTENANCE_INTERVAL_SECONDS", "60")),
        ),
    )
    config.validate()
    return config
