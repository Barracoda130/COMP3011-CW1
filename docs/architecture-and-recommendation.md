# Architecture and Recommendation Flow

This document describes the implemented architecture and runtime behavior of the coursework submission.

## System Architecture

- Frontend: Vue 3 SPA (`frontend/src`) with route-level views for Discover, Suggested, Cook, Rated, My Recipes, Create/Edit, and Weekly Plan.
- Backend: FastAPI (`backend/app`) with modular routers under `/api/v1`.
- Persistence: SQLite with SQLAlchemy ORM models and Alembic migrations.
- External Source: TheMealDB integration for Discover, Cook details, ratings, and Weekly Plan candidate generation.
- Analytics: user-facing analytics under `/api/v1/users/me/analytics/*` derived from ratings, recipes, weekly plans, and cached recommendation reasons.

## Request/Response Flow

1. User interacts with Vue page.
2. Frontend `api.js` calls FastAPI endpoint.
3. Authenticated routes validate JWT bearer token (`/auth/login` issued token).
4. Endpoint reads/writes SQLAlchemy models.
5. Endpoint may merge local recipes with TheMealDB data.
6. Response is normalized to shared schemas (`RecipeDiscoverItem`, `WeeklyPlanRead`, etc.).

## Recommendation Flow (`GET /api/v1/recipes/suggested`)

1. Load user local/external ratings.
2. Build preference signals from cuisine/tags/ingredients, rating-strength weighting, ingredient quantity+rarity profiles, and prep-time/calorie bands.
3. Build candidate pool from local unrated recipes and TheMealDB results derived from top preference query terms.
4. Score each candidate using weighted positive/negative overlap and affinity bands.
5. Generate explainability reasons per item.
6. Cache generated suggestions in `user_suggestion_cache` and mark stale when source data changes.

## Weekly Plan Flow (`POST /api/v1/users/me/weekly-plan/generate`)

1. Build candidate sets from local and TheMealDB.
2. Score by user signals and day context.
3. Apply constraints: avoid consecutive same main ingredient, cap repeated cuisines, apply weekday quick-meal bias, and allow weekend flexible/treat bias.
4. Persist one local + one external option per day (7 days, 14 items total).
5. Allow per-day selection via `POST /api/v1/users/me/weekly-plan/current/select`.

## Reliability Notes

- Backend tests run against isolated test database (`backend/tests/conftest.py`) to avoid polluting `meal_api.db`.
- Frontend uses Vitest for API/auth client behavior.
- Session cache utility is used across major frontend pages with TTL and payload-size thresholding.

## Documentation Artifacts

- Static API PDF: `docs/api-documentation.pdf`
- Deployment runbook: `docs/deployment-runbook.md`
- Repository overview and endpoint examples: `README.md`

## Analytics Endpoints

- `GET /api/v1/users/me/analytics/summary`
- `GET /api/v1/users/me/analytics/taste-profile-summary`
- `GET /api/v1/users/me/analytics/favourite-cuisines`
- `GET /api/v1/users/me/analytics/favourite-ingredients`
- `GET /api/v1/users/me/analytics/preferred-prep-time-range`
- `GET /api/v1/users/me/analytics/preferred-calorie-range`
- `GET /api/v1/users/me/analytics/weekly-plan-diversity`
- `GET /api/v1/users/me/analytics/weekly-nutrition-summary`
- `GET /api/v1/users/me/analytics/weekly-plan`
- `GET /api/v1/users/me/analytics/recommendation-explanation-summary`

Dedicated inferred taste profile endpoint:

- `GET /api/v1/users/me/taste-profile`
