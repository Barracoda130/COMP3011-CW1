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

- Backend: FastAPI, SQLAlchemy, Pydantic, PostgreSQL (deployment), SQLite (local fallback), Alembic, pytest
- Frontend: Vue 3, Vue Router, Vite, Vitest

## Database Strategy

- Primary deployment database: **PostgreSQL** via `DATABASE_URL`.
- Local/test fallback: SQLite remains supported when `DATABASE_URL` is not set.
- Schema management is migration-based using Alembic (`alembic upgrade head`).

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

- Active database is PostgreSQL (Render-managed) via `DATABASE_URL`.
- Run migrations with Alembic before starting backend in new environments:

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
```

- SQLAlchemy driver target is `postgresql+psycopg://...` (psycopg v3).
- The config normalizes `postgres://` / `postgresql://` env values to psycopg v3 automatically.
- Local SQLite can still be used by leaving `DATABASE_URL` unset (uses the code default path `backend/meal_api.db`).

## Database Schema

The full schema reference (tables, relationships, indexes) is documented in:

- `docs/architecture-and-recommendation.md`

## API Notes

- API base path: `/api/v1`
- Most recipe-modifying operations require bearer auth
- Discover endpoints are public
- Health endpoint is public and remains directly accessible by URL

## Architecture and Recommendation Summary

- Frontend (Vue 3) calls FastAPI endpoints through a shared API client.
- Backend merges local SQL data with TheMealDB for discover, suggested, cook, and weekly-plan flows.
- Recommendation scoring combines feature overlap, ingredient quantity/rarity weighting, and prep/calorie preference bands.
- Suggested responses return explainability reasons per item and are cached per user with staleness invalidation.
- Weekly planning persists two options per day (`local` + `themealdb`) and records user selection state.

Detailed design notes: `docs/architecture-and-recommendation.md`

## API Documentation 

- Interactive docs at runtime: `/docs`

## Deployment Runbook

- Deployment runbook (env vars, migrate, seed, start): `docs/deployment-runbook.md`

## Troubleshooting

- If `npm` is blocked by PowerShell execution policy, use `npm.cmd` in commands.
- If backend import dependencies fail, verify the virtual environment is active and dependencies are installed.