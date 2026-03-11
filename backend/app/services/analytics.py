from __future__ import annotations

import re
from collections import Counter
from statistics import median

from sqlalchemy.orm import Session

from app.models.external_rating import ExternalRecipeRating
from app.models.rating import RecipeRating
from app.models.recipe import Recipe
from app.models.suggestion_cache import UserSuggestionCache
from app.models.user import User
from app.models.weekly_plan import WeeklyPlan, WeeklyPlanItem
from app.schemas.analytics import (
    AnalyticsRange,
    AnalyticsSummaryRead,
    DistributionItemRead,
    PreferenceItemRead,
    PreferenceListRead,
    QuickMealWeekdayComplianceRead,
    RecommendationExplanationSummaryRead,
    RepeatedIngredientItemRead,
    TasteProfileRead,
    TasteProfileSummaryRead,
    WeeklyCalorieAnalyticsRead,
    WeeklyPlanAnalyticsRead,
    WeeklyNutritionSummaryRead,
    WeeklyPlanDiversityRead,
)
from app.services.themealdb import get_themealdb_recipe_by_id

_STOPWORDS = {
    "cup",
    "cups",
    "tbsp",
    "tsp",
    "teaspoon",
    "teaspoons",
    "tablespoon",
    "tablespoons",
    "gram",
    "grams",
    "kg",
    "ml",
    "l",
    "oz",
    "lb",
    "small",
    "medium",
    "large",
    "fresh",
    "chopped",
    "sliced",
    "diced",
    "of",
}


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z]", "", value.lower()).strip()


def _main_ingredient(ingredients: list[str]) -> str:
    if not ingredients:
        return "unknown"

    line = ingredients[0].lower()
    line = re.sub(r"^\s*\d+[\d\s\./-]*", "", line)
    tokens = [_normalize_token(token) for token in re.split(r"\s+", line) if token.strip()]
    filtered = [token for token in tokens if token and token not in _STOPWORDS]
    return filtered[0] if filtered else "unknown"


def _ingredient_keywords(ingredients: list[str]) -> list[str]:
    tokens: list[str] = []
    for ingredient in ingredients:
        for token in re.split(r"\s+", ingredient.lower()):
            normalized = _normalize_token(token)
            if not normalized or normalized in _STOPWORDS:
                continue
            tokens.append(normalized)
    return tokens


def _counter_top_names(counter: Counter[str], *, limit: int) -> list[str]:
    entries = [(name, count) for name, count in counter.items() if name and name != "unknown"]
    entries.sort(key=lambda entry: (-entry[1], entry[0]))
    return [name for name, _count in entries[: max(limit, 1)]]


def _to_preference_list(counter: Counter[str], *, limit: int) -> PreferenceListRead:
    items: list[PreferenceItemRead] = []
    for name, count in counter.most_common(max(limit, 1)):
        if not name or name == "unknown":
            continue
        items.append(PreferenceItemRead(name=name, score=float(count)))
    return PreferenceListRead(items=items)


def _build_range(values: list[int], *, quick_upper: int = 25, balanced_upper: int = 45) -> AnalyticsRange:
    if not values:
        return AnalyticsRange()

    min_value = min(values)
    max_value = max(values)
    median_value = int(median(values))

    if median_value <= quick_upper:
        label = "quick"
    elif median_value <= balanced_upper:
        label = "balanced"
    else:
        label = "slow"

    return AnalyticsRange(min=min_value, max=max_value, median=median_value, label=label)


def _build_calorie_range(values: list[int]) -> AnalyticsRange:
    if not values:
        return AnalyticsRange()

    min_value = min(values)
    max_value = max(values)
    median_value = int(median(values))

    if median_value <= 450:
        label = "light"
    elif median_value <= 700:
        label = "moderate"
    else:
        label = "hearty"

    return AnalyticsRange(min=min_value, max=max_value, median=median_value, label=label)


def get_taste_profile(db: Session, user: User) -> TasteProfileRead:
    local_ratings = db.query(RecipeRating).filter(RecipeRating.user_id == user.id).all()
    external_ratings = (
        db.query(ExternalRecipeRating)
        .filter(ExternalRecipeRating.user_id == user.id, ExternalRecipeRating.source == "themealdb")
        .all()
    )

    local_ids = [rating.recipe_id for rating in local_ratings]
    local_lookup = {recipe.id: recipe for recipe in db.query(Recipe).filter(Recipe.id.in_(local_ids)).all()} if local_ids else {}

    liked_cuisines: Counter[str] = Counter()
    liked_tags: Counter[str] = Counter()
    liked_ingredients: Counter[str] = Counter()
    disliked_ingredients: Counter[str] = Counter()
    liked_prep_minutes: list[int] = []
    liked_calories: list[int] = []

    for rating in local_ratings:
        recipe = local_lookup.get(rating.recipe_id)
        if recipe is None:
            continue

        ingredient_tokens = _ingredient_keywords(recipe.ingredients or [])
        if rating.score >= 4:
            liked_cuisines[(recipe.cuisine or "Unknown").strip() or "Unknown"] += 1
            for tag in recipe.tags or []:
                normalized_tag = str(tag).strip().lower()
                if normalized_tag:
                    liked_tags[normalized_tag] += 1
            for token in ingredient_tokens:
                liked_ingredients[token] += 1
            if recipe.prep_minutes is not None:
                liked_prep_minutes.append(int(recipe.prep_minutes))
            if recipe.calories is not None:
                liked_calories.append(int(recipe.calories))
        elif rating.score <= 2:
            for token in ingredient_tokens:
                disliked_ingredients[token] += 1

    for rating in external_ratings:
        external_id = (rating.external_recipe_id or "").strip()
        if not external_id:
            continue
        recipe = _load_external_recipe(external_id)
        if recipe is None:
            continue

        ingredient_names = [
            str(item.get("name") or "").strip()
            for item in recipe.get("ingredients", [])
            if str(item.get("name") or "").strip()
        ]
        ingredient_tokens = _ingredient_keywords(ingredient_names)

        if rating.score >= 4:
            liked_cuisines[(str(recipe.get("cuisine") or "Unknown").strip() or "Unknown")] += 1
            for tag in recipe.get("tags", []) or []:
                normalized_tag = str(tag).strip().lower()
                if normalized_tag:
                    liked_tags[normalized_tag] += 1
            for token in ingredient_tokens:
                liked_ingredients[token] += 1
            prep_minutes = _as_int(recipe.get("prep_minutes"))
            calories = _as_int(recipe.get("calories"))
            if prep_minutes is not None:
                liked_prep_minutes.append(prep_minutes)
            if calories is not None:
                liked_calories.append(calories)
        elif rating.score <= 2:
            for token in ingredient_tokens:
                disliked_ingredients[token] += 1

    prep_band = _build_range(liked_prep_minutes).label
    calorie_band = _build_calorie_range(liked_calories).label
    total_ratings = len(local_ratings) + len(external_ratings)
    confidence = min(1.0, round(total_ratings / 10.0, 3)) if total_ratings else 0.0

    return TasteProfileRead(
        total_ratings=total_ratings,
        favourite_cuisines=_counter_top_names(liked_cuisines, limit=5),
        favourite_tags=_counter_top_names(liked_tags, limit=8),
        favourite_ingredients=_counter_top_names(liked_ingredients, limit=8),
        disliked_ingredients=_counter_top_names(disliked_ingredients, limit=8),
        preferred_prep_time_band=prep_band,
        preferred_calorie_band=calorie_band,
        confidence=confidence,
    )


def _active_plan_for_user(db: Session, user_id: int) -> WeeklyPlan | None:
    return (
        db.query(WeeklyPlan)
        .filter(WeeklyPlan.user_id == user_id, WeeklyPlan.status == "active")
        .order_by(WeeklyPlan.created_at.desc())
        .first()
    )


def _plan_items_for_analytics(db: Session, plan_id: int) -> list[WeeklyPlanItem]:
    day_items = db.query(WeeklyPlanItem).filter(WeeklyPlanItem.weekly_plan_id == plan_id).all()
    selected = [item for item in day_items if item.is_selected]
    return selected if selected else day_items


def _load_external_recipe(external_id: str) -> dict | None:
    try:
        return get_themealdb_recipe_by_id(external_id)
    except Exception:
        return None


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(float(stripped))
        except ValueError:
            return None
    return None


def get_taste_profile_summary(db: Session, user: User) -> TasteProfileSummaryRead:
    local_ratings = db.query(RecipeRating).filter(RecipeRating.user_id == user.id).all()
    external_ratings = (
        db.query(ExternalRecipeRating)
        .filter(ExternalRecipeRating.user_id == user.id, ExternalRecipeRating.source == "themealdb")
        .all()
    )
    all_scores = [rating.score for rating in local_ratings] + [rating.score for rating in external_ratings]

    liked = sum(1 for score in all_scores if score >= 4)
    neutral = sum(1 for score in all_scores if score == 3)
    disliked = sum(1 for score in all_scores if score <= 2)
    total = len(all_scores)

    confidence = min(1.0, round(total / 10.0, 3)) if total else 0.0

    return TasteProfileSummaryRead(
        total_ratings=total,
        local_ratings=len(local_ratings),
        external_ratings=len(external_ratings),
        liked_ratings=liked,
        neutral_ratings=neutral,
        disliked_ratings=disliked,
        confidence=confidence,
    )


def _liked_recipes(db: Session, user_id: int) -> tuple[list[Recipe], list[dict]]:
    local_liked = db.query(RecipeRating).filter(RecipeRating.user_id == user_id, RecipeRating.score >= 4).all()
    local_ids = [rating.recipe_id for rating in local_liked]
    local_recipes = db.query(Recipe).filter(Recipe.id.in_(local_ids)).all() if local_ids else []

    external_liked = (
        db.query(ExternalRecipeRating)
        .filter(
            ExternalRecipeRating.user_id == user_id,
            ExternalRecipeRating.source == "themealdb",
            ExternalRecipeRating.score >= 4,
        )
        .all()
    )
    external_recipes: list[dict] = []
    for rating in external_liked:
        if not rating.external_recipe_id:
            continue
        recipe = _load_external_recipe(rating.external_recipe_id.strip())
        if recipe:
            external_recipes.append(recipe)

    return local_recipes, external_recipes


def get_favourite_cuisines(db: Session, user: User, *, limit: int = 5) -> PreferenceListRead:
    local_recipes, external_recipes = _liked_recipes(db, user.id)
    counts: Counter[str] = Counter()

    for recipe in local_recipes:
        cuisine = (recipe.cuisine or "Unknown").strip() or "Unknown"
        counts[cuisine] += 1

    for recipe in external_recipes:
        cuisine = str(recipe.get("cuisine") or "Unknown").strip() or "Unknown"
        counts[cuisine] += 1

    return _to_preference_list(counts, limit=limit)


def get_favourite_ingredients(db: Session, user: User, *, limit: int = 8) -> PreferenceListRead:
    local_recipes, external_recipes = _liked_recipes(db, user.id)
    counts: Counter[str] = Counter()

    for recipe in local_recipes:
        main_ing = _main_ingredient(recipe.ingredients or [])
        counts[main_ing] += 1

    for recipe in external_recipes:
        ingredients = [
            str(item.get("name") or "").strip()
            for item in recipe.get("ingredients", [])
            if str(item.get("name") or "").strip()
        ]
        counts[_main_ingredient(ingredients)] += 1

    return _to_preference_list(counts, limit=limit)


def get_preferred_prep_time_range(db: Session, user: User) -> AnalyticsRange:
    local_recipes, external_recipes = _liked_recipes(db, user.id)
    values: list[int] = [recipe.prep_minutes for recipe in local_recipes if recipe.prep_minutes is not None]
    for recipe in external_recipes:
        prep_minutes = _as_int(recipe.get("prep_minutes"))
        if prep_minutes is not None:
            values.append(prep_minutes)
    return _build_range(values)


def get_preferred_calorie_range(db: Session, user: User) -> AnalyticsRange:
    local_recipes, external_recipes = _liked_recipes(db, user.id)
    values: list[int] = [recipe.calories for recipe in local_recipes if recipe.calories is not None]
    for recipe in external_recipes:
        calories = _as_int(recipe.get("calories"))
        if calories is not None:
            values.append(calories)
    return _build_calorie_range(values)


def get_weekly_plan_diversity_score(db: Session, user: User) -> WeeklyPlanDiversityRead:
    plan = _active_plan_for_user(db, user.id)
    if plan is None:
        return WeeklyPlanDiversityRead(
            diversity_score=0.0,
            total_items=0,
            unique_cuisines=0,
            unique_main_ingredients=0,
            source_balance=0.0,
        )

    items = _plan_items_for_analytics(db, plan.id)
    if not items:
        return WeeklyPlanDiversityRead(
            diversity_score=0.0,
            total_items=0,
            unique_cuisines=0,
            unique_main_ingredients=0,
            source_balance=0.0,
        )

    cuisines: set[str] = set()
    main_ingredients: set[str] = set()
    source_counts: Counter[str] = Counter()

    local_ids = [item.recipe_id for item in items if item.recipe_source == "local" and item.recipe_id is not None]
    local_lookup = {recipe.id: recipe for recipe in db.query(Recipe).filter(Recipe.id.in_(local_ids)).all()} if local_ids else {}

    for item in items:
        source_counts[item.recipe_source] += 1
        if item.recipe_source == "local":
            if item.recipe_id is None:
                cuisines.add("Unknown")
                main_ingredients.add("unknown")
                continue
            recipe = local_lookup.get(item.recipe_id)
            if recipe:
                cuisines.add((recipe.cuisine or "Unknown").strip() or "Unknown")
                main_ingredients.add(_main_ingredient(recipe.ingredients or []))
                continue
        if item.recipe_source == "themealdb" and item.external_recipe_id:
            external_recipe = _load_external_recipe(item.external_recipe_id)
            if external_recipe:
                cuisines.add((str(external_recipe.get("cuisine") or "Unknown").strip() or "Unknown"))
                ingredients = [
                    str(entry.get("name") or "").strip()
                    for entry in external_recipe.get("ingredients", [])
                    if str(entry.get("name") or "").strip()
                ]
                main_ingredients.add(_main_ingredient(ingredients))
                continue

        cuisines.add("Unknown")
        main_ingredients.add("unknown")

    total_items = len(items)
    cuisine_diversity = len(cuisines) / total_items
    ingredient_diversity = len(main_ingredients) / total_items
    local_count = source_counts.get("local", 0)
    external_count = source_counts.get("themealdb", 0)
    source_balance = 1.0 - (abs(local_count - external_count) / total_items)

    score = 100.0 * ((0.5 * cuisine_diversity) + (0.3 * ingredient_diversity) + (0.2 * source_balance))

    return WeeklyPlanDiversityRead(
        diversity_score=round(score, 2),
        total_items=total_items,
        unique_cuisines=len(cuisines),
        unique_main_ingredients=len(main_ingredients),
        source_balance=round(source_balance, 3),
    )


def get_weekly_nutrition_summary(db: Session, user: User) -> WeeklyNutritionSummaryRead:
    plan = _active_plan_for_user(db, user.id)
    if plan is None:
        return WeeklyNutritionSummaryRead(total_items=0, items_with_calories=0, total_calories=0)

    items = _plan_items_for_analytics(db, plan.id)
    if not items:
        return WeeklyNutritionSummaryRead(total_items=0, items_with_calories=0, total_calories=0)

    calories: list[int] = []
    local_ids = [item.recipe_id for item in items if item.recipe_source == "local" and item.recipe_id is not None]
    local_lookup = {recipe.id: recipe for recipe in db.query(Recipe).filter(Recipe.id.in_(local_ids)).all()} if local_ids else {}

    for item in items:
        if item.recipe_source == "local":
            if item.recipe_id is None:
                continue
            recipe = local_lookup.get(item.recipe_id)
            if recipe and recipe.calories is not None:
                calories.append(int(recipe.calories))
            continue

        if item.recipe_source == "themealdb" and item.external_recipe_id:
            external_recipe = _load_external_recipe(item.external_recipe_id)
            external_calories = _as_int(external_recipe.get("calories") if external_recipe else None)
            if external_calories is not None:
                calories.append(external_calories)

    if not calories:
        return WeeklyNutritionSummaryRead(total_items=len(items), items_with_calories=0, total_calories=0)

    total_calories = int(sum(calories))
    return WeeklyNutritionSummaryRead(
        total_items=len(items),
        items_with_calories=len(calories),
        total_calories=total_calories,
        average_calories=int(total_calories / len(calories)),
        min_calories=min(calories),
        max_calories=max(calories),
    )


def get_weekly_plan_analytics(db: Session, user: User) -> WeeklyPlanAnalyticsRead:
    plan = _active_plan_for_user(db, user.id)
    if plan is None:
        return WeeklyPlanAnalyticsRead(
            status="no-active-plan",
            total_items=0,
            cuisine_distribution=[],
            repeated_ingredients=[],
            quick_meal_weekday_compliance=QuickMealWeekdayComplianceRead(
                quick_threshold_minutes=35,
                weekday_items=0,
                items_with_prep=0,
                compliant_items=0,
                compliance_rate=0.0,
            ),
            calorie_summary=WeeklyCalorieAnalyticsRead(total_items=0, items_with_calories=0, total_calories=0),
            diversity=WeeklyPlanDiversityRead(
                diversity_score=0.0,
                total_items=0,
                unique_cuisines=0,
                unique_main_ingredients=0,
                source_balance=0.0,
            ),
        )

    items = _plan_items_for_analytics(db, plan.id)
    total_items = len(items)

    local_ids = [item.recipe_id for item in items if item.recipe_source == "local" and item.recipe_id is not None]
    local_lookup = (
        {recipe.id: recipe for recipe in db.query(Recipe).filter(Recipe.id.in_(local_ids)).all()}
        if local_ids
        else {}
    )

    cuisine_counter: Counter[str] = Counter()
    ingredient_counter: Counter[str] = Counter()
    weekday_items = 0
    items_with_prep = 0
    compliant_items = 0
    calories: list[int] = []

    for item in items:
        cuisine = "Unknown"
        ingredients: list[str] = []
        prep_minutes: int | None = None
        calories_value: int | None = None

        if item.recipe_source == "local" and item.recipe_id is not None:
            recipe = local_lookup.get(item.recipe_id)
            if recipe is not None:
                cuisine = (recipe.cuisine or "Unknown").strip() or "Unknown"
                ingredients = recipe.ingredients or []
                prep_minutes = recipe.prep_minutes
                calories_value = recipe.calories
        elif item.recipe_source == "themealdb" and item.external_recipe_id:
            external = _load_external_recipe(item.external_recipe_id)
            if external is not None:
                cuisine = (str(external.get("cuisine") or "Unknown").strip() or "Unknown")
                ingredients = [
                    str(entry.get("name") or "").strip()
                    for entry in external.get("ingredients", [])
                    if str(entry.get("name") or "").strip()
                ]
                prep_minutes = _as_int(external.get("prep_minutes"))
                calories_value = _as_int(external.get("calories"))

        cuisine_counter[cuisine] += 1
        ingredient_counter[_main_ingredient(ingredients)] += 1

        if item.planned_for is not None and item.planned_for.weekday() <= 4:
            weekday_items += 1
            if prep_minutes is not None:
                items_with_prep += 1
                if prep_minutes <= 35:
                    compliant_items += 1

        if calories_value is not None:
            calories.append(calories_value)

    cuisine_distribution = [
        DistributionItemRead(
            name=name,
            count=count,
            percentage=round((count / total_items) * 100.0, 2) if total_items else 0.0,
        )
        for name, count in cuisine_counter.most_common()
    ]

    repeated_ingredients = [
        RepeatedIngredientItemRead(ingredient=name, count=count)
        for name, count in ingredient_counter.items()
        if name != "unknown" and count > 1
    ]
    repeated_ingredients.sort(key=lambda item: (-item.count, item.ingredient))

    calorie_total = int(sum(calories))
    compliance_rate = round((compliant_items / items_with_prep), 3) if items_with_prep else 0.0

    return WeeklyPlanAnalyticsRead(
        status=plan.status,
        start_date=plan.start_date,
        end_date=plan.end_date,
        total_items=total_items,
        cuisine_distribution=cuisine_distribution,
        repeated_ingredients=repeated_ingredients,
        quick_meal_weekday_compliance=QuickMealWeekdayComplianceRead(
            quick_threshold_minutes=35,
            weekday_items=weekday_items,
            items_with_prep=items_with_prep,
            compliant_items=compliant_items,
            compliance_rate=compliance_rate,
        ),
        calorie_summary=WeeklyCalorieAnalyticsRead(
            total_items=total_items,
            items_with_calories=len(calories),
            total_calories=calorie_total,
            average_calories=int(calorie_total / len(calories)) if calories else None,
        ),
        diversity=get_weekly_plan_diversity_score(db, user),
    )


def get_recommendation_explanation_summary(db: Session, user: User, *, limit: int = 5) -> RecommendationExplanationSummaryRead:
    cache_entry = db.query(UserSuggestionCache).filter(UserSuggestionCache.user_id == user.id).first()
    if cache_entry is None:
        return RecommendationExplanationSummaryRead(total_recommendations=0, recommendations_with_reasons=0)

    items_json = cache_entry.items_json or []
    reason_counter: Counter[str] = Counter()
    with_reasons = 0

    for item in items_json:
        reasons = item.get("reasons")
        if not isinstance(reasons, list):
            continue
        clean_reasons = [str(reason).strip() for reason in reasons if isinstance(reason, str) and reason.strip()]
        if not clean_reasons:
            continue
        with_reasons += 1
        for reason in clean_reasons:
            reason_counter[reason] += 1

    top_reasons = [
        PreferenceItemRead(name=reason, score=float(count))
        for reason, count in reason_counter.most_common(max(limit, 1))
    ]

    return RecommendationExplanationSummaryRead(
        total_recommendations=len(items_json),
        recommendations_with_reasons=with_reasons,
        top_reasons=top_reasons,
    )


def build_analytics_summary(db: Session, user: User) -> AnalyticsSummaryRead:
    return AnalyticsSummaryRead(
        taste_profile=get_taste_profile_summary(db, user),
        favourite_cuisines=get_favourite_cuisines(db, user),
        favourite_ingredients=get_favourite_ingredients(db, user),
        preferred_prep_time_range=get_preferred_prep_time_range(db, user),
        preferred_calorie_range=get_preferred_calorie_range(db, user),
        weekly_plan_diversity=get_weekly_plan_diversity_score(db, user),
        weekly_nutrition_summary=get_weekly_nutrition_summary(db, user),
        recommendation_explanation_summary=get_recommendation_explanation_summary(db, user),
    )
