from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.rating import RecipeRating
from app.models.recipe import Recipe
from app.models.user import User
from app.schemas.recipe import RecipeCreate, RecipeRead, RecipeUpdate
from app.schemas.rating import RatingCreate, RatingRead

router = APIRouter()


@router.get("", response_model=list[RecipeRead])
def list_recipes(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    db: Session = Depends(get_db),
) -> list[Recipe]:
    return db.query(Recipe).offset(skip).limit(limit).all()


@router.post("", response_model=RecipeRead, status_code=201)
def create_recipe(
    payload: RecipeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Recipe:
    recipe = Recipe(owner_id=current_user.id, **payload.model_dump())
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
