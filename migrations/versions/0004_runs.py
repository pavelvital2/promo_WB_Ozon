from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from migrations.versions._types import enum_types


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    types = enum_types()

    op.create_table(
        "runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_run_number", sa.String(length=50), nullable=False),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("initiated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("operation_type", types["operation_type"], nullable=False),
        sa.Column("lifecycle_status", types["run_lifecycle_status"], nullable=False),
        sa.Column("business_result", types["business_result"], nullable=True),
        sa.Column("module_code", types["module_code"], nullable=False),
        sa.Column("input_set_signature", sa.String(length=255), nullable=False),
        sa.Column("started_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("short_result_text", sa.String(length=500), nullable=True),
        sa.Column("result_file_id", sa.Integer(), nullable=True),
        sa.Column(
            "validation_was_auto_before_process",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("public_run_number", name="uq_runs_public_run_number"),
    )
    op.create_index("ix_runs_store_id", "runs", ["store_id"])
    op.create_index("ix_runs_initiated_by_user_id", "runs", ["initiated_by_user_id"])
    op.create_index("ix_runs_operation_type", "runs", ["operation_type"])
    op.create_index("ix_runs_lifecycle_status", "runs", ["lifecycle_status"])
    op.create_index("ix_runs_business_result", "runs", ["business_result"])
    op.create_index("ix_runs_module_code", "runs", ["module_code"])
    op.create_index("ix_runs_input_set_signature", "runs", ["input_set_signature"])
    op.create_index("ix_runs_started_at_utc", "runs", ["started_at_utc"])
    op.create_index("ix_runs_finished_at_utc", "runs", ["finished_at_utc"])


def downgrade() -> None:
    op.drop_index("ix_runs_finished_at_utc", table_name="runs")
    op.drop_index("ix_runs_started_at_utc", table_name="runs")
    op.drop_index("ix_runs_input_set_signature", table_name="runs")
    op.drop_index("ix_runs_module_code", table_name="runs")
    op.drop_index("ix_runs_business_result", table_name="runs")
    op.drop_index("ix_runs_lifecycle_status", table_name="runs")
    op.drop_index("ix_runs_operation_type", table_name="runs")
    op.drop_index("ix_runs_initiated_by_user_id", table_name="runs")
    op.drop_index("ix_runs_store_id", table_name="runs")
    op.drop_table("runs")

