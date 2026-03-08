from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.rating import RecipeRating
from app.models.recipe import Recipe
from app.models.user import User
from app.schemas.recipe import (
    RecipeCookIngredient,
    RecipeCookRead,
    RecipeCreate,
    RecipeDiscoverItem,
    RecipeDiscoverResponse,
    RecipeRead,
    RecipeUpdate,
)
from app.schemas.rating import RatingCreate, RatingRead
from app.services.shopping import estimate_recipe_cost
from app.services.themealdb import get_themealdb_recipe_by_id, search_themealdb_recipes

router = APIRouter()


def _normalized_cuisine(value: str | None) -> str:
    if value is None:
        return "Unknown"
    normalized = value.strip()
    return normalized or "Unknown"


@router.get("", response_model=list[RecipeRead])
def list_recipes(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    db: Session = Depends(get_db),
) -> list[Recipe]:
    return db.query(Recipe).offset(skip).limit(limit).all()


@router.get("/discover", response_model=RecipeDiscoverResponse)
def discover_recipes(
    query: Annotated[str, Query(min_length=0)] = "",
    local_limit: Annotated[int, Query(ge=1, le=100)] = 50,
    external_limit: Annotated[int, Query(ge=1, le=300)] = 80,
    db: Session = Depends(get_db),
) -> RecipeDiscoverResponse:
    local_query = db.query(Recipe)
    if query.strip():
        like_pattern = f"%{query.strip()}%"
        local_query = local_query.filter(
            (Recipe.title.ilike(like_pattern)) | (Recipe.cuisine.ilike(like_pattern))
        )

    local_recipes = local_query.limit(local_limit).all()
    local_items: list[RecipeDiscoverItem] = []
    for recipe in local_recipes:
        local_hints = recipe.tags if recipe.tags else recipe.title.split()[:3]
        (
            estimated_cost,
            estimated_currency,
            estimated_confidence,
            estimated_debug,
        ) = estimate_recipe_cost(local_hints)

        local_items.append(
            RecipeDiscoverItem(
                id=recipe.id,
                source="local",
                title=recipe.title,
                cuisine=_normalized_cuisine(recipe.cuisine),
                image_url=None,
                prep_minutes=recipe.prep_minutes,
                calories=recipe.calories,
                tags=recipe.tags,
                description=recipe.description,
                average_rating=recipe.average_rating,
                owner_id=recipe.owner_id,
                category=None,
                key_ingredients=[],
                estimated_cost=estimated_cost,
                estimated_cost_currency=estimated_currency,
                estimated_cost_confidence=estimated_confidence,
                estimated_cost_debug=estimated_debug,
            )
        )

    external_raw = search_themealdb_recipes(query=query.strip(), limit=external_limit)
    external_items: list[RecipeDiscoverItem] = []
    for item in external_raw:
        ingredient_hints = item.get("key_ingredients") or []
        (
            estimated_cost,
            estimated_currency,
            estimated_confidence,
            estimated_debug,
        ) = estimate_recipe_cost(ingredient_hints)
        external_items.append(
            RecipeDiscoverItem(
                **item,
                estimated_cost=estimated_cost,
                estimated_cost_currency=estimated_currency,
                estimated_cost_confidence=estimated_confidence,
                estimated_cost_debug=estimated_debug,
            )
        )

    # Local recipes are intentionally prioritized ahead of external suggestions.
    combined_items = [*local_items, *external_items]

    return RecipeDiscoverResponse(
        items=combined_items,
        local_count=len(local_items),
        external_count=len(external_items),
    )


@router.get("/cook/{source}/{recipe_id}", response_model=RecipeCookRead)
def get_recipe_for_cooking(
    source: str,
    recipe_id: str,
    db: Session = Depends(get_db),
) -> RecipeCookRead:
    normalized_source = source.strip().lower()
    if normalized_source == "local":
        if not recipe_id.isdigit():
            raise HTTPException(status_code=400, detail="Local recipe id must be numeric")

        recipe = db.query(Recipe).filter(Recipe.id == int(recipe_id)).first()
        if recipe is None:
            raise HTTPException(status_code=404, detail="Recipe not found")

        local_hints = recipe.tags if recipe.tags else recipe.title.split()[:3]
        (
            estimated_cost,
            estimated_currency,
            estimated_confidence,
            estimated_debug,
        ) = estimate_recipe_cost(local_hints)

        return RecipeCookRead(
            id=recipe.id,
            source="local",
            title=recipe.title,
            cuisine=_normalized_cuisine(recipe.cuisine),
            description=recipe.description,
            instructions=recipe.description,
            tags=recipe.tags,
            ingredients=[],
            prep_minutes=recipe.prep_minutes,
            calories=recipe.calories,
            estimated_cost=estimated_cost,
            estimated_cost_currency=estimated_currency,
            estimated_cost_confidence=estimated_confidence,
            estimated_cost_debug=estimated_debug,
        )

    if normalized_source == "themealdb":
        external_recipe = get_themealdb_recipe_by_id(recipe_id)
        if external_recipe is None:
            raise HTTPException(status_code=404, detail="External recipe not found")

        ingredient_names = [
            ingredient.get("name", "")
            for ingredient in external_recipe.get("ingredients") or []
            if ingredient.get("name")
        ]
        ingredient_measures = {
            ingredient.get("name", ""): ingredient.get("measure")
            for ingredient in external_recipe.get("ingredients") or []
            if ingredient.get("name")
        }
        (
            estimated_cost,
            estimated_currency,
            estimated_confidence,
            estimated_debug,
        ) = estimate_recipe_cost(
            ingredient_names,
            ingredient_measures=ingredient_measures,
        )
        return RecipeCookRead(
            **external_recipe,
            estimated_cost=estimated_cost,
            estimated_cost_currency=estimated_currency,
            estimated_cost_confidence=estimated_confidence,
            estimated_cost_debug=estimated_debug,
        )

    raise HTTPException(status_code=400, detail="Invalid source. Use 'local' or 'themealdb'.")


@router.post("", response_model=RecipeRead, status_code=201)
def create_recipe(
    payload: RecipeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Recipe:
    payload_data = payload.model_dump()
    payload_data["cuisine"] = _normalized_cuisine(payload_data.get("cuisine"))

    recipe = Recipe(owner_id=current_user.id, **payload_data)
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


@router.get("/{recipe_id}", response_model=RecipeRead)
def get_recipe(recipe_id: int, db: Session = Depends(get_db)) -> Recipe:
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@router.put("/{recipe_id}", response_model=RecipeRead)
def update_recipe(
    recipe_id: int,
    payload: RecipeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Recipe:
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if recipe.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the recipe owner can update this recipe")

    updated_data = payload.model_dump(exclude_unset=True)
    if "cuisine" in updated_data:
        updated_data["cuisine"] = _normalized_cuisine(updated_data.get("cuisine"))

    for key, value in updated_data.items():
        setattr(recipe, key, value)

    db.commit()
    db.refresh(recipe)
    return recipe


@router.delete("/{recipe_id}", status_code=204)
def delete_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if recipe.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the recipe owner can delete this recipe")

    db.delete(recipe)
    db.commit()


@router.post("/{recipe_id}/ratings", response_model=RatingRead)
def rate_recipe(
    recipe_id: int,
    payload: RatingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeRating:
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")

    existing = (
        db.query(RecipeRating)
        .filter(RecipeRating.user_id == current_user.id, RecipeRating.recipe_id == recipe_id)
        .first()
    )

    if existing is None:
        rating = RecipeRating(
            user_id=current_user.id,
            recipe_id=recipe_id,
            score=payload.score,
            comment=payload.comment,
        )
        db.add(rating)
    else:
        existing.score = payload.score
        existing.comment = payload.comment
        rating = existing

    db.flush()

    average_score = (
        db.query(func.avg(RecipeRating.score)).filter(RecipeRating.recipe_id == recipe_id).scalar()
    )
    recipe.average_rating = round(float(average_score if average_score is not None else payload.score), 2)

    db.commit()
    db.refresh(rating)
    return rating
