import math
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.external_rating import ExternalRecipeRating
from app.models.rating import RecipeRating
from app.models.recipe import Recipe
from app.models.suggestion_cache import UserSuggestionCache
from app.models.user import User
from app.schemas.recipe import (
    RecipeCookIngredient,
    RecipeCookRead,
    RecipeCreate,
    RecipeDiscoverItem,
    RecipeDiscoverResponse,
    RecipeImportPreview,
    RecipeImportRequest,
    RecipeRatedItem,
    RecipeRatedResponse,
    RecipeRead,
    RecipeSuggestionResponse,
    RecipeUpdate,
)
from app.schemas.rating import ExternalRatingRead, RatingCreate, RatingRead
from app.services.recipe_import import RecipeImportError, extract_recipe_from_url
from app.services.themealdb import get_themealdb_recipe_by_id, search_themealdb_recipes

router = APIRouter()


def _normalized_cuisine(value: str | None) -> str:
    if value is None:
        return "Unknown"
    normalized = value.strip()
    return normalized or "Unknown"


def _tokenize_feature(value: str) -> list[str]:
    normalized = value.strip().lower()
    if not normalized:
        return []
    return [token for token in re.split(r"[^a-z0-9]+", normalized) if token and len(token) > 1]


def _local_recipe_feature_set(recipe: Recipe) -> set[str]:
    features: set[str] = set()
    for tag in recipe.tags or []:
        features.update(token for token in _tokenize_feature(tag) if not _is_measurement_token(token))
    for ingredient in recipe.ingredients or []:
        ingredient_phrase = _normalize_ingredient_phrase(ingredient)
        if ingredient_phrase:
            features.add(ingredient_phrase)
    features.update(token for token in _tokenize_feature(recipe.cuisine or "") if not _is_measurement_token(token))
    return features


def _ingredient_tokens(ingredients: list[str]) -> set[str]:
    tokens: set[str] = set()
    for ingredient in ingredients:
        ingredient_phrase = _normalize_ingredient_phrase(ingredient)
        if ingredient_phrase:
            tokens.add(ingredient_phrase)
    return tokens


_INGREDIENT_STOPWORDS = {
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
    "g",
    "mg",
    "lbs",
    "pound",
    "pounds",
    "ounce",
    "ounces",
    "liter",
    "liters",
    "litre",
    "litres",
    "clove",
    "cloves",
    "pinch",
    "pinches",
    "slice",
    "slices",
    "piece",
    "pieces",
    "can",
    "cans",
    "package",
    "packages",
}


def _is_measurement_token(token: str) -> bool:
    if not token:
        return True
    if token.isdigit():
        return True
    if re.match(r"^\d+(?:\.\d+)?(?:g|kg|mg|ml|l|oz|lb|lbs)$", token):
        return True
    return token in _INGREDIENT_STOPWORDS


def _parse_quantity_prefix(raw_value: str) -> float:
    value = raw_value.strip().lower()
    if not value:
        return 1.0

    mixed_match = re.match(r"^(\d+)\s+(\d+)/(\d+)", value)
    if mixed_match:
        whole = float(mixed_match.group(1))
        numerator = float(mixed_match.group(2))
        denominator = float(mixed_match.group(3))
        if denominator > 0:
            return min(whole + (numerator / denominator), 8.0)

    fraction_match = re.match(r"^(\d+)/(\d+)", value)
    if fraction_match:
        numerator = float(fraction_match.group(1))
        denominator = float(fraction_match.group(2))
        if denominator > 0:
            return min(numerator / denominator, 8.0)

    decimal_match = re.match(r"^(\d+(?:\.\d+)?)", value)
    if decimal_match:
        return min(float(decimal_match.group(1)), 8.0)

    return 1.0


def _normalize_ingredient_phrase(raw_value: str) -> str:
    value = raw_value.strip().lower()
    if not value:
        return ""

    # Remove leading quantity (e.g. "1 1/2", "3/4", "250", "2.5") before token filtering.
    value = re.sub(r"^\s*(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)\s*", "", value)

    words: list[str] = []
    for token in re.split(r"[^a-z0-9]+", value):
        if not token or _is_measurement_token(token):
            continue
        words.append(token)

    return " ".join(words)


def _ingredient_profile(ingredients: list[str]) -> dict[str, float]:
    profile: dict[str, float] = defaultdict(float)
    for raw in ingredients:
        quantity = _parse_quantity_prefix(raw)
        ingredient_phrase = _normalize_ingredient_phrase(raw)
        if not ingredient_phrase:
            continue
        profile[ingredient_phrase] += quantity
    return dict(profile)


def _build_ingredient_rarity_weights(all_profiles: list[dict[str, float]]) -> dict[str, float]:
    document_frequency: Counter[str] = Counter()
    for profile in all_profiles:
        for token in profile:
            document_frequency[token] += 1

    if not document_frequency:
        return {}

    rarity_weights: dict[str, float] = {}
    for token, count in document_frequency.items():
        # Common tokens receive a lower score; rarer tokens have stronger influence.
        rarity_weights[token] = 1.0 / (1.0 + math.log1p(float(count)))
    return rarity_weights


def _ingredient_weighted_overlap(
    candidate_profile: dict[str, float],
    preference_weights: dict[str, float],
    rarity_weights: dict[str, float],
) -> float:
    if not candidate_profile:
        return 0.0

    score = 0.0
    for token, quantity in candidate_profile.items():
        if token not in preference_weights:
            continue
        rarity = rarity_weights.get(token, 1.0)
        score += preference_weights[token] * quantity * rarity
    return score


def _prep_band(minutes: int | None) -> str | None:
    if minutes is None:
        return None
    if minutes <= 25:
        return "quick"
    if minutes <= 45:
        return "balanced"
    return "slow"


def _calorie_band(calories: int | None) -> str | None:
    if calories is None:
        return None
    if calories <= 450:
        return "light"
    if calories <= 700:
        return "moderate"
    return "hearty"


def _external_item_feature_set(item: RecipeDiscoverItem) -> set[str]:
    features: set[str] = set()
    for tag in item.tags:
        features.update(token for token in _tokenize_feature(tag) if not _is_measurement_token(token))
    for ingredient in item.key_ingredients:
        ingredient_phrase = _normalize_ingredient_phrase(ingredient)
        if ingredient_phrase:
            features.add(ingredient_phrase)
    features.update(token for token in _tokenize_feature(item.cuisine) if not _is_measurement_token(token))
    return features


def _weighted_overlap(candidate_features: set[str], feature_weights: dict[str, float]) -> float:
    if not candidate_features:
        return 0.0
    return sum(feature_weights.get(feature, 0.0) for feature in candidate_features)


def _jaccard(candidate_features: set[str], reference_features: set[str]) -> float:
    if not candidate_features or not reference_features:
        return 0.0
    union = candidate_features | reference_features
    if not union:
        return 0.0
    return len(candidate_features & reference_features) / len(union)


def _extract_themealdb_external_id(item: RecipeDiscoverItem) -> str:
    if item.external_id and str(item.external_id).strip().isdigit():
        return str(item.external_id).strip()

    raw_id = str(item.id).strip()
    if raw_id.startswith("themealdb-"):
        suffix = raw_id.split("themealdb-", maxsplit=1)[1]
        if suffix.isdigit():
            return suffix

    if raw_id.isdigit():
        return raw_id

    return ""


def _cache_is_fresh(cache_entry: UserSuggestionCache | None) -> bool:
    if cache_entry is None:
        return False
    if cache_entry.is_stale:
        return False
    if cache_entry.generated_at is None:
        return False
    generated_at = cache_entry.generated_at
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=UTC)
    return datetime.now(UTC) - generated_at < timedelta(days=1)


def _mark_suggestions_stale(db: Session, user_id: int) -> None:
    cache_entry = db.query(UserSuggestionCache).filter(UserSuggestionCache.user_id == user_id).first()
    if cache_entry is None:
        cache_entry = UserSuggestionCache(user_id=user_id, items_json=[], is_stale=True, generated_at=None)
        db.add(cache_entry)
        return

    cache_entry.is_stale = True


def _hydrate_cached_suggestion_items(
    db: Session,
    user_id: int,
    items_json: list[dict],
) -> list[RecipeDiscoverItem]:
    rated_local_ids = {
        rating.recipe_id
        for rating in db.query(RecipeRating).filter(RecipeRating.user_id == user_id).all()
    }
    rated_external_ids = {
        (rating.external_recipe_id or "").strip()
        for rating in db.query(ExternalRecipeRating)
        .filter(
            ExternalRecipeRating.user_id == user_id,
            ExternalRecipeRating.source == "themealdb",
        )
        .all()
    }

    hydrated: list[RecipeDiscoverItem] = []
    for raw in items_json:
        try:
            item = RecipeDiscoverItem(**raw)
        except Exception:
            continue

        if item.source == "local":
            if int(item.id) in rated_local_ids:
                continue
        elif item.source == "themealdb":
            external_id = _extract_themealdb_external_id(item)
            if external_id in rated_external_ids:
                continue

        hydrated.append(item)

    return hydrated


@router.get("", response_model=list[RecipeRead])
def list_recipes(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    db: Session = Depends(get_db),
) -> list[Recipe]:
    return db.query(Recipe).offset(skip).limit(limit).all()


@router.get("/mine", response_model=list[RecipeRead])
def list_my_recipes(
    query: Annotated[str, Query(min_length=0)] = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Recipe]:
    recipe_query = db.query(Recipe).filter(Recipe.owner_id == current_user.id)
    if query.strip():
        like_pattern = f"%{query.strip()}%"
        recipe_query = recipe_query.filter(
            (Recipe.title.ilike(like_pattern)) | (Recipe.cuisine.ilike(like_pattern))
        )
    return recipe_query.order_by(Recipe.created_at.desc()).all()


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
    local_items = [
        RecipeDiscoverItem(
            id=recipe.id,
            source="local",
            title=recipe.title,
            cuisine=_normalized_cuisine(recipe.cuisine),
            image_url=recipe.image_url,
            prep_minutes=recipe.prep_minutes,
            calories=recipe.calories,
            tags=recipe.tags,
            description=recipe.intro or recipe.steps,
            average_rating=recipe.average_rating,
            owner_id=recipe.owner_id,
            category=None,
            key_ingredients=[],
        )
        for recipe in local_recipes
    ]

    external_raw = search_themealdb_recipes(query=query.strip(), limit=external_limit)
    external_items = [RecipeDiscoverItem(**item) for item in external_raw]

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

        return RecipeCookRead(
            id=recipe.id,
            source="local",
            title=recipe.title,
            cuisine=_normalized_cuisine(recipe.cuisine),
            description=recipe.intro,
            instructions=recipe.steps,
            image_url=recipe.image_url,
            tags=recipe.tags,
            ingredients=[RecipeCookIngredient(name=item, measure=None) for item in (recipe.ingredients or [])],
            prep_minutes=recipe.prep_minutes,
            calories=recipe.calories,
        )

    if normalized_source == "themealdb":
        external_recipe = get_themealdb_recipe_by_id(recipe_id)
        if external_recipe is None:
            raise HTTPException(status_code=404, detail="External recipe not found")
        return RecipeCookRead(**external_recipe)

    raise HTTPException(status_code=400, detail="Invalid source. Use 'local' or 'themealdb'.")


@router.get("/suggested", response_model=RecipeSuggestionResponse)
def suggested_recipes_for_user(
    local_limit: Annotated[int, Query(ge=1, le=80)] = 30,
    external_limit: Annotated[int, Query(ge=1, le=120)] = 40,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeSuggestionResponse:
    formula = (
        "score = 0.55 * Jaccard(candidate, liked_features) "
        "+ 0.30 * weighted_liked_overlap "
        "+ 0.18 * liked_ingredient_overlap "
        "+ 0.08 * prep_band_affinity "
        "+ 0.08 * calorie_band_affinity "
        "- 0.30 * Jaccard(candidate, disliked_features) "
        "- 0.20 * weighted_disliked_overlap "
        "- 0.18 * disliked_ingredient_overlap"
    )

    cache_entry = db.query(UserSuggestionCache).filter(UserSuggestionCache.user_id == current_user.id).first()
    if _cache_is_fresh(cache_entry):
        assert cache_entry is not None
        cached_items = _hydrate_cached_suggestion_items(
            db=db,
            user_id=current_user.id,
            items_json=cache_entry.items_json or [],
        )
        local_count = sum(1 for item in cached_items if item.source == "local")
        external_count = sum(1 for item in cached_items if item.source == "themealdb")
        return RecipeSuggestionResponse(
            items=cached_items,
            local_count=local_count,
            external_count=external_count,
            formula=formula,
        )

    local_ratings = db.query(RecipeRating).filter(RecipeRating.user_id == current_user.id).all()
    external_ratings = (
        db.query(ExternalRecipeRating)
        .filter(
            ExternalRecipeRating.user_id == current_user.id,
            ExternalRecipeRating.source == "themealdb",
        )
        .all()
    )

    if not local_ratings and not external_ratings:
        return RecipeSuggestionResponse(items=[], local_count=0, external_count=0, formula=formula)

    liked_features: set[str] = set()
    disliked_features: set[str] = set()
    liked_feature_weights: dict[str, float] = defaultdict(float)
    disliked_feature_weights: dict[str, float] = defaultdict(float)
    liked_ingredient_weights: dict[str, float] = defaultdict(float)
    disliked_ingredient_weights: dict[str, float] = defaultdict(float)
    liked_prep_bands: Counter[str] = Counter()
    disliked_prep_bands: Counter[str] = Counter()
    liked_calorie_bands: Counter[str] = Counter()
    disliked_calorie_bands: Counter[str] = Counter()

    rated_local_ids: set[int] = set()
    rated_external_ids: set[str] = set()

    local_recipe_ids = [rating.recipe_id for rating in local_ratings]
    local_recipe_map: dict[int, Recipe] = {}
    if local_recipe_ids:
        local_recipe_rows = db.query(Recipe).filter(Recipe.id.in_(local_recipe_ids)).all()
        local_recipe_map = {recipe.id: recipe for recipe in local_recipe_rows}

    for rating in local_ratings:
        rated_local_ids.add(rating.recipe_id)
        recipe = local_recipe_map.get(rating.recipe_id)
        if recipe is None:
            continue

        features = _local_recipe_feature_set(recipe)
        ingredient_profile = _ingredient_profile(recipe.ingredients or [])
        prep_band = _prep_band(recipe.prep_minutes)
        calorie_band = _calorie_band(recipe.calories)
        if not features:
            continue

        if rating.score >= 4:
            weight = float(rating.score - 3)
            liked_features.update(features)
            for feature in features:
                liked_feature_weights[feature] += weight
            for token, quantity in ingredient_profile.items():
                liked_ingredient_weights[token] += weight * quantity
            if prep_band:
                liked_prep_bands[prep_band] += 1
            if calorie_band:
                liked_calorie_bands[calorie_band] += 1
        elif rating.score <= 2:
            weight = float(3 - rating.score)
            disliked_features.update(features)
            for feature in features:
                disliked_feature_weights[feature] += weight
            for token, quantity in ingredient_profile.items():
                disliked_ingredient_weights[token] += weight * quantity
            if prep_band:
                disliked_prep_bands[prep_band] += 1
            if calorie_band:
                disliked_calorie_bands[calorie_band] += 1

    for rating in external_ratings:
        external_id = (rating.external_recipe_id or "").strip()
        if not external_id:
            continue
        rated_external_ids.add(external_id)

        external_recipe = get_themealdb_recipe_by_id(external_id)
        if external_recipe is None:
            continue

        ingredient_names = [item.get("name", "") for item in external_recipe.get("ingredients", [])]
        ingredient_profile = _ingredient_profile([name for name in ingredient_names if name])
        prep_band = _prep_band(external_recipe.get("prep_minutes"))
        calorie_band = _calorie_band(external_recipe.get("calories"))
        features: set[str] = set()
        for tag in external_recipe.get("tags", []):
            features.update(token for token in _tokenize_feature(tag) if not _is_measurement_token(token))
        for ingredient_name in ingredient_names:
            ingredient_phrase = _normalize_ingredient_phrase(ingredient_name)
            if ingredient_phrase:
                features.add(ingredient_phrase)
        features.update(
            token
            for token in _tokenize_feature(external_recipe.get("cuisine") or "")
            if not _is_measurement_token(token)
        )

        if not features:
            continue

        if rating.score >= 4:
            weight = float(rating.score - 3)
            liked_features.update(features)
            for feature in features:
                liked_feature_weights[feature] += weight
            for token, quantity in ingredient_profile.items():
                liked_ingredient_weights[token] += weight * quantity
            if prep_band:
                liked_prep_bands[prep_band] += 1
            if calorie_band:
                liked_calorie_bands[calorie_band] += 1
        elif rating.score <= 2:
            weight = float(3 - rating.score)
            disliked_features.update(features)
            for feature in features:
                disliked_feature_weights[feature] += weight
            for token, quantity in ingredient_profile.items():
                disliked_ingredient_weights[token] += weight * quantity
            if prep_band:
                disliked_prep_bands[prep_band] += 1
            if calorie_band:
                disliked_calorie_bands[calorie_band] += 1

    # If the user only has neutral ratings, there is no preference signal.
    if not liked_features and not disliked_features:
        return RecipeSuggestionResponse(items=[], local_count=0, external_count=0, formula=formula)

    candidate_items: list[RecipeDiscoverItem] = []

    local_candidates = db.query(Recipe).limit(400).all()
    local_candidate_features: dict[int, set[str]] = {}
    local_candidate_ingredient_profiles: dict[int, dict[str, float]] = {}
    local_candidate_prep: dict[int, str | None] = {}
    local_candidate_calorie: dict[int, str | None] = {}
    rarity_profiles: list[dict[str, float]] = []
    for recipe in local_candidates:
        if recipe.id in rated_local_ids:
            continue
        local_candidate_features[recipe.id] = _local_recipe_feature_set(recipe)
        local_candidate_ingredient_profiles[recipe.id] = _ingredient_profile(recipe.ingredients or [])
        rarity_profiles.append(local_candidate_ingredient_profiles[recipe.id])
        local_candidate_prep[recipe.id] = _prep_band(recipe.prep_minutes)
        local_candidate_calorie[recipe.id] = _calorie_band(recipe.calories)
        candidate_items.append(
            RecipeDiscoverItem(
                id=recipe.id,
                source="local",
                title=recipe.title,
                cuisine=_normalized_cuisine(recipe.cuisine),
                image_url=None,
                prep_minutes=recipe.prep_minutes,
                calories=recipe.calories,
                tags=recipe.tags,
                description=recipe.intro or recipe.steps,
                average_rating=recipe.average_rating,
                owner_id=recipe.owner_id,
                category=None,
                key_ingredients=[],
            )
        )

    query_terms = [
        feature
        for feature, _weight in sorted(
            liked_feature_weights.items(), key=lambda entry: entry[1], reverse=True
        )[:6]
    ]
    if not query_terms:
        query_terms = [
            feature
            for feature, _weight in sorted(
                disliked_feature_weights.items(), key=lambda entry: entry[1], reverse=True
            )[:3]
        ]

    external_candidates_by_id: dict[str, RecipeDiscoverItem] = {}
    for term in query_terms:
        for raw_item in search_themealdb_recipes(query=term, limit=external_limit):
            item = RecipeDiscoverItem(**raw_item)
            external_id = _extract_themealdb_external_id(item)
            if not external_id or external_id in rated_external_ids:
                continue
            if external_id not in external_candidates_by_id:
                external_candidates_by_id[external_id] = item

    candidate_items.extend(external_candidates_by_id.values())

    for item in external_candidates_by_id.values():
        rarity_profiles.append(_ingredient_profile(item.key_ingredients))

    ingredient_rarity_weights = _build_ingredient_rarity_weights(rarity_profiles)

    scored_items: list[RecipeDiscoverItem] = []
    for item in candidate_items:
        if item.source == "local":
            candidate_features = local_candidate_features.get(int(item.id), set())
            candidate_ingredient_profile = local_candidate_ingredient_profiles.get(int(item.id), {})
            prep_band = local_candidate_prep.get(int(item.id))
            calorie_band = local_candidate_calorie.get(int(item.id))
        else:
            candidate_features = _external_item_feature_set(item)
            candidate_ingredient_profile = _ingredient_profile(item.key_ingredients)
            prep_band = _prep_band(item.prep_minutes)
            calorie_band = _calorie_band(item.calories)

        if not candidate_features:
            continue

        liked_jaccard = _jaccard(candidate_features, liked_features)
        disliked_jaccard = _jaccard(candidate_features, disliked_features)
        liked_overlap = _weighted_overlap(candidate_features, liked_feature_weights)
        disliked_overlap = _weighted_overlap(candidate_features, disliked_feature_weights)
        liked_ingredient_overlap = _ingredient_weighted_overlap(
            candidate_ingredient_profile,
            liked_ingredient_weights,
            ingredient_rarity_weights,
        )
        disliked_ingredient_overlap = _ingredient_weighted_overlap(
            candidate_ingredient_profile,
            disliked_ingredient_weights,
            ingredient_rarity_weights,
        )

        prep_affinity = 0.0
        if prep_band:
            prep_affinity = float(liked_prep_bands.get(prep_band, 0) - disliked_prep_bands.get(prep_band, 0))

        calorie_affinity = 0.0
        if calorie_band:
            calorie_affinity = float(
                liked_calorie_bands.get(calorie_band, 0) - disliked_calorie_bands.get(calorie_band, 0)
            )

        score = (
            (0.55 * liked_jaccard)
            + (0.30 * liked_overlap)
            + (0.18 * liked_ingredient_overlap)
            + (0.08 * prep_affinity)
            + (0.08 * calorie_affinity)
            - (0.30 * disliked_jaccard)
            - (0.20 * disliked_overlap)
            - (0.18 * disliked_ingredient_overlap)
        )

        if score <= 0:
            continue

        reasons: list[str] = []
        if prep_band and liked_prep_bands.get(prep_band, 0) > disliked_prep_bands.get(prep_band, 0):
            reasons.append(f"Prep time aligns with your {prep_band} cooking preference")

        if calorie_band and liked_calorie_bands.get(calorie_band, 0) > disliked_calorie_bands.get(calorie_band, 0):
            reasons.append(f"Calorie range matches your {calorie_band} meal preference")

        top_liked_features = sorted(
            (feature for feature in candidate_features if feature in liked_feature_weights),
            key=lambda feature: liked_feature_weights[feature],
            reverse=True,
        )
        if top_liked_features:
            reasons.append(f"Matches your liked flavors: {', '.join(top_liked_features[:3])}")

        top_ingredients = sorted(
            (token for token in candidate_ingredient_profile if token in liked_ingredient_weights),
            key=lambda token: liked_ingredient_weights[token]
            * candidate_ingredient_profile.get(token, 0.0)
            * ingredient_rarity_weights.get(token, 1.0),
            reverse=True,
        )
        if top_ingredients:
            reasons.append(f"Uses ingredients you rate highly: {', '.join(top_ingredients[:2])}")

        if not reasons:
            reasons.append("Overall profile is close to your positively rated recipes")

        item.recommendation_score = round(score, 4)
        item.reasons = reasons[:4]
        scored_items.append(item)

    scored_items.sort(key=lambda item: item.recommendation_score or 0.0, reverse=True)

    total_limit = local_limit + external_limit
    items = scored_items[:total_limit]
    local_count = sum(1 for item in items if item.source == "local")
    external_count = sum(1 for item in items if item.source == "themealdb")

    if cache_entry is None:
        cache_entry = UserSuggestionCache(user_id=current_user.id)
        db.add(cache_entry)
    cache_entry.items_json = [item.model_dump() for item in items]
    cache_entry.generated_at = datetime.now(UTC)
    cache_entry.is_stale = False
    db.commit()

    return RecipeSuggestionResponse(
        items=items,
        local_count=local_count,
        external_count=external_count,
        formula=formula,
    )


@router.get("/rated", response_model=RecipeRatedResponse)
def get_my_rated_recipes(
    query: Annotated[str, Query(min_length=0)] = "",
    score: Annotated[int | None, Query(ge=1, le=5)] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeRatedResponse:
    normalized_query = query.strip().lower()

    local_rating_query = db.query(RecipeRating).filter(RecipeRating.user_id == current_user.id)
    external_rating_query = (
        db.query(ExternalRecipeRating)
        .filter(
            ExternalRecipeRating.user_id == current_user.id,
            ExternalRecipeRating.source == "themealdb",
        )
    )

    if score is not None:
        local_rating_query = local_rating_query.filter(RecipeRating.score == score)
        external_rating_query = external_rating_query.filter(ExternalRecipeRating.score == score)

    local_ratings = local_rating_query.order_by(RecipeRating.created_at.desc()).all()
    external_ratings = external_rating_query.order_by(ExternalRecipeRating.created_at.desc()).all()

    local_recipe_ids = [rating.recipe_id for rating in local_ratings]
    local_recipe_map: dict[int, Recipe] = {}
    if local_recipe_ids:
        local_recipes = db.query(Recipe).filter(Recipe.id.in_(local_recipe_ids)).all()
        local_recipe_map = {recipe.id: recipe for recipe in local_recipes}

    local_items: list[RecipeRatedItem] = []
    for rating in local_ratings:
        recipe = local_recipe_map.get(rating.recipe_id)
        if recipe is None:
            continue

        if normalized_query and normalized_query not in recipe.title.lower() and normalized_query not in (
            recipe.cuisine or ""
        ).lower():
            continue

        local_items.append(
            RecipeRatedItem(
                id=recipe.id,
                source="local",
                title=recipe.title,
                cuisine=_normalized_cuisine(recipe.cuisine),
                image_url=recipe.image_url,
                prep_minutes=recipe.prep_minutes,
                calories=recipe.calories,
                tags=recipe.tags,
                description=recipe.intro or recipe.steps,
                average_rating=recipe.average_rating,
                owner_id=recipe.owner_id,
                category=None,
                key_ingredients=[],
                my_rating=rating.score,
                my_comment=rating.comment,
            )
        )

    external_items: list[RecipeRatedItem] = []
    for rating in external_ratings:
        external_id = (rating.external_recipe_id or "").strip()
        if not external_id:
            continue

        cooked = get_themealdb_recipe_by_id(external_id)
        if cooked is None:
            continue

        title = cooked.get("title") or "Untitled"
        cuisine = cooked.get("cuisine") or "Unknown"

        if normalized_query and normalized_query not in title.lower() and normalized_query not in cuisine.lower():
            continue

        key_ingredients = [
            ingredient.get("name", "")
            for ingredient in cooked.get("ingredients", [])[:4]
            if ingredient.get("name")
        ]

        external_items.append(
            RecipeRatedItem(
                id=f"themealdb-{external_id}",
                external_id=external_id,
                source="themealdb",
                title=title,
                cuisine=cuisine,
                image_url=cooked.get("image_url"),
                prep_minutes=cooked.get("prep_minutes"),
                calories=cooked.get("calories"),
                tags=cooked.get("tags") or [],
                description=cooked.get("description"),
                average_rating=None,
                owner_id=None,
                category=cooked.get("description"),
                key_ingredients=key_ingredients,
                my_rating=rating.score,
                my_comment=rating.comment,
            )
        )

    items: list[RecipeRatedItem] = [*local_items, *external_items]
    items.sort(key=lambda item: item.my_rating, reverse=True)

    return RecipeRatedResponse(
        items=items,
        local_count=len(local_items),
        external_count=len(external_items),
    )


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


@router.post("/import-url", response_model=RecipeImportPreview)
def import_recipe_from_url(
    payload: RecipeImportRequest,
    current_user: User = Depends(get_current_user),
) -> RecipeImportPreview:
    del current_user
    try:
        preview = extract_recipe_from_url(str(payload.url))
        return RecipeImportPreview(**preview)
    except RecipeImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{recipe_id}/copy", response_model=RecipeRead, status_code=201)
def create_modified_recipe_copy(
    recipe_id: int,
    payload: RecipeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Recipe:
    source_recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if source_recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")

    overrides = payload.model_dump(exclude_unset=True)

    copied_recipe = Recipe(
        owner_id=current_user.id,
        title=overrides.get("title", source_recipe.title),
        cuisine=_normalized_cuisine(overrides.get("cuisine", source_recipe.cuisine)),
        prep_minutes=overrides.get("prep_minutes", source_recipe.prep_minutes),
        calories=overrides.get("calories", source_recipe.calories),
        intro=overrides.get("intro", source_recipe.intro),
        image_url=overrides.get("image_url", source_recipe.image_url),
        ingredients=overrides.get("ingredients", source_recipe.ingredients),
        tags=overrides.get("tags", source_recipe.tags),
        steps=overrides.get("steps", source_recipe.steps),
        average_rating=None,
    )

    db.add(copied_recipe)
    db.commit()
    db.refresh(copied_recipe)
    return copied_recipe


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

    if existing is not None:
        raise HTTPException(status_code=409, detail="You have already rated this recipe")

    rating = RecipeRating(
        user_id=current_user.id,
        recipe_id=recipe_id,
        score=payload.score,
        comment=payload.comment,
    )
    db.add(rating)

    db.flush()

    average_score = (
        db.query(func.avg(RecipeRating.score)).filter(RecipeRating.recipe_id == recipe_id).scalar()
    )
    recipe.average_rating = round(float(average_score if average_score is not None else payload.score), 2)

    _mark_suggestions_stale(db, current_user.id)

    db.commit()
    db.refresh(rating)
    return rating


@router.get("/{recipe_id}/ratings/me", response_model=RatingRead)
def get_my_recipe_rating(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeRating:
    rating = (
        db.query(RecipeRating)
        .filter(RecipeRating.user_id == current_user.id, RecipeRating.recipe_id == recipe_id)
        .first()
    )
    if rating is None:
        raise HTTPException(status_code=404, detail="No rating found for this recipe")
    return rating


@router.post("/themealdb/{external_recipe_id}/ratings", response_model=ExternalRatingRead)
def rate_external_themealdb_recipe(
    external_recipe_id: str,
    payload: RatingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExternalRecipeRating:
    normalized_id = external_recipe_id.strip()
    if not normalized_id.isdigit():
        raise HTTPException(status_code=400, detail="TheMealDB recipe id must be a numeric string")

    existing = (
        db.query(ExternalRecipeRating)
        .filter(
            ExternalRecipeRating.user_id == current_user.id,
            ExternalRecipeRating.external_recipe_id == normalized_id,
            ExternalRecipeRating.source == "themealdb",
        )
        .first()
    )

    if existing is not None:
        raise HTTPException(status_code=409, detail="You have already rated this TheMealDB recipe")

    rating = ExternalRecipeRating(
        user_id=current_user.id,
        external_recipe_id=normalized_id,
        source="themealdb",
        score=payload.score,
        comment=payload.comment,
    )
    db.add(rating)

    _mark_suggestions_stale(db, current_user.id)

    db.commit()
    db.refresh(rating)
    return rating


@router.get("/themealdb/{external_recipe_id}/ratings/me", response_model=ExternalRatingRead)
def get_my_themealdb_recipe_rating(
    external_recipe_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExternalRecipeRating:
    normalized_id = external_recipe_id.strip()
    if not normalized_id.isdigit():
        raise HTTPException(status_code=400, detail="TheMealDB recipe id must be a numeric string")

    rating = (
        db.query(ExternalRecipeRating)
        .filter(
            ExternalRecipeRating.user_id == current_user.id,
            ExternalRecipeRating.external_recipe_id == normalized_id,
            ExternalRecipeRating.source == "themealdb",
        )
        .first()
    )
    if rating is None:
        raise HTTPException(status_code=404, detail="No rating found for this TheMealDB recipe")
    return rating
