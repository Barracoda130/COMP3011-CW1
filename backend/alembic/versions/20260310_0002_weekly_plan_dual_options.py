"""Weekly plan dual daily options

Revision ID: 20260310_0002
Revises: 20260310_0001
Create Date: 2026-03-10
"""

from __future__ import annotations

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa


revision = "20260310_0002"
down_revision = "20260310_0001"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_unique(inspector: sa.Inspector, table_name: str, unique_name: str) -> bool:
    return any(unique.get("name") == unique_name for unique in inspector.get_unique_constraints(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "weekly_plan_items" not in inspector.get_table_names():
        return

    if not _has_column(inspector, "weekly_plan_items", "is_selected"):
        op.add_column(
            "weekly_plan_items",
            sa.Column("is_selected", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    inspector = sa.inspect(bind)
    if _has_unique(inspector, "weekly_plan_items", "uq_weekly_plan_day_index"):
        op.drop_constraint("uq_weekly_plan_day_index", "weekly_plan_items", type_="unique")

    inspector = sa.inspect(bind)
    if not _has_unique(inspector, "weekly_plan_items", "uq_weekly_plan_day_source"):
        op.create_unique_constraint(
            "uq_weekly_plan_day_source",
            "weekly_plan_items",
            ["weekly_plan_id", "day_index", "recipe_source"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "weekly_plan_items" not in inspector.get_table_names():
        return

    if _has_unique(inspector, "weekly_plan_items", "uq_weekly_plan_day_source"):
        op.drop_constraint("uq_weekly_plan_day_source", "weekly_plan_items", type_="unique")

    inspector = sa.inspect(bind)
    if not _has_unique(inspector, "weekly_plan_items", "uq_weekly_plan_day_index"):
        op.create_unique_constraint(
            "uq_weekly_plan_day_index",
            "weekly_plan_items",
            ["weekly_plan_id", "day_index"],
        )

    inspector = sa.inspect(bind)
    if _has_column(inspector, "weekly_plan_items", "is_selected"):
        op.drop_column("weekly_plan_items", "is_selected")
