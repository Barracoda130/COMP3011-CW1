import json
from pathlib import Path

from app.db.session import SessionLocal
from app.models.recipe import Recipe
from app.services.dataset_import import (
    get_or_create_import_user,
    import_curated_foodcom_subset,
    iter_source_records,
    load_usda_enrichment,
    parse_foodcom_record,
)


def test_parse_foodcom_record_prefers_primary_nutrition_calories() -> None:
    raw = {
        "id": "1001",
        "name": "Lemon Chicken",
        "minutes": 40,
        "nutrition": [612.4, 10.0, 5.0],
        "description": "Bright and zesty",
        "steps": ["Prep chicken", "Roast"],
        "ingredients": ["1 chicken breast", "1 lemon"],
        "tags": ["dinner", "quick"],
        "cuisine": "French",
    }

    parsed = parse_foodcom_record(
        raw,
        usda_enrichment_by_source_id={
            "1001": {
                "calories": 500,
                "protein_g": 30.0,
                "carbs_g": 45.0,
                "fat_g": 12.0,
                "allergens": ["dairy"],
            }
        },
    )

    assert parsed is not None
    assert parsed.title == "Lemon Chicken"
    assert parsed.prep_minutes == 40
    assert parsed.calories == 612
    assert parsed.fat_g == 10.0
    assert parsed.protein_g == 30.0
    assert parsed.carbs_g == 45.0
    assert parsed.cuisine == "French"
    assert parsed.allergens == ["dairy"]
    assert "dataset:foodcom" in parsed.tags
    assert parsed.steps == "Prep chicken\nRoast"


def test_load_usda_enrichment_and_jsonl_source(tmp_path: Path) -> None:
    source = tmp_path / "recipes.jsonl"
    source.write_text(
        "\n".join(
            [
                json.dumps({"id": "r1", "name": "One", "minutes": 10}),
                json.dumps({"id": "r2", "name": "Two", "minutes": 12}),
            ]
        ),
        encoding="utf-8",
    )

    usda = tmp_path / "nutrition.jsonl"
    usda.write_text(
        "\n".join(
            [
                json.dumps({"recipe_id": "r1", "calories_kcal": 450}),
                json.dumps({"recipe_id": "r2", "calories": 520, "protein_g": 22, "allergens": ["nuts"]}),
            ]
        ),
        encoding="utf-8",
    )

    records = iter_source_records(str(source))
    enrichment = load_usda_enrichment(str(usda))

    assert len(records) == 2
    assert enrichment["r1"]["calories"] == 450
    assert enrichment["r2"]["calories"] == 520
    assert enrichment["r2"]["protein_g"] == 22.0
    assert enrichment["r2"]["allergens"] == ["nuts"]


def test_import_curated_subset_inserts_recipes_and_skips_duplicates() -> None:
    records = [
        {
            "id": "a1",
            "name": "Tomato Pasta",
            "minutes": 25,
            "nutrition": [540],
            "ingredients": ["pasta", "tomato"],
            "steps": ["Boil", "Serve"],
            "cuisine": "Italian",
            "tags": ["pasta"],
        },
        {
            "id": "a2",
            "name": "Tomato Pasta",
            "minutes": 25,
            "nutrition": [540],
            "ingredients": ["pasta", "tomato"],
            "steps": ["Boil", "Serve"],
            "cuisine": "Italian",
            "tags": ["pasta"],
        },
        {
            "id": "a3",
            "name": "Chickpea Bowl",
            "minutes": 15,
            "ingredients": ["chickpea", "spinach"],
            "steps": ["Mix", "Serve"],
            "cuisine": "Mediterranean",
            "tags": ["vegetarian"],
            "allergens": ["sesame"],
            "estimated_cost": 6.5,
        },
    ]

    db = SessionLocal()
    try:
        owner = get_or_create_import_user(db, email="importer-test@example.com", full_name="Importer")

        stats = import_curated_foodcom_subset(
            db,
            records=records,
            owner=owner,
            limit=10,
            usda_enrichment_by_source_id={"a3": {"protein_g": 19.5, "carbs_g": 35.0, "fat_g": 9.0}},
        )

        assert stats.scanned == 3
        assert stats.imported == 2
        assert stats.skipped_duplicate == 1

        imported = db.query(Recipe).filter(Recipe.owner_id == owner.id).all()
        assert len(imported) == 2
        assert all("dataset:foodcom" in recipe.tags for recipe in imported)
        chickpea = next(recipe for recipe in imported if recipe.title == "Chickpea Bowl")
        assert chickpea.protein_g == 19.5
        assert chickpea.carbs_g == 35.0
        assert chickpea.fat_g == 9.0
        assert chickpea.allergens == ["sesame"]
        assert chickpea.cost_estimate == 6.5
    finally:
        db.close()
