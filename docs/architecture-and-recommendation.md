# Architecture and Recommendation Flow

## System Architecture

- Frontend: Vue 3 SPA (`frontend/src`) with route-level views for discover, suggested, cook, rated, my-recipes, create/edit, and weekly plan.
- Backend: FastAPI (`backend/app`) with modular routers under `/api/v1`.
- Persistence: PostgreSQL (deployment) with SQLAlchemy ORM models and Alembic migrations; SQLite remains available as local fallback.
- External Source: TheMealDB integration for discovery, cook details, ratings, and weekly-plan candidate generation.

## Database Schema

### Tables

`users`

- `id` (PK)
- `email` (unique, indexed)
- `hashed_password`
- `full_name`
- `created_at`

`recipes`

- `id` (PK)
- `owner_id` (FK -> `users.id`, indexed)
- `title` (indexed)
- `cuisine` (indexed)
- `prep_minutes`
- `calories`
- `intro`
- `steps`
- `image_url`
- `ingredients` (JSON)
- `tags` (JSON)
- `average_rating`
- `created_at`

`weekly_plans`

- `id` (PK)
- `user_id` (FK -> `users.id`, indexed)
- `start_date`
- `end_date`
- `status`
- `created_at`

`weekly_plan_items`

- `id` (PK)
- `weekly_plan_id` (FK -> `weekly_plans.id`, indexed)
- `day_index` (indexed)
- `planned_for`
- `recipe_source` (`local` or `themealdb`)
- `recipe_id` (nullable FK -> `recipes.id`)
- `external_recipe_id` (nullable)
- `title_snapshot`
- `is_selected`
- `notes`
- `created_at`
- Unique constraint: `(weekly_plan_id, day_index, recipe_source)`

`recipe_ratings`

- `id` (PK)
- `user_id` (FK -> `users.id`, indexed)
- `recipe_id` (FK -> `recipes.id`, indexed)
- `score`
- `comment`
- `created_at`
- Unique constraint: `(user_id, recipe_id)`

`external_recipe_ratings`

- `id` (PK)
- `user_id` (FK -> `users.id`, indexed)
- `external_recipe_id` (indexed)
- `source`
- `score`
- `comment`
- `created_at`
- Unique constraint: `(user_id, external_recipe_id)`

`user_suggestion_cache`

- `id` (PK)
- `user_id` (FK -> `users.id`, indexed, unique)
- `items_json` (JSON)
- `is_stale`
- `generated_at`
- `updated_at`

### Relationship Summary

- One `user` can own many `recipes`
- One `user` can create many `recipe_ratings` and `external_recipe_ratings`
- One `recipe` can have many `recipe_ratings`
- One `user` has at most one `user_suggestion_cache` row
- One `user` can have many `weekly_plans`
- One `weekly_plan` has many `weekly_plan_items`

### Indexes (high level)

- `users`: index on `id`, unique index on `email`
- `recipes`: indexes on `id`, `owner_id`, `title`, `cuisine`
- `recipe_ratings`: indexes on `id`, `user_id`, `recipe_id`
- `external_recipe_ratings`: indexes on `id`, `user_id`, `external_recipe_id`
- `user_suggestion_cache`: indexes on `id`, `user_id`
- `weekly_plans`: indexes on `id`, `user_id`
- `weekly_plan_items`: indexes on `id`, `weekly_plan_id`, `day_index`

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
