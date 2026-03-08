# Backend (FastAPI)

## Run locally

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Copy environment file:
   - `copy .env.example .env`
4. Start API:
   - `uvicorn app.main:app --reload`

API will run at `http://127.0.0.1:8000` and docs at `http://127.0.0.1:8000/docs`.

## Current database-backed features

- User registration and login (JWT bearer auth)
- Users can upload their own recipes
- Only recipe owners can update/delete their recipes
- Users can rate recipes (one rating per user per recipe, re-rating updates score)
- Recipe cost estimation from ingredients (Spoonacular first, fallback shopping API)

## Cost Estimation Setup

- Primary provider: Spoonacular ingredient cost data.
- Fallback provider: generic shopping search API (`SHOPPING_API_BASE_URL`, defaults to DummyJSON).

To enable Spoonacular, set in `.env`:

- `SPOONACULAR_API_KEY=your_key_here`

If no Spoonacular key is provided, the app will automatically use the fallback provider only.

## Quick API flow

1. Register user:
   - `POST /api/v1/auth/register`
2. Login:
   - `POST /api/v1/auth/login` (form fields: `username` = email, `password`)
3. Authorize in Swagger using `Bearer <token>`
4. Upload recipe:
   - `POST /api/v1/recipes`
5. Rate a recipe:
   - `POST /api/v1/recipes/{recipe_id}/ratings`

Default `DATABASE_URL` uses local SQLite (`meal_api.db`) so it runs without extra setup.

## Why this structure works for a future Vue frontend

- Versioned API prefix: `/api/v1`
- CORS origins include Vue dev server defaults (`5173`)
- Clear module separation (`api`, `schemas`, `services`, `db`)
- Ready for token auth and persistent database models
