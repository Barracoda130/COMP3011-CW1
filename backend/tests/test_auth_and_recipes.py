from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.v1.endpoints import recipes as recipes_endpoints
from app.main import app


def test_register_login_create_recipe_and_rate() -> None:
    email = f"test-{uuid4().hex[:8]}@example.com"
    password = "StrongPass123"

    with TestClient(app) as client:
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
        headers = {"Authorization": f"Bearer {token}"}

        create_recipe_response = client.post(
            "/api/v1/recipes",
            json={
                "title": "Protein Pasta",
                "prep_minutes": 20,
                "calories": 650,
                "tags": ["high-protein", "quick"],
                "steps": "Simple high-protein meal.",
            },
            headers=headers,
        )
        assert create_recipe_response.status_code == 201
        assert create_recipe_response.json()["cuisine"] == "Unknown"
        recipe_id = create_recipe_response.json()["id"]

        rate_response = client.post(
            f"/api/v1/recipes/{recipe_id}/ratings",
            json={"score": 5, "comment": "Loved it"},
            headers=headers,
        )
        assert rate_response.status_code == 200
        assert rate_response.json()["score"] == 5

        get_my_rating_response = client.get(
            f"/api/v1/recipes/{recipe_id}/ratings/me",
            headers=headers,
        )
        assert get_my_rating_response.status_code == 200
        assert get_my_rating_response.json()["score"] == 5

        second_rate_response = client.post(
            f"/api/v1/recipes/{recipe_id}/ratings",
            json={"score": 3, "comment": "Second attempt"},
            headers=headers,
        )
        assert second_rate_response.status_code == 409


def test_rate_themealdb_recipe_by_external_id() -> None:
    email = f"test-{uuid4().hex[:8]}@example.com"
    password = "StrongPass123"

    with TestClient(app) as client:
        register_response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "External Rating User"},
        )
        assert register_response.status_code == 201

        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        rate_response = client.post(
            "/api/v1/recipes/themealdb/52772/ratings",
            json={"score": 4, "comment": "Great external meal"},
            headers=headers,
        )
        assert rate_response.status_code == 200
        payload = rate_response.json()
        assert payload["external_recipe_id"] == "52772"
        assert payload["score"] == 4
        assert payload["source"] == "themealdb"

        get_my_rating_response = client.get(
            "/api/v1/recipes/themealdb/52772/ratings/me",
            headers=headers,
        )
        assert get_my_rating_response.status_code == 200
        assert get_my_rating_response.json()["score"] == 4

        second_rate_response = client.post(
            "/api/v1/recipes/themealdb/52772/ratings",
            json={"score": 2, "comment": "Second attempt"},
            headers=headers,
        )
        assert second_rate_response.status_code == 409


def test_get_suggested_recipes_uses_user_rating_profile(monkeypatch) -> None:
    email = f"test-{uuid4().hex[:8]}@example.com"
    password = "StrongPass123"

    # Keep the test deterministic and offline.
    monkeypatch.setattr(recipes_endpoints, "search_themealdb_recipes", lambda query, limit=20: [])

    with TestClient(app) as client:
        register_response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Suggestion User"},
        )
        assert register_response.status_code == 201

        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        liked_recipe_response = client.post(
            "/api/v1/recipes",
            json={
                "title": "Tomato Pasta",
                "cuisine": "Italian",
                "prep_minutes": 25,
                "calories": 540,
                "ingredients": ["rarebasil", "tomato"],
                "tags": ["pasta", "tomato", "quick"],
                "steps": "Simple tomato pasta",
            },
            headers=headers,
        )
        assert liked_recipe_response.status_code == 201
        liked_recipe_id = liked_recipe_response.json()["id"]

        candidate_recipe_response = client.post(
            "/api/v1/recipes",
            json={
                "title": "Creamy Pasta",
                "cuisine": "Italian",
                "prep_minutes": 30,
                "calories": 620,
                "ingredients": ["rarebasil", "cream"],
                "tags": ["pasta", "creamy"],
                "steps": "Creamy pasta",
            },
            headers=headers,
        )
        assert candidate_recipe_response.status_code == 201

        disliked_recipe_response = client.post(
            "/api/v1/recipes",
            json={
                "title": "Spicy Tofu Stir Fry",
                "cuisine": "Asian",
                "prep_minutes": 20,
                "calories": 450,
                "tags": ["tofu", "spicy"],
                "steps": "Spicy tofu",
            },
            headers=headers,
        )
        assert disliked_recipe_response.status_code == 201
        disliked_recipe_id = disliked_recipe_response.json()["id"]

        like_rating_response = client.post(
            f"/api/v1/recipes/{liked_recipe_id}/ratings",
            json={"score": 5, "comment": "Loved it"},
            headers=headers,
        )
        assert like_rating_response.status_code == 200

        dislike_rating_response = client.post(
            f"/api/v1/recipes/{disliked_recipe_id}/ratings",
            json={"score": 1, "comment": "Not for me"},
            headers=headers,
        )
        assert dislike_rating_response.status_code == 200

        suggested_response = client.get("/api/v1/recipes/suggested?local_limit=80&external_limit=1", headers=headers)
        assert suggested_response.status_code == 200
        payload = suggested_response.json()

        assert "score =" in payload["formula"]
        assert payload["local_count"] >= 1
        assert any(item["title"] == "Creamy Pasta" for item in payload["items"])
        creamy = next(item for item in payload["items"] if item["title"] == "Creamy Pasta")
        assert isinstance(creamy.get("reasons"), list)
        assert creamy["reasons"]


def test_suggested_recipes_excludes_already_rated(monkeypatch) -> None:
    email = f"test-{uuid4().hex[:8]}@example.com"
    password = "StrongPass123"

    external_candidate = {
        "id": "themealdb-52772",
        "external_id": "52772",
        "source": "themealdb",
        "title": "Rated External Meal",
        "cuisine": "British",
        "image_url": None,
        "prep_minutes": None,
        "calories": None,
        "steps": "Already rated",
        "tags": ["beef"],
        "category": "Beef",
        "key_ingredients": ["beef"],
        "average_rating": None,
        "owner_id": None,
    }

    monkeypatch.setattr(
        recipes_endpoints,
        "search_themealdb_recipes",
        lambda query, limit=20: [external_candidate],
    )
    monkeypatch.setattr(
        recipes_endpoints,
        "get_themealdb_recipe_by_id",
        lambda external_id: {
            "id": f"themealdb-{external_id}",
            "source": "themealdb",
            "title": "Rated External Meal",
            "cuisine": "British",
            "steps": "Beef",
            "instructions": "Cook it",
            "image_url": None,
            "tags": ["beef"],
            "ingredients": [{"name": "beef", "measure": None}],
            "prep_minutes": None,
            "calories": None,
        },
    )

    with TestClient(app) as client:
        register_response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Exclude Rated User"},
        )
        assert register_response.status_code == 201

        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        liked_recipe_response = client.post(
            "/api/v1/recipes",
            json={
                "title": "Beef Pie",
                "cuisine": "British",
                "prep_minutes": 35,
                "calories": 700,
                "tags": ["beef", "pie"],
                "steps": "Hearty",
            },
            headers=headers,
        )
        assert liked_recipe_response.status_code == 201
        liked_recipe_id = liked_recipe_response.json()["id"]

        like_rating_response = client.post(
            f"/api/v1/recipes/{liked_recipe_id}/ratings",
            json={"score": 5, "comment": "Great"},
            headers=headers,
        )
        assert like_rating_response.status_code == 200

        rate_external_response = client.post(
            "/api/v1/recipes/themealdb/52772/ratings",
            json={"score": 4, "comment": "Also great"},
            headers=headers,
        )
        assert rate_external_response.status_code == 200

        suggested_response = client.get("/api/v1/recipes/suggested?local_limit=80&external_limit=1", headers=headers)
        assert suggested_response.status_code == 200
        suggested_items = suggested_response.json()["items"]

        assert all(item.get("external_id") != "52772" for item in suggested_items)
        assert all(item.get("id") != liked_recipe_id for item in suggested_items)


def test_get_rated_recipes_supports_search_and_score_filter(monkeypatch) -> None:
    email = f"test-{uuid4().hex[:8]}@example.com"
    password = "StrongPass123"

    monkeypatch.setattr(
        recipes_endpoints,
        "get_themealdb_recipe_by_id",
        lambda external_id: {
            "id": f"themealdb-{external_id}",
            "source": "themealdb",
            "title": "Chicken Handi",
            "cuisine": "Indian",
            "steps": "Chicken",
            "instructions": "Cook it",
            "image_url": None,
            "tags": ["chicken"],
            "ingredients": [{"name": "chicken", "measure": None}],
            "prep_minutes": None,
            "calories": None,
        },
    )

    with TestClient(app) as client:
        register_response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Rated List User"},
        )
        assert register_response.status_code == 201

        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        local_recipe_response = client.post(
            "/api/v1/recipes",
            json={
                "title": "Lemon Pasta",
                "cuisine": "Italian",
                "prep_minutes": 20,
                "calories": 550,
                "tags": ["pasta", "lemon"],
                "steps": "Tangy",
            },
            headers=headers,
        )
        assert local_recipe_response.status_code == 201
        local_recipe_id = local_recipe_response.json()["id"]

        local_rating_response = client.post(
            f"/api/v1/recipes/{local_recipe_id}/ratings",
            json={"score": 5, "comment": "Favorite"},
            headers=headers,
        )
        assert local_rating_response.status_code == 200

        external_rating_response = client.post(
            "/api/v1/recipes/themealdb/52846/ratings",
            json={"score": 2, "comment": "Not great"},
            headers=headers,
        )
        assert external_rating_response.status_code == 200

        filtered_response = client.get("/api/v1/recipes/rated?query=pasta&score=5", headers=headers)
        assert filtered_response.status_code == 200
        payload = filtered_response.json()

        assert payload["local_count"] == 1
        assert payload["external_count"] == 0
        assert len(payload["items"]) == 1
        assert payload["items"][0]["title"] == "Lemon Pasta"
        assert payload["items"][0]["my_rating"] == 5


def test_suggested_recipes_uses_cache_until_new_rating(monkeypatch) -> None:
    email = f"test-{uuid4().hex[:8]}@example.com"
    password = "StrongPass123"

    call_counter = {"count": 0}

    def fake_search_themealdb(query, limit=20):
        call_counter["count"] += 1
        return []

    monkeypatch.setattr(recipes_endpoints, "search_themealdb_recipes", fake_search_themealdb)

    with TestClient(app) as client:
        register_response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Cache User"},
        )
        assert register_response.status_code == 201

        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r1 = client.post(
            "/api/v1/recipes",
            json={
                "title": "Herb Pasta",
                "cuisine": "Italian",
                "prep_minutes": 20,
                "calories": 550,
                "tags": ["pasta", "herb"],
                "steps": "Good",
            },
            headers=headers,
        )
        assert r1.status_code == 201
        r1_id = r1.json()["id"]

        rate1 = client.post(
            f"/api/v1/recipes/{r1_id}/ratings",
            json={"score": 5, "comment": "great"},
            headers=headers,
        )
        assert rate1.status_code == 200

        candidate = client.post(
            "/api/v1/recipes",
            json={
                "title": "Pesto Pasta",
                "cuisine": "Italian",
                "prep_minutes": 25,
                "calories": 600,
                "tags": ["pasta", "basil"],
                "steps": "Candidate",
            },
            headers=headers,
        )
        assert candidate.status_code == 201

        first_suggested = client.get("/api/v1/recipes/suggested", headers=headers)
        assert first_suggested.status_code == 200
        first_payload = first_suggested.json()
        assert any(item["title"] == "Pesto Pasta" for item in first_payload["items"])

        first_call_count = call_counter["count"]
        assert first_call_count >= 1

        second_suggested = client.get("/api/v1/recipes/suggested", headers=headers)
        assert second_suggested.status_code == 200
        assert call_counter["count"] == first_call_count

        r2 = client.post(
            "/api/v1/recipes",
            json={
                "title": "Spicy Tofu",
                "cuisine": "Asian",
                "prep_minutes": 18,
                "calories": 430,
                "tags": ["tofu", "spicy"],
                "steps": "Disliked pattern",
            },
            headers=headers,
        )
        assert r2.status_code == 201
        r2_id = r2.json()["id"]

        rate2 = client.post(
            f"/api/v1/recipes/{r2_id}/ratings",
            json={"score": 1, "comment": "bad"},
            headers=headers,
        )
        assert rate2.status_code == 200

        third_suggested = client.get("/api/v1/recipes/suggested", headers=headers)
        assert third_suggested.status_code == 200
        assert call_counter["count"] > first_call_count


def test_suggested_recipes_include_prep_and_calorie_reasons(monkeypatch) -> None:
    email = f"test-{uuid4().hex[:8]}@example.com"
    password = "StrongPass123"

    monkeypatch.setattr(recipes_endpoints, "search_themealdb_recipes", lambda query, limit=20: [])

    with TestClient(app) as client:
        register_response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Band Preference User"},
        )
        assert register_response.status_code == 201

        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        liked = client.post(
            "/api/v1/recipes",
            json={
                "title": "Quick Light Bowl",
                "cuisine": "Mediterranean",
                "prep_minutes": 20,
                "calories": 420,
                "ingredients": ["chickpeas", "spinach"],
                "tags": ["quick", "light"],
                "steps": "Mix",
            },
            headers=headers,
        )
        assert liked.status_code == 201
        liked_id = liked.json()["id"]

        candidate = client.post(
            "/api/v1/recipes",
            json={
                "title": "Fast Veg Plate",
                "cuisine": "Mediterranean",
                "prep_minutes": 22,
                "calories": 430,
                "ingredients": ["spinach", "tomato"],
                "tags": ["quick"],
                "steps": "Serve",
            },
            headers=headers,
        )
        assert candidate.status_code == 201

        disliked = client.post(
            "/api/v1/recipes",
            json={
                "title": "Slow Heavy Dish",
                "cuisine": "American",
                "prep_minutes": 70,
                "calories": 880,
                "ingredients": ["beef", "cream"],
                "tags": ["heavy"],
                "steps": "Cook long",
            },
            headers=headers,
        )
        assert disliked.status_code == 201
        disliked_id = disliked.json()["id"]

        like_rating = client.post(
            f"/api/v1/recipes/{liked_id}/ratings",
            json={"score": 5, "comment": "Great"},
            headers=headers,
        )
        assert like_rating.status_code == 200

        dislike_rating = client.post(
            f"/api/v1/recipes/{disliked_id}/ratings",
            json={"score": 1, "comment": "Too heavy"},
            headers=headers,
        )
        assert dislike_rating.status_code == 200

        suggested_response = client.get("/api/v1/recipes/suggested", headers=headers)
        assert suggested_response.status_code == 200
        payload = suggested_response.json()

        matched = next(item for item in payload["items"] if item["title"] == "Fast Veg Plate")
        reasons_text = " ".join(matched.get("reasons") or []).lower()
        assert "prep time aligns" in reasons_text
        assert "calorie range matches" in reasons_text


def test_suggested_recipes_weight_rare_and_high_quantity_liked_ingredients(monkeypatch) -> None:
    email = f"test-{uuid4().hex[:8]}@example.com"
    password = "StrongPass123"

    monkeypatch.setattr(recipes_endpoints, "search_themealdb_recipes", lambda query, limit=20: [])

    with TestClient(app) as client:
        register_response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Rarity Quantity User"},
        )
        assert register_response.status_code == 201

        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        liked = client.post(
            "/api/v1/recipes",
            json={
                "title": "Loved Rare Stew",
                "cuisine": "Fusion",
                "prep_minutes": 30,
                "calories": 600,
                "ingredients": ["6 saffron threads", "1 pinch salt"],
                "tags": ["stew"],
                "steps": "Cook",
            },
            headers=headers,
        )
        assert liked.status_code == 201
        liked_id = liked.json()["id"]

        for idx in range(12):
            filler = client.post(
                "/api/v1/recipes",
                json={
                    "title": f"Salt Filler {idx}",
                    "cuisine": "Generic",
                    "prep_minutes": 20,
                    "calories": 500,
                    "ingredients": ["1 tsp salt", "1 cup water"],
                    "tags": ["filler"],
                    "steps": "Mix",
                },
                headers=headers,
            )
            assert filler.status_code == 201

        strong_rare_candidate = client.post(
            "/api/v1/recipes",
            json={
                "title": "Saffron Forward Rice",
                "cuisine": "Fusion",
                "prep_minutes": 28,
                "calories": 610,
                "ingredients": ["5 saffron threads", "1 cup rice"],
                "tags": ["rice"],
                "steps": "Simmer",
            },
            headers=headers,
        )
        assert strong_rare_candidate.status_code == 201

        common_candidate = client.post(
            "/api/v1/recipes",
            json={
                "title": "Extra Salty Soup",
                "cuisine": "Generic",
                "prep_minutes": 18,
                "calories": 480,
                "ingredients": ["7 tsp salt", "1 cup stock"],
                "tags": ["soup"],
                "steps": "Boil",
            },
            headers=headers,
        )
        assert common_candidate.status_code == 201

        like_rating = client.post(
            f"/api/v1/recipes/{liked_id}/ratings",
            json={"score": 5, "comment": "Loved this"},
            headers=headers,
        )
        assert like_rating.status_code == 200

        suggested_response = client.get("/api/v1/recipes/suggested?local_limit=80&external_limit=1", headers=headers)
        assert suggested_response.status_code == 200
        payload = suggested_response.json()

        rare_item = next(item for item in payload["items"] if item["title"] == "Saffron Forward Rice")
        common_item = next(item for item in payload["items"] if item["title"] == "Extra Salty Soup")
        assert rare_item["recommendation_score"] > common_item["recommendation_score"]


def test_my_recipes_list_and_copy_edit_flow() -> None:
    owner_email = f"owner-{uuid4().hex[:8]}@example.com"
    editor_email = f"editor-{uuid4().hex[:8]}@example.com"
    password = "StrongPass123"

    with TestClient(app) as client:
        owner_register = client.post(
            "/api/v1/auth/register",
            json={"email": owner_email, "password": password, "full_name": "Owner"},
        )
        assert owner_register.status_code == 201

        editor_register = client.post(
            "/api/v1/auth/register",
            json={"email": editor_email, "password": password, "full_name": "Editor"},
        )
        assert editor_register.status_code == 201

        owner_login = client.post(
            "/api/v1/auth/login",
            data={"username": owner_email, "password": password},
        )
        assert owner_login.status_code == 200
        owner_headers = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}

        editor_login = client.post(
            "/api/v1/auth/login",
            data={"username": editor_email, "password": password},
        )
        assert editor_login.status_code == 200
        editor_headers = {"Authorization": f"Bearer {editor_login.json()['access_token']}"}

        create_response = client.post(
            "/api/v1/recipes",
            json={
                "title": "Original Pasta",
                "cuisine": "Italian",
                "prep_minutes": 20,
                "calories": 500,
                "image_url": "data:image/png;base64,AAA",
                "tags": ["pasta", "quick"],
                "steps": "Original description",
            },
            headers=owner_headers,
        )
        assert create_response.status_code == 201
        original_recipe = create_response.json()
        original_id = original_recipe["id"]

        my_recipes_owner = client.get("/api/v1/recipes/mine", headers=owner_headers)
        assert my_recipes_owner.status_code == 200
        owner_titles = [item["title"] for item in my_recipes_owner.json()]
        assert "Original Pasta" in owner_titles

        my_recipes_editor_before = client.get("/api/v1/recipes/mine", headers=editor_headers)
        assert my_recipes_editor_before.status_code == 200
        assert my_recipes_editor_before.json() == []

        copy_response = client.post(
            f"/api/v1/recipes/{original_id}/copy",
            json={
                "title": "Original Pasta - My Version",
                "steps": "Tweaked version",
                "tags": ["pasta", "custom"],
            },
            headers=editor_headers,
        )
        assert copy_response.status_code == 201
        copied_recipe = copy_response.json()
        assert copied_recipe["title"] == "Original Pasta - My Version"
        assert copied_recipe["steps"] == "Tweaked version"
        assert copied_recipe["image_url"] == "data:image/png;base64,AAA"
        assert copied_recipe["owner_id"] != original_recipe["owner_id"]

        original_after_copy = client.get(f"/api/v1/recipes/{original_id}")
        assert original_after_copy.status_code == 200
        assert original_after_copy.json()["title"] == "Original Pasta"
        assert original_after_copy.json()["steps"] == "Original description"

        my_recipes_editor_after = client.get("/api/v1/recipes/mine", headers=editor_headers)
        assert my_recipes_editor_after.status_code == 200
        editor_titles = [item["title"] for item in my_recipes_editor_after.json()]
        assert "Original Pasta - My Version" in editor_titles
