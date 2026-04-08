from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from migrations.versions._types import enum_types


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    types = enum_types()

    op.create_table(
        "run_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("file_role", types["file_role"], nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_relative_path", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("unavailable_reason", types["unavailable_reason"], nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("stored_filename", name="uq_run_files_stored_filename"),
        sa.UniqueConstraint("storage_relative_path", name="uq_run_files_storage_relative_path"),
    )
    op.create_index("ix_run_files_run_id", "run_files", ["run_id"])
    op.create_index("ix_run_files_file_sha256", "run_files", ["file_sha256"])
    op.create_index("ix_run_files_uploaded_at_utc", "run_files", ["uploaded_at_utc"])
    op.create_index("ix_run_files_expires_at_utc", "run_files", ["expires_at_utc"])
    op.create_index("ix_run_files_is_available", "run_files", ["is_available"])


def downgrade() -> None:
    op.drop_index("ix_run_files_is_available", table_name="run_files")
    op.drop_index("ix_run_files_expires_at_utc", table_name="run_files")
    op.drop_index("ix_run_files_uploaded_at_utc", table_name="run_files")
    op.drop_index("ix_run_files_file_sha256", table_name="run_files")
    op.drop_index("ix_run_files_run_id", table_name="run_files")
    op.drop_table("run_files")

