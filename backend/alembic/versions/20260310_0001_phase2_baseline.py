"""Phase 2 baseline migration

Revision ID: 20260310_0001
Revises:
Create Date: 2026-03-10
"""

from __future__ import annotations

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa


revision = "20260310_0001"
down_revision = None
branch_labels = None
depends_on = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "recipes" in tables:
        recipe_columns = _column_names(inspector, "recipes")

        if "intro" not in recipe_columns:
            op.add_column("recipes", sa.Column("intro", sa.Text(), nullable=True))

        if "steps" not in recipe_columns:
            op.add_column("recipes", sa.Column("steps", sa.Text(), nullable=True))

        if "ingredients" not in recipe_columns:
            op.add_column("recipes", sa.Column("ingredients", sa.JSON(), nullable=True))

        # Data backfill from legacy field.
        if "description" in recipe_columns:
            bind.execute(
                sa.text(
                    "UPDATE recipes SET steps = description "
                    "WHERE steps IS NULL AND description IS NOT NULL"
                )
            )
            bind.execute(
                sa.text(
                    "UPDATE recipes SET intro = description "
                    "WHERE intro IS NULL AND description IS NOT NULL"
                )
            )

        if bind.dialect.name == "postgresql":
            bind.execute(sa.text("UPDATE recipes SET ingredients = '[]'::json WHERE ingredients IS NULL"))
        else:
            bind.execute(sa.text("UPDATE recipes SET ingredients = '[]' WHERE ingredients IS NULL"))

    if "weekly_plans" not in tables:
        op.create_table(
            "weekly_plans",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_weekly_plans_id"), "weekly_plans", ["id"], unique=False)
        op.create_index(op.f("ix_weekly_plans_user_id"), "weekly_plans", ["user_id"], unique=False)

    if "weekly_plan_items" not in tables:
        op.create_table(
            "weekly_plan_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("weekly_plan_id", sa.Integer(), nullable=False),
            sa.Column("day_index", sa.Integer(), nullable=False),
            sa.Column("planned_for", sa.Date(), nullable=True),
            sa.Column("recipe_source", sa.String(length=20), nullable=False, server_default="local"),
            sa.Column("recipe_id", sa.Integer(), nullable=True),
            sa.Column("external_recipe_id", sa.String(length=64), nullable=True),
            sa.Column("title_snapshot", sa.String(length=150), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["weekly_plan_id"], ["weekly_plans.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("weekly_plan_id", "day_index", name="uq_weekly_plan_day_index"),
        )
        op.create_index(op.f("ix_weekly_plan_items_id"), "weekly_plan_items", ["id"], unique=False)
        op.create_index(
            op.f("ix_weekly_plan_items_weekly_plan_id"), "weekly_plan_items", ["weekly_plan_id"], unique=False
        )
        op.create_index(op.f("ix_weekly_plan_items_day_index"), "weekly_plan_items", ["day_index"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "weekly_plan_items" in tables:
        op.drop_index(op.f("ix_weekly_plan_items_day_index"), table_name="weekly_plan_items")
        op.drop_index(op.f("ix_weekly_plan_items_weekly_plan_id"), table_name="weekly_plan_items")
        op.drop_index(op.f("ix_weekly_plan_items_id"), table_name="weekly_plan_items")
        op.drop_table("weekly_plan_items")

    if "weekly_plans" in tables:
        op.drop_index(op.f("ix_weekly_plans_user_id"), table_name="weekly_plans")
        op.drop_index(op.f("ix_weekly_plans_id"), table_name="weekly_plans")
        op.drop_table("weekly_plans")
