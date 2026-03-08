from __future__ import annotations

import re
from statistics import median

import httpx

from app.core.config import settings

# Cache lookups to keep discover/cook endpoints responsive.
_PRICE_CACHE: dict[str, float | None] = {}

_TINY_KEYWORDS = {
    "pinch",
    "dash",
    "sprinkle",
    "few",
    "drop",
    "drops",
    "to taste",
}


def _parse_amount_token(token: str) -> float | None:
    token = token.strip()
    if not token:
        return None

    if " " in token:
        # Mixed fraction format like "1 1/2".
        parts = token.split()
        if len(parts) == 2:
            whole = _parse_amount_token(parts[0])
            frac = _parse_amount_token(parts[1])
            if whole is not None and frac is not None:
                return whole + frac

    if "/" in token:
        num_den = token.split("/", maxsplit=1)
        if len(num_den) == 2:
            try:
                num = float(num_den[0])
                den = float(num_den[1])
                if den != 0:
                    return num / den
            except ValueError:
                return None

    try:
        return float(token)
    except ValueError:
        return None


def _extract_amount_and_unit(measure: str) -> tuple[float | None, str]:
    text = (measure or "").strip().lower()
    if not text:
        return None, ""

    compact = re.sub(r"\s+", " ", text)
    match = re.match(r"^([0-9]+(?:\s+[0-9]+/[0-9]+|/[0-9]+|\.[0-9]+)?|[0-9]+/[0-9]+)", compact)
    amount = None
    unit = compact
    if match:
        amount_token = match.group(1)
        amount = _parse_amount_token(amount_token)
        unit = compact[len(amount_token) :].strip()

    return amount, unit


def _should_skip_small_quantity(measure: str | None) -> bool:
    if not measure:
        return False

    normalized = measure.strip().lower()
    if not normalized:
        return False

    if any(keyword in normalized for keyword in _TINY_KEYWORDS):
        return True

    amount, unit = _extract_amount_and_unit(normalized)
    if amount is None:
        return False

    # Ignore low-cost pantry-sized amounts.
    if ("tsp" in unit or "teaspoon" in unit) and amount < 3:
        return True
    if ("tbsp" in unit or "tablespoon" in unit) and amount < 3:
        return True
    if "ml" in unit and amount < 100:
        return True
    if ("g" == unit or " gram" in f" {unit}" or "grams" in unit) and amount < 100:
        return True
    # 100 g is about 3.5 oz, so we use that as the ounce equivalent cutoff.
    if ("oz" in unit or "ounce" in unit) and amount < 3.5:
        return True

    if not unit and amount <= 0.25:
        return True

    return False


def _normalize_ingredient_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z\s]", " ", name).lower()
    words = [word for word in cleaned.split() if len(word) > 2]
    if not words:
        return ""
    return " ".join(words[:2])


def _spoonacular_key() -> str | None:
    key = settings.SPOONACULAR_API_KEY
    if key is None:
        return None
    normalized = key.strip()
    return normalized or None


def _lookup_price_spoonacular(query: str) -> float | None:
    api_key = _spoonacular_key()
    if not api_key:
        return None

    cache_key = f"spoon:{query}"
    if cache_key in _PRICE_CACHE:
        return _PRICE_CACHE[cache_key]

    search_url = f"{settings.SPOONACULAR_BASE_URL}/food/ingredients/search"
    try:
        with httpx.Client(timeout=4.5) as client:
            search_response = client.get(
                search_url,
                params={"query": query, "number": 1, "apiKey": api_key},
            )
            search_response.raise_for_status()
            search_payload = search_response.json()
    except Exception:
        _PRICE_CACHE[cache_key] = None
        return None

    results = search_payload.get("results") or []
    if not results:
        _PRICE_CACHE[cache_key] = None
        return None

    ingredient_id = results[0].get("id")
    if ingredient_id is None:
        _PRICE_CACHE[cache_key] = None
        return None

    info_url = f"{settings.SPOONACULAR_BASE_URL}/food/ingredients/{ingredient_id}/information"
    try:
        with httpx.Client(timeout=4.5) as client:
            info_response = client.get(
                info_url,
                params={"amount": 1, "unit": "serving", "apiKey": api_key},
            )
            info_response.raise_for_status()
            info_payload = info_response.json()
    except Exception:
        _PRICE_CACHE[cache_key] = None
        return None

    estimated = info_payload.get("estimatedCost") or {}
    value = estimated.get("value")
    unit = (estimated.get("unit") or "").lower()
    if not isinstance(value, (int, float)):
        _PRICE_CACHE[cache_key] = None
        return None

    usd = float(value)
    if "cent" in unit:
        usd = usd / 100.0

    estimate = round(usd, 2)
    _PRICE_CACHE[cache_key] = estimate
    return estimate


def _lookup_price_fallback(query: str) -> float | None:
    cache_key = f"fallback:{query}"
    if cache_key in _PRICE_CACHE:
        return _PRICE_CACHE[cache_key]

    if not query:
        return None

    url = f"{settings.SHOPPING_API_BASE_URL}/products/search"
    try:
        with httpx.Client(timeout=4.0) as client:
            response = client.get(url, params={"q": query})
            response.raise_for_status()
            payload = response.json()
    except Exception:
        _PRICE_CACHE[cache_key] = None
        return None

    prices: list[float] = []
    for product in payload.get("products") or []:
        value = product.get("price")
        if isinstance(value, (int, float)):
            prices.append(float(value))
        if len(prices) >= 3:
            break

    if not prices:
        _PRICE_CACHE[cache_key] = None
        return None

    # Convert whole-item store price into a rough per-recipe ingredient share.
    estimate = round(median(prices) * 0.25, 2)
    _PRICE_CACHE[cache_key] = estimate
    return estimate


def _lookup_price_with_source(query: str) -> tuple[float | None, str | None]:
    spoonacular_price = _lookup_price_spoonacular(query)
    if spoonacular_price is not None:
        return spoonacular_price, "spoonacular"

    fallback_price = _lookup_price_fallback(query)
    if fallback_price is not None:
        return fallback_price, "fallback"

    return None, None


def _confidence_from_ratio(success_ratio: float) -> str:
    if success_ratio >= 0.75:
        return "high"
    if success_ratio >= 0.4:
        return "medium"
    return "low"


def estimate_recipe_cost(
    ingredient_names: list[str],
    ingredient_measures: dict[str, str | None] | None = None,
) -> tuple[float | None, str | None, str | None, dict | None]:
    include_debug = settings.COST_ESTIMATOR_DEBUG
    seen: set[str] = set()
    queries: list[tuple[str, str, str | None]] = []
    debug_entries: list[dict] = []

    for ingredient in ingredient_names:
        measure = ingredient_measures.get(ingredient) if ingredient_measures else None
        if ingredient_measures and _should_skip_small_quantity(measure):
            if include_debug:
                debug_entries.append(
                    {
                        "ingredient": ingredient,
                        "measure": measure,
                        "query": None,
                        "status": "skipped",
                        "reason": "small_quantity",
                    }
                )
            continue

        query = _normalize_ingredient_name(ingredient)
        if not query:
            if include_debug:
                debug_entries.append(
                    {
                        "ingredient": ingredient,
                        "measure": measure,
                        "query": None,
                        "status": "skipped",
                        "reason": "unusable_name",
                    }
                )
            continue

        if query in seen:
            if include_debug:
                debug_entries.append(
                    {
                        "ingredient": ingredient,
                        "measure": measure,
                        "query": query,
                        "status": "skipped",
                        "reason": "duplicate_query",
                    }
                )
            continue

        seen.add(query)
        queries.append((ingredient, query, measure))

    if not queries:
        debug_payload = (
            {
                "enabled": True,
                "included_ingredient_count": 0,
                "priced_ingredient_count": 0,
                "total_queries": 0,
                "entries": debug_entries,
            }
            if include_debug
            else None
        )
        return None, None, None, debug_payload

    costs: list[float] = []
    for ingredient, query, measure in queries[:8]:
        price, provider = _lookup_price_with_source(query)
        if price is not None:
            costs.append(price)

        if include_debug:
            debug_entries.append(
                {
                    "ingredient": ingredient,
                    "measure": measure,
                    "query": query,
                    "provider": provider,
                    "status": "priced" if price is not None else "missing_price",
                    "price": price,
                }
            )

    debug_payload = None
    if include_debug:
        debug_payload = {
            "enabled": True,
            "included_ingredient_count": len(queries[:8]),
            "priced_ingredient_count": len(costs),
            "total_queries": len(queries),
            "entries": debug_entries,
        }

    if not costs:
        return None, None, None, debug_payload

    ratio = len(costs) / max(1, len(queries[:8]))
    confidence = _confidence_from_ratio(ratio)
    return round(sum(costs), 2), "USD", confidence, debug_payload
