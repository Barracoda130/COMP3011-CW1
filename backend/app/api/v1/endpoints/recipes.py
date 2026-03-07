from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.schemas.recipe import RecipeCreate, RecipeRead, RecipeUpdate

router = APIRouter()

RECIPES: list[RecipeRead] = []


@router.get("", response_model=Sequence[RecipeRead])
def list_recipes(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Sequence[RecipeRead]:
    return RECIPES[skip : skip + limit]


@router.post("", response_model=RecipeRead, status_code=201)
def create_recipe(payload: RecipeCreate) -> RecipeRead:
    recipe = RecipeRead(id=len(RECIPES) + 1, **payload.model_dump())
    RECIPES.append(recipe)
    return recipe


@router.get("/{recipe_id}", response_model=RecipeRead)
def get_recipe(recipe_id: int) -> RecipeRead:
    recipe = next((item for item in RECIPES if item.id == recipe_id), None)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@router.put("/{recipe_id}", response_model=RecipeRead)
def update_recipe(recipe_id: int, payload: RecipeUpdate) -> RecipeRead:
    index = next((idx for idx, item in enumerate(RECIPES) if item.id == recipe_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Recipe not found")

    current = RECIPES[index]
    updated_data = payload.model_dump(exclude_unset=True)
    updated_recipe = current.model_copy(update=updated_data)
    RECIPES[index] = updated_recipe
    return updated_recipe


@router.delete("/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int) -> None:
    index = next((idx for idx, item in enumerate(RECIPES) if item.id == recipe_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    RECIPES.pop(index)
