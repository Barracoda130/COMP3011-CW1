from uuid import uuid4

from fastapi.testclient import TestClient

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
