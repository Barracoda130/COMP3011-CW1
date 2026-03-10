from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.external_rating import ExternalRecipeRating
from app.models.rating import RecipeRating
from app.models.recipe import Recipe
from app.models.user import User
from app.models.weekly_plan import WeeklyPlan, WeeklyPlanItem
from app.schemas.weekly_plan import WeeklyPlanRead, WeeklyPlanSelectionUpdate
from app.services.themealdb import get_themealdb_recipe_by_id, search_themealdb_recipes

router = APIRouter()


@dataclass
class PlanCandidate:
    source: str
    recipe_id: int | None
    external_recipe_id: str | None
    title: str
    cuisine: str
    prep_minutes: int | None
    calories: int | None
    tags: list[str]
    ingredients: list[str]
    base_score: float


def _candidate_key(candidate: PlanCandidate) -> str:
    if candidate.source == "local" and candidate.recipe_id is not None:
        return f"local:{candidate.recipe_id}"
    if candidate.source == "themealdb" and candidate.external_recipe_id:
        return f"themealdb:{candidate.external_recipe_id}"
    return f"{candidate.source}:{candidate.title.strip().lower()}"


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z]", "", value.lower()).strip()


def _main_ingredient(ingredients: list[str]) -> str:
    if not ingredients:
        return "unknown"

    line = ingredients[0].lower()
    line = re.sub(r"^\s*\d+[\d\s\./-]*", "", line)
    tokens = [_normalize_token(token) for token in re.split(r"\s+", line) if token.strip()]
    stopwords = {
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
    }
    meaningful = [token for token in tokens if token and token not in stopwords]
    return meaningful[0] if meaningful else "unknown"


def _build_candidates_for_user(db: Session, current_user: User) -> list[PlanCandidate]:
    ratings = db.query(RecipeRating).filter(RecipeRating.user_id == current_user.id).all()
    external_ratings = (
        db.query(ExternalRecipeRating)
        .filter(
            ExternalRecipeRating.user_id == current_user.id,
            ExternalRecipeRating.source == "themealdb",
        )
        .all()
    )

    liked_recipe_ids = [rating.recipe_id for rating in ratings if rating.score >= 4]
    disliked_recipe_ids = [rating.recipe_id for rating in ratings if rating.score <= 2]

    liked_cuisines: Counter[str] = Counter()
    liked_tags: Counter[str] = Counter()
    liked_ingredients: Counter[str] = Counter()
    disliked_tags: Counter[str] = Counter()
    disliked_ingredients: Counter[str] = Counter()
    liked_external_ids: set[str] = set()
    disliked_external_ids: set[str] = set()

    if ratings:
        recipe_ids = [rating.recipe_id for rating in ratings]
        rated_recipes = db.query(Recipe).filter(Recipe.id.in_(recipe_ids)).all()
        rated_map = {recipe.id: recipe for recipe in rated_recipes}

        for rating in ratings:
            recipe = rated_map.get(rating.recipe_id)
            if recipe is None:
                continue

            cuisine = (recipe.cuisine or "Unknown").strip()
            tags = recipe.tags or []
            ingredients = recipe.ingredients or []
            main_ing = _main_ingredient(ingredients)

            if rating.score >= 4:
                liked_cuisines[cuisine] += 1
                for tag in tags:
                    liked_tags[tag.lower()] += 1
                liked_ingredients[main_ing] += 1
            elif rating.score <= 2:
                for tag in tags:
                    disliked_tags[tag.lower()] += 1
                disliked_ingredients[main_ing] += 1

    for rating in external_ratings:
        external_id = (rating.external_recipe_id or "").strip()
        if not external_id:
            continue

        if rating.score >= 4:
            liked_external_ids.add(external_id)
        elif rating.score <= 2:
            disliked_external_ids.add(external_id)

        external_recipe = get_themealdb_recipe_by_id(external_id)
        if not external_recipe:
            continue

        cuisine = (external_recipe.get("cuisine") or "Unknown").strip() or "Unknown"
        tags = [str(tag).strip() for tag in (external_recipe.get("tags") or []) if str(tag).strip()]
        ingredients = [
            str(ingredient.get("name") or "").strip()
            for ingredient in (external_recipe.get("ingredients") or [])
            if str(ingredient.get("name") or "").strip()
        ]
        main_ing = _main_ingredient(ingredients)

        if rating.score >= 4:
            liked_cuisines[cuisine] += 1
            for tag in tags:
                liked_tags[tag.lower()] += 1
            liked_ingredients[main_ing] += 1
        elif rating.score <= 2:
            for tag in tags:
                disliked_tags[tag.lower()] += 1
            disliked_ingredients[main_ing] += 1

    all_recipes = db.query(Recipe).all()
    candidates: list[PlanCandidate] = []
    for recipe in all_recipes:
        if recipe.id in disliked_recipe_ids:
            continue

        cuisine = (recipe.cuisine or "Unknown").strip()
        tags = recipe.tags or []
        ingredients = recipe.ingredients or []
        main_ing = _main_ingredient(ingredients)

        score = 0.0
        score += float(liked_cuisines.get(cuisine, 0)) * 1.8
        score += float(sum(liked_tags.get(tag.lower(), 0) for tag in tags)) * 0.9
        score -= float(sum(disliked_tags.get(tag.lower(), 0) for tag in tags)) * 1.1
        score += float(liked_ingredients.get(main_ing, 0)) * 1.2
        score -= float(disliked_ingredients.get(main_ing, 0)) * 1.5

        if recipe.id in liked_recipe_ids:
            score -= 2.5

        if recipe.average_rating is not None:
            score += float(recipe.average_rating) * 0.15

        candidates.append(
            PlanCandidate(
                source="local",
                recipe_id=recipe.id,
                external_recipe_id=None,
                title=recipe.title,
                cuisine=cuisine,
                prep_minutes=recipe.prep_minutes,
                calories=recipe.calories,
                tags=tags,
                ingredients=ingredients,
                base_score=score,
            )
        )

    query_terms: list[str] = []
    query_terms.extend([item for item, _count in liked_cuisines.most_common(3)])
    query_terms.extend([item for item, _count in liked_tags.most_common(4)])
    query_terms.extend([item for item, _count in liked_ingredients.most_common(4) if item != "unknown"])
    if not query_terms:
        query_terms = ["chicken", "beef", "vegetarian", "pasta", "rice"]

    deduped_terms: list[str] = []
    seen_terms: set[str] = set()
    for term in query_terms:
        normalized = term.strip().lower()
        if not normalized or normalized in seen_terms:
            continue
        seen_terms.add(normalized)
        deduped_terms.append(term)

    external_candidates_by_id: dict[str, PlanCandidate] = {}
    for term in deduped_terms[:6]:
        external_items = search_themealdb_recipes(query=term, limit=20)
        for item in external_items:
            external_id = str(item.get("external_id") or "").strip()
            if not external_id:
                continue
            if external_id in disliked_external_ids:
                continue
            if external_id in external_candidates_by_id:
                continue

            cuisine = (item.get("cuisine") or "Unknown").strip() or "Unknown"
            tags = [str(tag).strip() for tag in (item.get("tags") or []) if str(tag).strip()]
            ingredients = [
                str(ingredient).strip()
                for ingredient in (item.get("key_ingredients") or [])
                if str(ingredient).strip()
            ]
            main_ing = _main_ingredient(ingredients)

            score = 0.0
            score += float(liked_cuisines.get(cuisine, 0)) * 1.8
            score += float(sum(liked_tags.get(tag.lower(), 0) for tag in tags)) * 0.9
            score -= float(sum(disliked_tags.get(tag.lower(), 0) for tag in tags)) * 1.1
            score += float(liked_ingredients.get(main_ing, 0)) * 1.2
            score -= float(disliked_ingredients.get(main_ing, 0)) * 1.5

            if external_id in liked_external_ids:
                score -= 2.5

            external_candidates_by_id[external_id] = PlanCandidate(
                source="themealdb",
                recipe_id=None,
                external_recipe_id=external_id,
                title=str(item.get("title") or "Untitled"),
                cuisine=cuisine,
                prep_minutes=item.get("prep_minutes"),
                calories=item.get("calories"),
                tags=tags,
                ingredients=ingredients,
                base_score=score,
            )

    candidates.extend(external_candidates_by_id.values())

    candidates.sort(key=lambda item: item.base_score, reverse=True)
    return candidates


def _day_adjusted_score(
    day_index: int,
    candidate: PlanCandidate,
    cuisine_counts: dict[str, int],
    previous_main_ingredient: str | None,
) -> float:
    score = candidate.base_score
    cuisine_count = cuisine_counts.get(candidate.cuisine, 0)

    if cuisine_count >= 2:
        score -= 6.0

    main_ing = _main_ingredient(candidate.ingredients)
    if previous_main_ingredient and main_ing != "unknown" and main_ing == previous_main_ingredient:
        score -= 8.0

    # Weekday quick-meal bias (Mon-Fri) where day indices 0-4 should prefer quick meals.
    prep_minutes = candidate.prep_minutes
    if day_index <= 4:
        if prep_minutes is not None and prep_minutes <= 35:
            score += 2.5
        elif prep_minutes is not None and prep_minutes >= 50:
            score -= 1.8
    else:
        # Weekend treat/flexible behavior: allow longer cook times and slightly richer meals.
        if prep_minutes is not None and prep_minutes >= 30:
            score += 1.4
        if candidate.calories is not None and candidate.calories >= 650:
            score += 0.6

    return score


def _build_week_plan(candidates: list[PlanCandidate], days: int = 7) -> list[PlanCandidate]:
    selected: list[PlanCandidate] = []
    cuisine_counts: dict[str, int] = defaultdict(int)
    used_candidate_keys: set[str] = set()
    previous_main_ingredient: str | None = None

    def _pick_best(
        *,
        day_index: int,
        strict_constraints: bool,
        allow_repeat: bool,
    ) -> PlanCandidate | None:
        best: PlanCandidate | None = None
        best_score = float("-inf")

        for candidate in candidates:
            candidate_key = _candidate_key(candidate)
            if not allow_repeat and candidate_key in used_candidate_keys:
                continue

            if strict_constraints:
                if cuisine_counts.get(candidate.cuisine, 0) >= 2:
                    continue

                main_ing = _main_ingredient(candidate.ingredients)
                if (
                    previous_main_ingredient
                    and previous_main_ingredient != "unknown"
                    and main_ing != "unknown"
                    and main_ing == previous_main_ingredient
                ):
                    continue

            adjusted = _day_adjusted_score(
                day_index=day_index,
                candidate=candidate,
                cuisine_counts=cuisine_counts,
                previous_main_ingredient=previous_main_ingredient,
            )
            if adjusted > best_score:
                best = candidate
                best_score = adjusted

        return best

    for day_index in range(days):
        # First pass: enforce hard constraints where possible.
        best = _pick_best(day_index=day_index, strict_constraints=True, allow_repeat=False)

        # Fallback: if constraints are too tight for available data, pick best remaining recipe.
        if best is None:
            best = _pick_best(day_index=day_index, strict_constraints=False, allow_repeat=False)

        # Last fallback: permit reuse if source pool is smaller than requested days.
        if best is None:
            best = _pick_best(day_index=day_index, strict_constraints=False, allow_repeat=True)

        if best is None:
            break

        selected.append(best)
        used_candidate_keys.add(_candidate_key(best))
        cuisine_counts[best.cuisine] += 1
        previous_main_ingredient = _main_ingredient(best.ingredients)

    return selected


@router.post("/me/weekly-plan/generate", response_model=WeeklyPlanRead)
def generate_weekly_plan(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeeklyPlan:
    candidates = _build_candidates_for_user(db, current_user)
    if not candidates:
        raise HTTPException(status_code=400, detail="No recipes available to generate a weekly plan")

    local_candidates = [candidate for candidate in candidates if candidate.source == "local"]
    external_candidates = [candidate for candidate in candidates if candidate.source == "themealdb"]

    if not local_candidates:
        raise HTTPException(status_code=400, detail="No local recipes available to generate plan choices")
    if not external_candidates:
        raise HTTPException(status_code=400, detail="No ThemealDB recipes available to generate plan choices")

    local_selected = _build_week_plan(local_candidates, days=7)
    external_selected = _build_week_plan(external_candidates, days=7)
    if not local_selected or not external_selected:
        raise HTTPException(status_code=400, detail="Could not generate a weekly plan from available recipes")

    start_date = date.today()
    end_date = start_date + timedelta(days=6)

    # Archive previous active plans for this user.
    existing_active = (
        db.query(WeeklyPlan)
        .filter(WeeklyPlan.user_id == current_user.id, WeeklyPlan.status == "active")
        .all()
    )
    for plan in existing_active:
        plan.status = "archived"

    plan = WeeklyPlan(
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        status="active",
    )
    db.add(plan)
    db.flush()

    for day_index in range(7):
        local_candidate = local_selected[min(day_index, len(local_selected) - 1)]
        external_candidate = external_selected[min(day_index, len(external_selected) - 1)]
        planned_for = start_date + timedelta(days=day_index)

        db.add(
            WeeklyPlanItem(
                weekly_plan_id=plan.id,
                day_index=day_index,
                planned_for=planned_for,
                recipe_source="local",
                recipe_id=local_candidate.recipe_id,
                external_recipe_id=None,
                title_snapshot=local_candidate.title,
                is_selected=False,
            )
        )
        db.add(
            WeeklyPlanItem(
                weekly_plan_id=plan.id,
                day_index=day_index,
                planned_for=planned_for,
                recipe_source="themealdb",
                recipe_id=None,
                external_recipe_id=external_candidate.external_recipe_id,
                title_snapshot=external_candidate.title,
                is_selected=False,
            )
        )

    db.commit()
    db.refresh(plan)
    return plan


@router.get("/me/weekly-plan/current", response_model=WeeklyPlanRead)
def get_current_weekly_plan(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeeklyPlan:
    plan = (
        db.query(WeeklyPlan)
        .filter(WeeklyPlan.user_id == current_user.id, WeeklyPlan.status == "active")
        .order_by(WeeklyPlan.created_at.desc())
        .first()
    )

    if plan is None:
        raise HTTPException(status_code=404, detail="No active weekly plan found")

    return plan


@router.post("/me/weekly-plan/current/select", response_model=WeeklyPlanRead)
def select_weekly_plan_option(
    payload: WeeklyPlanSelectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeeklyPlan:
    source = payload.recipe_source.strip().lower()
    if source not in {"local", "themealdb"}:
        raise HTTPException(status_code=400, detail="recipe_source must be 'local' or 'themealdb'")

    plan = (
        db.query(WeeklyPlan)
        .filter(WeeklyPlan.user_id == current_user.id, WeeklyPlan.status == "active")
        .order_by(WeeklyPlan.created_at.desc())
        .first()
    )

    if plan is None:
        raise HTTPException(status_code=404, detail="No active weekly plan found")

    day_items = (
        db.query(WeeklyPlanItem)
        .filter(WeeklyPlanItem.weekly_plan_id == plan.id, WeeklyPlanItem.day_index == payload.day_index)
        .all()
    )
    if not day_items:
        raise HTTPException(status_code=404, detail="No plan options found for selected day")

    has_target = False
    for item in day_items:
        item.is_selected = item.recipe_source == source
        if item.recipe_source == source:
            has_target = True

    if not has_target:
        raise HTTPException(status_code=404, detail="Requested option source is not available for that day")

    db.commit()
    db.refresh(plan)
    return plan
