from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from migrations.versions._types import create_all_types, drop_all_types


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_all_types(bind)

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.UniqueConstraint("code", name="uq_roles_code"),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
        sa.UniqueConstraint("name", name="uq_permissions_name"),
    )

    op.bulk_insert(
        sa.table("roles", sa.column("code", sa.String()), sa.column("name", sa.String())),
        [
            {"code": "admin", "name": "Администратор"},
            {"code": "manager_lead", "name": "Управляющий"},
            {"code": "manager", "name": "Менеджер"},
        ],
    )
    op.bulk_insert(
        sa.table(
            "permissions",
            sa.column("code", sa.String()),
            sa.column("name", sa.String()),
            sa.column("description", sa.String()),
        ),
        [
            {"code": "create_store", "name": "create_store", "description": None},
            {"code": "edit_store", "name": "edit_store", "description": None},
        ],
    )


def downgrade() -> None:
    op.drop_table("permissions")
    op.drop_table("roles")
    drop_all_types(op.get_bind())

