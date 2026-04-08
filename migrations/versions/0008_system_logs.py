from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from migrations.versions._types import enum_types


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    types = enum_types()

    op.create_table(
        "system_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id"), nullable=True),
        sa.Column("module_code", types["module_code"], nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("severity", types["severity"], nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_system_logs_event_time_utc", "system_logs", ["event_time_utc"])
    op.create_index("ix_system_logs_user_id", "system_logs", ["user_id"])
    op.create_index("ix_system_logs_store_id", "system_logs", ["store_id"])
    op.create_index("ix_system_logs_run_id", "system_logs", ["run_id"])
    op.create_index("ix_system_logs_module_code", "system_logs", ["module_code"])
    op.create_index("ix_system_logs_event_type", "system_logs", ["event_type"])
    op.create_index("ix_system_logs_severity", "system_logs", ["severity"])


def downgrade() -> None:
    op.drop_index("ix_system_logs_severity", table_name="system_logs")
    op.drop_index("ix_system_logs_event_type", table_name="system_logs")
    op.drop_index("ix_system_logs_module_code", table_name="system_logs")
    op.drop_index("ix_system_logs_run_id", table_name="system_logs")
    op.drop_index("ix_system_logs_store_id", table_name="system_logs")
    op.drop_index("ix_system_logs_user_id", table_name="system_logs")
    op.drop_index("ix_system_logs_event_time_utc", table_name="system_logs")
    op.drop_table("system_logs")

