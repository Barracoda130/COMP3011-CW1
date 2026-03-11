from collections import Counter
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.v1.endpoints import recipes as recipes_endpoints
from app.api.v1.endpoints import users as users_endpoints
from app.main import app


def _register_and_login(client: TestClient, email: str, password: str = "StrongPass123") -> dict[str, str]:
    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_recipe(client: TestClient, headers: dict[str, str], title: str = "Protein Pasta") -> int:
    response = client.post(
        "/api/v1/recipes",
        json={
            "title": title,
            "cuisine": "Italian",
            "prep_minutes": 25,
            "calories": 600,
            "tags": ["quick", "pasta"],
            "steps": "Simple instructions",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_unauthorized_access_to_protected_endpoints() -> None:
    protected_calls = [
        ("get", "/api/v1/auth/me", None),
        ("get", "/api/v1/recipes/mine", None),
        ("get", "/api/v1/recipes/suggested", None),
        ("get", "/api/v1/recipes/rated", None),
        (
            "post",
            "/api/v1/recipes",
            {
                "title": "Unauthorized",
                "cuisine": "Italian",
                "prep_minutes": 20,
                "calories": 500,
                "tags": ["test"],
                "steps": "No token",
            },
        ),
        ("post", "/api/v1/recipes/import-url", {"url": "https://example.com/recipe"}),
        ("post", "/api/v1/recipes/1/copy", {"title": "Copy attempt"}),
        ("put", "/api/v1/recipes/1", {"title": "Update attempt"}),
        ("delete", "/api/v1/recipes/1", None),
        ("post", "/api/v1/recipes/1/ratings", {"score": 4, "comment": "Good"}),
        ("get", "/api/v1/recipes/1/ratings/me", None),
        ("post", "/api/v1/recipes/themealdb/52772/ratings", {"score": 4, "comment": "Good"}),
        ("get", "/api/v1/recipes/themealdb/52772/ratings/me", None),
        ("post", "/api/v1/users/me/weekly-plan/generate", None),
        ("get", "/api/v1/users/me/weekly-plan/current", None),
        (
            "post",
            "/api/v1/users/me/weekly-plan/current/select",
            {"day_index": 0, "recipe_source": "local"},
        ),
    ]

    with TestClient(app) as client:
        for method, path, payload in protected_calls:
            response = getattr(client, method)(path, json=payload) if payload is not None else getattr(client, method)(path)
            assert response.status_code == 401, f"Expected 401 for {method.upper()} {path}, got {response.status_code}"


def test_auth_validation_and_duplicate_registration() -> None:
    email = f"test-{uuid4().hex[:8]}@example.com"

    with TestClient(app) as client:
        invalid_email_response = client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "StrongPass123", "full_name": "Bad Email"},
        )
        assert invalid_email_response.status_code == 422

        short_password_response = client.post(
            "/api/v1/auth/register",
            json={"email": f"short-{uuid4().hex[:8]}@example.com", "password": "short", "full_name": "Short Pass"},
        )
        assert short_password_response.status_code == 422

        register_response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "StrongPass123", "full_name": "User One"},
        )
        assert register_response.status_code == 201

        duplicate_register_response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "StrongPass123", "full_name": "User One"},
        )
        assert duplicate_register_response.status_code == 400

        bad_login_response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "WrongPass123"},
        )
        assert bad_login_response.status_code == 401


def test_recipe_create_validation_and_public_listing() -> None:
    email = f"test-{uuid4().hex[:8]}@example.com"

    with TestClient(app) as client:
        headers = _register_and_login(client, email)

        create_response = client.post(
            "/api/v1/recipes",
            json={
                "title": "Valid Recipe",
                "cuisine": "",
                "prep_minutes": 15,
                "calories": 450,
                "ingredients": ["2 eggs", "1 cup flour"],
                "tags": ["quick"],
                "steps": "A valid recipe",
            },
            headers=headers,
        )
        assert create_response.status_code == 201
        assert create_response.json()["cuisine"] == "Unknown"
        assert create_response.json()["ingredients"] == ["2 eggs", "1 cup flour"]

        cook_response = client.get(f"/api/v1/recipes/cook/local/{create_response.json()['id']}")
        assert cook_response.status_code == 200
        assert cook_response.json()["ingredients"] == [
            {"name": "2 eggs", "measure": None},
            {"name": "1 cup flour", "measure": None},
        ]

        invalid_prep_response = client.post(
            "/api/v1/recipes",
            json={
                "title": "Invalid Prep",
                "cuisine": "Italian",
                "prep_minutes": 0,
                "calories": 300,
                "tags": ["bad"],
                "steps": "Invalid prep",
            },
            headers=headers,
        )
        assert invalid_prep_response.status_code == 422

        invalid_title_response = client.post(
            "/api/v1/recipes",
            json={
                "title": "",
                "cuisine": "Italian",
                "prep_minutes": 10,
                "calories": 300,
                "tags": ["bad"],
                "steps": "Invalid title",
            },
            headers=headers,
        )
        assert invalid_title_response.status_code == 422

        invalid_calories_response = client.post(
            "/api/v1/recipes",
            json={
                "title": "Negative Calories",
                "cuisine": "Italian",
                "prep_minutes": 10,
                "calories": -1,
                "tags": ["bad"],
                "steps": "Invalid calories",
            },
            headers=headers,
        )
        assert invalid_calories_response.status_code == 422

        list_response = client.get("/api/v1/recipes")
        assert list_response.status_code == 200
        assert isinstance(list_response.json(), list)

        missing_recipe_response = client.get("/api/v1/recipes/999999")
        assert missing_recipe_response.status_code == 404


def test_recipe_update_and_delete_authorization_rules() -> None:
    owner_email = f"owner-{uuid4().hex[:8]}@example.com"
    other_email = f"other-{uuid4().hex[:8]}@example.com"

    with TestClient(app) as client:
        owner_headers = _register_and_login(client, owner_email)
        other_headers = _register_and_login(client, other_email)

        recipe_id = _create_recipe(client, owner_headers, title="Owner Recipe")

        forbidden_update = client.put(
            f"/api/v1/recipes/{recipe_id}",
            json={"title": "Illegal Update"},
            headers=other_headers,
        )
        assert forbidden_update.status_code == 403

        invalid_owner_update = client.put(
            f"/api/v1/recipes/{recipe_id}",
            json={"prep_minutes": 0},
            headers=owner_headers,
        )
        assert invalid_owner_update.status_code == 422

        valid_owner_update = client.put(
            f"/api/v1/recipes/{recipe_id}",
            json={"title": "Updated Title", "prep_minutes": 30},
            headers=owner_headers,
        )
        assert valid_owner_update.status_code == 200
        assert valid_owner_update.json()["title"] == "Updated Title"

        forbidden_delete = client.delete(f"/api/v1/recipes/{recipe_id}", headers=other_headers)
        assert forbidden_delete.status_code == 403

        owner_delete = client.delete(f"/api/v1/recipes/{recipe_id}", headers=owner_headers)
        assert owner_delete.status_code == 204

        deleted_lookup = client.get(f"/api/v1/recipes/{recipe_id}")
        assert deleted_lookup.status_code == 404


def test_recipe_copy_endpoint_valid_and_invalid_submissions() -> None:
    owner_email = f"owner-{uuid4().hex[:8]}@example.com"
    editor_email = f"editor-{uuid4().hex[:8]}@example.com"

    with TestClient(app) as client:
        owner_headers = _register_and_login(client, owner_email)
        editor_headers = _register_and_login(client, editor_email)

        recipe_id = _create_recipe(client, owner_headers, title="Source Recipe")

        copy_response = client.post(
            f"/api/v1/recipes/{recipe_id}/copy",
            json={"title": "Copied Version", "prep_minutes": 28},
            headers=editor_headers,
        )
        assert copy_response.status_code == 201
        assert copy_response.json()["title"] == "Copied Version"

        missing_copy_response = client.post(
            "/api/v1/recipes/999999/copy",
            json={"title": "Missing"},
            headers=editor_headers,
        )
        assert missing_copy_response.status_code == 404

        invalid_copy_payload = client.post(
            f"/api/v1/recipes/{recipe_id}/copy",
            json={"prep_minutes": 0},
            headers=editor_headers,
        )
        assert invalid_copy_payload.status_code == 422


def test_local_rating_validation_and_conflict_behavior() -> None:
    email = f"test-{uuid4().hex[:8]}@example.com"

    with TestClient(app) as client:
        headers = _register_and_login(client, email)
        recipe_id = _create_recipe(client, headers, title="Rate Me")

        valid_rate = client.post(
            f"/api/v1/recipes/{recipe_id}/ratings",
            json={"score": 5, "comment": "Excellent"},
            headers=headers,
        )
        assert valid_rate.status_code == 200

        duplicate_rate = client.post(
            f"/api/v1/recipes/{recipe_id}/ratings",
            json={"score": 4, "comment": "Again"},
            headers=headers,
        )
        assert duplicate_rate.status_code == 409

        invalid_rate_value = client.post(
            f"/api/v1/recipes/{recipe_id}/ratings",
            json={"score": 6, "comment": "Invalid"},
            headers=headers,
        )
        # Validation runs before conflict check.
        assert invalid_rate_value.status_code == 422

        get_my_rating = client.get(f"/api/v1/recipes/{recipe_id}/ratings/me", headers=headers)
        assert get_my_rating.status_code == 200
        assert get_my_rating.json()["score"] == 5

        another_recipe_id = _create_recipe(client, headers, title="Unrated")
        unrated_lookup = client.get(f"/api/v1/recipes/{another_recipe_id}/ratings/me", headers=headers)
        assert unrated_lookup.status_code == 404


def test_themealdb_rating_validation_and_lookup() -> None:
    email = f"test-{uuid4().hex[:8]}@example.com"

    with TestClient(app) as client:
        headers = _register_and_login(client, email)

        invalid_external_id_response = client.post(
            "/api/v1/recipes/themealdb/not-a-number/ratings",
            json={"score": 4, "comment": "Bad id"},
            headers=headers,
        )
        assert invalid_external_id_response.status_code == 400

        valid_external_rate = client.post(
            "/api/v1/recipes/themealdb/52772/ratings",
            json={"score": 4, "comment": "Great"},
            headers=headers,
        )
        assert valid_external_rate.status_code == 200

        duplicate_external_rate = client.post(
            "/api/v1/recipes/themealdb/52772/ratings",
            json={"score": 3, "comment": "Again"},
            headers=headers,
        )
        assert duplicate_external_rate.status_code == 409

        get_external_rating = client.get("/api/v1/recipes/themealdb/52772/ratings/me", headers=headers)
        assert get_external_rating.status_code == 200
        assert get_external_rating.json()["score"] == 4

        missing_external_rating = client.get("/api/v1/recipes/themealdb/99999/ratings/me", headers=headers)
        assert missing_external_rating.status_code == 404


def test_recipe_import_url_success_and_parse_failure(monkeypatch) -> None:
    email = f"test-{uuid4().hex[:8]}@example.com"

    with TestClient(app) as client:
        headers = _register_and_login(client, email)

        def _fake_extract_success(_url: str) -> dict[str, object]:
            return {
                "title": "Imported Curry",
                "cuisine": "Indian",
                "prep_minutes": 45,
                "calories": None,
                "image_url": "https://example.com/curry.jpg",
                "ingredients": ["1 onion", "2 tomatoes"],
                "tags": ["curry", "spicy"],
                "steps": "Imported description",
                "source_url": "https://example.com/curry",
            }

        monkeypatch.setattr(recipes_endpoints, "extract_recipe_from_url", _fake_extract_success)

        success = client.post(
            "/api/v1/recipes/import-url",
            json={"url": "https://example.com/curry"},
            headers=headers,
        )
        assert success.status_code == 200
        body = success.json()
        assert body["title"] == "Imported Curry"
        assert body["prep_minutes"] == 45
        assert body["ingredients"] == ["1 onion", "2 tomatoes"]
        assert body["source_url"] == "https://example.com/curry"

        def _fake_extract_failure(_url: str) -> dict[str, object]:
            raise recipes_endpoints.RecipeImportError("Could not parse recipe data from this URL")

        monkeypatch.setattr(recipes_endpoints, "extract_recipe_from_url", _fake_extract_failure)

        failure = client.post(
            "/api/v1/recipes/import-url",
            json={"url": "https://example.com/no-recipe"},
            headers=headers,
        )
        assert failure.status_code == 400
        assert failure.json()["detail"] == "Could not parse recipe data from this URL"


def test_recipe_import_url_unsupported_source_error(monkeypatch) -> None:
    email = f"test-{uuid4().hex[:8]}@example.com"

    with TestClient(app) as client:
        headers = _register_and_login(client, email)

        def _fake_extract_failure(_url: str) -> dict[str, object]:
            raise recipes_endpoints.RecipeImportError("URL does not appear to be an HTML recipe page")

        monkeypatch.setattr(recipes_endpoints, "extract_recipe_from_url", _fake_extract_failure)

        response = client.post(
            "/api/v1/recipes/import-url",
            json={"url": "https://example.com/file.pdf"},
            headers=headers,
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "URL does not appear to be an HTML recipe page"

        invalid_scheme_response = client.post(
            "/api/v1/recipes/import-url",
            json={"url": "ftp://example.com/recipe"},
            headers=headers,
        )
        assert invalid_scheme_response.status_code == 422

def test_discover_suggested_and_rated_query_validation(monkeypatch) -> None:
    email = f"test-{uuid4().hex[:8]}@example.com"

    # Keep search deterministic and offline.
    monkeypatch.setattr(recipes_endpoints, "search_themealdb_recipes", lambda query, limit=20: [])

    with TestClient(app) as client:
        headers = _register_and_login(client, email)
        _create_recipe(client, headers, title="Query Recipe")

        discover_ok = client.get("/api/v1/recipes/discover?query=pasta&local_limit=10&external_limit=20")
        assert discover_ok.status_code == 200
        payload = discover_ok.json()
        assert "items" in payload and "local_count" in payload and "external_count" in payload

        discover_bad_local_limit = client.get("/api/v1/recipes/discover?local_limit=0")
        assert discover_bad_local_limit.status_code == 422

        discover_bad_external_limit = client.get("/api/v1/recipes/discover?external_limit=999")
        assert discover_bad_external_limit.status_code == 422

        suggested_ok = client.get("/api/v1/recipes/suggested", headers=headers)
        assert suggested_ok.status_code == 200
        assert "formula" in suggested_ok.json()

        suggested_bad_limit = client.get("/api/v1/recipes/suggested?local_limit=0", headers=headers)
        assert suggested_bad_limit.status_code == 422

        rated_bad_score_filter = client.get("/api/v1/recipes/rated?score=6", headers=headers)
        assert rated_bad_score_filter.status_code == 422

        mine_ok = client.get("/api/v1/recipes/mine?query=query", headers=headers)
        assert mine_ok.status_code == 200
        assert isinstance(mine_ok.json(), list)


def test_weekly_plan_generate_and_get_current_with_constraints(monkeypatch) -> None:
    email = f"planner-{uuid4().hex[:8]}@example.com"

    # Keep weekly plan generation deterministic and offline for this constraints test.
    external_catalog = [
        {
            "id": "themealdb-8001",
            "external_id": "8001",
            "source": "themealdb",
            "title": "External Chicken Plate",
            "cuisine": "French",
            "image_url": None,
            "prep_minutes": None,
            "calories": None,
            "description": "zesty",
            "tags": ["chicken"],
            "category": "Chicken",
            "key_ingredients": ["chicken", "lemon"],
            "average_rating": None,
            "owner_id": None,
        },
        {
            "id": "themealdb-8002",
            "external_id": "8002",
            "source": "themealdb",
            "title": "External Tofu Plate",
            "cuisine": "Japanese",
            "image_url": None,
            "prep_minutes": None,
            "calories": None,
            "description": "light",
            "tags": ["tofu"],
            "category": "Vegetarian",
            "key_ingredients": ["tofu", "rice"],
            "average_rating": None,
            "owner_id": None,
        },
        {
            "id": "themealdb-8003",
            "external_id": "8003",
            "source": "themealdb",
            "title": "External Beef Plate",
            "cuisine": "Mexican",
            "image_url": None,
            "prep_minutes": None,
            "calories": None,
            "description": "hearty",
            "tags": ["beef"],
            "category": "Beef",
            "key_ingredients": ["beef", "pepper"],
            "average_rating": None,
            "owner_id": None,
        },
    ]
    monkeypatch.setattr(users_endpoints, "search_themealdb_recipes", lambda query, limit=20: external_catalog)
    monkeypatch.setattr(users_endpoints, "get_themealdb_recipe_by_id", lambda external_id: None)

    with TestClient(app) as client:
        headers = _register_and_login(client, email)

        recipe_payloads = [
            {
                "title": "Quick Chicken Pasta",
                "cuisine": "Italian",
                "prep_minutes": 20,
                "calories": 550,
                "ingredients": ["chicken breast", "pasta"],
                "tags": ["quick"],
                "steps": "Cook quickly",
            },
            {
                "title": "Quick Tofu Bowl",
                "cuisine": "Asian",
                "prep_minutes": 18,
                "calories": 500,
                "ingredients": ["tofu", "rice"],
                "tags": ["quick"],
                "steps": "Stir fry",
            },
            {
                "title": "Quick Beef Wrap",
                "cuisine": "Mexican",
                "prep_minutes": 22,
                "calories": 620,
                "ingredients": ["beef", "tortilla"],
                "tags": ["quick"],
                "steps": "Assemble",
            },
            {
                "title": "Quick Salmon Rice",
                "cuisine": "Japanese",
                "prep_minutes": 25,
                "calories": 580,
                "ingredients": ["salmon", "rice"],
                "tags": ["quick"],
                "steps": "Steam and serve",
            },
            {
                "title": "Quick Veg Curry",
                "cuisine": "Indian",
                "prep_minutes": 30,
                "calories": 540,
                "ingredients": ["cauliflower", "peas"],
                "tags": ["quick"],
                "steps": "Simmer",
            },
            {
                "title": "Slow Lamb Roast",
                "cuisine": "British",
                "prep_minutes": 75,
                "calories": 760,
                "ingredients": ["lamb", "potato"],
                "tags": ["hearty"],
                "steps": "Roast slowly",
            },
            {
                "title": "Weekend Lasagna",
                "cuisine": "Italian",
                "prep_minutes": 65,
                "calories": 820,
                "ingredients": ["beef mince", "pasta sheets"],
                "tags": ["comfort"],
                "steps": "Bake",
            },
            {
                "title": "Quick Chickpea Salad",
                "cuisine": "Mediterranean",
                "prep_minutes": 15,
                "calories": 430,
                "ingredients": ["chickpea", "tomato"],
                "tags": ["quick"],
                "steps": "Mix",
            },
        ]

        for payload in recipe_payloads:
            created = client.post("/api/v1/recipes", json=payload, headers=headers)
            assert created.status_code == 201

        generated = client.post("/api/v1/users/me/weekly-plan/generate", headers=headers)
        assert generated.status_code == 200
        generated_body = generated.json()
        assert generated_body["status"] == "active"
        assert len(generated_body["items"]) == 14

        current = client.get("/api/v1/users/me/weekly-plan/current", headers=headers)
        assert current.status_code == 200
        current_items = sorted(current.json()["items"], key=lambda item: item["day_index"])
        assert current_items == sorted(generated_body["items"], key=lambda item: item["day_index"])

        # Constraint checks on local option track only.
        local_items = [item for item in current_items if item["recipe_source"] == "local"]
        external_items = [item for item in current_items if item["recipe_source"] == "themealdb"]
        assert len(local_items) == 7
        assert len(external_items) == 7

        # Constraint: avoid consecutive same main ingredient inferred from local selected recipes.
        recipe_lookup = {}
        for recipe in client.get("/api/v1/recipes").json():
            recipe_lookup[recipe["id"]] = recipe

        local_items_sorted = sorted(local_items, key=lambda item: item["day_index"])
        for idx in range(1, len(local_items_sorted)):
            prev_recipe = recipe_lookup.get(local_items_sorted[idx - 1]["recipe_id"])
            current_recipe = recipe_lookup.get(local_items_sorted[idx]["recipe_id"])
            if not prev_recipe or not current_recipe:
                continue
            prev_first = (prev_recipe.get("ingredients") or ["unknown"])[0].split()[0].lower()
            current_first = (current_recipe.get("ingredients") or ["unknown"])[0].split()[0].lower()
            if prev_first != "unknown" and current_first != "unknown":
                assert prev_first != current_first

        # Constraint: cap repeated cuisine to max 2 in generated local options.
        cuisines = [
            recipe_lookup[item["recipe_id"]]["cuisine"]
            for item in local_items
            if item.get("recipe_id") in recipe_lookup
        ]
        for _cuisine, count in Counter(cuisines).items():
            assert count <= 2

        # User selection should persist one chosen option per day.
        select_response = client.post(
            "/api/v1/users/me/weekly-plan/current/select",
            json={"day_index": 0, "recipe_source": "themealdb"},
            headers=headers,
        )
        assert select_response.status_code == 200
        day0_items = [item for item in select_response.json()["items"] if item["day_index"] == 0]
        selected_sources = [item["recipe_source"] for item in day0_items if item["is_selected"]]
        assert selected_sources == ["themealdb"]


def test_weekly_plan_can_include_themealdb_and_local(monkeypatch) -> None:
    email = f"planner-mixed-{uuid4().hex[:8]}@example.com"

    external_catalog = [
        {
            "id": "themealdb-9001",
            "external_id": "9001",
            "source": "themealdb",
            "title": "External Lemon Chicken",
            "cuisine": "French",
            "image_url": None,
            "prep_minutes": None,
            "calories": None,
            "description": "zesty",
            "tags": ["chicken", "quick"],
            "category": "Chicken",
            "key_ingredients": ["chicken", "lemon"],
            "average_rating": None,
            "owner_id": None,
        },
        {
            "id": "themealdb-9002",
            "external_id": "9002",
            "source": "themealdb",
            "title": "External Veg Pasta",
            "cuisine": "Italian",
            "image_url": None,
            "prep_minutes": None,
            "calories": None,
            "description": "comfort",
            "tags": ["vegetarian"],
            "category": "Pasta",
            "key_ingredients": ["pasta", "tomato"],
            "average_rating": None,
            "owner_id": None,
        },
        {
            "id": "themealdb-9003",
            "external_id": "9003",
            "source": "themealdb",
            "title": "External Beef Rice",
            "cuisine": "Thai",
            "image_url": None,
            "prep_minutes": None,
            "calories": None,
            "description": "hearty",
            "tags": ["beef"],
            "category": "Beef",
            "key_ingredients": ["beef", "rice"],
            "average_rating": None,
            "owner_id": None,
        },
        {
            "id": "themealdb-9004",
            "external_id": "9004",
            "source": "themealdb",
            "title": "External Fish Stew",
            "cuisine": "Spanish",
            "image_url": None,
            "prep_minutes": None,
            "calories": None,
            "description": "rich",
            "tags": ["fish"],
            "category": "Seafood",
            "key_ingredients": ["cod", "pepper"],
            "average_rating": None,
            "owner_id": None,
        },
    ]

    monkeypatch.setattr(users_endpoints, "search_themealdb_recipes", lambda query, limit=20: external_catalog)
    monkeypatch.setattr(users_endpoints, "get_themealdb_recipe_by_id", lambda external_id: None)

    with TestClient(app) as client:
        headers = _register_and_login(client, email)

        local_payloads = [
            {
                "title": "Local Chicken Bowl",
                "cuisine": "Asian",
                "prep_minutes": 20,
                "calories": 500,
                "ingredients": ["chicken", "rice"],
                "tags": ["quick"],
                "steps": "Cook",
            },
            {
                "title": "Local Bean Chili",
                "cuisine": "Mexican",
                "prep_minutes": 35,
                "calories": 620,
                "ingredients": ["beans", "tomato"],
                "tags": ["hearty"],
                "steps": "Simmer",
            },
            {
                "title": "Local Herb Salmon",
                "cuisine": "Nordic",
                "prep_minutes": 28,
                "calories": 580,
                "ingredients": ["salmon", "potato"],
                "tags": ["fresh"],
                "steps": "Bake",
            },
        ]

        for payload in local_payloads:
            created = client.post("/api/v1/recipes", json=payload, headers=headers)
            assert created.status_code == 201

        generated = client.post("/api/v1/users/me/weekly-plan/generate", headers=headers)
        assert generated.status_code == 200
        items = generated.json()["items"]
        assert len(items) == 14

        sources = {item["recipe_source"] for item in items}
        assert "local" in sources
        assert "themealdb" in sources

        external_ids = [item["external_recipe_id"] for item in items if item["recipe_source"] == "themealdb"]
        assert all(external_id for external_id in external_ids)
