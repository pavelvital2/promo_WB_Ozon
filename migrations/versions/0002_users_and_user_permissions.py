from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_role_id", "users", ["role_id"])
    op.create_index("ix_users_is_blocked", "users", ["is_blocked"])
    op.create_index("ix_users_created_at_utc", "users", ["created_at_utc"])

    op.create_table(
        "user_permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id"), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "permission_id", name="uq_user_permissions_user_id_permission_id"),
    )
    op.create_index("ix_user_permissions_user_id", "user_permissions", ["user_id"])
    op.create_index("ix_user_permissions_permission_id", "user_permissions", ["permission_id"])


def downgrade() -> None:
    op.drop_index("ix_user_permissions_permission_id", table_name="user_permissions")
    op.drop_index("ix_user_permissions_user_id", table_name="user_permissions")
    op.drop_table("user_permissions")
    op.drop_index("ix_users_created_at_utc", table_name="users")
    op.drop_index("ix_users_is_blocked", table_name="users")
    op.drop_index("ix_users_role_id", table_name="users")
    op.drop_table("users")

