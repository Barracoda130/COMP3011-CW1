from app.schemas.recipe import RecipeRead


def score_recipe_for_user(recipe: RecipeRead, preferred_cuisines: set[str]) -> float:
    score = 0.0

    if recipe.cuisine in preferred_cuisines:
        score += 0.3

    if "quick" in recipe.tags and recipe.prep_minutes <= 30:
        score += 0.2

    if recipe.calories is not None and 350 <= recipe.calories <= 750:
        score += 0.15

    return round(score, 3)
