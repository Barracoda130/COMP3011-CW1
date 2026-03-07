from typing import Any

import httpx

from app.core.config import settings


def _get_json(path: str, params: dict[str, str], timeout: float = 8.0) -> dict[str, Any]:
    url = f"{settings.THEMEALDB_BASE_URL}/{path}"
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def _normalize_full_meal(meal: dict[str, Any]) -> dict[str, Any]:
    tags = []
    if meal.get("strTags"):
        tags = [tag.strip() for tag in meal["strTags"].split(",") if tag.strip()]

    return {
        "id": f"themealdb-{meal.get('idMeal')}",
        "external_id": meal.get("idMeal"),
        "source": "themealdb",
        "title": meal.get("strMeal") or "Untitled",
        "cuisine": meal.get("strArea") or "Unknown",
        "image_url": meal.get("strMealThumb"),
        "prep_minutes": None,
        "calories": None,
        "description": meal.get("strInstructions") or meal.get("strCategory"),
        "tags": tags,
        "average_rating": None,
        "owner_id": None,
    }


def _normalize_filter_meal(meal: dict[str, Any], cuisine_hint: str | None = None) -> dict[str, Any]:
    return {
        "id": f"themealdb-{meal.get('idMeal')}",
        "external_id": meal.get("idMeal"),
        "source": "themealdb",
        "title": meal.get("strMeal") or "Untitled",
        "cuisine": cuisine_hint or "Unknown",
        "image_url": meal.get("strMealThumb"),
        "prep_minutes": None,
        "calories": None,
        "description": None,
        "tags": [],
        "average_rating": None,
        "owner_id": None,
    }


def search_themealdb_recipes(query: str, limit: int = 20) -> list[dict[str, Any]]:
    normalized_query = query.strip()
    if not normalized_query:
        return []

    deduped_by_external_id: dict[str, dict[str, Any]] = {}

    def add_item(item: dict[str, Any]) -> None:
        external_id = item.get("external_id")
        if not external_id:
            return
        if external_id not in deduped_by_external_id:
            deduped_by_external_id[external_id] = item

    # 1) Exact/partial meal name search.
    try:
        payload = _get_json("search.php", {"s": normalized_query})
        for meal in payload.get("meals") or []:
            add_item(_normalize_full_meal(meal))
    except Exception:
        pass

    # 2) Ingredient-based search catches specific food types (e.g., chicken, salmon, tofu).
    try:
        ingredient_payload = _get_json("filter.php", {"i": normalized_query})
        for meal in ingredient_payload.get("meals") or []:
            add_item(_normalize_filter_meal(meal))
    except Exception:
        pass

    # 3) Category and area searches provide broad themed results (e.g., Seafood, Italian).
    category_targets = {normalized_query.lower()}
    area_targets = {normalized_query.lower()}

    query_words = [word.strip().lower() for word in normalized_query.split() if word.strip()]
    category_targets.update(query_words)
    area_targets.update(query_words)

    try:
        categories_payload = _get_json("categories.php", {"c": "list"})
        available_categories = [
            (item.get("strCategory") or "").strip()
            for item in categories_payload.get("categories") or []
            if (item.get("strCategory") or "").strip()
        ]
        for category in available_categories:
            lowered = category.lower()
            if any(token in lowered or lowered in token for token in category_targets):
                try:
                    category_payload = _get_json("filter.php", {"c": category})
                    for meal in category_payload.get("meals") or []:
                        add_item(_normalize_filter_meal(meal, cuisine_hint=category))
                except Exception:
                    continue
    except Exception:
        pass

    try:
        areas_payload = _get_json("list.php", {"a": "list"})
        available_areas = [
            (item.get("strArea") or "").strip()
            for item in areas_payload.get("meals") or []
            if (item.get("strArea") or "").strip()
        ]
        for area in available_areas:
            lowered = area.lower()
            if any(token in lowered or lowered in token for token in area_targets):
                try:
                    area_payload = _get_json("filter.php", {"a": area})
                    for meal in area_payload.get("meals") or []:
                        add_item(_normalize_filter_meal(meal, cuisine_hint=area))
                except Exception:
                    continue
    except Exception:
        pass

    # 4) Fallback broadening: first-letter search can recover results when specific matching is sparse.
    if len(deduped_by_external_id) < max(10, limit // 2):
        first_letter = normalized_query[0].lower()
        try:
            letter_payload = _get_json("search.php", {"f": first_letter})
            for meal in letter_payload.get("meals") or []:
                add_item(_normalize_full_meal(meal))
        except Exception:
            pass

    return list(deduped_by_external_id.values())[:limit]


def get_themealdb_recipe_by_id(external_id: str) -> dict[str, Any] | None:
    url = f"{settings.THEMEALDB_BASE_URL}/lookup.php"
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get(url, params={"i": external_id})
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return None

    meals = payload.get("meals") or []
    if not meals:
        return None

    meal = meals[0]
    tags = []
    if meal.get("strTags"):
        tags = [tag.strip() for tag in meal["strTags"].split(",") if tag.strip()]

    ingredients = []
    for idx in range(1, 21):
        name = (meal.get(f"strIngredient{idx}") or "").strip()
        measure = (meal.get(f"strMeasure{idx}") or "").strip()
        if name:
            ingredients.append({"name": name, "measure": measure or None})

    return {
        "id": f"themealdb-{meal.get('idMeal')}",
        "source": "themealdb",
        "title": meal.get("strMeal") or "Untitled",
        "cuisine": meal.get("strArea") or "Unknown",
        "description": meal.get("strCategory"),
        "instructions": meal.get("strInstructions"),
        "image_url": meal.get("strMealThumb"),
        "tags": tags,
        "ingredients": ingredients,
        "prep_minutes": None,
        "calories": None,
    }
