# COMP3011-CW1 Meal Planner Pro

Full-stack recipe application built with a FastAPI backend and a Vue 3 frontend.

## Scope (MVP vs Stretch)

### MVP (submission-critical)

- Authentication and protected recipe actions
- CRUD for local recipes
- Discover + cook flows for local and external recipes
- Ratings for local and external recipes
- Suggested recipes based on user rating history
- Import from URL into structured recipe fields (`intro`, `ingredients`, `steps`)
- Automated tests and runnable local setup

### Stretch (time permitting)

- Weekly plan generation with day-level constraints
- Stronger taste-profile learning (prep-time/calorie bands + richer ingredient preferences)
- Explainable recommendation reasons in API responses and UI
- Video import (captions-first, manual transcript fallback)
- Formal migration workflow (Alembic) replacing startup schema patching

## Overview

The project provides:

- Authentication (register/login, JWT bearer token)
- Local recipe management (create, edit, delete, copy-on-edit)
- Discover recipes from local storage and TheMealDB
- Cooking workflow page with checklist-style ingredients and rating UI
- Personal recommendation flow with cached suggestion results
- Rated recipes and My Recipes management pages

## Tech Stack

- Backend: FastAPI, SQLAlchemy, Pydantic, SQLite (default), pytest
- Frontend: Vue 3, Vue Router, Vite, Vitest

## Submission Database Strategy

- Locked strategy for this submission: **SQLite** as the primary database.
Why this choice:

- It is already integrated and stable in the current codebase.
- It minimizes setup friction for local marking/demo environments.
- It keeps focus on coursework features (recommendation, planning, testing, docs) instead of deployment/database operations.
- PostgreSQL remains a documented future upgrade path after feature completion.

## Project Structure

- `backend/`: API, models, schemas, services, tests
- `frontend/`: Vue application, routes, views, API client, frontend tests
- `package.json` (root): helper script to run backend + frontend together

## Prerequisites

- Python 3.12+
- Node.js 18+ and npm

## Setup

### 1. Backend setup

From `backend/`:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Run backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Backend URLs:

- API root: `http://127.0.0.1:8000/`
- Swagger docs: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/api/v1/openapi.json`
- Health endpoint: `http://127.0.0.1:8000/api/v1/health`

### 2. Frontend setup

From `frontend/`:

```powershell
npm install
npm run dev
```

Frontend runs on:

- `http://127.0.0.1:5173`

### 3. Run both services from project root (optional)

From repository root:

```powershell
npm install
npm run dev
```

This uses `concurrently` to run both backend and frontend.

## Testing

### Backend tests

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

### Frontend tests

From `frontend/`:

```powershell
npm run test
```

Watch mode:

```powershell
npm run test:watch
```

## Build

From `frontend/`:

```powershell
npm run build
```

## Database Notes

- Default DB is SQLite at `backend/meal_api.db`
- Tables are created on startup
- `backend/app/db/init_db.py` also applies lightweight schema backfills for incremental changes
- Legacy recipe text in `description` is backfilled into `steps` on startup

## Target Data Model Changes

Target additions for next phases:

- `weekly_plans` table for per-user generated plans.
- `weekly_plan_items` table for day-level plan entries and ordering.
- `taste_profiles` (or `user_preference_snapshots`) for persisted preference signals.
- `recommendation_reasons` payload support in suggested results (stored or computed).

Current recipe model direction:

- Keep `recipes` with `intro`, `steps`, `ingredients`, and `tags`.
- Continue to evaluate normalization (`ingredients` and `tags`) as a post-MVP enhancement.

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

## API Notes

- API base path: `/api/v1`
- Most recipe-modifying operations require bearer auth
- Discover endpoints are public
- Health endpoint is public and remains directly accessible by URL

## API Endpoint Examples

Base path: `/api/v1`

Auth:

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

Recipes:

- `GET /recipes`
- `GET /recipes/mine`
- `GET /recipes/discover`
- `GET /recipes/cook/{source}/{recipe_id}`
- `GET /recipes/suggested`
- `GET /recipes/rated`
- `POST /recipes`
- `POST /recipes/import-url`
- `POST /recipes/{recipe_id}/copy`
- `PUT /recipes/{recipe_id}`
- `DELETE /recipes/{recipe_id}`
- `POST /recipes/{recipe_id}/ratings`
- `GET /recipes/{recipe_id}/ratings/me`
- `POST /recipes/themealdb/{external_recipe_id}/ratings`
- `GET /recipes/themealdb/{external_recipe_id}/ratings/me`

Users / Weekly plan:

- `POST /users/me/weekly-plan/generate`
- `GET /users/me/weekly-plan/current`
- `POST /users/me/weekly-plan/current/select`

Example response: `GET /recipes/discover`

```json
{
	"items": [
		{
			"id": 12,
			"source": "local",
			"title": "Quick Chickpea Salad",
			"cuisine": "Mediterranean",
			"prep_minutes": 15,
			"calories": 430,
			"tags": ["quick"],
			"description": "Fresh weekday meal",
			"average_rating": 4.5,
			"owner_id": 1,
			"reasons": []
		}
	],
	"local_count": 1,
	"external_count": 0
}
```

Example response: `GET /recipes/suggested`

```json
{
	"items": [
		{
			"id": 44,
			"source": "local",
			"title": "Saffron Forward Rice",
			"cuisine": "Fusion",
			"recommendation_score": 2.1142,
			"reasons": [
				"Prep time aligns with your quick cooking preference",
				"Uses ingredients you rate highly: saffron"
			]
		}
	],
	"local_count": 1,
	"external_count": 0,
	"formula": "score = 0.55 * Jaccard(candidate, liked_features) + ..."
}
```

Example response: `GET /users/me/weekly-plan/current`

```json
{
	"id": 7,
	"status": "active",
	"start_date": "2026-03-09",
	"end_date": "2026-03-15",
	"items": [
		{
			"day_index": 0,
			"recipe_source": "local",
			"recipe_id": 12,
			"external_recipe_id": null,
			"title_snapshot": "Quick Chickpea Salad",
			"is_selected": false
		},
		{
			"day_index": 0,
			"recipe_source": "themealdb",
			"recipe_id": null,
			"external_recipe_id": "52772",
			"title_snapshot": "Teriyaki Chicken Casserole",
			"is_selected": true
		}
	]
}
```

## Architecture and Recommendation Summary

- Frontend (Vue 3) calls FastAPI endpoints through a shared API client.
- Backend merges local SQL data with TheMealDB for discover, suggested, cook, and weekly-plan flows.
- Recommendation scoring combines feature overlap, ingredient quantity/rarity weighting, and prep/calorie preference bands.
- Suggested responses return explainability reasons per item and are cached per user with staleness invalidation.
- Weekly planning persists two options per day (`local` + `themealdb`) and records user selection state.

Detailed design notes: `docs/architecture-and-recommendation.md`

## API Documentation PDF

- Exported API documentation: `docs/api-documentation.pdf`
- Interactive docs at runtime: `/docs`

## Deployment Runbook

- Deployment runbook (env vars, migrate, seed, start): `docs/deployment-runbook.md`

## Troubleshooting

- If `npm` is blocked by PowerShell execution policy, use `npm.cmd` in commands.
- If backend import dependencies fail, verify the virtual environment is active and dependencies are installed.