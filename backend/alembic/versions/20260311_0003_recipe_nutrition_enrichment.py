"""Recipe nutrition enrichment fields

Revision ID: 20260311_0003
Revises: 20260310_0002
Create Date: 2026-03-11
"""

from __future__ import annotations

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa


revision = "20260311_0003"
down_revision = "20260310_0002"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "recipes" not in inspector.get_table_names():
        return

    if not _has_column(inspector, "recipes", "protein_g"):
        op.add_column("recipes", sa.Column("protein_g", sa.Float(), nullable=True))

    inspector = sa.inspect(bind)
    if not _has_column(inspector, "recipes", "carbs_g"):
        op.add_column("recipes", sa.Column("carbs_g", sa.Float(), nullable=True))

    inspector = sa.inspect(bind)
    if not _has_column(inspector, "recipes", "fat_g"):
        op.add_column("recipes", sa.Column("fat_g", sa.Float(), nullable=True))

    inspector = sa.inspect(bind)
    if not _has_column(inspector, "recipes", "allergens"):
        op.add_column("recipes", sa.Column("allergens", sa.JSON(), nullable=True))

    inspector = sa.inspect(bind)
    if not _has_column(inspector, "recipes", "cost_estimate"):
        op.add_column("recipes", sa.Column("cost_estimate", sa.Float(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "recipes" not in inspector.get_table_names():
        return

    if _has_column(inspector, "recipes", "cost_estimate"):
        op.drop_column("recipes", "cost_estimate")

    inspector = sa.inspect(bind)
    if _has_column(inspector, "recipes", "allergens"):
        op.drop_column("recipes", "allergens")

    inspector = sa.inspect(bind)
    if _has_column(inspector, "recipes", "fat_g"):
        op.drop_column("recipes", "fat_g")

    inspector = sa.inspect(bind)
    if _has_column(inspector, "recipes", "carbs_g"):
        op.drop_column("recipes", "carbs_g")

    inspector = sa.inspect(bind)
    if _has_column(inspector, "recipes", "protein_g"):
        op.drop_column("recipes", "protein_g")
