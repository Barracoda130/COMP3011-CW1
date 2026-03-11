from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.ingredient import Ingredient, RecipeIngredient
from app.models.recipe import Recipe
from app.models.recipe_feedback import RecipeFeedback
from app.models.tag import RecipeTag, Tag


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def sync_recipe_entities(db: Session, recipe: Recipe) -> None:
    # Replace bridge rows in full to keep logic deterministic and simple for coursework.
    db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe.id).delete()
    db.query(RecipeTag).filter(RecipeTag.recipe_id == recipe.id).delete()

    seen_ingredients: set[str] = set()
    for index, raw in enumerate(recipe.ingredients or []):
        display_name = str(raw).strip()
        if not display_name:
            continue
        normalized = _normalize_text(display_name)
        if not normalized or normalized in seen_ingredients:
            continue
        seen_ingredients.add(normalized)

        ingredient = db.query(Ingredient).filter(Ingredient.name_normalized == normalized).first()
        if ingredient is None:
            ingredient = Ingredient(name_normalized=normalized, display_name=display_name)
            db.add(ingredient)
            db.flush()

        db.add(
            RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ingredient.id,
                free_text=display_name,
                position=index,
                is_main=index == 0,
            )
        )

    seen_tags: set[str] = set()
    for raw in recipe.tags or []:
        display_name = str(raw).strip()
        if not display_name:
            continue
        normalized = _normalize_text(display_name)
        if not normalized or normalized in seen_tags:
            continue
        seen_tags.add(normalized)

        tag = db.query(Tag).filter(Tag.name_normalized == normalized).first()
        if tag is None:
            tag = Tag(name_normalized=normalized, display_name=display_name)
            db.add(tag)
            db.flush()

        db.add(RecipeTag(recipe_id=recipe.id, tag_id=tag.id))


def upsert_recipe_feedback(
    db: Session,
    *,
    user_id: int,
    recipe_id: int,
    score: int,
    comment: str | None,
    context: str | None = None,
) -> None:
    existing = (
        db.query(RecipeFeedback)
        .filter(RecipeFeedback.user_id == user_id, RecipeFeedback.recipe_id == recipe_id)
        .first()
    )
    if existing is None:
        db.add(
            RecipeFeedback(
                user_id=user_id,
                recipe_id=recipe_id,
                score=score,
                comment=comment,
                context=context,
            )
        )
        return

    existing.score = score
    existing.comment = comment
    existing.context = context
