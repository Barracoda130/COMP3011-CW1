from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.v1.endpoints import recipes as recipes_endpoints
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
            "description": "Simple instructions",
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
                "description": "No token",
            },
        ),
        ("post", "/api/v1/recipes/1/copy", {"title": "Copy attempt"}),
        ("put", "/api/v1/recipes/1", {"title": "Update attempt"}),
        ("delete", "/api/v1/recipes/1", None),
        ("post", "/api/v1/recipes/1/ratings", {"score": 4, "comment": "Good"}),
        ("get", "/api/v1/recipes/1/ratings/me", None),
        ("post", "/api/v1/recipes/themealdb/52772/ratings", {"score": 4, "comment": "Good"}),
        ("get", "/api/v1/recipes/themealdb/52772/ratings/me", None),
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
                "tags": ["quick"],
                "description": "A valid recipe",
            },
            headers=headers,
        )
        assert create_response.status_code == 201
        assert create_response.json()["cuisine"] == "Unknown"

        invalid_prep_response = client.post(
            "/api/v1/recipes",
            json={
                "title": "Invalid Prep",
                "cuisine": "Italian",
                "prep_minutes": 0,
                "calories": 300,
                "tags": ["bad"],
                "description": "Invalid prep",
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
                "description": "Invalid title",
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
                "description": "Invalid calories",
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
