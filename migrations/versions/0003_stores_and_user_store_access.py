from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from migrations.versions._types import enum_types


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    types = enum_types()

    op.create_table(
        "stores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("marketplace", types["marketplace_code"], nullable=False),
        sa.Column("status", types["store_status"], nullable=False),
        sa.Column("wb_threshold_percent", sa.Integer(), nullable=True),
        sa.Column("wb_fallback_no_promo_percent", sa.Integer(), nullable=True),
        sa.Column("wb_fallback_over_threshold_percent", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("marketplace", "name", name="uq_stores_marketplace_name"),
        sa.CheckConstraint(
            "("
            "marketplace = 'wb' AND wb_threshold_percent IS NOT NULL "
            "AND wb_fallback_no_promo_percent IS NOT NULL "
            "AND wb_fallback_over_threshold_percent IS NOT NULL"
            ") OR ("
            "marketplace = 'ozon' AND wb_threshold_percent IS NULL "
            "AND wb_fallback_no_promo_percent IS NULL "
            "AND wb_fallback_over_threshold_percent IS NULL"
            ")",
            name="stores_marketplace_specific_fields",
        ),
    )
    op.create_index("ix_stores_marketplace", "stores", ["marketplace"])
    op.create_index("ix_stores_status", "stores", ["status"])
    op.create_index("ix_stores_created_by_user_id", "stores", ["created_by_user_id"])

    op.create_table(
        "user_store_access",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "store_id", name="uq_user_store_access_user_id_store_id"),
    )
    op.create_index("ix_user_store_access_user_id", "user_store_access", ["user_id"])
    op.create_index("ix_user_store_access_store_id", "user_store_access", ["store_id"])


def downgrade() -> None:
    op.drop_index("ix_user_store_access_store_id", table_name="user_store_access")
    op.drop_index("ix_user_store_access_user_id", table_name="user_store_access")
    op.drop_table("user_store_access")
    op.drop_index("ix_stores_created_by_user_id", table_name="stores")
    op.drop_index("ix_stores_status", table_name="stores")
    op.drop_index("ix_stores_marketplace", table_name="stores")
    op.drop_table("stores")

