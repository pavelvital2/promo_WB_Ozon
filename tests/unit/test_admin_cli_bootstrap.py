from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from promo.admin_cli.bootstrap import create_first_admin, seed_reference_data
from promo.shared.config import AppConfig, DatabaseConfig, RetentionConfig, StorageConfig, WebConfig
from promo.shared.enums import RoleCode
from promo.shared.persistence.wiring import build_app_context


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        app_name="promo-cli-test",
        environment="test",
        timezone="UTC",
        database=DatabaseConfig(dsn=f"sqlite+pysqlite:///{tmp_path / 'promo-cli.sqlite3'}"),
        storage=StorageConfig(root_path=tmp_path / "storage"),
        retention=RetentionConfig(),
        log_level="INFO",
        web=WebConfig(auto_create_schema=False),
    )


def test_create_first_admin_persists_admin_user(tmp_path: Path) -> None:
    config = _config(tmp_path)

    outcome = create_first_admin("admin", "admin-pass", config=config, clock=lambda: _dt("2026-04-07T12:00:00+00:00"))
    assert outcome.status == "created"

    app = build_app_context(config, clock=lambda: _dt("2026-04-07T12:00:00+00:00"))
    with app.request_scope() as bundle:
        roles = bundle.uow.repositories.roles.list()
        users = bundle.uow.repositories.users.list()
        admin_role = next(item for item in roles if item.code == RoleCode.ADMIN.value)
        created = next(item for item in users if item.username == "admin")

    assert created.role_id == admin_role.id
    assert created.is_blocked is False
    assert created.password_hash != "admin-pass"


def test_create_first_admin_is_idempotent_and_validates_input(tmp_path: Path) -> None:
    config = _config(tmp_path)

    first = create_first_admin("admin", "admin-pass", config=config, clock=lambda: _dt("2026-04-07T12:00:00+00:00"))
    second = create_first_admin("another-admin", "admin-pass", config=config, clock=lambda: _dt("2026-04-07T12:05:00+00:00"))
    invalid = create_first_admin(" ", "123", config=config, clock=lambda: _dt("2026-04-07T12:10:00+00:00"))

    assert first.status == "created"
    assert second.status == "already_exists"
    assert invalid.status == "validation_failed"

    app = build_app_context(config, clock=lambda: _dt("2026-04-07T12:10:00+00:00"))
    with app.request_scope() as bundle:
        users = bundle.uow.repositories.users.list()
    assert len(users) == 1


def test_seed_reference_data_materializes_roles_and_permissions(tmp_path: Path) -> None:
    config = _config(tmp_path)

    outcome = seed_reference_data(config=config, clock=lambda: _dt("2026-04-07T12:00:00+00:00"))
    assert outcome.status == "seeded"

    app = build_app_context(config, clock=lambda: _dt("2026-04-07T12:00:00+00:00"))
    with app.request_scope() as bundle:
        assert len(bundle.uow.repositories.roles.list()) == 3
        assert len(bundle.uow.repositories.permissions.list()) == 2
