# Architecture and Recommendation Flow

## System Architecture

- Frontend: Vue 3 SPA (`frontend/src`) with route-level views for discover, suggested, cook, rated, my-recipes, create/edit, and weekly plan.
- Backend: FastAPI (`backend/app`) with modular routers under `/api/v1`.
- Persistence: SQLite with SQLAlchemy ORM models and Alembic migrations.
- External Source: TheMealDB integration for discovery, cook details, ratings, and weekly-plan candidate generation.

## Request/Response Flow

1. User interacts with Vue page.
2. Frontend `api.js` calls FastAPI endpoint.
3. Authenticated routes validate JWT bearer token (`/auth/login` issued token).
4. Endpoint reads/writes SQLAlchemy models.
5. Endpoint may merge local recipes with TheMealDB data.
6. Response is normalized to shared schemas (`RecipeDiscoverItem`, `WeeklyPlanRead`, etc.).

## Recommendation Flow (`GET /api/v1/recipes/suggested`)

1. Load user local/external ratings.
2. Build preference signals:
- liked/disliked feature sets from cuisine, tags, and ingredients
- weighted signals from rating strength
- ingredient profiles with quantity parsing and rarity weighting
- prep-time and calorie band preferences
3. Build candidate pool:
- local unrated recipes
- TheMealDB candidates from top preference query terms
4. Score each candidate using weighted positive/negative overlap and affinity bands.
5. Generate explainability reasons per item.
6. Cache generated suggestions in `user_suggestion_cache` and mark stale when source data changes.

## Weekly Plan Flow (`POST /api/v1/users/me/weekly-plan/generate`)

1. Build candidate sets from local and TheMealDB.
2. Score by user signals and day context.
3. Apply constraints:
- avoid consecutive same main ingredient
- cap repeated cuisines
- weekday quick-meal bias
- weekend flexible/treat bias
4. Persist one local + one external option per day (7 days, 14 items total).
5. Allow per-day selection via `/users/me/weekly-plan/current/select`.

## Reliability Notes

- Backend tests run against isolated test database (`backend/tests/conftest.py`) to avoid polluting `meal_api.db`.
- Frontend uses Vitest for API/auth client behavior.
- Session cache utility is used across major frontend pages with TTL and payload-size thresholding.
