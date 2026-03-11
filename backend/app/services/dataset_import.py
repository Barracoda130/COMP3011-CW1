from __future__ import annotations

import ast
import csv
import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.recipe import Recipe
from app.models.user import User


class DatasetImportError(ValueError):
    pass


@dataclass(slots=True)
class ImportedRecipeRecord:
    source_id: str
    title: str
    cuisine: str
    prep_minutes: int
    calories: int | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    allergens: list[str]
    cost_estimate: float | None
    intro: str | None
    steps: str | None
    image_url: str | None
    ingredients: list[str]
    tags: list[str]


@dataclass(slots=True)
class ImportStats:
    scanned: int = 0
    imported: int = 0
    skipped_invalid: int = 0
    skipped_duplicate: int = 0


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = ast.literal_eval(stripped)
            except (ValueError, SyntaxError):
                parsed = None
            if isinstance(parsed, list):
                return parsed
        return [part.strip() for part in stripped.split(",") if part.strip()]
    return []


def _as_string_list(value: Any, *, limit: int) -> list[str]:
    values: list[str] = []
    for item in _as_list(value):
        text = str(item).strip()
        if text:
            values.append(text)
    return values[:limit]


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
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


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _normalize_title(value: Any) -> str:
    text = str(value or "").strip()
    return text[:150]


def _normalize_cuisine(value: Any) -> str:
    text = str(value or "").strip()
    return text[:60] if text else "Unknown"


def _normalize_steps(raw_steps: Any) -> str | None:
    parts = _as_string_list(raw_steps, limit=100)
    if not parts:
        return None
    return "\n".join(parts)


def _normalize_calories(raw_nutrition: Any, fallback_calories: int | None) -> int | None:
    nutrition_values = _as_list(raw_nutrition)
    if nutrition_values:
        primary = _as_int(nutrition_values[0])
        if primary is not None and primary >= 0:
            return primary
    if fallback_calories is not None and fallback_calories >= 0:
        return fallback_calories
    return None


def _normalize_macros(raw_nutrition: Any) -> tuple[float | None, float | None, float | None]:
    # Food.com-style nutrition array commonly maps to:
    # [calories, fat, sugar, sodium, protein, sat_fat, carbs]
    values = _as_list(raw_nutrition)
    fat_g = _as_float(values[1]) if len(values) > 1 else None
    protein_g = _as_float(values[4]) if len(values) > 4 else None
    carbs_g = _as_float(values[6]) if len(values) > 6 else None
    return protein_g, carbs_g, fat_g


def _normalize_allergens(value: Any) -> list[str]:
    allergens: list[str] = []
    seen: set[str] = set()
    for item in _as_string_list(value, limit=20):
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        allergens.append(normalized)
    return allergens


def parse_foodcom_record(
    record: dict[str, Any],
    *,
    usda_enrichment_by_source_id: dict[str, dict[str, Any]] | None = None,
    source_tag: str = "dataset:foodcom",
) -> ImportedRecipeRecord | None:
    title = _normalize_title(record.get("name") or record.get("title"))
    if not title:
        return None

    source_id = str(record.get("id") or record.get("recipe_id") or "").strip()
    if not source_id:
        source_id = f"title:{title.lower()}"

    usda_payload: dict[str, Any] = {}
    if usda_enrichment_by_source_id is not None:
        usda_payload = usda_enrichment_by_source_id.get(source_id, {})

    usda_calories = _as_int(usda_payload.get("calories"))
    usda_protein = _as_float(usda_payload.get("protein_g"))
    usda_carbs = _as_float(usda_payload.get("carbs_g"))
    usda_fat = _as_float(usda_payload.get("fat_g"))
    usda_allergens = _normalize_allergens(usda_payload.get("allergens"))
    usda_cost_estimate = _as_float(usda_payload.get("cost_estimate"))

    prep_minutes = _as_int(record.get("minutes"))
    if prep_minutes is None or prep_minutes <= 0:
        prep_minutes = 30

    cuisine = _normalize_cuisine(record.get("cuisine") or record.get("region"))
    ingredients = _as_string_list(record.get("ingredients"), limit=60)
    tags = _as_string_list(record.get("tags"), limit=25)
    protein_g, carbs_g, fat_g = _normalize_macros(record.get("nutrition"))
    allergens = _normalize_allergens(record.get("allergens") or record.get("allergen_tags"))
    cost_estimate = _as_float(record.get("cost_estimate") or record.get("estimated_cost"))

    if protein_g is None:
        protein_g = usda_protein
    if carbs_g is None:
        carbs_g = usda_carbs
    if fat_g is None:
        fat_g = usda_fat
    if not allergens:
        allergens = usda_allergens
    if cost_estimate is None:
        cost_estimate = usda_cost_estimate

    if source_tag not in tags:
        tags.append(source_tag)

    return ImportedRecipeRecord(
        source_id=source_id,
        title=title,
        cuisine=cuisine,
        prep_minutes=min(prep_minutes, 600),
        calories=_normalize_calories(record.get("nutrition"), usda_calories),
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        allergens=allergens,
        cost_estimate=cost_estimate,
        intro=(str(record.get("description") or "").strip() or None),
        steps=_normalize_steps(record.get("steps")),
        image_url=(str(record.get("image_url") or record.get("photo_url") or "").strip() or None),
        ingredients=ingredients,
        tags=tags,
    )


def _iter_json_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        recipes = payload.get("recipes")
        if isinstance(recipes, list):
            return [item for item in recipes if isinstance(item, dict)]
    raise DatasetImportError("JSON source must be a list of objects or {\"recipes\": [...]} ")


def iter_source_records(source_path: str) -> list[dict[str, Any]]:
    path = Path(source_path)
    if not path.exists():
        raise DatasetImportError(f"Source file not found: {source_path}")

    suffix = path.suffix.lower()
    if suffix in {".jsonl", ".ndjson"}:
        records: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw:
                continue
            item = json.loads(raw)
            if isinstance(item, dict):
                records.append(item)
        return records

    if suffix == ".json":
        return _iter_json_records(path)

    if suffix == ".csv":
        with path.open("r", newline="", encoding="utf-8") as handle:
            return [dict(row) for row in csv.DictReader(handle)]

    raise DatasetImportError("Unsupported source format. Use .jsonl, .ndjson, .json, or .csv")


def load_usda_enrichment(usda_path: str | None) -> dict[str, dict[str, Any]]:
    if not usda_path:
        return {}

    records = iter_source_records(usda_path)
    enrichment_lookup: dict[str, dict[str, Any]] = {}

    for record in records:
        source_id = str(record.get("id") or record.get("recipe_id") or "").strip()
        if not source_id:
            continue
        payload = {
            "calories": _as_int(record.get("calories_kcal") or record.get("calories")),
            "protein_g": _as_float(record.get("protein_g") or record.get("protein")),
            "carbs_g": _as_float(record.get("carbs_g") or record.get("carbs")),
            "fat_g": _as_float(record.get("fat_g") or record.get("fat")),
            "allergens": _normalize_allergens(record.get("allergens") or record.get("allergen_tags")),
            "cost_estimate": _as_float(record.get("cost_estimate") or record.get("estimated_cost")),
        }
        enrichment_lookup[source_id] = payload

    return enrichment_lookup


def get_or_create_import_user(db: Session, *, email: str, full_name: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is not None:
        return user

    generated_password = secrets.token_urlsafe(24)
    user = User(
        email=email,
        full_name=full_name,
        hashed_password=get_password_hash(generated_password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def import_curated_foodcom_subset(
    db: Session,
    *,
    records: list[dict[str, Any]],
    owner: User,
    limit: int = 250,
    usda_enrichment_by_source_id: dict[str, dict[str, Any]] | None = None,
    source_tag: str = "dataset:foodcom",
    skip_duplicates: bool = True,
    dry_run: bool = False,
) -> ImportStats:
    stats = ImportStats()

    existing_keys: set[tuple[str, str]] = set()
    if skip_duplicates:
        rows = db.query(Recipe.title, Recipe.cuisine).filter(Recipe.owner_id == owner.id).all()
        for title, cuisine in rows:
            existing_keys.add((str(title).strip().lower(), str(cuisine).strip().lower()))

    for raw in records:
        if stats.imported >= limit:
            break

        stats.scanned += 1
        parsed = parse_foodcom_record(
            raw,
            usda_enrichment_by_source_id=usda_enrichment_by_source_id,
            source_tag=source_tag,
        )
        if parsed is None:
            stats.skipped_invalid += 1
            continue

        dedupe_key = (parsed.title.strip().lower(), parsed.cuisine.strip().lower())
        if skip_duplicates and dedupe_key in existing_keys:
            stats.skipped_duplicate += 1
            continue

        recipe = Recipe(
            owner_id=owner.id,
            title=parsed.title,
            cuisine=parsed.cuisine,
            prep_minutes=parsed.prep_minutes,
            calories=parsed.calories,
            protein_g=parsed.protein_g,
            carbs_g=parsed.carbs_g,
            fat_g=parsed.fat_g,
            allergens=parsed.allergens,
            cost_estimate=parsed.cost_estimate,
            intro=parsed.intro,
            steps=parsed.steps,
            image_url=parsed.image_url,
            ingredients=parsed.ingredients,
            tags=parsed.tags,
        )

        if not dry_run:
            db.add(recipe)

        stats.imported += 1
        existing_keys.add(dedupe_key)

    if not dry_run:
        db.commit()

    return stats


def count_recipes_for_owner(db: Session, owner_id: int) -> int:
    return int(db.query(func.count(Recipe.id)).filter(Recipe.owner_id == owner_id).scalar() or 0)
