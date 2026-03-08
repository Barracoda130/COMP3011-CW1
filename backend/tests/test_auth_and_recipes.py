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
                "description": "Simple high-protein meal.",
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
                "tags": ["pasta", "tomato", "quick"],
                "description": "Simple tomato pasta",
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
                "tags": ["pasta", "creamy"],
                "description": "Creamy pasta",
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
                "description": "Spicy tofu",
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

        suggested_response = client.get("/api/v1/recipes/suggested", headers=headers)
        assert suggested_response.status_code == 200
        payload = suggested_response.json()

        assert "score =" in payload["formula"]
        assert payload["local_count"] >= 1
        assert any(item["title"] == "Creamy Pasta" for item in payload["items"])


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
        "description": "Already rated",
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
            "description": "Beef",
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
                "description": "Hearty",
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

        suggested_response = client.get("/api/v1/recipes/suggested", headers=headers)
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
            "description": "Chicken",
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
                "description": "Tangy",
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
