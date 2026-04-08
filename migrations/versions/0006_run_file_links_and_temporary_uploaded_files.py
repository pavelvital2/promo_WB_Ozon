from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from migrations.versions._types import enum_types


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    types = enum_types()

    op.create_foreign_key(
        "fk_runs_result_file_id_run_files",
        "runs",
        "run_files",
        ["result_file_id"],
        ["id"],
    )

    op.create_table(
        "temporary_uploaded_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("module_code", types["module_code"], nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_relative_path", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active_in_current_set", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("stored_filename", name="uq_temporary_uploaded_files_stored_filename"),
        sa.UniqueConstraint("storage_relative_path", name="uq_temporary_uploaded_files_storage_relative_path"),
    )
    op.create_index("ix_temporary_uploaded_files_uploaded_by_user_id", "temporary_uploaded_files", ["uploaded_by_user_id"])
    op.create_index("ix_temporary_uploaded_files_store_id", "temporary_uploaded_files", ["store_id"])
    op.create_index("ix_temporary_uploaded_files_module_code", "temporary_uploaded_files", ["module_code"])
    op.create_index("ix_temporary_uploaded_files_file_sha256", "temporary_uploaded_files", ["file_sha256"])
    op.create_index("ix_temporary_uploaded_files_uploaded_at_utc", "temporary_uploaded_files", ["uploaded_at_utc"])
    op.create_index("ix_temporary_uploaded_files_expires_at_utc", "temporary_uploaded_files", ["expires_at_utc"])
    op.create_index("ix_temporary_uploaded_files_is_active_in_current_set", "temporary_uploaded_files", ["is_active_in_current_set"])
    op.create_index(
        "uq_temporary_uploaded_files_active_set",
        "temporary_uploaded_files",
        ["uploaded_by_user_id", "store_id", "module_code"],
        unique=True,
        postgresql_where=sa.text("is_active_in_current_set"),
    )


def downgrade() -> None:
    op.drop_index("uq_temporary_uploaded_files_active_set", table_name="temporary_uploaded_files")
    op.drop_index("ix_temporary_uploaded_files_is_active_in_current_set", table_name="temporary_uploaded_files")
    op.drop_index("ix_temporary_uploaded_files_expires_at_utc", table_name="temporary_uploaded_files")
    op.drop_index("ix_temporary_uploaded_files_uploaded_at_utc", table_name="temporary_uploaded_files")
    op.drop_index("ix_temporary_uploaded_files_file_sha256", table_name="temporary_uploaded_files")
    op.drop_index("ix_temporary_uploaded_files_module_code", table_name="temporary_uploaded_files")
    op.drop_index("ix_temporary_uploaded_files_store_id", table_name="temporary_uploaded_files")
    op.drop_index("ix_temporary_uploaded_files_uploaded_by_user_id", table_name="temporary_uploaded_files")
    op.drop_table("temporary_uploaded_files")
    op.drop_constraint("fk_runs_result_file_id_run_files", "runs", type_="foreignkey")

