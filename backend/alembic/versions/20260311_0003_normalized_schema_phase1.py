"""Normalized schema phase 1 for analytics and recommendations.

Revision ID: 20260311_0003
Revises: 20260310_0002
Create Date: 2026-03-11
"""

from __future__ import annotations

import json

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa


revision = "20260311_0003"
down_revision = "20260310_0002"
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _coerce_list(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        return [part.strip() for part in stripped.split(",") if part.strip()]
    return []


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "ingredients"):
        op.create_table(
            "ingredients",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name_normalized", sa.String(length=120), nullable=False),
            sa.Column("display_name", sa.String(length=120), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name_normalized", name="uq_ingredients_name_normalized"),
        )
        op.create_index(op.f("ix_ingredients_id"), "ingredients", ["id"], unique=False)
        op.create_index(op.f("ix_ingredients_name_normalized"), "ingredients", ["name_normalized"], unique=False)

    inspector = sa.inspect(bind)
    if not _has_table(inspector, "recipe_ingredients"):
        op.create_table(
            "recipe_ingredients",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("recipe_id", sa.Integer(), nullable=False),
            sa.Column("ingredient_id", sa.Integer(), nullable=False),
            sa.Column("quantity_value", sa.Float(), nullable=True),
            sa.Column("quantity_unit", sa.String(length=40), nullable=True),
            sa.Column("free_text", sa.String(length=255), nullable=True),
            sa.Column("position", sa.Integer(), nullable=True),
            sa.Column("is_main", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_recipe_ingredients_id"), "recipe_ingredients", ["id"], unique=False)
        op.create_index(op.f("ix_recipe_ingredients_recipe_id"), "recipe_ingredients", ["recipe_id"], unique=False)
        op.create_index(op.f("ix_recipe_ingredients_ingredient_id"), "recipe_ingredients", ["ingredient_id"], unique=False)

    inspector = sa.inspect(bind)
    if not _has_table(inspector, "tags"):
        op.create_table(
            "tags",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name_normalized", sa.String(length=80), nullable=False),
            sa.Column("display_name", sa.String(length=80), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name_normalized", name="uq_tags_name_normalized"),
        )
        op.create_index(op.f("ix_tags_id"), "tags", ["id"], unique=False)
        op.create_index(op.f("ix_tags_name_normalized"), "tags", ["name_normalized"], unique=False)

    inspector = sa.inspect(bind)
    if not _has_table(inspector, "recipe_tags"):
        op.create_table(
            "recipe_tags",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("recipe_id", sa.Integer(), nullable=False),
            sa.Column("tag_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_recipe_tags_id"), "recipe_tags", ["id"], unique=False)
        op.create_index(op.f("ix_recipe_tags_recipe_id"), "recipe_tags", ["recipe_id"], unique=False)
        op.create_index(op.f("ix_recipe_tags_tag_id"), "recipe_tags", ["tag_id"], unique=False)

    inspector = sa.inspect(bind)
    if not _has_table(inspector, "recipe_feedback"):
        op.create_table(
            "recipe_feedback",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("recipe_id", sa.Integer(), nullable=False),
            sa.Column("score", sa.Integer(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("context", sa.String(length=40), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "recipe_id", name="uq_recipe_feedback_user_recipe"),
        )
        op.create_index(op.f("ix_recipe_feedback_id"), "recipe_feedback", ["id"], unique=False)
        op.create_index(op.f("ix_recipe_feedback_user_id"), "recipe_feedback", ["user_id"], unique=False)
        op.create_index(op.f("ix_recipe_feedback_recipe_id"), "recipe_feedback", ["recipe_id"], unique=False)

    inspector = sa.inspect(bind)
    if not _has_table(inspector, "recipe_nutrition"):
        op.create_table(
            "recipe_nutrition",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("recipe_id", sa.Integer(), nullable=False),
            sa.Column("serving_size_text", sa.String(length=80), nullable=True),
            sa.Column("calories_kcal", sa.Float(), nullable=True),
            sa.Column("protein_g", sa.Float(), nullable=True),
            sa.Column("carbs_g", sa.Float(), nullable=True),
            sa.Column("fat_g", sa.Float(), nullable=True),
            sa.Column("fiber_g", sa.Float(), nullable=True),
            sa.Column("sugar_g", sa.Float(), nullable=True),
            sa.Column("sodium_mg", sa.Float(), nullable=True),
            sa.Column("source", sa.String(length=40), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_recipe_nutrition_id"), "recipe_nutrition", ["id"], unique=False)
        op.create_index(op.f("ix_recipe_nutrition_recipe_id"), "recipe_nutrition", ["recipe_id"], unique=False)

    inspector = sa.inspect(bind)
    if not _has_table(inspector, "user_recipe_events"):
        op.create_table(
            "user_recipe_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("recipe_id", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=40), nullable=False),
            sa.Column("event_value", sa.Float(), nullable=True),
            sa.Column("session_id", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_user_recipe_events_id"), "user_recipe_events", ["id"], unique=False)
        op.create_index(op.f("ix_user_recipe_events_user_id"), "user_recipe_events", ["user_id"], unique=False)
        op.create_index(op.f("ix_user_recipe_events_recipe_id"), "user_recipe_events", ["recipe_id"], unique=False)
        op.create_index(op.f("ix_user_recipe_events_event_type"), "user_recipe_events", ["event_type"], unique=False)
        op.create_index(op.f("ix_user_recipe_events_created_at"), "user_recipe_events", ["created_at"], unique=False)

    ingredients_table = sa.table(
        "ingredients",
        sa.column("id", sa.Integer()),
        sa.column("name_normalized", sa.String()),
        sa.column("display_name", sa.String()),
    )
    recipe_ingredients_table = sa.table(
        "recipe_ingredients",
        sa.column("recipe_id", sa.Integer()),
        sa.column("ingredient_id", sa.Integer()),
        sa.column("free_text", sa.String()),
        sa.column("position", sa.Integer()),
        sa.column("is_main", sa.Boolean()),
    )
    tags_table = sa.table(
        "tags",
        sa.column("id", sa.Integer()),
        sa.column("name_normalized", sa.String()),
        sa.column("display_name", sa.String()),
    )
    recipe_tags_table = sa.table(
        "recipe_tags",
        sa.column("recipe_id", sa.Integer()),
        sa.column("tag_id", sa.Integer()),
    )
    recipe_feedback_table = sa.table(
        "recipe_feedback",
        sa.column("user_id", sa.Integer()),
        sa.column("recipe_id", sa.Integer()),
        sa.column("score", sa.Integer()),
        sa.column("comment", sa.Text()),
        sa.column("context", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    ingredient_id_by_name: dict[str, int] = {}
    tag_id_by_name: dict[str, int] = {}

    recipes_rows = bind.execute(sa.text("SELECT id, ingredients, tags FROM recipes")).fetchall()
    for recipe_id, ingredients_raw, tags_raw in recipes_rows:
        ingredients = _coerce_list(ingredients_raw)
        tags = _coerce_list(tags_raw)

        seen_ings: set[str] = set()
        for index, raw in enumerate(ingredients):
            display_name = str(raw).strip()
            if not display_name:
                continue
            normalized = _normalize(display_name)
            if not normalized or normalized in seen_ings:
                continue
            seen_ings.add(normalized)

            ingredient_id = ingredient_id_by_name.get(normalized)
            if ingredient_id is None:
                existing = bind.execute(
                    sa.text("SELECT id FROM ingredients WHERE name_normalized = :name"),
                    {"name": normalized},
                ).fetchone()
                if existing:
                    ingredient_id = int(existing[0])
                else:
                    bind.execute(
                        ingredients_table.insert().values(
                            name_normalized=normalized,
                            display_name=display_name,
                        )
                    )
                    inserted = bind.execute(
                        sa.text("SELECT id FROM ingredients WHERE name_normalized = :name"),
                        {"name": normalized},
                    ).fetchone()
                    if not inserted:
                        raise RuntimeError("Failed to resolve inserted ingredient id during backfill")
                    ingredient_id = int(inserted[0])
                ingredient_id_by_name[normalized] = ingredient_id

            bind.execute(
                recipe_ingredients_table.insert().values(
                    recipe_id=recipe_id,
                    ingredient_id=ingredient_id,
                    free_text=display_name,
                    position=index,
                    is_main=index == 0,
                )
            )

        seen_tags: set[str] = set()
        for raw in tags:
            display_name = str(raw).strip()
            if not display_name:
                continue
            normalized = _normalize(display_name)
            if not normalized or normalized in seen_tags:
                continue
            seen_tags.add(normalized)

            tag_id = tag_id_by_name.get(normalized)
            if tag_id is None:
                existing = bind.execute(
                    sa.text("SELECT id FROM tags WHERE name_normalized = :name"),
                    {"name": normalized},
                ).fetchone()
                if existing:
                    tag_id = int(existing[0])
                else:
                    bind.execute(
                        tags_table.insert().values(
                            name_normalized=normalized,
                            display_name=display_name,
                        )
                    )
                    inserted = bind.execute(
                        sa.text("SELECT id FROM tags WHERE name_normalized = :name"),
                        {"name": normalized},
                    ).fetchone()
                    if not inserted:
                        raise RuntimeError("Failed to resolve inserted tag id during backfill")
                    tag_id = int(inserted[0])
                tag_id_by_name[normalized] = tag_id

            bind.execute(recipe_tags_table.insert().values(recipe_id=recipe_id, tag_id=tag_id))

    rating_rows = bind.execute(
        sa.text("SELECT user_id, recipe_id, score, comment, created_at FROM recipe_ratings")
    ).fetchall()
    for user_id, recipe_id, score, comment, created_at in rating_rows:
        exists = bind.execute(
            sa.text(
                "SELECT id FROM recipe_feedback WHERE user_id = :user_id AND recipe_id = :recipe_id"
            ),
            {"user_id": user_id, "recipe_id": recipe_id},
        ).fetchone()
        if exists:
            continue
        bind.execute(
            recipe_feedback_table.insert().values(
                user_id=user_id,
                recipe_id=recipe_id,
                score=score,
                comment=comment,
                context="legacy-local-rating",
                created_at=created_at,
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "user_recipe_events"):
        op.drop_index(op.f("ix_user_recipe_events_created_at"), table_name="user_recipe_events")
        op.drop_index(op.f("ix_user_recipe_events_event_type"), table_name="user_recipe_events")
        op.drop_index(op.f("ix_user_recipe_events_recipe_id"), table_name="user_recipe_events")
        op.drop_index(op.f("ix_user_recipe_events_user_id"), table_name="user_recipe_events")
        op.drop_index(op.f("ix_user_recipe_events_id"), table_name="user_recipe_events")
        op.drop_table("user_recipe_events")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "recipe_nutrition"):
        op.drop_index(op.f("ix_recipe_nutrition_recipe_id"), table_name="recipe_nutrition")
        op.drop_index(op.f("ix_recipe_nutrition_id"), table_name="recipe_nutrition")
        op.drop_table("recipe_nutrition")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "recipe_feedback"):
        op.drop_index(op.f("ix_recipe_feedback_recipe_id"), table_name="recipe_feedback")
        op.drop_index(op.f("ix_recipe_feedback_user_id"), table_name="recipe_feedback")
        op.drop_index(op.f("ix_recipe_feedback_id"), table_name="recipe_feedback")
        op.drop_table("recipe_feedback")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "recipe_tags"):
        op.drop_index(op.f("ix_recipe_tags_tag_id"), table_name="recipe_tags")
        op.drop_index(op.f("ix_recipe_tags_recipe_id"), table_name="recipe_tags")
        op.drop_index(op.f("ix_recipe_tags_id"), table_name="recipe_tags")
        op.drop_table("recipe_tags")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "tags"):
        op.drop_index(op.f("ix_tags_name_normalized"), table_name="tags")
        op.drop_index(op.f("ix_tags_id"), table_name="tags")
        op.drop_table("tags")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "recipe_ingredients"):
        op.drop_index(op.f("ix_recipe_ingredients_ingredient_id"), table_name="recipe_ingredients")
        op.drop_index(op.f("ix_recipe_ingredients_recipe_id"), table_name="recipe_ingredients")
        op.drop_index(op.f("ix_recipe_ingredients_id"), table_name="recipe_ingredients")
        op.drop_table("recipe_ingredients")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "ingredients"):
        op.drop_index(op.f("ix_ingredients_name_normalized"), table_name="ingredients")
        op.drop_index(op.f("ix_ingredients_id"), table_name="ingredients")
        op.drop_table("ingredients")
