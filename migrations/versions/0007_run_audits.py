from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from migrations.versions._types import enum_types


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    types = enum_types()

    op.create_table(
        "run_summary_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("audit_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", name="uq_run_summary_audit_run_id"),
    )

    op.create_table(
        "run_detail_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("entity_key_1", sa.String(length=255), nullable=True),
        sa.Column("entity_key_2", sa.String(length=255), nullable=True),
        sa.Column("severity", types["severity"], nullable=False),
        sa.Column("decision_reason", sa.String(length=255), nullable=True),
        sa.Column("message", sa.String(length=1000), nullable=False),
        sa.Column("audit_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_run_detail_audit_run_id", "run_detail_audit", ["run_id"])
    op.create_index("ix_run_detail_audit_row_number", "run_detail_audit", ["row_number"])
    op.create_index("ix_run_detail_audit_entity_key_1", "run_detail_audit", ["entity_key_1"])
    op.create_index("ix_run_detail_audit_entity_key_2", "run_detail_audit", ["entity_key_2"])
    op.create_index("ix_run_detail_audit_severity", "run_detail_audit", ["severity"])
    op.create_index("ix_run_detail_audit_decision_reason", "run_detail_audit", ["decision_reason"])
    op.create_index("ix_run_detail_audit_run_id_row_number", "run_detail_audit", ["run_id", "row_number"])


def downgrade() -> None:
    op.drop_index("ix_run_detail_audit_run_id_row_number", table_name="run_detail_audit")
    op.drop_index("ix_run_detail_audit_decision_reason", table_name="run_detail_audit")
    op.drop_index("ix_run_detail_audit_severity", table_name="run_detail_audit")
    op.drop_index("ix_run_detail_audit_entity_key_2", table_name="run_detail_audit")
    op.drop_index("ix_run_detail_audit_entity_key_1", table_name="run_detail_audit")
    op.drop_index("ix_run_detail_audit_row_number", table_name="run_detail_audit")
    op.drop_index("ix_run_detail_audit_run_id", table_name="run_detail_audit")
    op.drop_table("run_detail_audit")
    op.drop_table("run_summary_audit")
